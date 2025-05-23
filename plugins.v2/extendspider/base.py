from abc import ABCMeta, abstractmethod
from typing import Optional, Tuple

from log import logger
from sites import SiteRateLimiter
from utils.string import StringUtils


class _ExtendSpiderBase(metaclass=ABCMeta):
    """
        插件爬虫基类
    """
    # 爬虫名称
    _spider_name: Optional[str] = ""
    # 爬虫描述
    _spider_desc: Optional[str] = ""
    # 爬虫地址
    _spider_url = ""
    # 爬虫是否启用
    _spider_enable = True
    # 爬虫是否使用代理
    _spider_proxy = False
    # 爬虫是否公开
    _spider_public = False
    # page
    _spider_page_start = 1
    # 最多获取页数
    _spider_max_load_page = 2
    # 是否开启限流
    _spider_ratelimit = True
    # 爬虫插件名称
    _plugin_name = "PluginSpider"

    _limiters = {}

    # UA
    _spider_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"

    def __init__(self, config: dict = None):
        self._init_spider(config)
        # 初始化限速器
        self._limiters[self._spider_name] = SiteRateLimiter(
            limit_interval=60,
            limit_count=3,
            limit_seconds=60
        )

    @abstractmethod
    def _init_spider(self, config: dict = None):
        """
        :param config: 配置信息字典
        """
        pass

    def _get_domain(self) -> str:
        """
        获取爬虫域名
        :return: 爬虫域名
        """
        return StringUtils.get_url_domain(self._spider_url)

    def get_name(self) -> str:
        """
        获取爬虫名称
        :return: 爬虫名称
        """
        return self._spider_name

    def get_state(self) -> bool:
        """
        获取爬虫运行状态
        """
        return self._spider_enable

    def get_indexer(self) -> dict:
        return {
            "id": f'{self._plugin_name}-{self._spider_name}',
            "name": f'【{self._plugin_name}】{self._spider_name}',
            "url": self._spider_url,
            "domain": self._get_domain(),
            "public": self._spider_public,
            "proxy": self._spider_proxy,
            "parser": "PluginExtendSpider"
        }

    def get_indexers(self) -> list:
        return [self.get_indexer()]

    def search(self, keyword: str, page: int):
        """
        搜索资源，支持限速控制。
        :param keyword: 搜索关键词
        :param page: 分页页码
        :return: 匹配的种子资源列表
        """
        # 检查是否触发限速
        state, msg = self.check_ratelimit()
        if state:
            return []
        return self._do_search(keyword, page)

    @abstractmethod
    def _do_search(self, keyword: str, page: int):
        pass

    def check_ratelimit(self) -> Tuple[bool, str]:
        """
        检查站点是否触发流控
        :return: (是否触发流控, 错误信息)
        """
        if not self._limiters.get(self._get_domain()):
            return False, ""
        state, msg = self._limiters[self._get_domain()].check_rate_limit()
        if msg:
            logger.warn(f"【{self._spider_name}】站点 {self._get_domain} {msg}")
        return state, msg
