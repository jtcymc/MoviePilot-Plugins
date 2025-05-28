from concurrent.futures import as_completed, ThreadPoolExecutor
from typing import Tuple, Optional

from bs4 import BeautifulSoup
from app.log import logger
from app.core.config import settings
from app.plugins.extendspider.base import _ExtendSpiderBase
from app.plugins.extendspider.utils.url import pass_cloudflare
from playwright.sync_api import sync_playwright, Page
from app.schemas import SearchContext

from app.helper.search_filter import SearchFilterHelper
from utils.common import retry


class BtBtlSpider(_ExtendSpiderBase):
    #  网站搜索接口Cookie
    spider_cookie = ""

    def __init__(self, config: dict = None):
        super(BtBtlSpider, self).__init__(config)
        #  最大详情页链接数
        self.max_detail_urls = 5
        logger.info(f"初始化 {self.spider_name} 爬虫")

    def init_spider(self, config: dict = None):
        self.spider_url = "https://www.btbtl.com"
        self.spider_search_url = f"{self.spider_url}/search/$key$"
        self.spider_cookie = ""
        self.spider_headers = {
            "User-Agent": settings.USER_AGENT,
        }

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
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(user_agent=settings.USER_AGENT,
                                              proxy=settings.PROXY_SERVER if self.spider_proxy else None)
                browser_page = context.new_page()

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

                    # 执行搜索
                    browser_page.fill("#txtKeywords", keyword)
                    browser_page.click("button[type='submit'].search-go")
                    browser_page.wait_for_load_state("networkidle", timeout=30 * 1000)
                    logger.info(f"{self.spider_name}-搜索完成，开始解析结果...")
                    results = self._parse_search_result(browser_page, ctx)
                    logger.info(f"{self.spider_name}-搜索完成，共找到 {len(results)} 个结果")
                    return results

                except Exception as e:
                    logger.error(f"搜索过程发生错误: {str(e)}")
                    return []
                finally:
                    browser_page.close()
                    context.close()
                    browser.close()

        except Exception as e:
            logger.error(f"Playwright 初始化失败: {str(e)}")
            return []

    def _parse_search_result(self, page: Page, ctx: SearchContext):
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
                    detail_url = f"{self.spider_url}/{detail_url}"
                detail_urls.add(detail_url)
            results = []
            if detail_urls:
                logger.info(f"{self.spider_name}-解析到{len(detail_urls)}个搜索结果，开始获取链接地址...")
                down_urls = set()
                for url in detail_urls:
                    down_urls = down_urls.union(down_urls, self._get_down_urls(url, page))
                if down_urls:
                    results = self._get_torrent(down_urls)
            logger.info(f"{self.spider_name}-搜索结果解析完成，共找到 {len(results)} 个种子")
            return results
        except Exception as e:
            logger.error(f"{self.spider_name}-解析搜索结果失败: {str(e)}")
            return []
    @retry(Exception, 5, 3, 2, logger=logger)
    def _get_down_urls(self, detail_url: str, detail_page: Page) -> Optional[set]:
        # 使用线程池并发获取种子信息
        logger.info(f"{self.spider_name}-开始获取详情页: {detail_url}")
        self._wait()
        detail_page.goto(detail_url)
        detail_page.wait_for_load_state("networkidle", timeout=30 * 1000)

        content = detail_page.content()
        soup = BeautifulSoup(content, "html.parser")
        a_tags = soup.select("div.module-downlist div.module-row-info a[title].btn-down")

        seen_titles = set()
        seen_links = set()
        down_urls = set()

        for a_tag in a_tags:
            title = a_tag['title'].strip()
            if ".torrent" not in title:
                continue
            link = a_tag['href'].strip()
            if not link.startswith("http"):
                link = f"{self.spider_url}/{link}"
            if title in seen_titles or link in seen_links:
                logger.debug(f"{self.spider_name}-跳过重复项: {title} / {link}")
                continue
            seen_titles.add(title)
            seen_links.add(link)
            down_urls.add(link)
        logger.info(f"{self.spider_name}-详情页解析完成，共找到 {len(down_urls)} 个下载链接")
        return down_urls

    def _get_torrent(self, down_urls) -> Optional[list]:
        results = set()
        with ThreadPoolExecutor(max_workers=min(4, len(down_urls))) as executor:
            futures = [executor.submit(self._parse_torrent, url) for url in down_urls]
            for future in as_completed(futures):
                state, data = future.result()
                if state:
                    results.add(data)
        return list(results)

    def _parse_torrent(self, down_url: str) -> Tuple[bool, Optional[dict]]:
        self._wait()  # 每个任务开始前等待
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(user_agent=settings.USER_AGENT,
                                          proxy=settings.PROXY_SERVER if self.spider_proxy else None)
            detail_page = context.new_page()
            try:
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
                    "page_url": down_url,
                    "size": title_info.sie_num,
                    "pubdate": publish_time
                }

                logger.info(f"{self.spider_name}-成功解析: {title}")
                return True, result
            except Exception as e:
                logger.error(f"{self.spider_name}-解析下载链接失败: {str(e)}", exc_info=True)
            finally:
                detail_page.close()
                browser.close()
                context.close()
        return False, None


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
