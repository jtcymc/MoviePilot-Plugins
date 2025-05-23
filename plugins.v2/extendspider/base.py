from abc import ABCMeta, abstractmethod
from typing import Optional, Tuple

from log import logger
from sites import SiteRateLimiter
from utils.string import StringUtils
import requests


class _ExtendSpiderBase(metaclass=ABCMeta):
    """
        插件爬虫基类
    """
    # 爬虫名称
    spider_name: Optional[str] = ""
    # 爬虫描述
    spider_desc: Optional[str] = ""
    # 爬虫地址
    spider_url = ""
    # 爬虫是否启用
    spider_enable = True
    # 爬虫是否使用代理
    spider_proxy = False
    # 爬虫是否公开
    spider_public = True
    # page
    spider_page_start = 1
    # order
    spider_order = 0
    # 最多获取页数
    spider_max_load_page = 2
    # 是否开启限流
    spider_ratelimit = True
    # 爬虫插件名称
    _plugin_name = "PluginSpider"

    _limiters = {}
    # 代理实例
    spider_proxy_client = None  # 请求间隔时间范围（秒）
    #  请求间隔时间
    spider_request_interval = (2, 5)  # 最小2秒，最大5秒
    # 爬虫网站连通
    spider_web_status = True

    # UA
    spider_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"

    def __init__(self, config: dict = None):
        self._plugin_name = config.get("plugin_name")
        self.spider_name = config.get("spider_name")
        self.spider_desc = config.get("spider_desc")
        self.spider_enable = config.get("spider_enable")
        self.init_spider(config)
        # 初始化限速器
        self._limiters[self.spider_name] = SiteRateLimiter(
            limit_interval=60,
            limit_count=3,
            limit_seconds=60
        )

    @abstractmethod
    def init_spider(self, config: dict = None):
        """
        :param config: 配置信息字典
        """
        pass

    def _get_domain(self) -> str:
        """
        获取爬虫域名
        :return: 爬虫域名
        """
        return StringUtils.get_url_domain(self.spider_url)

    def get_name(self) -> str:
        """
        获取爬虫名称
        :return: 爬虫名称
        """
        return self.spider_name

    def get_enable(self) -> bool:
        """
        获取爬虫是否启用
        """
        return self.spider_enable

    def get_web_status(self) -> bool:
        """
        获取爬虫目标网站是否连通
        """
        # 检查是否触发限速
        sate, msg = self.test_connectivity()
        self.spider_web_status = sate
        logger.info(f"{self.spider_name} 测试网站连通性 {sate} {msg}")
        return self.spider_web_status

    def get_indexer(self) -> dict:
        return {
            "id": f'{self._plugin_name}-{self.spider_name}',
            "name": f'【{self._plugin_name}】{self.spider_name}',
            "url": self.spider_url,
            "domain": self._get_domain(),
            "public": self.spider_public,
            "proxy": self.spider_proxy,
            "parser": "PluginExtendSpider"
        }

    def get_indexers(self) -> list:
        return [self.get_indexer()]

    def test_connectivity(self) -> Tuple[bool, str]:
        """
        测试爬虫网站连通性
        :return: (是否连通, 错误信息)
        """
        state, msg = self.check_ratelimit()
        if state:
            logger.info("爬虫 %s 触发限速，请稍后再试" % self.get_name())
            return False, f"爬虫 {self.get_name()} 触发限速，请稍后再试"
        try:
            logger.info(f"正在测试 {self.spider_name} 代理连通性...")
            # 使用代理访问
            proxy_response = self.spider_proxy_client.request('GET', self.spider_url)
            if proxy_response.status_code != 200:
                return False, f"代理访问失败: HTTP {proxy_response.status_code}"
            logger.info(f"{self.spider_name} 网站连通性测试通过")
            return True, "网站连通性测试通过"
        except requests.exceptions.Timeout:
            return False, "网站访问超时"
        except requests.exceptions.ConnectionError:
            return False, "网站连接失败"
        except Exception as e:
            return False, f"测试过程发生异常: {str(e)}"

    def search(self, keyword: str, page: int):
        """
        搜索资源，支持限速控制。
        :param keyword: 搜索关键词
        :param page: 分页页码
        :return: 匹配的种子资源列表
        """
        if not self.get_enable() or not self.get_web_status():
            logger.warn(f"爬虫 {self.spider_name} 已被禁用/或网站连通测试失败，请检查配置！")
            return []
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
            logger.warn(f"【{self.spider_name}】站点 {self._get_domain} {msg}")
        return state, msg
