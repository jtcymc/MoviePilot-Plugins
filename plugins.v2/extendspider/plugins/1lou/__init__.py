import traceback
from typing import Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from DrissionPage._base.chromium import Chromium
from DrissionPage._pages.chromium_page import ChromiumPage
from bs4 import BeautifulSoup
from app.log import logger
from plugins.extendspider.plugins.base import _ExtendSpiderBase
from plugins.extendspider.utils.pass_verify import pass_turnstile_verification
from plugins.extendspider.utils.url import xn_url_encode
from plugins.extendspider.utils.browser import create_drission_chromium
from app.schemas import SearchContext
import threading

from app.helper.search_filter import SearchFilterHelper
from app.utils.common import retry


class Bt1louSpider(_ExtendSpiderBase):

    def __init__(self, config: dict = None):
        super(Bt1louSpider, self).__init__(config)
        self._result_lock = threading.Lock()
        # 初始化线程锁
        self._torrent_lock = threading.Lock()
        self.spider_max_load_page = 2

    def init_spider(self, config: dict = None):
        self.spider_url = self.spider_url or "https://www.1lou.me"
        self.spider_search_url = f"{self.spider_url}/search-$key$-$page$.htm"

    def _get_page(self, page: int) -> str:
        if page <= self.spider_page_start:
            page = self.spider_page_start
        return f"1-{page}"

    def get_search_url(self, keyword: str, page: int) -> str:
        if not keyword:
            return ""
        return self.spider_search_url.replace("$key$", xn_url_encode(keyword)).replace("$page$",
                                                                                       self._get_page(page))

    def _do_search(self, keyword: str, page: int, ctx: SearchContext):
        if not keyword:
            logger.warning(f"{self.spider_name}-搜索关键词为空")
            return []
        results = []
        if self.pass_cloud_flare:
            logger.info(f"{self.spider_name}-使用flaresolver代理...")
            self._from_pass_cloud_flare(self.spider_url)
        headless = True
        browser, display = create_drission_chromium(headless=headless, ua=self.spider_ua)
        if self.spider_cookie:
            browser.set.cookies(self.spider_cookie)
        try:
            # 访问主页并处理 Cloudflare
            logger.info(f"{self.spider_name}-正在访问 {self.spider_url}...")
            # 等待页面加载完成
            browser.set.load_mode.eager()  # 设置加载模式为none
            browser.get(self.spider_url)
            logger.info(f"{self.spider_name}-访问主页成功,开始搜索【{keyword}】...")
            if not pass_turnstile_verification(browser, headless):
                logger.warn(f"{self.spider_name}-未通过 Cloudflare 验证")
            self._wait_inner()
            # 如果起始页大于1，只抓取指定页
            if page > self.spider_page_start:
                logger.info(
                    f"{self.spider_name}-指定页码 {page} 大于起始页 {self.spider_page_start}，只抓取指定页")
                results.extend(self._parse_search_result_page(keyword, browser, True, ctx))
                return results

            # 执行搜索
            search_url = self.get_search_url(keyword, 1)
            browser.get(search_url)
            results = self._parse_search_result_page(keyword, browser, False, ctx)
            logger.info(f"{self.spider_name}-搜索完成，共找到 {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f"搜索过程发生错误: {str(e)}, {traceback.format_exc()}")
            return []
        finally:
            browser.quit()
            if display:
                display.stop()

    @staticmethod
    def _parse_total_pages(html_content: str) -> int:
        """解析总页数"""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            pagination = soup.find("ul", class_="pagination")
            if not pagination:
                return 1

            # 获取所有页码链接
            page_items = pagination.find_all("li", class_="page-item")
            if not page_items or len(page_items) < 2:
                return 1

            # 获取最后一个li的文本（排除▶按钮）
            last_item = page_items[-1]
            last_text = last_item.find("a", class_="page-link").text.strip()

            # 如果最后一个不是▶，说明只有一页
            if last_text != "▶":
                return 1

            # 获取倒数第二个li的文本
            second_last_item = page_items[-2]
            second_last_text = second_last_item.find("a", class_="page-link").text.strip()

            # 如果倒数第二个是...XX格式，说明页数大于10
            if second_last_text.startswith("..."):
                try:
                    # 提取...后面的数字
                    max_page = int(second_last_text[3:])
                    logger.info(f"解析到总页数(>10): {max_page}")
                    return max_page
                except (ValueError, TypeError):
                    pass

            # 否则页数小于等于10，使用倒数第二个数字作为总页数
            try:
                max_page = int(second_last_text)
                logger.info(f"解析到总页数(≤10): {max_page}")
                return max_page
            except (ValueError, TypeError):
                logger.error("无法解析页码")
                return 1

        except Exception as e:
            logger.error(f"解析总页数失败: {str(e)}")
            return 1

    def _parse_search_result_page(self, keyword, browser: ChromiumPage, one_page: bool, ctx: SearchContext):
        """ 统计搜索结果页数信息 """
        _processed_titles = set()
        _processed_urls = set()
        detail_urls = {}
        # 抓取第一页
        self._parse_search_page_detail_urls(browser.html, _processed_titles,
                                            _processed_urls, detail_urls)

        if not one_page:
            # 解析总页数
            total_pages = self._parse_total_pages(browser.html)
            # 计算需要抓取的页数
            pages_to_fetch = min(total_pages or 1, self.spider_max_load_page)
            logger.info(f"{self.spider_name}-总页数: {total_pages or 1}, 将抓取前 {pages_to_fetch} 页")

            if pages_to_fetch >= 2:
                # 抓取后续页面
                for current_page in range(2, pages_to_fetch + 1):
                    try:
                        self._wait_inner(0.5, 1.9)
                        search_url = self.get_search_url(keyword, current_page)
                        logger.info(f"{self.spider_name}-正在抓取第 {current_page} 页: {search_url}")
                        browser.get(search_url)
                        self._parse_search_page_detail_urls(browser.html, _processed_titles,
                                                            _processed_urls, detail_urls)
                    except Exception as e:
                        logger.error(f"{self.spider_name}-抓取第 {current_page} 页时发生错误: {str(e)}")
            logger.info(f"{self.spider_name}-共抓取 {pages_to_fetch} 页数据，找到详情页 {len(detail_urls)} 个结果")
        if not detail_urls:
            logger.info(f"{self.spider_name}-没有找到详情页，可能没有搜索到结果")
            return []
        to_filter_titles = [title for title in detail_urls.keys()]
        filter_titles = self.search_helper.do_filter(self.spider_name, keyword, to_filter_titles, ctx)
        if not filter_titles:
            logger.info(f"{self.spider_name}-没有找到符合要求的结果")
            return []
        detail_urls_tp = {detail_urls[title] for title in filter_titles}
        results = self._parse_detail_results(browser, detail_urls_tp)
        logger.info(f"{self.spider_name}-搜索完成，共找到 {len(results)} 个结果")
        return results

    @retry(Exception, 2, 3, 2, logger=logger)
    def _parse_search_page_detail_urls(self, html_content: str, _processed_titles, _processed_urls, detail_urls: dict):
        """搜索结果解析，主要收集详情页信息"""
        if not html_content:
            return _processed_titles, detail_urls
        # 获取页面内容
        soup = BeautifulSoup(html_content, "html.parser")
        for result in soup.find_all("li", class_="media thread tap"):
            # 不是磁力或者种子的链接
            if not result.find("div", class_="subject break-all").find("i", class_="icon small filetype other"):
                continue
            title_link = result.find("div", class_="subject break-all").find("a")
            if not title_link or not title_link.get('href'):
                continue
            # 处理标题中的 text-danger 标签
            title = ''.join(
                c.text if getattr(c, 'name', None) == "span" and "text-danger" in c.get("class", []) else str(c)
                for c in title_link.contents
            ).strip()
            detail_url = title_link['href']
            if not detail_url.startswith("http"):
                detail_url = f"{self.spider_url}/{detail_url}"
            if title in _processed_titles or detail_url in _processed_urls:
                continue
            # 添加到待处理列表
            _processed_titles.add(title)
            _processed_urls.add(detail_url)
            detail_urls[title] = detail_url
        return _processed_titles, detail_urls

    def _parse_detail_results(self, browser: ChromiumPage, detail_urls: set) -> list:
        """ 处理详情页 """
        results = []
        _processed_torrent_titles = set()

        # 将URL列表分成多个批次
        def chunk_list(lst, chunk_size):
            return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

        def process_url_batch(url_batch, index):
            new_tab = browser.new_tab()
            new_tab.set.load_mode.eager()
            current_batch_results = []
            try:
                for url_idx, detail_url in enumerate(url_batch):
                    self._wait_inner(1.5, 6.9)
                    logger.info(
                        f"{self.spider_name}-线程 {index} 正在处理第 {url_idx + 1}/{len(url_batch)} 个详情页: {detail_url}")
                    new_tab.get(detail_url)
                    state, torrent_list = self._get_torrent_info(new_tab.html, _processed_torrent_titles)
                    if state:
                        current_batch_results.extend(torrent_list)
                        logger.info(
                            f"{self.spider_name}-线程 {index} 成功获取第 {url_idx + 1}/{len(url_batch)} 个详情页的种子信息: {len(torrent_list)} 个")
                return current_batch_results
            except Exception as ex:
                logger.error(f"{self.spider_name}-线程 {index} 处理批次失败: {str(ex)}")
            return []

        # 计算每个线程处理的URL数量
        batch_size = max(1, len(detail_urls) // self.spider_batch_size)  # 确保每个批次至少有一个URL
        url_batches = chunk_list(list(detail_urls), batch_size)

        logger.info(f"{self.spider_name}-将 {len(detail_urls)} 个详情页分成 {len(url_batches)} 个批次处理")

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
                    with self._result_lock:
                        results.extend(batch_results)
                        logger.info(
                            f"{self.spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理完成，获取到 {len(batch_results)} 个种子")
                except Exception as e:
                    logger.error(f"{self.spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理失败: {str(e)}")

        logger.info(f"{self.spider_name}-所有批次处理完成，共获取到 {len(results)} 个种子")
        return results

    @retry(Exception, 2, 2, 2, logger=logger)
    def _get_torrent_info(self, html_content: str, _processed_torrent_titles: set) -> Tuple[
        bool, list]:
        """同步版本的线程安全的获取种子信息"""
        results = []
        soup = BeautifulSoup(html_content, "html.parser")
        fieldset = soup.find("fieldset", class_="fieldset")
        if not fieldset:
            return True, []

        for li in fieldset.find_all("li"):
            if not li.find("i", class_="icon filetype torrent"):
                continue
            title = li.find("a").text.strip()
            # 使用线程锁保护共享资源的访问
            with self._torrent_lock:
                if title in _processed_torrent_titles:
                    logger.info(f"{self.spider_name}-跳过已处理种子：{title}")
                    continue
                _processed_torrent_titles.add(title)

            href = li.find("a")['href']
            # 判断是否是磁力链接
            if href.startswith('magnet:?'):
                enclosure = href
                logger.debug(f"{self.spider_name}-找到磁力链接: {enclosure}")
            else:
                # 处理普通下载链接
                if href.startswith('http'):
                    enclosure = href
                else:
                    enclosure = f"{self.spider_url}/{href}"
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
        return True, results


if __name__ == "__main__":
    lou = Bt1louSpider({
        'spider_name': 'Bt1louSpider',
        'proxy_type': 'playwright',
        'pass_cloud_flare': True,
        'spider_enable': True,
        'proxy_config': {
            'flaresolverr_url': 'http://192.168.68.115:8191'
        },
        'request_interval': (2, 5)  # 设置随机请求间隔，最小2秒，最大5秒
    })
    # 使用直接请求
    lou.search("遮天", 1)
