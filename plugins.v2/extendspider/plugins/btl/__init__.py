import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from app.log import logger
from app.plugins.extendspider.plugins.base import _ExtendSpiderBase
from app.schemas import SearchContext
from app.utils.common import retry
from app.utils.string import StringUtils
from app.plugins.extendspider.utils.pass_verify import pass_slider_verification


class BtlSpider(_ExtendSpiderBase):

    def __init__(self, config: dict = None):
        super(BtlSpider, self).__init__(config)
        self._result_lock = threading.Lock()

    def init_spider(self, config: dict = None):
        self.spider_url = self.spider_url or "https://www.6bt0.com"
        self.spider_search_url = f"{self.spider_url}/search?sb=$key$"

    def get_search_url(self, keyword: str, page: int) -> str:
        if not keyword:
            return ""
        return self.spider_search_url.replace("$key$", keyword)

    def _do_search(self, keyword: str, page: int, ctx: SearchContext):
        results = []
        if not keyword:
            logger.warning(f"{self.spider_name}-搜索关键词为空")
            return results
        if not self.browser:
            logger.warn(f"{self.spider_name}-未初始化浏览器")
            return  []
        tab = self.browser.new_tab(url=self.spider_url)
        try:
            # self.browser.get(self.spider_url)
            if not pass_slider_verification(tab):
                logger.warn("cloudflare challenge fail！")
                return results
            # 访问搜索页
            logger.info(f"{self.spider_name}-访问主页成功,开始搜索【{keyword}】...")
            self._wait_inner(min_delay=1, max_delay=2)
            search_url = self.get_search_url(keyword, page)
            listen_url = "api/v1/getVideoList"
            tab.listen.start(listen_url)
            # 滚动到页面底部以触发更多数据加载
            tab.scroll.to_bottom()
            tab.get(search_url)
            packet = tab.listen.wait(timeout=60)
            if not packet:
                logger.warn(f"{self.spider_name}-没有搜索到数据，url:【{search_url}】")
                return results
                # 监听的url
            resp = packet.response
            if resp.status != 200 or not resp.body:
                logger.warn(f"{self.spider_name}-搜索数据获取失败，status:【{resp.status}】，url:【{search_url}】")
                return results
            json_data = resp.body.get("data")
            if json_data and (json_data.get("total", 0) > 0 or len(json_data.get("data", [])) > 0):
                results = self._parse_search_result(json_data.get("data", []), ctx)
                logger.info(f"{self.spider_name}-搜索完成，共找到 {len(results)} 个结果")
            return results
        except Exception as e:
            logger.error(f"{self.spider_name}-搜索失败: {str(e)} - {traceback.format_exc()}")
            return results
        finally:
            tab.close()

    @staticmethod
    def match_ids(data: dict, ids2: list) -> bool:
        """
        判断 data 中的 ID 与 ctx.media_info 中的 ID 是否存在交集。
        :param data: 数据字典，可能包含 "IMDB_number" 和 "doub_id"
        :return: 如果存在交集或 ctx/data/ctx.media_info 为空，则返回 True
        """
        if not ids2:
            return True

        # 提取并标准化 data 中的 IDs
        ids1 = [
                   str(data.get("IMDB_number")).lower()
                   for _ in [0] if data.get("IMDB_number") not in ("", "0")
               ] + [
                   str(data.get("doub_id")).lower()
                   for _ in [0] if data.get("doub_id") not in ("", "0")
               ]
        # 计算交集
        common_ids = set(ids1) & set(ids2)

        # 若有交集则返回 True，否则返回 False
        return bool(common_ids)

    def _parse_search_result(self, datas: list[dict], ctx: SearchContext):
        if not datas:
            return []
        detail_urls = set()
        ids = []
        if ctx and ctx.media_info:
            ids = [
                      str(ctx.media_info.douban_id).lower()
                      for _ in [0] if ctx.media_info.douban_id not in ("", "0", "none")
                  ] + [
                      str(ctx.media_info.imdb_id).lower()
                      for _ in [0] if ctx.media_info.imdb_id not in ("", "0", "none")
                  ]
        for data in datas:
            if not data.get("idcode"):
                continue
            # 匹配id
            if self.match_ids(data, ids):
                detail_url = f"{self.spider_url}/mv/{data.get('idcode')}"
                detail_urls.add(detail_url)
        results = []
        if detail_urls:
            logger.info(f"{self.spider_name}-解析到{len(detail_urls)}个搜索结果，开始获取链接地址...")
            # 计算每个线程处理的URL数量
            batch_size = max(1, len(detail_urls) // self.spider_batch_size)  # 确保每个批次至少有一个URL
            url_batches = self.chunk_list(list(detail_urls), batch_size)

            logger.info(f"{self.spider_name}-将 {len(detail_urls)} 个详情页分成 {len(url_batches)} 个批次处理")
            # 使用线程池并发处理批次
            with ThreadPoolExecutor(max_workers=min(4, len(url_batches))) as tp:
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
        results = []
        new_tab = self.browser.new_tab()
        try:
            for down_url in down_urls:
                try:
                    listen_url = "api/v1/getVideoDetail"
                    new_tab.listen.start(listen_url)
                    new_tab.get(down_url, timeout=20)
                    new_tab.scroll.to_bottom()
                    packet = new_tab.listen.wait(1, timeout=60)
                    new_tab.listen.stop()
                    if not packet:
                        logger.warn(f"详情页:【{down_url}】,没有捕获到数据，url:【{listen_url}】")
                        return []
                        # 监听的url
                    resp = packet.response
                    if resp.status != 200 or not resp.body:
                        logger.warn(f"详情页:【{down_url}】,数据获取失败，status:【{resp.status}】，url:【{listen_url}】")
                        return []
                    json_data = resp.body.get("data")
                    if not json_data or json_data.get("znum", 0) <= 0:
                        return results
                    url_set = set()
                    for _, values in json_data.get("ecca", {}).items():
                        for value in values:
                            enclosure = value.get("down", "")
                            if not enclosure:
                                continue
                            elif not enclosure.startswith("http"):
                                enclosure = f"{self.spider_url.strip("/")}{enclosure}"
                            if enclosure in url_set:
                                continue
                            zlink = value.get("zlink")
                            if zlink and not zlink.startswith("magnet"):
                                logger.debug(f"详情页:【{down_url}】,种子链接不是磁力链接:【{zlink}】")
                                continue
                            url_set.add(enclosure)
                            results.append({
                                "title": value.get("zname"),
                                "enclosure": enclosure,
                                "description": value.get("zname"),
                                'pubdate': StringUtils.str_to_timestamp(value.get('ezt')),
                                "size": StringUtils.num_filesize(value.get("zsize", ""))
                            })
                except Exception as e:
                    logger.error(
                        f"{self.spider_name}-详情页:【{down_url}】,获取种子失败: {str(e)} - {traceback.format_exc()}")
        finally:
            new_tab.close()
        return results


if __name__ == "__main__":
    lou = BtlSpider({
        'spider_proxy': False,
        'spider_enable': True,
        'spider_name': 'BtlSpider',
        'proxy_type': 'playwright',
        'proxy_config': {
            'flaresolverr_url': 'http://192.168.68.116:8191'
        },
        'request_interval': (1.5, 1.9),  # 设置随机请求间隔，最小2秒，最大5秒
        'spider_headless': False,
        'use_drission_browser': True,
    })
    # ctx = SearchContext(
    #     keyword="遮天",
    #     media_info=MediaInfo(
    #         imdb_id="tt27617390",
    #         title="遮天",
    #         year="2015"
    #     )
    # )
    # 使用直接请求
    rest = lou.search("灵笼 第二季", 1)
    print(rest)
