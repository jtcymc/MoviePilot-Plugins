import urllib.parse
from typing import Tuple
from bs4 import BeautifulSoup
from app.log import logger
from core.config import settings
from plugins.extendspider.base import _ExtendSpiderBase
from modules.indexer.utils.proxy import ProxyFactory
from plugins.extendspider.utils.guard_js import get_guard_ret
from plugins.extendspider.utils.url import xn_url_encode, get_dn
import requests


class BtdxSpider(_ExtendSpiderBase):
    #  网站搜索接口Cookie
    spider_cookie = ""

    def __init__(self, config: dict = None):
        super(BtdxSpider, self).__init__(config)

    def init_spider(self, config: dict = None):
        self.spider_url = "https://www.btdx8.vip"
        self.spider_search_url = f"{self.spider_url}/?s=$key$"
        self.spider_cookie = ""
        self.spider_headers = {
            "Content-Type": "text/html; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",

        }

    def get_search_url(self, keyword: str, page: int) -> str:
        if not keyword:
            return ""
        return self.spider_search_url.replace("$key$", keyword)

    def _get_cookie(self):
        # 访问主页获取 cookie
        try:
            logger.info(f"{self.spider_name}-正在获取 {self.spider_name} 的 Cookie...")
            response = self.spider_proxy_client.request('GET', self.spider_url)
            # cookies = {}
            # # 2. 设置cookie，第一次请求获取guard，处理得到guardret
            # for cookie in response.cookies:
            #     cookies[cookie.name] = cookie.value
            #     # 调用函数
            # cookies['guardret'] = get_guard_ret(response.cookies['guardret'])
            # self.spider_headers["Cookie"] = cookies
            # response = self.spider_proxy_client.request('GET', self.spider_url,headers=self.spider_headers)
            if response.cookies:
                self.spider_cookie = "; ".join([f"{cookie.name}={cookie.value}" for cookie in response.cookies])
                self.spider_headers["Cookie"] = self.spider_cookie
                logger.info(f"{self.spider_name}-成功获取 Cookie: {self.spider_cookie}")
            #
            # else:
            #     logger.warning("未获取到 Cookie")
        except Exception as e:
            logger.error(f"{self.spider_name}-获取 Cookie 失败: {str(e)}")

    def _do_search(self, keyword: str, page: int):
        # 确保已经初始化并获取了 cookie
        if not self.spider_cookie:
            self._get_cookie()
        try:
            results = self._search_page(keyword, page)
            logger.info(f"{self.spider_name}-搜索完成，共找到 {len(results)} 个结果")
            return results
        except Exception as e:
            logger.error(f"{self.spider_name}-搜索过程发生错误: {str(e)}")
            return []

    def _search_page(self, keyword: str, page: int):
        try:
            search_url = self.get_search_url(keyword, page)
            logger.info(f"{self.spider_name}-正在抓取第 {page} 页: {search_url}")
            response = self.spider_proxy_client.request('GET', search_url, headers=self.spider_headers)
            if response.status_code != 200:
                logger.error(f"{self.spider_name}-抓取第 {page} 页失败: HTTP {response.status_code}")
                return []
            results = self._parse_search_result(response)
            logger.info(f"{self.spider_name}-第 {page} 页抓取完成，找到 {len(results)} 个结果")
            return results
        except Exception as e:
            logger.error(f"{self.spider_name}-抓取第 {page} 页时发生错误: {str(e)}")
            return []

    def _parse_search_result(self, response: requests.Response):
        # 初始化已处理标题集合
        _processed_torrent_titles = set()

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            detail_tag = soup.select_one("div.post-grid  div.post a.entry-thumb")
            # 判断是否有搜索结果
            if not detail_tag:
                _, res = self._parse_torrent(soup, _processed_torrent_titles, response.url)
                return res
            detail_url = detail_tag['href'].strip()
            if not detail_url.startswith("http"):
                detail_url = f"{self.spider_url}/{detail_url}"
            if not detail_url:
                return []
            # 使用线程池并发获取种子信息
            logger.info(f"{self.spider_name}-开始获取 {detail_url} 详情页的种子信息")
            try:
                state, torrents = self._get_torrent_thread_safe(_processed_torrent_titles, detail_url)
                if state:
                    logger.info(f"{self.spider_name}-成功获取详情页 {detail_url} 的种子信息: {len(torrents)} 个")
                return torrents if state else []
            except Exception as ex:
                logger.error(f"{self.spider_name}-详情抓取失败: {detail_url}: {str(ex)}")
                return []
        except Exception as e:
            logger.error(f"{self.spider_name}-解析搜索结果失败: {str(e)}")
            return []

    def _get_torrent_thread_safe(self, _processed_torrent_titles: set, detail_url: str) -> Tuple[bool, list]:
        """线程安全的获取种子信息"""
        results = []
        try:
            response = self.spider_proxy_client.request('GET', detail_url)
            if response.status_code != 200:
                return False, []
            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_torrent(soup, _processed_torrent_titles, detail_url)
        except Exception as e:
            logger.error(f"{self.spider_name}-获取种子链接失败: {str(e)}")
            return False, results

    def _parse_torrent(self, soup, _processed_torrent_titles: set, detail_url):
        results = []
        a_tags = soup.select("div a.download-link")
        if not a_tags:
            return False, []
        for a_tag in a_tags:
            link = a_tag['href'].strip()
            if not link or link.startswith("thunder://"):
                continue
            title = a_tag.text.strip()
            if title in _processed_torrent_titles:
                logger.info(f"{self.spider_name}-跳过已处理种子：{title}")
                continue
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
            _processed_torrent_titles.add(title)
            results.append({
                "title": title,
                "enclosure": enclosure,
                "description": title,
                "page_url": detail_url,
            })
            logger.info(f"{self.spider_name}-找到种子: {title}")

        return True, results


if __name__ == "__main__":
    lou = BtdxSpider({
        'spider_proxy': True,
        'spider_name': 'BtdxSpider',
        'proxy_type': 'direct',
        'proxy_config': {
            'flaresolverr_url': 'http://192.168.68.116:8191'
        },
        'request_interval': (1, 3)  # 设置随机请求间隔，最小2秒，最大5秒
    })
    # 使用直接请求
    rest = lou.search("藏海传", 1)
    print(rest)
