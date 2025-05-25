# _*_ coding: utf-8 _*_
from copy import copy
from typing import List, Dict, Any, Tuple

from app.plugins import _PluginBase
from app.log import logger
from plugins.extendspider.base import _ExtendSpiderBase
from plugins.extendspider.utils.spinder_helper import SpiderHelper

spider_configs = \
    {
        "Bt1louSpider": {'spider_name': 'Bt1louSpider',
                         'spider_enable': True,
                         'spider_proxy': True,
                         'spider_desc': 'BT之家1LOU站-回归初心，追求极简',
                         'plugin_name': 'ExtendSpider'  # 必须和插件名一致
                         },
        "BtBuLuoSpider": {'spider_name': 'BtBuLuoSpider',
                          'spider_enable': True,
                          'spider_proxy': True,
                          'spider_desc': 'BT部落天堂 - 注重体验与质量的影视资源下载网站',
                          'plugin_name': 'ExtendSpider'  # 必须和插件名一致
                          },
        "Dytt8899Spider": {'spider_name': 'Dytt8899Spider',
                           'spider_enable': True,
                           'spider_proxy': False,
                           'spider_desc': '电影天堂_电影下载_高清首发',
                           'plugin_name': 'ExtendSpider'  # 必须和插件名一致
                           },
        "BtdxSpider": {'spider_name': 'BtdxSpider',
                       'spider_enable': True,
                       'spider_proxy': True,
                       'spider_desc': '比特大雄_BT电影天堂_最新720P、1080P高清电影BT种子免注册下载网站',
                       'plugin_name': 'ExtendSpider'  # 必须和插件名一致
                       }
    }


class ExtendSpider(_PluginBase):
    # 插件名称
    plugin_name = "ExtendSpider"
    # 插件描述
    plugin_desc = "以插件的方式获取索引器信息，支持更多的站点（app/sites/site_indexer.py和app/sites/sites.py的支持）"
    # 插件图标
    plugin_icon = "ExtendSpider.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "shaw"
    # 作者主页
    author_url = "https://github.com/jtcymc"
    # 插件配置项ID前缀
    plugin_config_prefix = "extend_spider_shaw_"
    # 加载顺序
    plugin_order = 15
    # 可使用的用户级别
    auth_level = 1
    # TODO 爬虫必须要！！！！！！！！！ app/modules/indexer/spider/plugins.py:31
    is_spider = True
    # 私有属性
    _scheduler = None
    _cron = None
    _enabled = False
    _onlyonce = False
    _spider_config = None
    _indexers = []
    _spider_helper = None

    def init_plugin(self, config: dict = None):
        """
        初始化插件
        """
        # 读取配置
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
            self._spider_config = config.get("spider_config") if config.get("spider_config") else spider_configs
        else:
            self._spider_config = copy(spider_configs)
        # 停止现有任务
        self.stop_service()
        self._spider_helper = SpiderHelper(self._spider_config)
        # 启动定时任务 & 立即运行一次
        # self._scheduler = BackgroundScheduler(timezone=settings.TZ)
        # 初始化定时任务
        # if self._enabled:
        # if self._scheduler:
        #     self._scheduler.remove_all_jobs()
        # if self._cron:
        #     self._scheduler.add_job(self.__update_spider_status, CronTrigger.from_crontab(self._cron))
        #     logger.info(f"爬虫状态更新任务已启动，执行周期：{self._cron}")

        # # 立即执行一次
        # if self._onlyonce:
        #     self.__update_spider_status()
        #     self._onlyonce = False
        #     self.__update_config()

    def __update_spider_status(self):
        """
        更新爬虫状态
        """
        try:
            if not self._spider_helper:
                return
            # 测试所有爬虫连通性
            results = self._spider_helper.test_all_connectivity()
            # 更新爬虫状态
            for spider_name, (success, message) in results.items():
                if spider_name in self._spider_helper.spider_config:
                    self._spider_helper.spider_config[spider_name]['web_status'] = success
            logger.info("爬虫状态更新完成")
        except Exception as e:
            logger.error(f"更新爬虫状态失败：{str(e)}")

    def get_status(self):
        """
        检查连通性
        :return: True、False
        """
        self._indexers = self.get_indexers()
        return True if isinstance(self._indexers, list) and len(self._indexers) > 0 else False

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
            if self._spider_helper:
                self._spider_helper.remove_plugin()
                self._spider_helper = None
        except Exception as e:
            logger.error(f"【{self.plugin_name}】停止插件错误: {str(e)}")

    def __update_config(self):
        """
        更新插件配置
        """
        self.update_config({
            "onlyonce": False,
            "cron": self._cron,
            "spider_config": self._spider_config
        })

    def get_indexers(self):
        """
            构建索引器
        """
        indexers = []
        for spider in self._spider_helper.running_spiders:
            indexers.extend(spider.get_indexers())
        return indexers

    def search(self, indexer, keyword, page):
        """
        根据关键字多线程检索
        """
        if not indexer or not keyword:
            return None
        s_name = indexer.get("id", "").split('-')[1]
        logger.info(f"【{self.plugin_name}】开始检索Indexer：{s_name} ...")
        ret = self._spider_helper.search(s_name, keyword, page)
        logger.info(f"【{self.plugin_name}】检索Indexer：{s_name} 返回资源数：{len(ret)}")
        return ret

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
        return [
            {
                "path": "/toggle_spider",
                "endpoint": self.__toggle_spider,
                "methods": ["POST"],
                "summary": "启用/停止爬虫"
            }
        ]

    def __toggle_spider(self, spider_name: str) -> Dict[str, Any]:
        """
        启用/停止爬虫
        :param spider_name: 爬虫名称
        :return: 操作结果
        """
        try:
            if not self._spider_helper:
                return {"success": False, "message": "爬虫助手未初始化"}
            enable = self._spider_helper.spider_config[spider_name]['spider_enable']
            # 更新配置
            if spider_name in self._spider_helper.spider_config:
                self._spider_helper.spider_config[spider_name]['spider_enable'] = not enable

                # 重启爬虫
                if enable:
                    self._spider_helper.load_spiders(spider_name)
                else:
                    self._spider_helper.remove_plugin(spider_name)

                return {"success": True, "message": f"爬虫 {spider_name} {'启用' if enable else '停止'}成功"}
            else:
                return {"success": False, "message": f"爬虫 {spider_name} 不存在"}
        except Exception as e:
            logger.error(f"操作爬虫 {spider_name} 失败：{str(e)}")
            return {"success": False, "message": f"操作失败：{str(e)}"}

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
            拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        # 获取爬虫状态
        spider_status = self._spider_helper.get_spider_status() if self._spider_helper else []

        # 构建爬虫状态表格
        spider_items = []
        for spider in spider_status:
            spider_name = spider.get('name')
            spider_items.append({
                'component': 'tr',
                'content': [
                    {
                        'component': 'td',
                        'text': spider.get("name", "")
                    },
                    {
                        'component': 'td',
                        'text': spider.get("desc", "")
                    },
                    {
                        'component': 'td',
                        'content': [
                            {
                                'component': 'VSwitch',
                                'props': {
                                    'model': f'spider_enable_{spider.get("name")}',
                                    'label': '启用',
                                    'color': 'success' if spider.get("enable") else 'error'
                                },
                                "events": {
                                    "click": {
                                        "api": "plugin/ExtendSpider/toggle_spider",
                                        "method": "post",
                                        "params": {
                                            "spider_name": spider_name
                                        }
                                    }
                                }

                            }
                        ]
                    },
                    {
                        'component': 'td',
                        'content': [
                            {
                                'component': 'VBtn',
                                'props': {
                                    'color': 'success' if spider.get("web_status") else 'error',
                                    'size': 'small',
                                    'text': '正常' if spider.get("web_status") else '异常'
                                }
                            }
                        ]
                    }
                ]
            })

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
                                ]
                            },
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
                                                                'text': '爬虫名称'
                                                            },
                                                            {
                                                                'component': 'th',
                                                                'props': {
                                                                    'class': 'text-start ps-4'
                                                                },
                                                                'text': '描述'
                                                            },
                                                            {
                                                                'component': 'th',
                                                                'props': {
                                                                    'class': 'text-start ps-4'
                                                                },
                                                                'text': '状态'
                                                            },
                                                            {
                                                                'component': 'th',
                                                                'props': {
                                                                    'class': 'text-start ps-4'
                                                                },
                                                                'text': '连通性'
                                                            }
                                                        ]
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'tbody',
                                                'content': spider_items
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
                                            'model': 'cron',
                                            'label': '更新周期',
                                            'placeholder': '0 0 */24 * *',
                                            'hint': '爬虫状态更新周期，支持5位cron表达式，默认每24小时运行一次'
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
            "cron": "0 0 */24 * *",
            "onlyonce": False
        }

    def get_page(self) -> List[dict]:
        """
            拼装插件详情页面，需要返回页面配置，同时附带数据
        """
        pass
