# _*_ coding: utf-8 _*_
from copy import copy
from typing import List, Dict, Any, Tuple, Optional

from cachetools import TTLCache, cached

from app.plugins import _PluginBase
from app.log import logger
from app.schemas import SearchContext
from .utils.spider_helper import SpiderHelper

spider_configs = \
    {
        "Bt1louSpider": {'spider_name': 'Bt1louSpider',
                         'spider_enable': True,
                         'spider_proxy': False,
                         'pass_cloud_flare': True,
                         'proxy_type': 'playwright',
                         'spider_desc': 'BT之家1LOU站-回归初心，追求极简',
                         },
        "BtBtlSpider": {'spider_name': 'BtBtlSpider',
                        'spider_enable': True,
                        'spider_proxy': False,
                        'proxy_type': 'playwright',
                        'spider_desc': 'BT影视_4k高清电影BT下载_蓝光迅雷电影下载_最新电视剧下载',
                        },
        "BtBuLuoSpider": {'spider_name': 'BtBuLuoSpider',
                          'spider_enable': True,
                          'spider_proxy': False,
                          'proxy_type': 'playwright',
                          'spider_desc': 'BT部落天堂 - 注重体验与质量的影视资源下载网站',
                          },

        "BtdxSpider": {'spider_name': 'BtdxSpider',
                       'spider_enable': True,
                       'spider_proxy': False,
                       'proxy_type': 'playwright',
                       'spider_desc': '比特大雄_BT电影天堂_最新720P、1080P高清电影BT种子免注册下载网站',
                       },
        "BtttSpider": {'spider_name': 'BtttSpider',
                       'spider_enable': True,
                       'spider_proxy': False,
                       'proxy_type': 'playwright',
                       'spider_desc': 'BT天堂 - 2025最新高清电影1080P|2160P|4K资源免费下载',
                       },
        "Dytt8899Spider": {'spider_name': 'Dytt8899Spider',
                           'spider_enable': True,
                           'spider_proxy': False,
                           'proxy_type': 'playwright',
                           'spider_desc': '电影天堂_电影下载_高清首发',
                           },
        "Bt0lSpider": {'spider_name': 'Bt0lSpider',
                       'spider_enable': True,
                       'spider_proxy': False,
                       'proxy_type': 'playwright',
                       'spider_desc': '不太灵-影视管理系统',
                       },
        "CiLiXiongSpider": {'spider_name': 'CiLiXiongSpider',
                            'spider_enable': True,
                            'spider_proxy': False,
                            'pass_cloud_flare': True,
                            'proxy_type': 'playwright',
                            'spider_desc': '磁力熊，支持完结影视',
                            },
        "GyingKSpider": {'spider_name': 'GyingKSpider',
                         'spider_enable': True,
                         'spider_proxy': False,
                         'pass_cloud_flare': False,
                         'proxy_type': 'playwright',
                         'spider_desc': '观影 GYING',
                         'spider_username': '',
                         'spider_password': '',
                         },
    }


class ExtendSpider(_PluginBase):
    # 插件名称
    plugin_name = "ExtendSpider"
    # 插件描述
    plugin_desc = "以插件的方式获取索引器信息，支持更多的站点（app/sites/site_indexer.py和app/sites/sites.py的支持）"
    # 插件图标
    plugin_icon = "ExtendSpider.png"
    # 插件版本
    plugin_version = "1.4"
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
            self._spider_config = config.get("spider_config") if config.get("spider_config") else copy(spider_configs)
        else:
            self._spider_config = copy(spider_configs)
        # 停止现有任务
        self.stop_service()
        self._spider_helper = SpiderHelper(self._spider_config)
        self.reload_config()

    def reload_config(self):
        """
        重新加载配置
        """
        self._spider_helper.spider_config = self._spider_config
        self._spider_helper.init_config()
        self.get_status()
        self.__update_config()

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
            "enabled": self._enabled,
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

    @cached(cache=TTLCache(maxsize=200, ttl=1 * 3600),
            key=lambda self, indexer, keyword, page, search_context=None: (indexer.get("id"), keyword, page,
                                                                           hash(
                                                                               f"{search_context.search_type}{search_context.search_sub_id}{search_context.media_info.title} ") if search_context else None))
    def search(self, indexer, keyword, page, search_context: Optional[SearchContext] = None):
        """
        根据关键字多线程检索
        """
        if not indexer or not keyword:
            return None
        s_name = indexer.get("name", "").split('-')[1]
        logger.info(f"【{self.plugin_name}】开始检索Indexer：{s_name} ...")
        ret = self._spider_helper.search(s_name, keyword, page, search_context=search_context)
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
            },
            {
                "path": "/edit_config",
                "endpoint": self.__edit_config,
                "methods": ["POST"],
                "summary": "编辑爬虫配置"
            },
            {
                "path": "/reset_config",
                "endpoint": self.__reset_config,
                "methods": ["POST"],
                "summary": "重置爬虫配置"
            },
            {
                "path": "/reset_all_config",
                "endpoint": self.__reset_all_config,
                "methods": ["POST"],
                "summary": "重置所有爬虫配置"
            }
        ]

    def __toggle_spider(self, spider_name: str) -> Dict[str, Any]:
        """
        启用/停止爬虫
        :param spider_name: 爬虫名称
        :return: 操作结果
        """
        try:
            if not self._spider_config:
                return {"success": False, "message": "爬虫配置未初始化"}

            if spider_name in self._spider_config:
                # 更新配置
                enable = self._spider_config[spider_name]['spider_enable']
                self._spider_config[spider_name]['spider_enable'] = not enable
                # 重新加载配置
                self.reload_config()
                return {"success": True, "message": f"爬虫 {spider_name} {'启用' if enable else '停止'}成功"}
            else:
                return {"success": False, "message": f"爬虫 {spider_name} 不存在"}
        except Exception as e:
            logger.error(f"操作爬虫 {spider_name} 失败：{str(e)}")
            return {"success": False, "message": f"操作失败：{str(e)}"}

    def __edit_config(self, spider_name: str, config: dict) -> Dict[str, Any]:
        """
        编辑爬虫配置
        :param spider_name: 爬虫名称
        :param config: 新的配置
        :return: 操作结果
        """
        try:
            if not self._spider_helper:
                return {"success": False, "message": "爬虫助手未初始化"}

            if spider_name in self._spider_helper.spider_config:
                # 更新配置
                self._spider_helper.spider_config[spider_name].update(config)
                # 保存配置
                self.reload_config()
                return {"success": True, "message": f"爬虫 {spider_name} 配置更新成功"}
            else:
                return {"success": False, "message": f"爬虫 {spider_name} 不存在"}
        except Exception as e:
            logger.error(f"更新爬虫 {spider_name} 配置失败：{str(e)}")
            return {"success": False, "message": f"更新配置失败：{str(e)}"}

    def __reset_config(self, spider_name: str) -> Dict[str, Any]:
        """
        重置爬虫配置
        :param spider_name: 爬虫名称
        :return: 操作结果
        """
        try:
            if not self._spider_helper:
                return {"success": False, "message": "爬虫助手未初始化"}

            if spider_name in spider_configs:
                # 重置为默认配置
                self._spider_helper.spider_config[spider_name] = copy(spider_configs[spider_name])
                # 保存配置
                self.reload_config()
                return {"success": True, "message": f"爬虫 {spider_name} 配置已重置为默认值"}
            else:
                return {"success": False, "message": f"爬虫 {spider_name} 不存在"}
        except Exception as e:
            logger.error(f"重置爬虫 {spider_name} 配置失败：{str(e)}")
            return {"success": False, "message": f"重置配置失败：{str(e)}"}

    def __reset_all_config(self) -> Dict[str, Any]:
        """
        重置所有爬虫配置
        :return: 操作结果
        """
        try:
            if not self._spider_helper:
                return {"success": False, "message": "爬虫助手未初始化"}

            # 重置所有配置为默认值
            self._spider_helper.spider_config = copy(spider_configs)
            # 保存配置
            self.reload_config()
            return {"success": True, "message": "所有爬虫配置已重置为默认值"}
        except Exception as e:
            logger.error(f"重置所有爬虫配置失败：{str(e)}")
            return {"success": False, "message": f"重置配置失败：{str(e)}"}

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
            拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        import json
        # 获取爬虫状态
        spider_status = self._spider_helper.get_spider_status() if self._spider_helper else []

        # 构建爬虫配置面板
        spider_panels = []
        for spider in spider_status:
            spider_name = spider.get('name')
            spider_config = self._spider_helper.spider_config[spider_name]
            spider_panels.append({
                'component': 'VExpansionPanel',
                'content': [
                    {
                        'component': 'VExpansionPanelTitle',
                        'text': f"{spider.get('name')} - {spider.get('desc')}"
                    },
                    {
                        'component': 'VExpansionPanelText',
                        'content': [
                            {
                                'component': 'VRow',
                                'content': [
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': 12},
                                        'content': [
                                            {
                                                'component': 'VTextField',
                                                'props': {
                                                    'label': '网站地址',
                                                    'value': spider.get('url', ''),
                                                    'readonly': True
                                                }
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': 12},
                                        'content': [
                                            {
                                                'component': 'VSwitch',
                                                'props': {
                                                    'model': f'spider_enable_{spider.get("name")}',
                                                    'label': '启用爬虫',
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
                                        'component': 'VCol',
                                        'props': {'cols': 12},
                                        'content': [
                                            {
                                                'component': 'VBtn',
                                                'props': {
                                                    'color': 'success' if spider.get("web_status") else 'error',
                                                    'text': '正常' if spider.get("web_status") else '异常',
                                                    'block': True
                                                }
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': 12},
                                        'content': [
                                            {
                                                'component': 'VTextarea',
                                                'props': {
                                                    'model': f'config_json_{spider_name}',
                                                    'label': '爬虫配置（JSON格式）',
                                                    'rows': 10,
                                                    'value': json.dumps(spider_config, ensure_ascii=False, indent=2)
                                                }
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': 12},
                                        'content': [
                                            {
                                                'component': 'VBtn',
                                                'props': {
                                                    'color': 'primary',
                                                    'text': '保存配置',
                                                    'block': True
                                                },
                                                'events': {
                                                    'click': {
                                                        'api': 'plugin/ExtendSpider/edit_config',
                                                        'method': 'post',
                                                        'params': {
                                                            'spider_name': spider_name,
                                                            'config': f'{{config_json_{spider_name}}}'
                                                        }
                                                    }
                                                }
                                            },
                                            {
                                                'component': 'VBtn',
                                                'props': {
                                                    'color': 'warning',
                                                    'text': '重置配置',
                                                    'block': True,
                                                    'class': 'mt-2'
                                                },
                                                'events': {
                                                    'click': {
                                                        'api': 'plugin/ExtendSpider/reset_config',
                                                        'method': 'post',
                                                        'params': {
                                                            'spider_name': spider_name
                                                        }
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                ]
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
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
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
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VBtn',
                                        'props': {
                                            'color': 'error',
                                            'text': '重置所有配置',
                                            'block': True
                                        },
                                        'events': {
                                            'click': {
                                                'api': 'plugin/ExtendSpider/reset_all_config',
                                                'method': 'post'
                                            }
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
                                            'hint': '爬虫状态更新周期，支持5位cron表达式，默认每24小时运行一次'
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
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VExpansionPanels',
                                        'content': spider_panels
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
