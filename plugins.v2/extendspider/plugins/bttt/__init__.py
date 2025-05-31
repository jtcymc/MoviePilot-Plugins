from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from bs4 import BeautifulSoup
from app.log import logger
from app.core.config import settings
from app.helper.search_filter import SearchFilterHelper
from plugins.extendspider.plugins.base import _ExtendSpiderBase
from playwright.sync_api import sync_playwright, Page
from playwright_stealth import stealth_sync

from app.plugins.extendspider.utils.url import pass_cloudflare
from app.schemas import SearchContext
from app.utils.common import retry


class BtttSpider(_ExtendSpiderBase):

    def __init__(self, config: dict = None):
        super(BtttSpider, self).__init__(config)
        self._result_lock = threading.Lock()
        

    def init_spider(self, config: dict = None):
        self.spider_url = "https://www.bttt11.com"
        self.spider_search_url = f"{self.spider_url}/e/search"

    def _do_search(self, keyword: str, page: int, ctx: SearchContext):
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-site-isolation-trials',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--disable-gpu'
                    ]
                )
                context = browser.new_context(
                    user_agent=settings.USER_AGENT,
                    proxy=settings.PROXY_SERVER if self.spider_proxy else None,
                    viewport={'width': 1920, 'height': 1080},
                    locale='zh-CN',
                    timezone_id='Asia/Shanghai',
                    device_scale_factor=1,
                    has_touch=False,
                    is_mobile=False,
                    java_script_enabled=True,
                    ignore_https_errors=True,
                    permissions=['geolocation']
                )
                page = context.new_page()
                stealth_sync(page)

                try:
                    # 访问主页并处理 Cloudflare
                    logger.info(f"{self.spider_name}-正在访问 {self.spider_url}...")
                    if not pass_cloudflare(self.spider_url, page):
                        logger.warn("cloudflare challenge fail！")
                        return []

                    # 等待页面加载完成
                    page.wait_for_load_state("networkidle", timeout=30 * 1000)
                    logger.info(f"{self.spider_name}-访问主页成功,开始搜索【{keyword}】...")
                    self._wait()
                    self.spider_cookie = context.cookies()
                    # 执行搜索
                    page.fill("#search-keyword", keyword)
                    page.click("input[name='searchtype'][value='搜索'].sub")
                    page.wait_for_load_state("networkidle", timeout=30 * 1000)

                    # 解析搜索结果
                    results = self._parse_search_result(page, ctx)
                    logger.info(f"{self.spider_name}-搜索完成，共找到 {len(results)} 个结果")
                    return results

                except Exception as e:
                    logger.error(f"{self.spider_name}-搜索过程发生错误: {str(e)}")
                    return []
                finally:
                    browser.close()

        except Exception as e:
            logger.error(f"Playwright 初始化失败: {str(e)}")
            return []

    def _parse_search_result(self, page: Page, ctx: SearchContext):
        try:
            # 获取页面内容
            content = page.content()
            soup = BeautifulSoup(content, "html.parser")
            ul_div = soup.find("ul", class_="ul-imgtxt2 row")

            if not ul_div:
                return []

            detail_urls = set()
            # 获取所有搜索结果
            for item in ul_div.find_all("li", class_="col-md-6"):
                detail_tag = item.select_one("div.txt  a")
                if not detail_tag:
                    continue

                detail_url = detail_tag['href'].strip()
                if not detail_url:
                    continue

                if not detail_url.startswith("http"):
                    detail_url = f"{self.spider_url}/{detail_url}"
                detail_urls.add(detail_url)
            
            if not detail_urls:
                return []
            
            # 获取种子信息
            logger.info(f"{self.spider_name}-开始获取 {len(detail_urls)} 个详情页的种子信息")
            return self._parse_detail_results(detail_urls)

        except Exception as e:
            logger.error(f"解析搜索结果失败: {str(e)}")
            return []

    def _parse_detail_results(self, detail_urls) -> list:
        """ 处理详情页 """
        results = []
        _processed_titles = set()

        # 将URL列表分成多个批次
        def chunk_list(lst, chunk_size):
            return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

        def process_url_batch(url_batch, index):
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(
                        headless=True,
                        args=[
                            '--disable-blink-features=AutomationControlled',
                            '--disable-features=IsolateOrigins,site-per-process',
                            '--disable-site-isolation-trials',
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-accelerated-2d-canvas',
                            '--no-first-run',
                            '--no-zygote',
                            '--disable-gpu'
                        ]
                    )
                    context = browser.new_context(
                        user_agent=settings.USER_AGENT,
                        proxy=settings.PROXY_SERVER if self.spider_proxy else None,
                        viewport={'width': 1920, 'height': 1080},
                        locale='zh-CN',
                        timezone_id='Asia/Shanghai',
                        device_scale_factor=1,
                        has_touch=False,
                        is_mobile=False,
                        java_script_enabled=True,
                        ignore_https_errors=True,
                        permissions=['geolocation']
                    )
                    if self.spider_cookie:
                        context.add_cookies(self.spider_cookie)
                    detail_page = context.new_page()
                    stealth_sync(detail_page)

                    current_batch_results = []
                    try:
                        for url_idx, detail_url in enumerate(url_batch):
                            self._wait()  # 每个URL处理前等待
                            logger.info(
                                f"{self.spider_name}-线程 {index} 正在处理第 {url_idx + 1}/{len(url_batch)} 个详情页: {detail_url}")

                            torrents = self._get_torrent_info(detail_page, detail_url, None)
                            if torrents:
                                current_batch_results.extend(torrents)
                                logger.info(
                                    f"{self.spider_name}-线程 {index} 成功获取第 {url_idx + 1}/{len(url_batch)} 个详情页的种子信息: {len(torrents)} 个")
                    finally:
                        detail_page.close()
                        context.close()
                        browser.close()
                    return current_batch_results
            except Exception as ex:
                logger.error(f"{self.spider_name}-线程 {index} 处理批次失败: {str(ex)}")
                return []

        # 计算每个线程处理的URL数量
        batch_size = max(1, len(detail_urls) // self.spider_batch_size)  # 确保每个批次至少有一个URL
        url_batches = chunk_list(list(detail_urls), batch_size)

        logger.info(f"{self.spider_name}-将 {len(detail_urls)} 个详情页分成 {len(url_batches)} 个批次处理")

        # 使用线程池并发处理批次
        with ThreadPoolExecutor(max_workers=min(4, len(url_batches))) as executor:
            future_to_batch = {
                executor.submit(process_url_batch, batch, idx + 1): (idx, batch)
                for idx, batch in enumerate(url_batches)
            }

            for future in as_completed(future_to_batch):
                idx, batch = future_to_batch[future]
                try:
                    batch_results = future.result()
                    with self._result_lock:
                        results.extend(batch_results)
                        logger.info(
                            f"{self.spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理完成，获取到 {len(batch_results)} 个种子")
                except Exception as e:
                    logger.error(f"{self.spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理失败: {str(e)}")

        logger.info(f"{self.spider_name}-所有批次处理完成，共获取到 {len(results)} 个种子")
        return results

    @retry(Exception, 5, 3, 2, logger=logger)
    def _get_torrent_info(self, page: Page, detail_url: str, ctx: SearchContext = None) -> list:
        try:
            self._wait()
            # 访问详情页
            page.goto(detail_url)
            page.wait_for_load_state("networkidle", timeout=30 * 1000)
            logger.info(f"{self.spider_name}-访问详情页成功,开始获取种子信息...")
            # 获取页面内容
            content = page.content()
            soup = BeautifulSoup(content, "html.parser")

            results = []
            a_tags = soup.select("div.bot a[href]")

            for a_tag in a_tags:
                link = a_tag['href'].strip()
                if not link.startswith('magnet:?'):
                    continue

                title = a_tag.text.strip()
                title_info = SearchFilterHelper().parse_title(title)
                if not title_info.episode:
                    title_info.episode = SearchFilterHelper().get_episode(title)
                results.append({
                    "title": title,
                    "enclosure": link,
                    "description": title,
                    # "page_url": detail_url, # 会下载字幕
                    "size": title_info.size_num
                })
                logger.debug(f"{self.spider_name}-找到种子: {title}")

            if not results:
                logger.warn(f"{self.spider_name}-没有找到种子")
            return results

        except Exception as e:
            logger.error(f"获取种子信息失败: {str(e)}")
            return []


if __name__ == "__main__":
    lou = BtttSpider({
        'spider_proxy': False,
        'spider_enable': True,
        'spider_name': 'BtttSpider',
        'proxy_type': 'playwright',
        'proxy_config': {
            'flaresolverr_url': 'http://192.168.68.116:8191'
        },
        'request_interval': (2, 5)  # 设置随机请求间隔，最小2秒，最大5秒
    })
    # 使用直接请求
    rest = lou.search("藏海传", 1)
    print(rest)
