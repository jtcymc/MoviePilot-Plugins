# _*_ coding: utf-8 _*_
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
import xml.dom.minidom
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from cachetools import cached, TTLCache
from app.helper.sites import SitesHelper
from app.log import logger
from app.plugins import _PluginBase
from app.core.config import settings
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils
from app.utils.string import StringUtils

jackett_indexer = {
    "id": "JackettExtend",
    "name": "JackettExtend",
    "domain": "https://jackett_extend.jtcymc/",
    "encoding": "UTF-8",
    "public": True,
    "timeout": 30,
    "search": {
        "paths": [
        ]
    },
    "torrents": {

    }
}


class JackettExtend(_PluginBase):
    # 插件名称
    plugin_name = "JackettExtend"
    # 插件描述
    plugin_desc = "扩展检索以支持Jackett站点资源"
    # 插件图标
    plugin_icon = "Jackett_A.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "jtcymc"
    # 作者主页
    author_url = "https://github.com/jtcymc"
    # 插件配置项ID前缀
    plugin_config_prefix = "jackett_extend_"
    # 加载顺序
    plugin_order = 15
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _scheduler = None
    _cron = None
    _enabled = False
    _proxy = False
    _host = ""
    _api_key = ""
    _password = ""
    _onlyonce = False
    _indexers = None
    sites_helper = None
    # 仅用于标识，避免重复注册
    jackett_domain = "jackett_extend.jtcymc"

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
            self._password = config.get("password")
            self._enabled = config.get("enabled")
            self._proxy = config.get("proxy")
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
        if not self._enabled:
            return
        # 停止现有任务
        self.stop_service()

        site_info = self.sites_helper.get_indexer(self.jackett_domain)
        if not site_info:
            # sites_helper 添加jackett_indexer
            self.sites_helper.add_indexer(self.jackett_domain, jackett_indexer)
        # 启动定时任务 & 立即运行一次
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
        if not self._cron:
            self._cron = "0 0 */24 * *"

    def get_status(self):
        """
        检查连通性
        :return: True、False
        """
        if not self._api_key or not self._host:
            return False
        return True

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
            "api_key": self._api_key,
            "password": self._password,
        })

    # @cached(cache=TTLCache(maxsize=200, ttl=1 * 3600),
    #         key=lambda self, indexer, keyword, page: (indexer.get("id"), keyword, page))
    def search_torrents(self, indexer, keyword, page):
        """
        根据关键字多线程检索
        """
        if not indexer or not keyword or indexer.get("id", "") == "JackettExtend":
            return None

        logger.info(f"【{self.plugin_name}】开始检索Indexer：{indexer.get("name")} ...")
        # 特殊符号处理
        api_url = f"{indexer.get("url")}?apikey={self._api_key}&t=search&q={keyword}"

        result_array = self.__parse_torznab_xml(api_url)

        if len(result_array) == 0:
            logger.warn(f"【{self.plugin_name}】{indexer.get("name")} 未检索到数据")
            return []
        else:
            logger.info(f"【{self.plugin_name}】{indexer.get("name")} 返回数据：{len(result_array)}")
            return result_array

    def get_module(self) -> Dict[str, Any]:
        """
        获取插件模块声明，用于胁持系统模块实现（方法名：方法实现）
        {
            "id1": self.xxx1,
            "id2": self.xxx2,
        }
        """
        return {
            "search_torrents": self.search_torrents,
        }

    def get_api(self) -> List[Dict[str, Any]]:
        """
        获取插件API
        [{
            "path": "/xx",
            "endpoint": self.xxx,
            "methods": ["GET", "POST"],
            "summary": "API说明"
        }]
        """

    pass

    def __parse_torznab_xml(self, url):
        """
        从torznab xml中解析种子信息
        :param url: URL地址
        :return: 解析出来的种子信息列表
        """
        if not url:
            return []
        try:
            ret = RequestUtils(timeout=60).get_res(url,
                                                   proxies=settings.PROXY if self._proxy else None)
        except Exception as e:
            logger.error(str(e))
            return []
        if not ret:
            return []
        xmls = ret.text
        if not xmls:
            return []

        torrents = []
        try:
            # 解析XML
            dom_tree = xml.dom.minidom.parseString(xmls)
            root_node = dom_tree.documentElement
            items = root_node.getElementsByTagName("item")
            for item in items:
                try:
                    # indexer id
                    indexer_id = DomUtils.tag_value(item, "jackettindexer", "id",
                                                    default=DomUtils.tag_value(item, "jackettindexer", "id", ""))
                    # indexer
                    indexer = DomUtils.tag_value(item, "jackettindexer",
                                                 default=DomUtils.tag_value(item, "jackettindexer", default=""))

                    # 标题
                    title = DomUtils.tag_value(item, "title", default="")
                    if not title:
                        continue
                    # 种子链接
                    enclosure = DomUtils.tag_value(item, "enclosure", "url", default="")
                    if not enclosure:
                        continue
                    # 描述
                    description = DomUtils.tag_value(item, "description", default="")
                    # 种子大小
                    size = DomUtils.tag_value(item, "size", default=0)
                    # 种子页面
                    page_url = DomUtils.tag_value(item, "comments", default="")
                    # 发布时间
                    pubdate = DomUtils.tag_value(item, "pubDate", default="")
                    if pubdate:
                        pubdate = StringUtils.unify_datetime_str(pubdate)
                    # 做种数
                    seeders = 0
                    # 下载数
                    peers = 0
                    # 是否免费
                    freeleech = False
                    # 下载因子
                    downloadvolumefactor = 1.0
                    # 上传因子
                    uploadvolumefactor = 1.0
                    # imdbid
                    imdbid = ""

                    torznab_attrs = item.getElementsByTagName("torznab:attr")
                    for torznab_attr in torznab_attrs:
                        name = torznab_attr.getAttribute('name')
                        value = torznab_attr.getAttribute('value')
                        if name == "seeders":
                            seeders = value
                        if name == "peers":
                            peers = value
                        if name == "downloadvolumefactor":
                            downloadvolumefactor = value
                            if float(downloadvolumefactor) == 0:
                                freeleech = True
                        if name == "uploadvolumefactor":
                            uploadvolumefactor = value
                        if name == "imdbid":
                            imdbid = value

                    tmp_dict = {
                        # 'id': indexer_id,
                        # 'indexer': indexer,
                        'title': title,
                        'enclosure': enclosure,
                        'description': description,
                        'size': size,
                        'seeders': seeders,
                        'peers': peers,
                        # 'freeleech': freeleech,
                        'downloadvolumefactor': downloadvolumefactor,
                        'uploadvolumefactor': uploadvolumefactor,
                        'page_url': page_url,
                        'imdbid': imdbid
                    }
                    torrents.append(tmp_dict)
                except Exception as e:
                    logger.error(str(e))
                    continue
        except Exception as e:
            logger.error(str(e))
            pass

        return torrents

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
                                            'label': 'Jackett地址',
                                            'placeholder': 'http://127.0.0.1:9117',
                                            'hint': 'Jackett访问地址和端口，如为https需加https://前缀。注意需要先在Jackett中添加indexer，才能正常测试通过和使用'
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
                                            'hint': 'Jackett管理界面右上角复制API Key'
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
                                            'model': 'password',
                                            'label': '密码',
                                            'placeholder': '',
                                            'hint': 'Jackett管理界面中配置的Admin password，如未配置可为空',
                                            'type': 'password'
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
                                            'model': 'cron',
                                            'label': '更新周期',
                                            'placeholder': '0 0 */24 * *',
                                            'hint': '索引列表更新周期，支持5位cron表达式，默认每24小时运行一次'
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
            "enabled": False,
            "proxy": False,
            "host": "",
            "api_key": "",
            "password": "",
            "cron": "0 0 */24 * *",
            "onlyonce": False
        }

    def _ensure_sites_loaded(self) -> bool:
        """
        确保 self._indexers 已加载数据，若为空则尝试重新加载。
        :return: 成功加载返回 True，否则 False
        """
        if isinstance(self._indexers, list) and len(self._indexers) > 0:
            return True

        # 尝试重新加载站点数据
        self.get_status()

        return isinstance(self._indexers, list) and len(self._indexers) > 0

    def get_page(self) -> List[dict]:
        """
        拼装插件详情页面，需要返回页面配置，同时附带数据
        """
        if not self._ensure_sites_loaded():
            return []

        items = []
        for site in self._indexers:
            items.append({
                'component': 'tr',
                'content': [
                    {
                        'component': 'td',
                        'text': site.get("id")
                    },
                    {
                        'component': 'td',
                        'text': site.get("domain")
                    },
                    {
                        'component': 'td',
                        'text': site.get("public")
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
