import traceback
from typing import List, Any, Optional, Dict, Tuple

from app.helper.module import ModuleHelper
from app.log import logger
from app.plugins.extendspider.plugins.base import _ExtendSpiderBase
from app.schemas import SearchContext
from app.utils.singleton import SingletonClass


class SpiderHelper(metaclass=SingletonClass):
    # 所有插件列表
    _extend_plugins: Dict[str, Any] = {}

    # 启用的插件列表
    _extend_running_plugins: Dict[str, _ExtendSpiderBase] = {}

    # 预设爬虫配置
    _presets_spider_config: Dict = {}

    def __init__(self, presets_spider_config: Dict = None):
        self._presets_spider_config = presets_spider_config
        self.init_config()

    def init_config(self):
        self.remove_plugin()
        self.load_spiders()

    @property
    def running_spiders(self):
        return self._extend_running_plugins.values()

    @property
    def spiders(self):
        return self._extend_plugins

    @property
    def spider_config(self):
        return self._presets_spider_config

    @spider_config.setter
    def spider_config(self, spider_config):
        self._presets_spider_config = spider_config

    def load_spiders(self, s_name: Optional[str] = None):
        def check_module(module: Any):
            """
            检查模块
            """
            if not hasattr(module, 'init_spider') or not hasattr(module, "spider_name"):
                logger.warning(f"插件 {module.__name__} 不正确")
                return False
            return True

        # 扫描插件目录
        if s_name:
            # 加载指定插件
            plugins = ModuleHelper.load_with_pre_filter(
                "app.plugins.extendspider.plugins",
                filter_func=lambda name, obj: check_module(obj) and name == s_name
            )
        else:
            # 加载所有插件
            plugins = ModuleHelper.load(
                "app.plugins.extendspider.plugins",
                filter_func=lambda _, obj: check_module(obj)
            )
        logger.info(f"正在加载爬虫插件：{', '.join(plugin.spider_name for plugin in plugins)} ...")
        plugins.sort(key=lambda x: x.spider_order if hasattr(x, "spider_order") else 0)
        for plugin in plugins:
            plugin_id = plugin.__name__
            if s_name and plugin_id != s_name:
                logger.warning(f"插件 {plugin_id} 不正确")
                continue
            try:
                # 存储Class
                self._extend_plugins[plugin_id] = plugin
                conf = self._presets_spider_config.get(plugin_id) or {}
                # 禁用的不安装
                if conf and hasattr(conf, "spider_enable") and not conf.spider_enable:
                    continue
                # 生成实例
                plugin_obj = plugin(conf)
                # 存储运行实例
                self._extend_running_plugins[plugin_id] = plugin_obj
                logger.info(f"加载爬虫插件：{plugin_id}")
            except Exception as err:
                logger.error(f"加载爬插件 {plugin_id} 出错：{str(err)} - {traceback.format_exc()}")

    def remove_plugin(self, s_name: Optional[str] = None):
        """
        移除爬虫插件
        :param s_name: 爬虫插件ID
        :return:
        """
        if s_name:
            logger.info(f"正在停止插件 {s_name}...")
            plugin_obj = self._extend_running_plugins.get(s_name)
            if not plugin_obj:
                logger.warning(f"插件 {s_name} 不存在或未加载")
                return
            plugins = {s_name: plugin_obj}
        else:
            logger.info("正在停止所有插件...")
            plugins = self._extend_running_plugins

        for _, plugin in plugins.items():
            plugin.spider_enable = False
            # 清空对像
        if s_name:
            # 清空指定插件
            self._extend_running_plugins.pop(s_name, None)
        else:
            # 清空
            self._extend_plugins = {}
            self._extend_running_plugins = {}
        logger.info("插件停止完成")

    def search(self, s_name, keyword, page, search_context: Optional[SearchContext] = None):
        spider = self._extend_running_plugins.get(s_name)
        if spider:
            return spider.search(keyword, page, search_context)
        return []

    def test_all_connectivity(self) -> Dict[str, Tuple[bool, str]]:
        """
        测试所有运行中的爬虫连通性
        :return: 字典 {爬虫名称: (是否连通, 错误信息)}
        """
        results = {}
        for spider_name, spider in self._extend_running_plugins.items():
            try:
                success, message = spider.get_web_status()
                results[spider_name] = (success, message)
            except Exception as e:
                results[spider_name] = (False, str(e))
        return results

    def update_spider_config(self, spider_name: str, config: Dict):
        """
        更新爬虫配置并重启爬虫
        :param spider_name: 爬虫名称
        :param config: 新的配置
        """
        if spider_name not in self._presets_spider_config:
            logger.error(f"爬虫 {spider_name} 配置不存在")
            return False

        # 更新配置
        self._presets_spider_config[spider_name].update(config)

        # 重启爬虫
        self.remove_plugin(spider_name)
        self.load_spiders(spider_name)
        return True

    def get_spider_status(self) -> List[Dict]:
        """
        获取所有爬虫状态
        :return: 爬虫状态列表
        """
        status_list = []
        for spider_name, spider in self._extend_running_plugins.items():
            config = self._presets_spider_config.get(spider_name, {})
            status_list.append({
                "name": spider_name,
                "url": spider.spider_url,
                "enable": config.get("spider_enable", False),
                "desc": config.get("spider_desc", ""),
                "web_status": spider.spider_web_status
            })
        return status_list
