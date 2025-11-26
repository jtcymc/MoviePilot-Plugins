# _*_ coding: utf-8 _*_
import os
import traceback
from copy import copy
from typing import List, Dict, Any, Tuple, Optional

from cachetools import TTLCache, cached

from app.plugins import _PluginBase
from app.log import logger
from app.schemas import SearchContext
from app.core.event import EventManager
from app.schemas.types import EventType

spider_configs = \
    {
        "Bt1louSpider": {"spider_name": "Bt1louSpider",
                         'spider_enable': True,
                         'spider_proxy': False,
                         'pass_cloud_flare': True,
                         'proxy_type': 'playwright',
                         'spider_url': 'https://www.1lou.info',
                         # 'spider_url': 'https://www.1lou.me',
                         'spider_desc': 'BT之家1LOU站-回归初心，追求极简',
                         'use_drission_browser': True,
                         'spider_headless': True,
                         "spider_tags": [
                             "电影", "电视剧", "动漫"
                         ],
                         "use_file_server": True,
                         "file_server_url": "",
                         },
        "BtBtlSpider": {'spider_name': 'BtBtlSpider',
                        'spider_enable': True,
                        'spider_proxy': False,
                        'proxy_type': 'playwright',
                        'spider_url': 'https://www.btbtl.com',
                        'spider_desc': 'BT影视_4k高清电影BT下载_蓝光迅雷电影下载_最新电视剧下载',
                        },
        "BtBuLuoSpider": {'spider_name': 'BtBuLuoSpider',
                          'spider_enable': False,
                          'spider_proxy': False,
                          'proxy_type': 'playwright',
                          'spider_url': 'https://www.btbuluo.net',
                          'spider_desc': 'BT部落天堂 - 注重体验与质量的影视资源下载网站',
                          },

        "BtdxSpider": {'spider_name': 'BtdxSpider',
                       'spider_enable': False,
                       'spider_proxy': False,
                       'proxy_type': 'playwright',
                       'spider_url': 'https://www.btdx8.vip',
                       'spider_desc': '比特大雄_BT电影天堂_最新720P、1080P高清电影BT种子免注册下载网站',
                       },
        "BtlSpider": {'spider_name': 'BtlSpider',
                      'spider_enable': True,
                      'spider_proxy': False,
                      'proxy_type': 'playwright',
                      'spider_url': 'https://www.6bt0.com',
                      'spider_desc': '不太灵-影视管理系统',
                      'use_drission_browser': True,
                      'spider_headless': True,
                      },
        "BtttSpider": {'spider_name': 'BtttSpider',
                       'spider_enable': False,
                       'spider_proxy': False,
                       'proxy_type': 'playwright',
                       'spider_url': 'https://www.bttt11.com',
                       'spider_desc': 'BT天堂 - 2025最新高清电影1080P|2160P|4K资源免费下载',
                       },

        "CiLiXiongSpider": {'spider_name': 'CiLiXiongSpider',
                            'spider_enable': True,
                            'spider_proxy': False,
                            'pass_cloud_flare': True,
                            'proxy_type': 'playwright',
                            'spider_url': 'https://www.cilixiong.cc',
                            'spider_desc': '磁力熊，支持完结影视',
                            "spider_tags": [
                                "电影", "电视剧", "动漫", "完结"
                            ],
                            'use_drission_browser': True,
                            'spider_headless': True,
                            },
        "Dytt8899Spider": {'spider_name': 'Dytt8899Spider',
                           'spider_enable': False,
                           'spider_proxy': False,
                           'proxy_type': 'playwright',
                           'spider_url': 'https://www.dytt8899.com',
                           'spider_desc': '电影天堂_电影下载_高清首发',
                           },

        "GyingKSpider": {'spider_name': 'GyingKSpider',
                         'spider_enable': True,
                         'spider_proxy': False,
                         'pass_cloud_flare': False,
                         'proxy_type': 'playwright',
                         'spider_url': 'https://www.gying.org',
                         'spider_desc': '观影 GYING',
                         'spider_username': '',
                         'spider_password': '',
                         'use_drission_browser': True,
                         'spider_headless': True,
                         },
    }


class ExtendSpider(_PluginBase):
    # 插件名称
    plugin_name = "ExtendSpider"
    # 插件描述
    plugin_desc = "以插件的方式获取索引器信息，支持更多的站点（app/sites/site_indexer.py和app/sites/sites.py的支持）"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/jtcymc/MoviePilot-Plugins/8ed891e0441a79628da01b9618fcd85ba7a88147/icons/Extend_Spider.png"
    # 插件版本
    plugin_version = "1.6.9"
    # 插件作者
    plugin_author = "shaw"
    # 作者主页
    author_url = "https://github.com/jtcymc"
    # 插件配置项ID前缀
    plugin_config_prefix = "extend_spider_shaw_"
    # 加载顺序
    plugin_order = 2
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
        try:
            # 读取配置
            if config:
                self._enabled = config.get("enabled")
                self._onlyonce = config.get("onlyonce")
                self._cron = config.get("cron")
                old_spider_config = config.get("spider_config") or copy(spider_configs)

                # 初始化 spider_config
                if not self._spider_helper:
                    # 如果是首次初始化或没有 helper，则直接使用旧配置或默认配置
                    self._spider_config = copy(old_spider_config)
                else:
                    # 版本不一致时进行合并更新
                    if self.plugin_version != old_spider_config.get("plugin_version"):
                        logger.info("检测到插件版本更新，正在合并配置...")
                        for spider_name, default_config in spider_configs.items():
                            if spider_name in old_spider_config:
                                old_config = old_spider_config[spider_name]
                                merged_config = copy(default_config)

                                # 合并逻辑：仅保留旧配置中非空字符串的字段
                                for key, value in old_config.items():
                                    if isinstance(value, str) and value.strip() != "":
                                        merged_config[key] = value

                                # 替换为合并后的配置
                                old_spider_config[spider_name] = merged_config

                    self._spider_config = copy(old_spider_config)

            # 初始化爬虫助手
            if not self._spider_helper:
                from app.plugins.extendspider.utils.spider_helper import SpiderHelper
                self._spider_helper = SpiderHelper(self._spider_config)
            else:
                # 重新加载配置
                self.reload_config(is_init=True)
            EventManager().send_event(EventType.SpiderPluginsRload, data={"plugin_id": self.plugin_name})
            logger.info(f"插件初始化完成，当前状态：{'启用' if self._enabled else '禁用'}")
        except Exception as e:
            logger.error(f"插件初始化失败：{str(e)}, {traceback.format_exc()}")
            self._spider_helper = None

    def reload_config(self, is_init=False):
        """
        重新加载配置
        """
        self._spider_helper.spider_config = self._spider_config
        self._spider_helper.init_config()
        self.get_status()
        self.__update_config()
        if not is_init:
            EventManager().send_event(EventType.SpiderPluginsRload, data={"plugin_id": self.plugin_name})

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
            logger.info(f"{self.plugin_name}-爬虫状态更新完成")
        except Exception as e:
            logger.error(f"更新爬虫状态失败：{str(e)}, {traceback.format_exc()}")

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
            logger.error(f"【{self.plugin_name}】停止插件错误: {str(e)}, {traceback.format_exc()}")

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

    @cached(cache=TTLCache(maxsize=2000, ttl=2 * 3600),
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
        try:
            ret = self._spider_helper.search(s_name, keyword, page, search_context=search_context)
        except Exception as e:
            logger.error(f"【{self.plugin_name}】检索Indexer：{s_name} 错误：{str(e)}, {traceback.format_exc()}")
            return []
        logger.info(f"【{self.plugin_name}】检索Indexer：{s_name} 返回资源数：{len(ret)}")
        return ret

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return [], {}

    def get_initial_config(self) -> Dict[str, Any]:
        """
        获取插件初始配置
        :return: 初始配置数据
        """
        try:
            # 获取爬虫状态
            spider_status = self._spider_helper.get_spider_status() if self._spider_helper else []

            # 构建初始配置数据
            initial_config = {
                "enabled": self._enabled,
                "cron": self._cron,
                "onlyonce": self._onlyonce,
                "spider_config": self._spider_config
            }

            return {
                "success": True,
                "data": initial_config
            }
        except Exception as e:
            logger.error(f"获取初始配置失败：{str(e)}")
            return {"success": False, "message": f"获取初始配置失败：{str(e)}"}

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
                "path": "/initial_config",
                "endpoint": self.get_initial_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取插件初始配置",
                "description": "获取插件初始配置信息"
            },
            {
                "path": "/config",
                "endpoint": self.__get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取插件配置",
                "description": "获取插件当前配置信息"
            },
            {
                "path": "/toggle_spider",
                "endpoint": self.__toggle_spider,
                "methods": ["POST"],
                "summary": "启用/停止爬虫",
                "auth": "bear",
                "description": "启用/停止爬虫"
            },
            {
                "path": "/edit_config",
                "endpoint": self.__edit_config,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "编辑爬虫配置",
                "description": "编辑爬虫配置"
            },
            {
                "path": "/reset_config",
                "endpoint": self.__reset_config,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "重置爬虫配置",
                "description": "重置爬虫配置"
            },
            {
                "path": "/reset_all_config",
                "endpoint": self.__reset_all_config,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "重置所有爬虫配置",
                "description": "重置所有爬虫配置"
            },
            {
                "path": "/status",
                "endpoint": self.__get_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取爬虫状态",
                "description": "获取爬虫状态和统计信息"
            },
            {
                "path": "/history",
                "endpoint": self.__get_history,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取历史记录",
                "description": "获取爬虫运行历史记录"
            },
            {
                "path": "/add_tag",
                "endpoint": self.__add_tag,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "添加标签",
                "description": "为指定爬虫添加标签"
            },
            {
                "path": "/remove_tag",
                "endpoint": self.__remove_tag,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "删除标签",
                "description": "从指定爬虫删除标签"
            }
        ]

    def __get_config(self) -> Dict[str, Any]:
        """
        获取插件配置
        :return: 配置信息
        """
        try:
            return {
                "success": True,
                "data": {
                    "enabled": self._enabled,
                    "cron": self._cron,
                    "onlyonce": self._onlyonce,
                    "spider_config": self._spider_config
                }
            }
        except Exception as e:
            logger.error(f"获取配置失败：{str(e)}")
            return {"success": False, "message": f"获取配置失败：{str(e)}"}

    def __toggle_spider(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        启用/停止爬虫
        :param params: {spider_name: str}
        :return: 操作结果
        """
        if not self._enabled:
            return {"success": False, "message": ""}
        spider_name = params.get("spider_name")
        if not params.get("spider_name"):
            return {"success": False, "message": "请指定爬虫名称"}
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

    def __edit_config(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        编辑爬虫配置
        :param params: {spider_name: str, config: dict}
        :return: 操作结果
        """
        if not self._enabled:
            return {"success": False, "message": ""}
        spider_name = params.get("spider_name")
        config = params.get("config")
        if not params.get("spider_name") or not config:
            return {"success": False, "message": "请指定爬虫名称和配置"}
        try:
            if not self._spider_helper:
                return {"success": False, "message": "爬虫助手未初始化"}

            if spider_name in self._spider_helper.spider_config:
                # 更新配置
                self._spider_config[spider_name].update(config)
                # 保存配置
                self.reload_config()
                return {"success": True, "message": f"爬虫 {spider_name} 配置更新成功"}
            else:
                return {"success": False, "message": f"爬虫 {spider_name} 不存在"}
        except Exception as e:
            logger.error(f"更新爬虫 {spider_name} 配置失败：{str(e)}")
            return {"success": False, "message": f"更新配置失败：{str(e)}"}

    def __reset_config(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        重置爬虫配置
        :param params: {spider_name: str}
        :return: 操作结果
        """
        if not self._enabled:
            return {"success": False, "message": ""}
        spider_name = params.get("spider_name")
        if not params.get("spider_name"):
            return {"success": False, "message": "请指定爬虫名称"}
        try:
            if not self._spider_helper:
                return {"success": False, "message": "爬虫助手未初始化"}

            if spider_name in spider_configs:
                # 重置为默认配置
                self._spider_config[spider_name] = copy(spider_configs[spider_name])
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
            self._spider_config = copy(spider_configs)
            # 保存配置
            self.reload_config()
            return {"success": True, "message": "所有爬虫配置已重置为默认值"}
        except Exception as e:
            logger.error(f"重置所有爬虫配置失败：{str(e)}")
            return {"success": False, "message": f"重置配置失败：{str(e)}"}

    def __get_status(self) -> Dict[str, Any]:
        """
        获取爬虫状态和统计信息
        :return: 状态信息
        """
        try:
            if not self._spider_helper:
                return {"success": False, "message": "爬虫助手未初始化"}

            # 获取所有爬虫状态
            total = len(self._spider_config)
            enabled = sum(1 for spider in self._spider_config.values() if spider.get('spider_enable'))
            disabled = total - enabled

            # 获取所有爬虫的标签和网址
            all_tags = set()
            spider_urls = {}
            for spider_name, spider in self._spider_config.items():
                if 'spider_tags' in spider:
                    all_tags.update(spider['spider_tags'])
                # 获取爬虫网址
                if hasattr(self._spider_helper, 'get_spider_url'):
                    url = self._spider_helper.get_spider_url(spider_name)
                    if url:
                        spider_urls[spider_name] = url
            for spider in self._spider_helper.running_spiders:
                url = spider.spider_url
                if url:
                    spider_urls[spider.spider_name] = url
            return {
                "success": True,
                "total": total,
                "enabled": enabled,
                "disabled": disabled,
                "tags": list(all_tags),
                "spider_urls": spider_urls,
                "status": "running" if self._enabled else "stopped"
            }
        except Exception as e:
            logger.error(f"获取爬虫状态失败：{str(e)}")
            return {"success": False, "message": f"获取状态失败：{str(e)}"}

    def __get_history(self) -> List[Dict[str, Any]]:
        """
        获取爬虫运行历史记录
        :return: 历史记录列表
        """
        try:
            if not self._spider_helper:
                return []

            # 获取最近的历史记录
            history = []
            for spider in self._spider_helper.running_spiders:
                spider_name = spider.__class__.__name__
                if hasattr(spider, 'get_history'):
                    spider_history = spider.get_history()
                    if spider_history:
                        history.extend(spider_history)

            # 按时间排序
            history.sort(key=lambda x: x.get('time', ''), reverse=True)
            return history[:50]  # 只返回最近50条记录
        except Exception as e:
            logger.error(f"获取历史记录失败：{str(e)}")
            return []

    def __add_tag(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        为指定爬虫添加标签
        :param params: { spider_name: str, tag: str}
        :return: 操作结果
        """
        if not self._enabled:
            return {"success": False, "message": ""}
        spider_name = params.get("spider_name")
        if not params.get("spider_name"):
            return {"success": False, "message": "请指定爬虫名称"}
        tag = params.get("tag")
        if not tag:
            return {"success": False, "message": "请指定标签"}
        try:
            if not self._spider_helper:
                return {"success": False, "message": "爬虫助手未初始化"}

            if spider_name not in self._spider_helper.spider_config:
                return {"success": False, "message": f"爬虫 {spider_name} 不存在"}

            # 获取爬虫的标签列表
            spider = self._spider_helper.spider_config[spider_name]
            if 'spider_tags' not in spider:
                spider['spider_tags'] = []

            # 检查标签是否已存在
            if tag in spider['spider_tags']:
                return {"success": False, "message": f"爬虫 {spider_name} 已存在标签 {tag}"}

            # 添加新标签
            spider['spider_tags'].append(tag)

            # 保存配置
            self.reload_config()
            return {"success": True, "message": f"爬虫 {spider_name} 添加标签 {tag} 成功"}
        except Exception as e:
            logger.error(f"添加标签失败：{str(e)}")
            return {"success": False, "message": f"添加标签失败：{str(e)}"}

    def __remove_tag(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        从指定爬虫删除标签
        :param params: { spider_name: str, tag: str}
        :return: 操作结果
        """
        if not self._enabled:
            return {"success": False, "message": ""}
        spider_name = params.get("spider_name")
        if not params.get("spider_name"):
            return {"success": False, "message": "请指定爬虫名称"}
        tag = params.get("tag")
        if not tag:
            return {"success": False, "message": "请指定标签"}
        try:
            if not self._spider_helper:
                return {"success": False, "message": "爬虫助手未初始化"}

            if spider_name not in self._spider_helper.spider_config:
                return {"success": False, "message": f"爬虫 {spider_name} 不存在"}

            # 获取爬虫的标签列表
            spider = self._spider_helper.spider_config[spider_name]
            if 'spider_tags' not in spider:
                return {"success": False, "message": f"爬虫 {spider_name} 没有标签"}

            # 检查标签是否存在
            if tag not in spider['spider_tags']:
                return {"success": False, "message": f"爬虫 {spider_name} 不存在标签 {tag}"}

            # 删除标签
            spider['spider_tags'].remove(tag)

            # 保存配置
            self.reload_config()
            return {"success": True, "message": f"爬虫 {spider_name} 删除标签 {tag} 成功"}
        except Exception as e:
            logger.error(f"删除标签失败：{str(e)}")
            return {"success": False, "message": f"删除标签失败：{str(e)}"}

    def get_render_mode(self) -> Tuple[str, str]:
        """
        获取插件渲染模式
        :return: 1、渲染模式，支持：vue/vuetify，默认vuetify
        :return: 2、组件路径，默认 dist/assets
        """
        return "vue", "dist/assets"

    def get_page(self) -> List[dict]:
        """
            拼装插件详情页面，需要返回页面配置，同时附带数据
        """
        pass
