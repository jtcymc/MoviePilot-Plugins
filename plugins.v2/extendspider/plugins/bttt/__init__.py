from bs4 import BeautifulSoup
from app.log import logger
from app.core.config import settings
from app.helper.search_filter import SearchFilterHelper
from app.plugins.extendspider.base import _ExtendSpiderBase
from playwright.sync_api import sync_playwright, Page

from app.plugins.extendspider.utils.url import pass_cloudflare
from app.schemas import SearchContext
from utils.common import retry


class BtttSpider(_ExtendSpiderBase):
    #  网站搜索接口Cookie
    spider_cookie = ""

    def __init__(self, config: dict = None):
        super(BtttSpider, self).__init__(config)

    def init_spider(self, config: dict = None):
        self.spider_url = "https://www.bttt11.com"
        self.spider_search_url = f"{self.spider_url}/e/search"
        self.spider_cookie = ""

    def _do_search(self, keyword: str, page: int, ctx: SearchContext):
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(user_agent=settings.USER_AGENT,
                                              proxy=settings.PROXY_SERVER if self.spider_proxy else None)
                page = context.new_page()

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
                    # 执行搜索
                    page.fill("#search-keyword", keyword)
                    page.click("input[name='searchtype'][value='搜索'].sub")
                    page.wait_for_load_state("networkidle", timeout=30 * 1000)

                    # 解析搜索结果
                    results = self._parse_search_result(page, ctx)
                    logger.info(f"{self.spider_name}-搜索完成，共找到 {len(results)} 个结果")
                    return results

                except Exception as e:
                    logger.error(f"搜索过程发生错误: {str(e)}")
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

            results = []
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
                self._wait()
                # 获取种子信息
                logger.info(f"{self.spider_name}-开始获取 {detail_url} 详情页的种子信息")
                torrents = self._get_torrent_info(page, detail_url, ctx)
                results.extend(torrents)
            return results

        except Exception as e:
            logger.error(f"解析搜索结果失败: {str(e)}")
            return []
    @retry(Exception, 5, 3, 2, logger=logger)
    def _get_torrent_info(self, page: Page, detail_url: str, ctx: SearchContext) -> list:
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
                    "page_url": detail_url,
                    "size": title_info.sie_num
                })
                logger.debug(f"{self.spider_name}-找到种子: {title}")

            if not results:
                logger.warn(f"{self.spider_name}-没有找到种子")
            # 过滤信息
            # self.get_link_size(results)
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
