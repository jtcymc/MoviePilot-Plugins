import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from DrissionPage._pages.chromium_page import ChromiumPage
from DrissionPage._pages.chromium_tab import ChromiumTab

from app.log import logger
from helper.search_filter import SearchFilterHelper
from app.plugins.extendspider.plugins.base import _ExtendSpiderBase
from app.schemas import SearchContext
from app.utils.common import retry
from app.plugins.extendspider.utils.browser import create_drission_chromium


class CiLiXiongSpider(_ExtendSpiderBase):

    def __init__(self, config: dict = None):
        super(CiLiXiongSpider, self).__init__(config)
        self._result_lock = threading.Lock()

    def init_spider(self, config: dict = None):
        self.spider_url = self.spider_url or "https://www.cilixiong.cc"

    def _do_search(self, keyword: str, page: int, ctx: SearchContext):
        results = []
        if not keyword:
            logger.warning(f"{self.spider_name}-搜索关键词为空")
            return results
        if not self.browser:
            logger.warn(f"{self.spider_name}-未初始化浏览器")
            return results
        if self.pass_cloud_flare:
            logger.info(f"{self.spider_name}-使用flaresolver代理...")
            self._from_pass_cloud_flare(self.spider_url)
        tab = self.browser.new_tab()
        try:
            self._wait(0.5, 1)
            # 访问主页并处理 Cloudflare
            logger.info(f"{self.spider_name}-正在访问 {self.spider_url}...")
            # 等待页面加载完成
            tab.set.load_mode.eager()  # 设置加载模式为none
            tab.get(self.spider_url)
            logger.info(f"{self.spider_name}-访问主页成功,开始搜索【{keyword}】...")
            search_ele = tab.ele('x://form[@id="searchform"]//input[@name="keyboard"]', timeout=20)
            if not search_ele:
                logger.error(f"{self.spider_name}-未找到搜索框")
                return results
            search_ele.input(f"{keyword}\n")
            return self._parse_search_result(tab, ctx)
        except Exception as e:
            logger.error(f"{self.spider_name}-搜索失败: {str(e)} - {traceback.format_exc()}")
            return results
        finally:
            tab.close()

    def _parse_search_result(self, browser: ChromiumPage | ChromiumTab, ctx: SearchContext):
        if not browser.wait.ele_displayed("条符合搜索条件", timeout=20):
            return []
        a_tags = browser("css=div .align-items-stretch").eles("t:a")
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
        logger.info(f"{self.spider_name}-所有批次处理完成，共获取到 {len(results)} 个种子")
        return results

    # @retry(Exception, 2, 3, 2, logger=logger)
    def _get_torrent(self, down_urls: list) -> Optional[list]:
        # self._wait(0.5,1.5)
        new_tab = self.browser.new_tab()
        new_tab.set.load_mode.eager()  # 设置加载模式为none
        results = []
        try:
            for down_url in down_urls:
                try:
                    new_tab.get(down_url, timeout=20)
                    link_tags = new_tab("css:div .mv_down").eles("tag:a")
                    if not link_tags:
                        return []
                    url_set = set()

                    for a_tag in link_tags:
                        link = a_tag.link
                        if link and link.startswith("magnet") and link not in url_set:
                            title_info = SearchFilterHelper().parse_title(a_tag.text)
                            if not title_info.episode:
                                title_info.episode = SearchFilterHelper().get_episode(a_tag.text)
                            results.append({
                                "title": a_tag.text,
                                "enclosure": link,
                                "description": a_tag.text,
                                "size": title_info.size_num
                            })
                            url_set.add(link)
                except Exception as e:
                    logger.error(
                        f"{self.spider_name}-详情页:【{down_url}】,获取种子失败: {str(e)} - {traceback.format_exc()}")
                    return []
        finally:
            new_tab.close()
        return results


if __name__ == "__main__":
    lou = CiLiXiongSpider({
        'spider_proxy': False,
        'spider_enable': True,
        'pass_cloud_flare': True,
        'spider_name': 'CiLiXiongSpider',
        'proxy_type': 'playwright',
        'proxy_config': {
            'flaresolverr_url': 'http://192.168.68.116:8191'
        },
        'request_interval': (1.5, 1.9),
        'use_drission_browser': True,
        'spider_headless': False
    })
    # 使用直接请求
    rest = lou.search("藏海传", 1)
    print(rest)
