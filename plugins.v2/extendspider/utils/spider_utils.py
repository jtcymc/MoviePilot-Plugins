import traceback
from concurrent.futures import as_completed, ThreadPoolExecutor
from typing import Tuple, Optional, Dict, List, Any
from bs4 import BeautifulSoup
from playwright.sync_api import Page, Browser, BrowserContext
from app.log import logger
from app.plugins.extendspider.utils.browser import create_browser, create_stealth_page
from app.plugins.extendspider.utils.url import pass_cloudflare
from app.schemas import SearchContext, TorrentInfo
from app.utils.string import StringUtils
from app.helper.search_filter import SearchFilterHelper

class SpiderUtils:
    @staticmethod
    def handle_browser_operation(spider_name: str, url: str, proxy: bool, cookies: List[Dict] = None,
                               operation: callable = None) -> Tuple[bool, Any]:
        """
        处理浏览器操作的通用方法
        :param spider_name: 爬虫名称
        :param url: 目标URL
        :param proxy: 是否使用代理
        :param cookies: 浏览器cookies
        :param operation: 要执行的操作函数
        :return: (是否成功, 操作结果)
        """
        browser: Browser = None
        context: BrowserContext = None
        page: Page = None
        try:
            browser, context = create_browser(proxy)
            if cookies:
                context.add_cookies(cookies)
            page = create_stealth_page(context)
            
            # 访问主页并处理 Cloudflare
            logger.info(f"{spider_name}-正在访问 {url}...")
            if not pass_cloudflare(url, page):
                logger.warn("cloudflare challenge fail！")
                return False, None
                
            # 等待页面加载完成
            page.wait_for_load_state("networkidle", timeout=15 * 1000)
            
            if operation:
                return True, operation(page)
            return True, None
            
        except Exception as e:
            logger.error(f"{spider_name}-浏览器操作失败: {str(e)}")
            return False, None
        finally:
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()

    @staticmethod
    def handle_response_data(response, spider_name: str) -> Optional[Dict]:
        """
        处理响应数据的通用方法
        :param response: 响应对象
        :param spider_name: 爬虫名称
        :return: 解析后的数据
        """
        try:
            data = response.json()
            if data.get("code") == 200:
                return data.get("data", {})
            return None
        except Exception as err:
            logger.error(f"{spider_name}-解析接口返回数据失败:{str(err)} {traceback.format_exc()}")
            return None

    @staticmethod
    def process_urls_in_batches(urls: List[str], spider_name: str, proxy: bool, cookies: List[Dict] = None,
                              process_func: callable = None, batch_size: int = 6) -> List[Any]:
        """
        批量处理URL的通用方法
        :param urls: URL列表
        :param spider_name: 爬虫名称
        :param proxy: 是否使用代理
        :param cookies: 浏览器cookies
        :param process_func: 处理函数
        :param batch_size: 批次大小
        :return: 处理结果列表
        """
        results = []
        
        def chunk_list(lst, size):
            return [lst[i:i + size] for i in range(0, len(lst), size)]
            
        def process_url_batch(url_batch, index):
            try:
                browser, context = create_browser(proxy)
                if cookies:
                    context.add_cookies(cookies)
                detail_page = create_stealth_page(context)
                
                current_batch_results = []
                try:
                    for url_idx, url in enumerate(url_batch):
                        logger.info(f"{spider_name}-线程 {index} 正在处理第 {url_idx + 1}/{len(url_batch)} 个URL: {url}")
                        if process_func:
                            result = process_func(url, detail_page)
                            if result:
                                current_batch_results.append(result)
                finally:
                    detail_page.close()
                    context.close()
                    browser.close()
                return current_batch_results
            except Exception as ex:
                logger.error(f"{spider_name}-线程 {index} 处理批次失败: {str(ex)}")
                return []
                
        # 计算每个线程处理的URL数量
        batch_size = max(1, len(urls) // batch_size)
        url_batches = chunk_list(urls, batch_size)
        
        logger.info(f"{spider_name}-将 {len(urls)} 个URL分成 {len(url_batches)} 个批次处理")
        
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
                    results.extend(batch_results)
                    logger.info(f"{spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理完成，获取到 {len(batch_results)} 个结果")
                except Exception as e:
                    logger.error(f"{spider_name}-第 {idx + 1}/{len(url_batches)} 个批次处理失败: {str(e)}")
                    
        return results

    @staticmethod
    def filter_torrents(torrents: Dict[str, str], spider_url: str, keyword: str, 
                       ctx: SearchContext) -> List[str]:
        """
        过滤种子的通用方法
        :param torrents: 种子字典 {标题: URL}
        :param spider_url: 爬虫URL
        :param keyword: 搜索关键词
        :param ctx: 搜索上下文
        :return: 过滤后的URL列表
        """
        if not torrents:
            return []
            
        if ctx.enable_search_filter:
            to_filter_titles = [name for name in torrents.keys()]
            filter_titles = SearchFilterHelper().do_filter(
                StringUtils.get_url_domain(spider_url),
                keyword,
                to_filter_titles,
                ctx
            )
            return [torrents[name] for name in torrents.keys() if name in filter_titles]
        return [torrents[name] for name in torrents.keys()] 