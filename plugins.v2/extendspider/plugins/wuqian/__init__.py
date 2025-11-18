import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from DrissionPage._pages.chromium_page import ChromiumPage
from DrissionPage._pages.chromium_tab import ChromiumTab

from app.log import logger
from helper.search_filter import SearchFilterHelper
from plugins.extendspider.plugins.base import _ExtendSpiderBase
from app.schemas import SearchContext
from app.utils.common import retry
from app.plugins.extendspider.utils.browser import create_drission_chromium
from utils.string import StringUtils


class WuQianSpider(_ExtendSpiderBase):

    def __init__(self, config: dict = None):
        super(WuQianSpider, self).__init__(config)
        self._result_lock = threading.Lock()

    def init_spider(self, config: dict = None):
        self.spider_url = self.spider_url or "https://wuqiangb.top"

    def _do_search(self, keyword: str, page: int, ctx: SearchContext):
        results = []
        if not keyword:
            logger.warning(f"{self.spider_name}-搜索关键词为空")
            return results
        if not self.browser:
            logger.warn(f"{self.spider_name}-未初始化浏览器")
            return results
        tab = self.browser.new_tab(self.spider_url)
        tab.set.load_mode.eager()  # 设置加载模式为none
        if self.pass_cloud_flare:
            # logger.info(f"{self.spider_name}-使用flaresolver代理...")
            # self._from_pass_cloud_flare(self.spider_url)
            if not self.drission_browser.getTurnstileToken(tab):
                logger.warn(f"{self.spider_name}-未通过Cloudflare验证")
                return results
        try:
            self._wait(0.5, 0.6)
            # 访问主页并处理 Cloudflare
            logger.info(f"{self.spider_name}-正在访问 {self.spider_url}...")
            # 等待页面加载完成
            logger.info(f"{self.spider_name}-访问主页成功,开始搜索【{keyword}】...")
            search_ele = tab.ele('x://form[@id="search-form"]//input[@name="keyword"]', timeout=5)
            if not search_ele:
                logger.error(f"{self.spider_name}-未找到搜索框")
                return results
            tab.actions.move_to(search_ele, duration=1)
            search_ele.click()
            self._wait(0.1, 0.2)

            search_ele.input(f"{keyword}\n")
            self._wait(3, 5)
            if not self.drission_browser.getTurnstileToken(tab):
                logger.warn(f"{self.spider_name}- 获取TurnstileToken失败")
                return results
            if not self.drission_browser.getTurnstileToken(tab):
                logger.warn(f"{self.spider_name}-未通过Cloudflare验证")
                return results
            return self._parse_search_result(tab, keyword, ctx)
        except Exception as e:
            logger.error(f"{self.spider_name}-搜索失败: {str(e)} - {traceback.format_exc()}")
            return results
        finally:
            tab.close()

    def _parse_search_result(self, browser: ChromiumPage | ChromiumTab, keyword: str, ctx: SearchContext):
        if not browser.wait.ele_displayed("找到约", timeout=20):
            return []
        # 只要近一周的数据
        a_tag = browser.ele("tag:a@@text():最近一周内")
        a_tag.click()
        self._wait(2, 3)
        if not browser.wait.ele_displayed("找到约", timeout=20):
            return []
        a_tags = browser("css=h3.panel-title.link").eles("t:a")
        if not a_tags:
            logger.warn(f"{self.spider_name}-没有搜索结果")
            return []
        detail_urls = {}
        for a_tag in a_tags:
            link = a_tag.link
            if not link.startswith("http"):
                link = f"{self.spider_url}{link}"
            title = a_tag.text
            if not title:
                continue
            detail_urls[title] = link
        results = []
        if detail_urls:
            urls = []
            # 过滤种子
            if ctx.enable_search_filter:
                to_filter_titles = [name for name in detail_urls.keys()]
                filter_titles = SearchFilterHelper().do_filter(StringUtils.get_url_domain(self.spider_url),
                                                               keyword, to_filter_titles, ctx, True)
                urls = [detail_urls[name] for name in detail_urls.keys() if name in filter_titles]
            else:
                urls = [detail_urls[name] for name in detail_urls.keys()]
            if not urls:
                return []
            logger.info(f"{self.spider_name}-解析到{len(urls)}个搜索结果，开始获取链接地址...")
            # 计算每个线程处理的URL数量
            batch_size = max(1, len(urls) // self.spider_batch_size)  # 确保每个批次至少有一个URL
            url_batches = self.chunk_list(list(urls), batch_size)

            logger.info(f"{self.spider_name}-将 {len(urls)} 个详情页分成 {len(url_batches)} 个批次处理")
            # 使用线程池并发处理批次
            with ThreadPoolExecutor(max_workers=min(6, len(url_batches))) as tp:
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

    @retry(Exception, 2, 3, 2, logger=logger)
    def _get_torrent(self, down_urls: list) -> Optional[list]:
        # self._wait(0.5,1.5)
        new_tab = None
        results = []
        try:
            for down_url in down_urls:
                try:
                    if not new_tab:
                        new_tab.set.load_mode.eager()  # 设置加载模式为none
                        new_tab = self.browser.new_tab(down_url, timeout=20)
                    else:
                        new_tab.get(down_url, timeout=20)

                    size_tag = new_tab.ele(
                        'x://div[@class="panel-body"]//ul[@class="list-unstyled"]/li[starts-with(., "文件大小：")]/text()')
                    date_tag = new_tab.ele(
                        'x://div[@class="panel-body"]//ul[@class="list-unstyled"]/li[starts-with(., "收录时间：")]/text()')
                    hash_tag = new_tab.ele(
                        'x://div[@class="panel-body"]//ul[@class="list-unstyled"]/li[starts-with(., "种子哈希：")]/text()')
                    if not hash_tag:
                        continue
                    url_set = set()
                    link = f"magnet:?xt=urn:btih:{hash_tag.text.replace("种子哈希：", "")}"
                    if link not in url_set:
                        title = new_tab.ele("css:.page-header h3").text
                        if not title:
                            continue
                        title_info = SearchFilterHelper().parse_title(title)
                        if not title_info.size:
                            title_info.size = size_tag.text
                        results.append({
                            "title": new_tab.ele("css:.page-header h3").text,
                            "enclosure": link,
                            "description": title,
                            "size": title_info.size_num
                        })
                        url_set.add(link)
                except Exception as e:
                    logger.error(
                        f"{self.spider_name}-详情页:【{down_url}】,获取种子失败: {str(e)} - {traceback.format_exc()}")
                    return []
        finally:
            if new_tab:
                new_tab.close()
        return results


if __name__ == "__main__":
    lou = WuQianSpider({
        'spider_proxy': False,
        'spider_enable': True,
        'pass_cloud_flare': True,
        'spider_name': 'WuQianSpider',
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
