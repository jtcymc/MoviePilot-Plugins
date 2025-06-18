import concurrent
import random
import threading
import time
from abc import ABCMeta, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple
from urllib.parse import urlparse

from app.core.config import settings
from app.helper.search_filter import SearchFilterHelper
from app.log import logger
from app.modules.indexer.utils.proxy import ProxyFactory
from app.schemas import SearchContext
from app.sites.site_limiter import SiteRateLimiter
from app.utils.string import StringUtils
import requests
import asyncio
import sys
import os

from plugins.extendspider.utils.browser import create_drission_chromium
from plugins.extendspider.utils.drission_page import DrissonBrowser


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
    _plugin_name = "ExtendSpider"
    _limiters = {}
    # 代理实例
    spider_proxy_client = None  # 请求间隔时间范围（秒）
    #  请求间隔时间
    spider_request_interval = (0.6, 1.8)  # 最小2秒，最大5秒
    # 爬虫网站连通
    spider_web_status = True
    #  请求头
    spider_headers = {}
    #  cookie
    spider_cookie = []
    #  网站搜索接口
    spider_search_url = ""
    #  是否支持浏览
    support_browse = False
    # 是否支持imdb_id
    support_imdb_id = False
    #  搜索结果锁
    _request_result_lock = None
    #  批量搜索结果
    spider_batch_size = 4

    # UA
    spider_ua = ""

    # 浏览器
    browser = None

    def __init__(self, config: dict = None):
        self._plugin_name = config.get("plugin_name", "ExtendSpider")
        self.spider_name = config.get("spider_name")
        self.spider_desc = config.get("spider_desc")
        self.spider_enable = config.get("spider_enable")
        self.spider_proxy = config.get("spider_proxy")
        self.spider_url = config.get("spider_url")
        self.spider_headless = config.get("spider_headless", True)
        self.use_drission_browser = config.get("use_drission_browser", False)
        # 跳过cloudflare
        self.pass_cloud_flare = config.get("pass_cloud_flare", False)
        self.spider_ua = config.get("spider_ua", settings.USER_AGENT)
        self.spider_headers = {
            "User-Agent": settings.USER_AGENT,
        }
        self.init_spider(config)
        # 初始化限速器
        self._limiters[self.spider_name] = SiteRateLimiter(
            limit_interval=40,
            limit_count=20,
            limit_seconds=10
        )
        self._min_interval, self._max_interval = self.spider_request_interval
        self._last_request_time = 0

        # 初始化代理配置
        proxy_type = config.get("proxy_type", "direct")
        proxy_config = config.get("proxy_config", {})

        if proxy_type == "playwright":
            logger.info(f"{self.spider_name}-初始化代理类型: playwright")
            # 设置事件循环策略
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                # 设置环境变量
                os.environ["PYTHONASYNCIODEBUG"] = "0"
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
        if self.pass_cloud_flare or proxy_type == "flaresolverr":
            # 初始化代理
            proxy_config = {
                'proxy_type': 'flaresolverr',
                'flaresolverr_url': settings.FLARESOLVERR_URL,
                'session_id': f"moviepilot_{self.spider_name}"
            }
        else:
            proxy_config = {
                'proxy_type': 'direct',
            }
        self.spider_proxy_client = ProxyFactory.create_proxy(headers={},
                                                             **proxy_config)
        logger.info(f"{self.spider_name}-初始化代理类型: {proxy_config.get('proxy_type')}, 配置: {proxy_config}")
        # 初始化过滤
        self.search_helper = SearchFilterHelper()
        # 初始化线程锁
        self._request_result_lock = threading.Lock()
        logger.info(f"初始化 {self.spider_name} 爬虫")
        #  创建浏览器
        if self.use_drission_browser:
            logger.info(f"{self.spider_name} 使用浏览器browser")
            self.browser = DrissonBrowser(proxy=self.spider_proxy, headless=self.spider_headless).browser

    def __del__(self):
        if self.spider_proxy_client:
            self.spider_proxy_client = None

    @abstractmethod
    def init_spider(self, config: dict = None):
        """
        :param config: 配置信息字典
        """
        pass

    def _wait_for_interval(self):
        """等待请求间隔"""
        if self._max_interval > 0:
            current_time = time.time()
            elapsed = current_time - self._last_request_time
            if elapsed < self._min_interval:
                # 生成随机等待时间
                wait_time = random.uniform(self._min_interval, self._max_interval)
                time.sleep(wait_time - elapsed)
            self._last_request_time = time.time()

    def _wait(self, min_delay: float = None, max_delay: float = None):
        """全局单一等待随机间隔时间"""
        with self._request_result_lock:  # 使用请求锁确保间隔时间正确执行
            delay = random.uniform(min_delay, max_delay) if max_delay else random.uniform(*self.spider_request_interval)
            time.sleep(delay)

    def _wait_inner(self, min_delay: float = None, max_delay: float = None):
        """等待随机间隔时间"""
        delay = random.uniform(min_delay, max_delay) if max_delay else random.uniform(*self.spider_request_interval)
        time.sleep(delay)

    def browse(self) -> list:
        """
        浏览页面，用于推荐
        """
        pass

    def search_by_imdb_id(self, imdb_id: Optional[str] = None) -> list:
        """
        :param imdb_id: imdb_id
        :return: 搜索结果
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
        logger.info(f"{self.spider_name}-测试网站连通性 {sate} {msg}")
        return self.spider_web_status

    def get_indexer(self) -> dict:
        return {
            "id": f'{self._plugin_name}-{self.spider_name}',
            "name": f'{self._plugin_name}-{self.spider_name}',
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

            # 如果是 playwright 代理
            if isinstance(self.spider_proxy_client, dict) and self.spider_proxy_client.get("type") == "playwright":
                from playwright.sync_api import sync_playwright
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    context = browser.new_context()
                    page = context.new_page()
                    try:
                        response = page.goto(self.spider_url)
                        if response.status == 200:
                            return True, "网站连通性测试通过"
                        return False, f"代理访问失败: HTTP {response.status}"
                    finally:
                        browser.close()
            else:
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

    # @cached(cache=TTLCache(maxsize=200, ttl=2 * 3600), key=lambda self, keyword, page: (id(self), keyword, page))
    def search(self, keyword: str, page: int, search_context: Optional[SearchContext] = None):
        """
        搜索资源，支持限速控制。
        :param keyword: 搜索关键词
        :param page: 分页页码
        :param search_context:  搜索上下文
        :return: 匹配的种子资源列表
        """
        state, result, search_context = self._pre_search_check(keyword, context=search_context)
        if not state:
            return result
        logger.info(f"{self.spider_name}-开始搜索 检索词: {keyword} ")
        new_page = page if page > 1 else 1

        return self._do_search(keyword, page=new_page, ctx=search_context)

    def _pre_search_check(self, keyword: str, context: SearchContext) -> Tuple[bool, list, SearchContext]:
        """
        预检搜索
        :param keyword: 搜索关键词
        :param context: 上下文
        :return: (是否通过, 搜索结果)
        """
        # 检查是否启用
        if not self.get_enable():
            logger.warn(f"爬虫 {self.spider_name}-已被禁用/或网站连通测试失败，请检查配置！")
            return False, [], context
        # 检查是否触发限速
        state, _ = self.check_ratelimit()
        if state:
            return False, [], context
        # 是否是直接 获取种子资源
        if self.support_browse:
            logger.info(f"{self.spider_name}-开始浏览,获取种子资源")
            return False, self.browse(), context
        # 检查关键词
        if not keyword:
            logger.warning("搜索关键词为空")
            return False, [], context
        if not context:
            context = SearchContext()
        # 校验是否是imdbid搜索
        if context.area == "imdbid" and self.support_imdb_id:
            logger.info(f"{self.spider_name}-开始通过imdb_id搜索 imdb_id: {keyword} ")
            return False, self.search_by_imdb_id(keyword), context
        return True, [], context

    @abstractmethod
    def _do_search(self, keyword: str, page: int, ctx: SearchContext):
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

    def _get_link_size(self, link_str: str):
        self._wait_for_interval()
        from plugins.extendspider.utils.url import get_magnet_info_from_url
        ret = get_magnet_info_from_url(link_str)
        if ret:
            logger.info(f"{self.spider_name}-获取种子信息成功: {link_str} 返回信息: {ret}")
            return ret['size']
        return None

    # 将URL列表分成多个批次
    @staticmethod
    def chunk_list(lst: list, chunk_size: int):
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

    def get_link_size(self, results: list):
        if not results:
            return
        logger.info(f"{self.spider_name}-开始获取种子大小")
        with ThreadPoolExecutor(max_workers=max(8, len(results))) as executor:
            futures = {
                executor.submit(self._get_link_size, result['enclosure']): result
                for result in results
                if result.get('enclosure', '').startswith("magnet:?") and not result.get('size')
            }
            for future in concurrent.futures.as_completed(futures):
                result = futures[future]
                size = future.result()
                if size:
                    # 更新原始对象
                    result['size'] = size

    def _from_pass_cloud_flare(self, url):
        # 发请求获取 cookies
        response = self.spider_proxy_client.request('GET', url)
        if not response.cookies:
            return
        parsed_url = urlparse(url)
        domain = parsed_url.hostname
        cookies = []
        for cookie in response.cookies:
            cookies.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": domain,
                "path": cookie.path or "/",
                "secure": cookie.secure,
                "httpOnly": getattr(cookie, "rest", {}).get("HttpOnly", False),
                "expires": cookie.expires if cookie.expires else -1  # Playwright 允许 -1 表示会话 cookie
            })

        self.spider_cookie = cookies
        self.spider_ua = response.user_agent if hasattr(response, "user_agent") else self.spider_ua
        self.spider_headers["User-Agent"] = self.spider_ua

        if self.browser:
            self.browser.set.cookies(cookies)
            self.browser.set.user_agent(self.spider_ua)
