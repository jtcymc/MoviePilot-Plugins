import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from DrissionPage import Chromium
from app.log import logger
from helper.search_filter import SearchFilterHelper
from plugins.extendspider.plugins.base import _ExtendSpiderBase
from app.schemas import SearchContext
from app.utils.common import retry
from app.plugins.extendspider.utils.browser import create_drission_chromium


class GyingKSpider(_ExtendSpiderBase):

    def __init__(self, config: dict = None):
        super(GyingKSpider, self).__init__(config)
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

        if self.pass_cloud_flare:
            logger.info(f"{self.spider_name}-使用flaresolver代理...")
            self._from_pass_cloud_flare(self.spider_url)
        browser = create_drission_chromium(headless=True, ua=self.spider_ua)
        if not self.spider_cookie:
            self.to_login(browser)
        if self.spider_cookie:
            browser.set.cookies(self.spider_cookie)
        tab1 = browser.latest_tab
        try:
            self._wait(0.5, 1)
            # 访问主页并处理 Cloudflare
            logger.info(f"{self.spider_name}-正在访问 {self.spider_url}...")
            # 等待页面加载完成
            tab1.set.load_mode.eager()  # 设置加载模式为none
            tab1.get(self.spider_url)
            logger.info(f"{self.spider_name}-访问主页成功,开始搜索【{keyword}】...")
            tab1.wait(0.5, 1.2)
            tab1.get(self.get_search_url(keyword, page))
            if "游客无权访问此页面，请登录！" in tab1.html:
                self.to_login(browser)
            return self._parse_search_result(browser, ctx)
        except Exception as e:
            logger.error(f"{self.spider_name}-搜索失败: {str(e)} - {traceback.format_exc()}")
            return results
        finally:
            tab1.close()
            browser.quit()

    def to_login(self, browser: Chromium):
        logger.info(f"{self.spider_name}-开始登录...")
        tab = browser.latest_tab
        tab.get(f"{self.spider_url}/user/login/", timeout=20)
        tab.ele("css:input[name='username']").input(self.spider_username)
        tab.ele("css:input[name='password']").input(self.spider_password)
        tab.ele("css:button[type='submit']").click()
        tab.wait.ele_displayed("最近更新的电影", timeout=20)
        self.spider_cookie = tab.cookies()
        if self.spider_cookie:
            browser.set.cookies(self.spider_cookie)

    def _parse_search_result(self, browser: Chromium, ctx: SearchContext):
        tab = browser.latest_tab

        tab.wait.ele_displayed("css=.search_head", timeout=20)
        a_tags = tab("css:.sr_lists").eles("t:a")
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
            # 计算每个线程处理的URL数量
            batch_size = max(1, len(detail_urls) // self.spider_batch_size)  # 确保每个批次至少有一个URL
            url_batches = self.chunk_list(list(detail_urls), batch_size)

            logger.info(f"{self.spider_name}-将 {len(detail_urls)} 个详情页分成 {len(url_batches)} 个批次处理")
            # 使用线程池并发处理批次
            with ThreadPoolExecutor(max_workers=min(6, len(url_batches))) as tp:
                future_to_batch = {
                    tp.submit(self._get_torrent, browser, batch, idx + 1): (idx, batch)
                    for idx, batch in enumerate(detail_urls)
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

    @retry(Exception, 2, 3, 2, logger=logger)
    def _get_torrent(self, browser: Chromium, down_url: str, index: int) -> Optional[list]:
        # self._wait(0.5,1.5)
        new_tab = browser.new_tab()
        try:
            new_tab.set.load_mode.eager()  # 设置加载模式为none
            new_tab.get(down_url, timeout=20)
            p_tags = new_tab("css:div .down-list").s_eles("tag:p")
            if not p_tags:
                return []
            url_set = set()
            results = []
            to_down_urls = set()
            for p_tag in p_tags:
                a_tag = p_tag.s_ele("tag:a")
                if not a_tag:
                    continue
                size_str = p_tag.s_ele("css:.size").text
                link = a_tag.link
                if link.startswith("magnet") and link not in url_set:
                    # 是磁力直接
                    title_info = SearchFilterHelper().parse_title(a_tag.text)
                    if not title_info.size_num:
                        title_info.size = size_str
                    results.append({
                        "title": a_tag.attr("title") or a_tag.text,
                        "enclosure": link,
                        "description": a_tag.attr("title") or a_tag.text,
                        "size": title_info.size_num
                    })
                    url_set.add(link)
                elif not link.startswith("magnet") and link not in to_down_urls:
                    if not link.startswith("http"):
                        link = f"{self.spider_url}{link}"
                    to_down_urls.add(link)

            if not to_down_urls:
                return results

            # 计算每个线程处理的URL数量
            batch_size = max(1, len(to_down_urls) // self.spider_batch_size)  # 确保每个批次至少有一个URL
            url_batches = self.chunk_list(list(to_down_urls), batch_size)

            logger.info(f"{self.spider_name}-将 {len(to_down_urls)} 个种子下载页分成 {len(url_batches)} 个批次处理")
            # 使用线程池并发处理批次
            with ThreadPoolExecutor(max_workers=min(6, len(url_batches))) as tp:
                future_to_batch = {
                    tp.submit(self.get_enclosure_by_down, browser, batch): (idx, batch)
                    for idx, batch in enumerate(to_down_urls)
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

            return results
        except Exception as e:
            logger.error(f"{self.spider_name}-详情页:【{down_url}】,获取种子失败: {str(e)} - {traceback.format_exc()}")
            return []
        finally:
            new_tab.close()

    def get_enclosure_by_down(self, browser: Chromium, down_urls: str) -> list:

        new_tab = browser.new_tab()
        results = []
        url_set = set()

        try:
            for down_url in down_urls:
                if down_url in url_set:
                    continue
                logger.info(f"{self.spider_name}-正在获取种子信息: {down_url}")
                new_tab.set.load_mode.eager()
                new_tab.get(down_url, timeout=20)
                new_tab.wait.ele_displayed("css:.down321", timeout=20)
                for li_tag in new_tab("css:ul.down321").eles("tag:li"):
                    title = li_tag.s_ele("@tag()=div").text
                    url_tag = li_tag.s_ele("css:span#d2")
                    size_str = li_tag.s_ele("css:div.left").text
                    if not url_tag:
                        continue
                    link = url_tag.attr("data-clipboard-text")
                    if link.startswith("magnet") and link not in url_set:
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
                new_tab.wait(0.5, 1.5)

        finally:
            new_tab.close()
        return results


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
        'request_interval': (1.5, 1.9)  # 设置随机请求间隔，最小2秒，最大5秒
    })
    # 使用直接请求
    rest = lou.search("藏海传", 1)
    print(rest)
