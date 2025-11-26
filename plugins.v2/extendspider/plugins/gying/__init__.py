import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from DrissionPage._pages.chromium_page import ChromiumPage
from DrissionPage._pages.chromium_tab import ChromiumTab
from DrissionPage.common import By
from app.log import logger
from helper.search_filter import SearchFilterHelper
from app.plugins.extendspider.plugins.base import _ExtendSpiderBase
from app.schemas import SearchContext
from app.utils.common import retry


class GyingKSpider(_ExtendSpiderBase):

    def __init__(self, config: dict = None):
        super(GyingKSpider, self).__init__(config)
        self._result_lock = None
        self._result_lock = threading.Lock()
        self.spider_search_url = f"{self.spider_url}/s/2-0--$page$/$key$"
        self.spider_username = config.get("spider_username")
        self.spider_password = config.get("spider_password")

    def init_spider(self, config: dict = None):
        self.spider_url = self.spider_url or "https://www.gying.org"

    def get_search_url(self, keyword: str, page: int) -> str:
        if not keyword:
            return ""
        return self.spider_search_url.replace("$key$", keyword).replace("$page$", str(page))

    def _do_search(self, keyword: str, page: int, ctx: SearchContext):
        results = []
        if not keyword:
            logger.warning(f"{self.spider_name}-搜索关键词为空")
            return results
        if not self.browser:
            logger.warn(f"{self.spider_name}-未初始化浏览器")
            return []
        if self.pass_cloud_flare:
            logger.info(f"{self.spider_name}-使用flaresolver代理...")
            self._from_pass_cloud_flare(self.spider_url)
        tab = self.browser.new_tab(self.spider_url)
        if not self.spider_cookie and not self.to_login(tab):
            return results
        try:
            # 访问主页并处理 Cloudflare
            logger.info(f"{self.spider_name}-正在访问 {self.spider_url}...")
            # 等待页面加载完成
            tab.set.load_mode.eager()  # 设置加载模式为none
            self._wait_inner(0.5, 1.2)
            tab.get(self.get_search_url(keyword, page))
            if "游客无权访问此页面，请登录！" in tab.html and not self.to_login(tab):
                return results
            logger.info(f"{self.spider_name}-访问主页成功,开始搜索【{keyword}】...")
            return self._parse_search_result(tab, ctx)
        except Exception as e:
            logger.error(f"{self.spider_name}-搜索失败: {str(e)} - {traceback.format_exc()}")
            return results
        finally:
            tab.close()

    def to_login(self, browser: ChromiumPage | ChromiumTab):
        logger.info(f"{self.spider_name}-开始登录...")

        browser.get(f"{self.spider_url}/user/login/", timeout=20)
        if not browser.wait.ele_displayed("css:input[name='username']", timeout=20):
            logger.warn(f"{self.spider_name}-登录失败")
            return False
        browser.ele("css:input[name='username']").input(self.spider_username)
        browser.wait(0.5, 1.2)
        popup_btn = browser.ele("css:.popup-content .popup-footer button")
        if popup_btn:
            popup_btn.click()
        browser.wait(0.5, 0.9)
        browser.ele("css:input[name='password']").input(f"{self.spider_password}\n")
        browser.wait(0.5, 0.9)
        browser.ele("css:button[type='submit']").click()
        if not browser.wait.ele_displayed("最近更新的电影", timeout=20):
            logger.warn(f"{self.spider_name}-登录失败")
            return False
        self.spider_cookie = browser.cookies()
        if self.spider_cookie:
            logger.info(f"{self.spider_name}-登录成功")
            browser.set.cookies(self.spider_cookie)
        return True

    def _parse_search_result(self, browser: ChromiumTab, ctx: SearchContext):
        if not browser.wait.ele_displayed("css=.search_head", timeout=20):
            logger.warn(f"{self.spider_name}-没有搜索结果")
            return []
        sr_ele = browser.ele("css:.sr_lists", timeout=20)
        if not sr_ele:
            logger.warn(f"{self.spider_name}-没有搜索结果")
            return []
        a_tags = sr_ele.eles("t:a")
        if not a_tags:
            logger.warn(f"{self.spider_name}-没有搜索结果")
            return []
        detail_urls = set()
        for link in a_tags.get.links():
            if not link.startswith("http"):
                link = f"{self.spider_url}{link}"
            detail_urls.add(link)
        results = []
        if detail_urls:

            logger.info(f"{self.spider_name}-解析到{len(detail_urls)}个搜索结果，开始获取链接地址...")
            urls = []
            if 0 < self.spider_max_load_result < len(detail_urls):
                urls = list(detail_urls)[:self.spider_max_load_result]
                logger.info(f"{self.spider_name}-已过滤，仅获取前 {self.spider_max_load_result} 个种子")
            else:
                urls = list(detail_urls)
            # 计算每个线程处理的URL数量
            batch_size = max(1, len(urls) // self.spider_batch_size)  # 确保每个批次至少有一个URL
            url_batches = self.chunk_list(urls, batch_size)

            logger.info(f"{self.spider_name}-将 {len(urls)} 个详情页分成 {len(url_batches)} 个批次处理")
            # 使用线程池并发处理批次
            with ThreadPoolExecutor(max_workers=min(2, len(url_batches))) as tp:
                future_to_batch = {
                    tp.submit(self._get_torrent, batch): (idx, batch)
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
                        return []
        logger.info(f"{self.spider_name}-所有批次处理完成，共获取到 {len(results)} 个种子")
        return results

    # @retry(Exception, 2, 3, 2, logger=logger)
    def _get_torrent(self, down_urls: list) -> Optional[list]:
        self._wait_inner(0.5, 1.2)
        new_tab = None
        results = []
        try:
            for down_url in down_urls:
                self._wait_inner(5, 15)
                try:
                    if not new_tab:
                        new_tab = self.browser.new_tab(down_url)
                        new_tab.set.load_mode.none()  # 设置加载模式为none
                    else:
                        new_tab.get(down_url)
                    if not new_tab.wait.ele_displayed("css:.down-link", timeout=40):
                        new_tab.stop_loading()
                        continue
                    new_tab.stop_loading()
                    tr_tags = new_tab.eles("css:.bit_list tbody tr")
                    if not tr_tags:
                        return []
                    url_set = set()
                    to_down_urls = set()
                    for tr_tag in tr_tags:
                        if not tr_tag:
                            continue
                        # 获取大小信息 - 从第三个td中获取
                        size_td = tr_tag.s_ele("xpath:./td[3]")
                        size_str = size_td.text.strip() if size_td else ""

                        # 获取做种信息 - 从第四个td中的i标签获取
                        seeders_td = tr_tag.s_ele("xpath:./td[4]//i")
                        seeders_text = seeders_td.attr("title") if seeders_td else ""
                        seeders_num = 0
                        # 解析做种数量
                        if seeders_text and "做种" in seeders_text:
                            try:
                                seeders_num = int(seeders_text.replace("做种", "").strip())
                            except:
                                seeders_num = 0
                        elif seeders_td and seeders_td.text and seeders_td.text != "--":
                            try:
                                seeders_num = int(seeders_td.text.strip())
                            except:
                                seeders_num = 0
                        # 获取标题和链接 - 从第一个td中的a.torrent或a.folder获取
                        title_a = tr_tag.s_ele("css:a.torrent, a.folder")
                        if not title_a:
                            continue
                        title = title_a.attr("title") or title_a.text

                        # 获取下载列中的磁力链接
                        download_td = tr_tag.s_ele("xpath:./td[2]")
                        magnet_a = download_td.s_ele("xpath:.//a[contains(@href, 'magnet:')]") if download_td else None
                        magnet_link = magnet_a.link if magnet_a else ""
                        # 获取详情链接 - 从第一个td中的"详情"链接获取
                        detail_a = tr_tag.s_ele("xpath:.//a[text()='详情']")
                        detail_link = detail_a.link if detail_a else ""

                        if magnet_link and magnet_link.startswith("magnet") and magnet_link not in url_set:
                            # 是磁力链接
                            title_info = SearchFilterHelper().parse_title(title)
                            if not title_info.size_num:
                                title_info.size = size_str

                            results.append({
                                "title": title,
                                "enclosure": magnet_link,
                                "description": title,
                                "size": title_info.size_num,
                                "seeders": seeders_num,
                            })
                        else:
                            # 没有磁力链接，将详情链接加入到to_down_urls
                            if detail_link and detail_link not in to_down_urls:
                                if not detail_link.startswith("http"):
                                    detail_link = f"{self.spider_url}{detail_link}"
                                to_down_urls.add(detail_link)

                    if not to_down_urls:
                        return results

                    if 0 < self.spider_max_load_result < len(to_down_urls):
                        logger.info(
                            f"{self.spider_name}-结果数量超过最大限制，将只处理前 {self.spider_max_load_result} 个结果")
                        to_down_urls = list(to_down_urls)[:self.spider_max_load_result]
                    # 计算每个线程处理的URL数量
                    batch_size = max(1, len(to_down_urls) // self.spider_batch_size)  # 确保每个批次至少有一个URL
                    url_batches = self.chunk_list(list(to_down_urls), batch_size)

                    logger.info(
                        f"{self.spider_name}-将 {len(to_down_urls)} 个种子详情页分成 {len(url_batches)} 个批次处理")
                    # 使用线程池并发处理批次
                    with ThreadPoolExecutor(max_workers=min(2, len(url_batches))) as tp:
                        future_to_batch = {
                            tp.submit(self.get_enclosure_by_down, batch): (idx, batch)
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
                                logger.error(
                                    f"{self.spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理失败: {str(e)}")
                except Exception as e:
                    logger.error(
                        f"{self.spider_name}-详情页:【{down_url}】,获取种子失败: {str(e)} - {traceback.format_exc()}")
            return results
        finally:
            if new_tab:
                new_tab.close()

    def get_enclosure_by_down(self, down_urls: list) -> list:
        new_tab = None
        results = []
        url_set = set()
        try:
            for down_url in down_urls:
                self._wait_inner(5, 15)
                logger.info(f"{self.spider_name}-正在获取种子信息: {down_url}")
                if not new_tab:
                    new_tab = self.browser.new_tab(down_url)
                    new_tab.set.load_mode.none()  # 设置加载模式为none
                else:
                    new_tab.get(down_url)
                new_tab.wait.ele_displayed("css:.down321", timeout=20)
                for li_tag in new_tab("css:ul.down321").eles("tag:li"):
                    # 提取标题：第一个 div
                    title_div = li_tag.s_ele("tag:div")
                    if not title_div:
                        continue
                    title = title_div.text.strip()

                    # 提取大小：class="left" 的 div
                    size_div = li_tag.s_ele("css:div.left")
                    size_str = size_div.text.strip() if size_div else ""

                    # 提取磁力链接：第一个 <a> 标签（磁力下载）
                    magnet_link_tag = li_tag.s_ele("css:a[href^='magnet:']")
                    if not magnet_link_tag:
                        continue
                    link = magnet_link_tag.attr("href").strip()

                    if link.startswith("magnet:") and link not in url_set:
                        title_info = SearchFilterHelper().parse_title(title)
                        if not title_info.size_num:
                            title_info.size = size_str

                        results.append({
                            "title": title,
                            "enclosure": link,
                            "description": title,
                            "size": title_info.size_num
                        })
                        url_set.add(link)
                new_tab.wait(1, 2)
            return results
        finally:
            if new_tab:
                new_tab.close()


if __name__ == "__main__":
    lou = GyingKSpider({
        'spider_proxy': False,
        'spider_enable': True,
        'pass_cloud_flare': False,
        'spider_name': 'GyingKSpider',
        'proxy_type': 'playwright',
        'proxy_config': {
            'flaresolverr_url': 'http://192.168.68.116:8191'
        },
        'request_interval': (1.5, 1.9),  # 设置随机请求间隔，最小2秒，最大5秒,
        'use_drission_browser': True,
        'spider_headless': False
    })
    # 使用直接请求
    rest = lou.search("神印王座", 1)
    print(rest)
