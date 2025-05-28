from bs4 import BeautifulSoup
from app.log import logger
from app.core.config import settings
from app.helper.search_filter import SearchFilterHelper
from app.plugins.extendspider.base import _ExtendSpiderBase
from app.plugins.extendspider.utils.url import get_dn, pass_cloudflare
from playwright.sync_api import sync_playwright, Page
from app.schemas import SearchContext
from utils.common import retry


class Dytt8899Spider(_ExtendSpiderBase):
    #  网站搜索接口Cookie
    spider_cookie = ""

    def __init__(self, config: dict = None):
        super(Dytt8899Spider, self).__init__(config)

    def init_spider(self, config: dict = None):
        self.spider_url = "https://www.dytt8899.com"
        self.spider_search_url = f"{self.spider_url}/e/search/index.php"
        self.spider_cookie = ""
        self.spider_headers = {
            "User-Agent": settings.USER_AGENT,
        }

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
                    page.goto(self.spider_search_url)
                    page.fill("div.searchl input[name='keyboard']", keyword)
                    page.click("div.searchr input[name='Submit'][value='立即搜索']")
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
            ul_div = soup.find("div", class_="co_content8")
            # 判断是否有搜索结果
            if not ul_div:
                return []
            #  获取标题
            tables = ul_div.select("ul  table")
            if not tables:
                return []
            detail_tag = tables[0]
            detail_url = detail_tag.find('a').get('href')[1:]
            if not detail_url.startswith("http"):
                detail_url = f"{self.spider_url}/{detail_url}"
            if not detail_url:
                return []
            # 获取种子信息
            try:
                self._wait()
                logger.info(f"{self.spider_name}-开始获取 {detail_url} 详情页的种子信息")
                torrents = self._get_torrent_info(page, detail_url, ctx)
                logger.info(f"{self.spider_name}-成功获取详情页 {detail_url} 的种子信息: {len(torrents)} 个")
                return torrents
            except Exception as ex:
                logger.error(f"{self.spider_name}-详情抓取失败: {detail_url}: {str(ex)}")
                return []
        except Exception as e:
            logger.error(f"{self.spider_name}-解析搜索结果失败: {str(e)}")
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
            downlist_div = soup.find("div", id="downlist")
            if not downlist_div:
                return []

            results = []
            tds = downlist_div.find_all("td", style=lambda value: value and "WORD-WRAP: break-word" in value)
            for td in tds:
                a_tags = td.find_all("a", href=lambda href: href and href.startswith("magnet:"))
                if not a_tags:
                    continue
                for a_tag in a_tags:
                    link = a_tag['href']
                    if not link or link.startswith("thunder://"):
                        continue
                    title = a_tag.text.strip()
                    # 判断是否是磁力链接
                    if link.startswith('magnet:?'):
                        enclosure = link
                        title = get_dn(link)
                        logger.debug(f"{self.spider_name}-找到磁力链接: {enclosure}")
                    else:
                        # 处理普通下载链接
                        if link.startswith('http'):
                            enclosure = link
                        else:
                            enclosure = f"{self.spider_url}/{link}"
                        logger.debug(f"{self.spider_name}-找到下载链接: {enclosure}")

                    title_info = SearchFilterHelper().parse_title(title)
                    if not title_info.episode:
                        title_info.episode = SearchFilterHelper().get_episode(title)
                    results.append({
                        "title": title,
                        "enclosure": enclosure,
                        "description": title,
                        "page_url": detail_url,
                        "size": title_info.sie_num
                    })
                    logger.info(f"{self.spider_name}-找到种子: {title}")

            if not results:
                logger.warn(f"{self.spider_name}-没有找到种子")
            # 过滤信息
            # self.get_link_size(results)
            return results

        except Exception as e:
            logger.error(f"获取种子信息失败: {str(e)}")
            return []


if __name__ == "__main__":
    lou = Dytt8899Spider({
        'spider_proxy': False,
        'spider_enable': True,
        'spider_name': 'Dytt8899Spider',
        'proxy_type': 'playwright',
        'proxy_config': {
            'flaresolverr_url': 'http://192.168.68.116:8191'
        },
        'request_interval': (2, 5)  # 设置随机请求间隔，最小2秒，最大5秒
    })
    # 使用直接请求
    rest = lou.search("斗罗大陆2", 1)
    print(rest)
