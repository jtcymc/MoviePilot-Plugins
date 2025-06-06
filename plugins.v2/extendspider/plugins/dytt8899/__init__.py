from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from bs4 import BeautifulSoup
from app.log import logger
from app.helper.search_filter import SearchFilterHelper
from app.plugins.extendspider.plugins.base import _ExtendSpiderBase
from app.plugins.extendspider.utils.url import get_dn, pass_cloudflare
from app.plugins.extendspider.utils.browser import create_browser, create_stealth_page
from playwright.sync_api import Page
from app.schemas import SearchContext
from app.utils.common import retry


class Dytt8899Spider(_ExtendSpiderBase):

    def __init__(self, config: dict = None):
        super(Dytt8899Spider, self).__init__(config)
        self._result_lock = threading.Lock()
        

    def init_spider(self, config: dict = None):
        self.spider_url = "https://www.dytt8899.com"
        self.spider_search_url = f"{self.spider_url}/e/search/index.php"

    def _do_search(self, keyword: str, page: int, ctx: SearchContext):
        try:
            browser, context = create_browser(self.spider_proxy)
            page = create_stealth_page(context)

            try:
                # 访问主页并处理 Cloudflare
                logger.info(f"{self.spider_name}-正在访问 {self.spider_url}...")
                if not pass_cloudflare(self.spider_url, page):
                    logger.warn("cloudflare challenge fail！")
                    return []

                # 等待页面加载完成
                page.wait_for_load_state("domcontentloaded", timeout=30 * 1000)
                logger.info(f"{self.spider_name}-访问主页成功,开始搜索【{keyword}】...")
                self._wait()
                self.spider_cookie = context.cookies()

                # 执行搜索
                page.goto(self.spider_search_url)
                page.fill("div.searchl input[name='keyboard']", keyword)
                page.click("div.searchr input[name='Submit'][value='立即搜索']")
                page.wait_for_load_state("domcontentloaded", timeout=30 * 1000)

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
            ul_div = soup.find("div", class_="co_content8")
            # 判断是否有搜索结果
            if not ul_div:
                return []
            #  获取标题
            tables = ul_div.select("ul  table")
            if not tables:
                return []
            
            detail_urls = set()
            for table in tables:
                detail_tag = table.find('a')
                if not detail_tag:
                    continue
                detail_url = detail_tag.get('href', '')
                if not detail_url:
                    continue
                if detail_url.startswith('/'):
                    detail_url = detail_url[1:]
                if not detail_url.startswith("http"):
                    detail_url = f"{self.spider_url}/{detail_url}"
                detail_urls.add(detail_url)
            
            if not detail_urls:
                return []
            
            # 获取种子信息
            logger.info(f"{self.spider_name}-开始获取 {len(detail_urls)} 个详情页的种子信息")
            return self._parse_detail_results(detail_urls)

        except Exception as e:
            logger.error(f"{self.spider_name}-解析搜索结果失败: {str(e)}")
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
                browser, context = create_browser(self.spider_proxy)
                if self.spider_cookie:
                    context.add_cookies(self.spider_cookie)
                detail_page = create_stealth_page(context)

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
        self._wait()
        # 访问详情页
        page.goto(detail_url)
        page.wait_for_load_state("domcontentloaded", timeout=30 * 1000)
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
                    # "page_url": detail_url, # 会下载字幕
                    "size": title_info.size_num
                })
                logger.info(f"{self.spider_name}-找到种子: {title}")

        if not results:
            logger.warn(f"{self.spider_name}-没有找到种子")
        return results


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
