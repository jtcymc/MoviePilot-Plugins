import asyncio
import re
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from app.helper.search_filter import SearchFilterHelper
from app.log import logger
from app.schemas import SearchContext
from app.utils.common import retry
from plugins.extendspider.plugins.base import _ExtendSpiderBase
from plugins.extendspider.utils.file import delete_folder, creat_folder
from plugins.extendspider.utils.file_server import FileCodeBox
from plugins.extendspider.utils.url import xn_url_encode


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
            # 访问主页并处理 Cloudflare
            logger.info(f"{self.spider_name}-正在访问 {self.spider_url}...")
            self._from_pass_cloud_flare(self.spider_url)
        try:
            logger.info(f"{self.spider_name}-访问主页成功,开始搜索【{keyword}】...")
            self._wait_inner()
            # 如果起始页大于1，只抓取指定页
            if page > self.spider_page_start:
                search_url = self.get_search_url(keyword, page)
                res = self.spider_proxy_client.request("GET", search_url)
                html = res.content
                logger.info(
                    f"{self.spider_name}-指定页码 {page} 大于起始页 {self.spider_page_start}，只抓取指定页")
                results.extend(self._parse_search_result_page(keyword, html, True, ctx))
                return results

            # 执行搜索
            search_url = self.get_search_url(keyword, 1)
            res = self.spider_proxy_client.request("GET", search_url)
            html = res.content
            results = self._parse_search_result_page(keyword, html, False, ctx)
            logger.info(f"{self.spider_name}-搜索完成，共找到 {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f"搜索过程发生错误: {str(e)}, {traceback.format_exc()}")
            return []

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

    def _parse_search_result_page(self, keyword, html: str, one_page: bool, ctx: SearchContext):
        """ 统计搜索结果页数信息 """
        _processed_titles = set()
        _processed_urls = set()
        detail_urls = {}

        # 抓取第一页
        self._parse_search_page_detail_urls(html, _processed_titles,
                                            _processed_urls, detail_urls)

        if not one_page:
            # 解析总页数
            total_pages = self._parse_total_pages(html)
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
                        res = self.spider_proxy_client.request("GET", search_url)
                        html = res.content
                        self._parse_search_page_detail_urls(html, _processed_titles,
                                                            _processed_urls, detail_urls)
                    except Exception as e:
                        logger.error(f"{self.spider_name}-抓取第 {current_page} 页时发生错误: {str(e)}")
            logger.info(f"{self.spider_name}-共抓取 {pages_to_fetch} 页数据，找到详情页 {len(detail_urls)} 个结果")
        if not detail_urls:
            logger.info(f"{self.spider_name}-没有找到详情页，可能没有搜索到结果")
            return []
        detail_urls_tp = []
        if ctx.enable_search_filter:
            to_filter_titles = [title for title in detail_urls.keys()]
            filter_titles = self.search_helper.do_filter(self.spider_name, keyword, to_filter_titles, ctx)
            if not filter_titles:
                logger.info(f"{self.spider_name}-没有找到符合要求的结果")
                return []
            detail_urls_tp = [{"title": title, "url": detail_urls[title]} for title in filter_titles if
                              title in detail_urls]
        else:
            detail_urls_tp = [{"title": title, "url": detail_url} for title, detail_url in detail_urls.items()]
        results = self._parse_detail_results(detail_urls_tp)
        logger.info(f"{self.spider_name}-搜索完成，共找到 {len(results)} 个结果")
        return results

    @retry(Exception, 2, 3, 2, logger=logger)
    def _parse_search_page_detail_urls(self, html_content: str, _processed_titles, _processed_urls, detail_urls: dict
                                       ):
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

    def _parse_detail_results(self, detail_urls: list[dict]) -> list:
        """ 处理详情页 """
        results = []
        _processed_torrent_titles = set()

        tmp_folder = os.path.join(self.tmp_folder, str(int(time.time())))

        def sanitize_filename(name: str) -> str:
            # 移除/替换 Windows 不允许的字符
            return re.sub(r'[<>:"/\\|?*]', '_', name)

        try:
            creat_folder(tmp_folder)

            # 将URL列表分成多个批次
            def chunk_list(lst, chunk_size):
                return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

            def process_url_batch(url_batch, index):
                # current_batch_results = []
                new_tab = None
                try:
                    for url_idx, detail_item in enumerate(url_batch):
                        self._wait_inner(0.6, 1.1)
                        if new_tab is None:
                            new_tab = self.browser.new_tab(detail_item['url'])
                            # new_tab.set.load_mode.eager()  # 设置加载模式为none
                            new_tab.set.when_download_file_exists('skip')
                        else:
                            new_tab.get(detail_item['url'], timeout=10)

                        if not self.drission_browser.getTurnstileToken(new_tab):
                            logger.warn(f"{self.spider_name}-线程 {index} 获取TurnstileToken失败")
                            continue
                        if not new_tab.wait.ele_displayed("css:fieldset a[href]", timeout=10):
                            continue
                        down = new_tab.ele("css:fieldset a[href]")
                        # new_tab.stop_loading()
                        if down:
                            title = sanitize_filename(detail_item['title'])
                            down.set.attr("target", "_self")
                            self._wait(0.01, 0.1)
                            new_tab.set.download_path(tmp_folder)
                            mission = down.click.to_download(tmp_folder, timeout=20, new_tab=True,
                                                             rename=title,
                                                             suffix="torrent",
                                                             by_js=True)  # 点击一个会触发下载的链接，同时设置下载路径和文件名
                            if mission:
                                mission.wait()
                            logger.info(f"{self.spider_name}-线程 {index} url:[{detail_item['url']}]下载成功")
                    return True
                except Exception as ex:
                    logger.error(f"{self.spider_name}-线程 {index} 处理批次失败: {str(ex)},{traceback.format_exc()}")
                finally:
                    if new_tab:
                        try:
                            new_tab.close()
                        except Exception:
                            pass
                return False

            # 计算每个线程处理的URL数量
            batch_size = max(1, len(detail_urls) // self.spider_batch_size)  # 确保每个批次至少有一个URL
            url_batches = chunk_list(list(detail_urls), batch_size)

            logger.info(f"{self.spider_name}-将 {len(detail_urls)} 个详情页分成 {len(url_batches)} 个批次处理")

            # 使用线程池并发处理批次
            with ThreadPoolExecutor(max_workers=min(self.spider_batch_size, len(url_batches))) as executor:
                future_to_batch = {
                    executor.submit(process_url_batch, batch, idx + 1): (idx, batch)
                    for idx, batch in enumerate(url_batches)
                }

                for future in as_completed(future_to_batch):
                    idx, batch = future_to_batch[future]
                    try:
                        flag = future.result()
                        if flag:
                            logger.info(
                                f"{self.spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理完成")
                        else:
                            logger.error(
                                f"{self.spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理失败")
                    except Exception as e:
                        logger.error(f"{self.spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理失败: {str(e)}")
            # 避免操作系统缓存
            # self._wait_inner(0.3, 0.6)
            results = self._upload_and_format_torrent_info(tmp_folder)
            logger.info(f"{self.spider_name}-所有批次处理完成，共获取到 {len(results)} 个种子")
        finally:
            delete_folder(tmp_folder)
            logger.info(f"{self.spider_name}-已删除临时文件夹 {tmp_folder}")
        return results

    def _upload_and_format_torrent_info(self, tmp_folder: str):

        files = os.listdir(tmp_folder)  # 得到文件夹下的所有文件名称
        results = []
        for file in files:
            if not os.path.isdir(file) and file.endswith(".torrent"):
                flag, file_name, enclosure = asyncio.run(self.file_server.upload_file(os.path.join(tmp_folder, file)))
                if not flag:
                    continue
                title_info = SearchFilterHelper().parse_title(file)
                results.append({
                    "title": file,
                    "enclosure": enclosure,
                    "description": file,
                    # "page_url": detail_url, # 会下载字幕
                    "size": title_info.size_num
                })
                logger.info(f"{self.spider_name}-找到种子: {file}")
                self._wait(2.5, 3.5)
        return results


if __name__ == "__main__":
    import os

    # lou = Bt1louSpider({
    #     'spider_name': 'Bt1louSpider',
    #     'proxy_type': 'playwright',
    #     'pass_cloud_flare': True,
    #     'spider_enable': True,
    #     'proxy_config': {
    #         'flaresolverr_url': 'http://192.168.68.115:8191'
    #     },
    #     'request_interval': (2, 5),
    #     'use_drission_browser': True,
    #     'spider_headless': False,
    #     "use_file_server": True,
    #     "file_server_url": "http://192.168.68.190:12345",
    #     "tmp_folder": os.path.join(os.path.dirname(__file__), "tmp_tt"),
    # })
    # # 使用直接请求
    # lou.search("大侠请上功", 1)
    file_server = FileCodeBox("http://192.168.68.190:12345")


    def _upload_and_format_torrent_info(tmp_folder: str):

        files = os.listdir(tmp_folder)  # 得到文件夹下的所有文件名称
        results = []
        for file in files:
            if not os.path.isdir(file) and file.endswith(".torrent"):
                time.sleep(3)
                flag, file_name, enclosure = asyncio.run(file_server.upload_file(os.path.join(tmp_folder, file)))
                if not flag:
                    continue
                title_info = SearchFilterHelper().parse_title(file)
                results.append({
                    "title": file,
                    "enclosure": enclosure,
                    "description": file,
                    # "page_url": detail_url, # 会下载字幕
                    "size": title_info.size_num
                })
                logger.info(f"找到种子: {file}")
        return results


    _upload_and_format_torrent_info(
        "F:\\ShawProject\\MoviePilot\\app\\plugins\\extendspider\\plugins\\1lou\\tmp_tt\\1750402053")
