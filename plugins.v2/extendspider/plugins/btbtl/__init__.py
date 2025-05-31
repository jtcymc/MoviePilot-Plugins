import traceback
from concurrent.futures import as_completed, ThreadPoolExecutor
from typing import Tuple, Optional, Dict

from bs4 import BeautifulSoup
from app.log import logger
from app.core.config import settings
from plugins.extendspider.plugins.base import _ExtendSpiderBase
from app.plugins.extendspider.utils.url import pass_cloudflare
from playwright.sync_api import sync_playwright, Page
from app.schemas import SearchContext
from playwright_stealth import stealth_sync

from app.helper.search_filter import SearchFilterHelper
from app.utils.common import retry
from schemas import TorrentInfo
from utils.string import StringUtils


class BtBtlSpider(_ExtendSpiderBase):

    def __init__(self, config: dict = None):
        super(BtBtlSpider, self).__init__(config)



    def init_spider(self, config: dict = None):
        self.spider_url = "https://www.btbtl.com"
        self.spider_search_url = f"{self.spider_url}/search/$key$"

    def get_search_url(self, keyword: str, page: int) -> str:
        if not keyword:
            return ""
        return self.spider_search_url.replace("$key$", keyword)

    def _do_search(self, keyword: str, page: int, ctx: SearchContext):
        if not keyword:
            logger.warning(f"{self.spider_name}-搜索关键词为空")
            return []

        results = []
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
                browser_page = context.new_page()
                stealth_sync(browser_page)

                try:
                    # 访问主页并处理 Cloudflare
                    logger.info(f"{self.spider_name}-正在访问 {self.spider_url}...")
                    if not pass_cloudflare(self.spider_url, browser_page):
                        logger.warn("cloudflare challenge fail！")
                        return []
                    # 等待页面加载完成
                    browser_page.wait_for_load_state("networkidle", timeout=15 * 1000)
                    logger.info(f"{self.spider_name}-访问主页成功,开始搜索【{keyword}】...")
                    self._wait()
                    self.spider_cookie = context.cookies()
                    # 执行搜索
                    browser_page.fill("#txtKeywords", keyword)
                    browser_page.click("button[type='submit'].search-go")
                    browser_page.wait_for_load_state("networkidle", timeout=30 * 1000)
                    logger.info(f"{self.spider_name}-搜索完成，开始解析结果...")
                    results = self._parse_search_result(keyword, browser_page, ctx)
                    logger.info(f"{self.spider_name}-搜索完成，共找到 {len(results)} 个结果")
                    return results

                except Exception as e:
                    logger.error(f"{self.spider_name}-搜索过程发生错误: {str(e)}")
                    return []
                finally:
                    browser_page.close()
                    context.close()
                    browser.close()

        except Exception as e:
            logger.error(f"Playwright 初始化失败: {str(e)}")
            return []

    def _parse_search_result(self, keyword: str, page: Page, ctx: SearchContext):
        try:
            # 获取页面内容
            content = page.content()
            soup = BeautifulSoup(content, "html.parser")
            detail_tags = soup.select_one("div.module-list  div.module-items")
            # 判断是否有搜索结果
            if not detail_tags:
                return []
            detail_urls = set()
            for detail_tag in detail_tags.select("div.module-item-titlebox a.module-item-title"):
                detail_url = detail_tag['href'].strip()
                if not detail_url.startswith("http"):
                    detail_url = f"{self.spider_url}{detail_url}"
                detail_urls.add(detail_url)
            results = []
            if detail_urls:
                logger.info(f"{self.spider_name}-解析到{len(detail_urls)}个搜索结果，开始获取链接地址...")
                down_urls = {}
                for url in detail_urls:
                    down_urls = self._get_down_urls(url, page, down_urls)
                if down_urls:
                    urls = []
                    # 过滤种子
                    if ctx.enable_search_filter:
                        to_filter_titles = [name for name in down_urls.keys()]
                        filter_titles = SearchFilterHelper().do_filter(StringUtils.get_url_domain(self.spider_url),
                                                                       keyword, to_filter_titles, ctx)
                        urls = [down_urls[name] for name in down_urls.keys() if name in filter_titles]
                    else:
                        urls = [down_urls[name] for name in down_urls.keys()]
                    if not urls:
                        return []
                    results = self._get_torrent(urls)
            logger.info(f"{self.spider_name}-搜索结果解析完成，共找到 {len(results)} 个种子")
            return results
        except Exception as e:
            logger.error(f"{self.spider_name}-解析搜索结果失败: {str(e)} - {traceback.format_exc()}")
            return []

    @retry(Exception, 2, 3, 2, logger=logger)
    def _get_down_urls(self, detail_url: str, detail_page: Page, down_urls: dict) -> Dict[str, str]:
        # 使用线程池并发获取种子信息
        logger.info(f"{self.spider_name}-开始获取详情页: {detail_url}")
        self._wait()
        detail_page.goto(detail_url)
        detail_page.wait_for_load_state("networkidle", timeout=30 * 1000)

        content = detail_page.content()
        soup = BeautifulSoup(content, "html.parser")
        a_tags = soup.select("div.module-downlist div.module-row-info a[title].module-row-text.copy")

        seen_titles = set()
        seen_links = set()
        for a_tag in a_tags:
            title = a_tag['title'].strip()
            if ".torrent" not in title:
                continue
            title.replace("下载量", "")
            link = a_tag['href'].strip()
            if not link.startswith("http"):
                link = f"{self.spider_url}{link}"
            if title in seen_titles or link in seen_links:
                logger.debug(f"{self.spider_name}-跳过重复项: {title} / {link}")
                continue
            seen_titles.add(title)
            seen_links.add(link)
            down_urls[title] = link
        logger.info(f"{self.spider_name}-详情页解析完成，共找到 {len(seen_links)} 个下载链接")
        return down_urls

    def _get_torrent(self, down_urls) -> Optional[list]:
        results = []

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
                        for url_idx, down_url in enumerate(url_batch):
                            self._wait()  # 每个URL处理前等待
                            logger.info(
                                f"{self.spider_name}-线程 {index} 正在处理第 {url_idx + 1}/{len(url_batch)} 个下载页: {down_url}")

                            state, data = self._parse_torrent(down_url, detail_page)
                            if state and data:
                                current_batch_results.append(data)
                                logger.info(
                                    f"{self.spider_name}-线程 {index} 成功获取第 {url_idx + 1}/{len(url_batch)} 个下载页的种子信息")
                    finally:
                        detail_page.close()
                        context.close()
                        browser.close()
                    return current_batch_results
            except Exception as ex:
                logger.error(f"{self.spider_name}-线程 {index} 处理批次失败: {str(ex)}")
                return []

        # 计算每个线程处理的URL数量
        batch_size = max(1, len(down_urls) // self.spider_batch_size)  # 确保每个批次至少有一个URL
        url_batches = chunk_list(list(down_urls), batch_size)

        logger.info(f"{self.spider_name}-将 {len(down_urls)} 个下载页分成 {len(url_batches)} 个批次处理")

        # 使用线程池并发处理批次
        with ThreadPoolExecutor(max_workers=min(6, len(url_batches))) as executor:
            future_to_batch = {
                executor.submit(process_url_batch, batch, idx + 1): (idx, batch)
                for idx, batch in enumerate(url_batches)
            }

            for future in as_completed(future_to_batch):
                idx, batch = future_to_batch[future]
                try:
                    batch_results = future.result()
                    results.extend(batch_results)
                    logger.info(
                        f"{self.spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理完成，获取到 {len(batch_results)} 个种子")
                except Exception as e:
                    logger.error(f"{self.spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理失败: {str(e)}")

        logger.info(f"{self.spider_name}-所有批次处理完成，共获取到 {len(results)} 个种子")
        return results

    def _parse_torrent(self, down_url: str, detail_page: Page = None) -> Tuple[bool, Optional[dict]]:
        try:
            if not detail_page:
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
                    try:
                        return self._parse_torrent_content(down_url, detail_page)
                    finally:
                        detail_page.close()
                        context.close()
                        browser.close()
            else:
                return self._parse_torrent_content(down_url, detail_page)
        except Exception as e:
            logger.error(f"{self.spider_name}-解析下载链接失败: {str(e)}", exc_info=True)
            return False, None

    def _parse_torrent_content(self, down_url: str, detail_page: Page) -> Tuple[bool, Optional[dict]]:
        logger.info(f"{self.spider_name}-解析下载页: {down_url}")
        self._wait()
        detail_page.goto(down_url)
        detail_page.wait_for_load_state("networkidle", timeout=30 * 1000)

        content = detail_page.content()
        soup = BeautifulSoup(content, "html.parser")
        info_main = soup.select_one("div.box.view-heading.tinfo div.video-info-main")
        if not info_main:
            logger.warning(f"{self.spider_name}-找不到视频信息块")
            return False, None

        title = info_main.select_one("span.video-info-itemtitle + div.video-info-item")
        title = title.get_text(strip=True) if title else ""
        title = title[1:] if title.startswith("/") else title

        torrent_hash = info_main.select_one(
            "span.video-info-itemtitle:-soup-contains('Hash:') + div.video-info-item")
        torrent_hash = torrent_hash.get_text(strip=True) if torrent_hash else ""

        size = info_main.select_one(
            "span.video-info-itemtitle:-soup-contains('影片大小:') + div.video-info-item")
        size = size.get_text(strip=True) if size else "0"

        publish_time = info_main.select_one(
            "span.video-info-itemtitle:-soup-contains('种子时间:') + div.video-info-item")
        publish_time = publish_time.get_text(strip=True) if publish_time else ""

        enclosure = ""
        magnet = soup.select_one("div.video-info-footer.display a[href]:not([target='_blank'])")
        if magnet and magnet['href'].startswith('magnet:?'):
            enclosure = magnet['href'].strip()
        else:
            for a in soup.select("div.video-info-footer.display a[href][target='_blank']"):
                href = a['href'].strip()
                enclosure = href if href.startswith("http") else f"{self.spider_url}{href}"
                break

        if not enclosure:
            logger.warning(f"{self.spider_name}-未获取到有效下载链接")
            return False, None

        title_info = SearchFilterHelper().parse_title(title)
        if not title_info.episode:
            title_info.episode = SearchFilterHelper().get_episode(title)

        result = {
            "title": title,
            "enclosure": enclosure,
            "description": f"{title} | 大小: {size} | 时间: {publish_time} | Hash: {torrent_hash}",
            # "page_url": down_url, # 会下载字幕
            "size": title_info.size_num,
            "pubdate": publish_time
        }

        logger.info(f"{self.spider_name}-成功解析: {title}")
        return True, result


if __name__ == "__main__":
    lou = BtBtlSpider({
        'spider_proxy': False,
        'spider_enable': True,
        'spider_name': 'BtBtlSpider',
        'proxy_type': 'playwright',
        'proxy_config': {
            'flaresolverr_url': 'http://192.168.68.116:8191'
        },
        'request_interval': (2, 5)  # 设置随机请求间隔，最小2秒，最大5秒
    })
    # 使用直接请求
    rest = lou.search("藏海传", 1)
    print(rest)
    title_info = SearchFilterHelper().parse_title(
        "藏海传[第01-09集][国语配音+中文字幕].Legend.of.Zang.Hai.S01.2025.1080p.Viu.WEB-DL.H264.AAC-DeePTV")
    size = StringUtils.num_filesize("2.4GB")
    TorrentInfo(title="s", size=title_info.size_num)
    print(size)
