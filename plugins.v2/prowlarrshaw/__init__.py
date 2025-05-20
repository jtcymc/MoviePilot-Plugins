# _*_ coding: utf-8 _*_
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import re
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.plugins import _PluginBase
from app.core.config import settings
from modules.indexer.indexerConf import IndexerConf
from utils.http import RequestUtils
from utils.string import StringUtils
from app.log import logger

class ProwlarrShaw(_PluginBase):
    # 插件名称
    plugin_name = "Prowlarr"
    # 插件描述
    plugin_desc = "让内荐索引器支持检索Prowlarr站点资源"
    # 插件图标
    plugin_icon = "Prowlarr.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "shaw"
    # 作者主页
    author_url = "https://github.com/jtcymc"
    # 插件配置项ID前缀
    plugin_config_prefix = "prowlarr_shaw_"
    # 加载顺序
    plugin_order = 16
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _scheduler = None
    _cron = None
    _enabled = False
    _proxy = False
    _host = ""
    _api_key = ""
    _onlyonce = False
    _sites = None

    def init_plugin(self, config: dict = None):
        """
        初始化插件
        """
        # 读取配置
        if config:
            self._host = config.get("host")
            if self._host:
                if not self._host.startswith('http'):
                    self._host = "http://" + self._host
                if self._host.endswith('/'):
                    self._host = self._host.rstrip('/')
            self._api_key = config.get("api_key")
            self._enabled = config.get("enabled")
            self._proxy = config.get("proxy")
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
            if not StringUtils.is_string_and_not_empty(self._cron):
                self._cron = "0 0 */24 * *"

        # 停止现有任务
        self.stop_service()

        # 启动定时任务 & 立即运行一次
        if self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            if self._cron:
                logger.info(f"【{self.plugin_name}】 索引更新服务启动，周期：{self._cron}")
                self._scheduler.add_job(self.get_status, CronTrigger.from_crontab(self._cron))

            if self._onlyonce:
                logger.info(f"【{self.plugin_name}】开始获取索引器状态")
                self._scheduler.add_job(self.get_status, 'date',
                                      run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3))
                # 关闭一次性开关
                self._onlyonce = False
                self.__update_config()

            if self._cron or self._onlyonce:
                # 启动服务
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_status(self):
        """
        检查连通性
        :return: True、False
        """
        if not self._api_key or not self._host:
            return False
        self._sites = self.get_indexers()
        return True if isinstance(self._sites, list) and len(self._sites) > 0 else False

    def get_state(self) -> bool:
        return self._enabled

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error(f"【{self.plugin_name}】停止插件错误: {str(e)}")

    def __update_config(self):
        """
        更新插件配置
        """
        self.update_config({
            "onlyonce": False,
            "cron": self._cron,
            "host": self._host,
            "api_key": self._api_key
        })

    def get_indexers(self):
        """
        获取配置的prowlarr indexer
        :return: indexer 信息 [(indexerId, indexerName, url)]
        """
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": settings.USER_AGENT,
            "X-Api-Key": self._api_key,
            "Accept": "application/json, text/javascript, */*; q=0.01"
        }
        indexer_query_url = f"{self._host}/api/v1/indexerstats"
        try:
            ret = RequestUtils(headers=headers).get_res(indexer_query_url)
            if not ret:
                return []
            if not RequestUtils.check_response_is_valid_json(ret):
                logger.info(f"【{self.plugin_name}】参数设置不正确，请检查所有的参数是否填写正确")
                return []
            if not ret.json():
                return []
            ret_indexers = ret.json()["indexers"]
            if not ret or ret_indexers == [] or ret is None:
                return []

            indexers = [IndexerConf({
                "id": f'{v["indexerName"]}-{self.plugin_name}',
                "name": f'【{self.plugin_name}】{v["indexerName"]}',
                "domain": f'{self._host}/api/v1/indexer/{v["indexerId"]}',
                "public": True,
                "builtin": False,
                "proxy": True,
                "parser": self.plugin_name
            }) for v in ret_indexers]
            return indexers
        except Exception as e:
            logger.error(str(e))
            return []

    def search(self, indexer, keyword, page):
        """
        根据关键字多线程检索
        """
        if not indexer or not keyword:
            return None
        logger.info(f"【{self.plugin_name}】开始检索Indexer：{indexer.name} ...")

        # 获取indexerId
        indexerId_pattern = r"/indexer/([^/]+)"
        indexerId_match = re.search(indexerId_pattern, indexer.domain)
        indexerId = ""
        if indexerId_match:
            indexerId = indexerId_match.group(1)

        if not StringUtils.is_string_and_not_empty(indexerId):
            logger.info(f"【{self.plugin_name}】{indexer.name} 索引id为空")
            return []

        try:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": settings.USER_AGENT,
                "X-Api-Key": self._api_key,
                "Accept": "application/json, text/javascript, */*; q=0.01"
            }
            api_url = f"{self._host}/api/v1/search?query={keyword}&indexerIds={indexerId}&type=search&limit=100&offset=0"
            ret = RequestUtils(headers=headers).get_res(api_url)
            if not ret:
                return []
            if not RequestUtils.check_response_is_valid_json(ret):
                logger.info(f"【{self.plugin_name}】参数设置不正确，请检查所有的参数是否填写正确")
                return []
            if not ret.json():
                return []

            ret_indexers = ret.json()
            if not ret or ret_indexers == [] or ret is None:
                return []

            torrents = []
            for entry in ret_indexers:
                tmp_dict = {
                    'indexer_id': entry["indexerId"],
                    'indexer': entry["indexer"],
                    'title': entry["title"],
                    'enclosure': entry["downloadUrl"],
                    'description': entry["sortTitle"],
                    'size': entry["size"],
                    'seeders': entry["seeders"],
                    'peers': None,
                    'freeleech': None,
                    'downloadvolumefactor': None,
                    'uploadvolumefactor': None,
                    'page_url': entry["guid"],
                    'imdbid': None
                }
                torrents.append(tmp_dict)
            return torrents
        except Exception as e:
            logger.error(str(e))
            return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'proxy',
                                            'label': '使用代理服务器',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'host',
                                            'label': 'Prowlarr地址',
                                            'placeholder': 'http://127.0.0.1:9696',
                                            'hint': 'Prowlarr访问地址和端口，如为https需加https://前缀。注意需要先在Prowlarr中添加搜刮器，同时勾选所有搜刮器后搜索一次，才能正常测试通过和使用'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'api_key',
                                            'label': 'Api Key',
                                            'placeholder': '',
                                            'hint': '在Prowlarr->Settings->General->Security-> API Key中获取'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '更新周期',
                                            'placeholder': '0 0 */24 * *',
                                            'hint': '索引列表更新周期，支持5位cron表达式，默认每24小时运行一次'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                            'hint': '打开后立即运行一次获取索引器列表，否则需要等到预先设置的更新周期才会获取'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "host": "",
            "api_key": "",
            "cron": "0 0 */24 * *",
            "onlyonce": False
        }

    def get_page(self) -> List[dict]:
        """
        拼装插件详情页面，需要返回页面配置，同时附带数据
        """
        if not isinstance(self._sites, list) or len(self._sites) <= 0:
            return []

        items = []
        for site in self._sites:
            items.append({
                'component': 'tr',
                'content': [
                    {
                        'component': 'td',
                        'text': site.id
                    },
                    {
                        'component': 'td',
                        'text': site.domain
                    },
                    {
                        'component': 'td',
                        'text': str(site.public)
                    }
                ]
            })

        return [
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12
                        },
                        'content': [
                            {
                                'component': 'VTable',
                                'props': {
                                    'hover': True
                                },
                                'content': [
                                    {
                                        'component': 'thead',
                                        'content': [
                                            {
                                                'component': 'tr',
                                                'content': [
                                                    {
                                                        'component': 'th',
                                                        'props': {
                                                            'class': 'text-start ps-4'
                                                        },
                                                        'text': 'id'
                                                    },
                                                    {
                                                        'component': 'th',
                                                        'props': {
                                                            'class': 'text-start ps-4'
                                                        },
                                                        'text': '索引'
                                                    },
                                                    {
                                                        'component': 'th',
                                                        'props': {
                                                            'class': 'text-start ps-4'
                                                        },
                                                        'text': '是否公开'
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'tbody',
                                        'content': items
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
