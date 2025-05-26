import urllib.parse
from typing import Tuple
from bs4 import BeautifulSoup
from app.log import logger
from plugins.extendspider.base import _ExtendSpiderBase
from plugins.extendspider.utils.url import get_dn
import requests


class BtttSpider(_ExtendSpiderBase):
    #  网站搜索接口Cookie
    spider_cookie = ""

    def __init__(self, config: dict = None):
        super(BtttSpider, self).__init__(config)

    def init_spider(self, config: dict = None):
        self.spider_url = "https://www.bttt11.com"
        self.spider_search_url = f"{self.spider_url}/e/search"
        self.spider_cookie = ""
        self.spider_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Content-Type": "application/x-www-form-urlencoded",
            'Referer': 'https://www.bttt11.com/',
            'Origin': 'https://www.bttt11.com',
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",

        }

    def _get_cookie(self):
        # 访问主页获取 cookie
        try:
            logger.info(f"{self.spider_name}-正在获取 {self.spider_name} 的 Cookie...")
            response = self.spider_proxy_client.request('GET', self.spider_url, headers={
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",

            })
            if response.cookies:
                self.spider_cookie = "; ".join([f"{cookie.name}={cookie.value}" for cookie in response.cookies])
                self.spider_headers["Cookie"] = self.spider_cookie
                logger.info(f"{self.spider_name}-成功获取 Cookie: {self.spider_cookie}")
            #
            else:
                logger.warning(f"{self.spider_name}-未获取到 Cookie")
        except Exception as e:
            logger.error(f"{self.spider_name}-获取 Cookie 失败: {str(e)}")

    def get_search_payload(self, keyword: str):
        if not keyword:
            return ""
        # 将字符串编码为 GB2312
        encoded_text01 = keyword.encode('utf-8')
        encoded_text02 = '搜索'.encode('utf-8')
        str1_encoded = 'title,newstext'.encode('utf-8')
        # 将编码后的字节数据转换为 URL 编码格式
        keyboard = urllib.parse.quote(encoded_text01)
        submit = urllib.parse.quote(encoded_text02)
        str1_encoded = urllib.parse.quote(str1_encoded)
        return {
            "show": str1_encoded,
            "keyboard": keyboard,
            "searchtype": submit
        }
        # return str1_encoded + f'&keyboard={keyboard}&searchtype={submit}'

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
            logger.info(f"{self.spider_name}-正在抓取第 {page} 页: {self.spider_search_url}")
            response = self.spider_proxy_client.request('POST', self.spider_search_url,
                                     headers=self.spider_headers,
                                     data=self.get_search_payload(keyword))
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

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            ul_div = soup.find("div", class_="ul-imgtxt2 row")
            # 判断是否有搜索结果
            if not ul_div:
                return []
            #  获取标题
            detail_tag = ul_div.select_one("li.col-md-6 div.text h3 a")
            detail_url = detail_tag['href'].strip()
            if not detail_url:
                return []
            if not detail_url.startswith("http"):
                detail_url = f"{self.spider_url}/{detail_url}"
            # 使用线程池并发获取种子信息
            logger.info(f"{self.spider_name}-开始获取 {detail_url} 详情页的种子信息")
            try:
                state, torrents = self._get_torrent_info(detail_url)
                if state:
                    logger.info(f"{self.spider_name}-成功获取详情页 {detail_url} 的种子信息: {len(torrents)} 个")
                return torrents if state else []
            except Exception as ex:
                logger.error(f"{self.spider_name}-详情抓取失败: {detail_url}: {str(ex)}")
                return []
        except Exception as e:
            logger.error(f"{self.spider_name}-解析搜索结果失败: {str(e)}")
            return []

    def _get_torrent_info(self, detail_url: str) -> Tuple[bool, list]:
        """线程安全的获取种子信息"""
        results = []
        try:
            response = self.spider_proxy_client.request('GET', detail_url)
            if response.status_code != 200:
                return False, []
            # response.encoding = 'gb2312'
            soup = BeautifulSoup(response.text, "html.parser")
            a_tags = soup.select_one("div.bot a[href]")
            titles = []
            links = []
            for a_tag in a_tags:
                link = a_tag['href'].strip()
                if not link.startswith('magnet:?'):
                    logger.info(f"{self.spider_name}-跳过非磁力链接：{link}")
                    continue
                title = a_tag.text.strip()
                if title in titles:
                    logger.info(f"{self.spider_name}-跳过已处理种子：{title}")
                    continue
                if link in links:
                    logger.info(f"{self.spider_name}-跳过重复的链接：{link}")
                    continue
                results.append({
                    "title": title,
                    "enclosure": link,
                    "description": title,
                    "page_url": detail_url,
                })
                logger.info(f"{self.spider_name}-找到种子: {title}")
            return True, results
        except Exception as e:
            logger.error(f"{self.spider_name}-获取种子链接失败: {str(e)}")
            return False, results


if __name__ == "__main__":
    lou = BtttSpider({
        'spider_proxy': True,
        'spider_enable': True,
        'spider_name': 'BtttSpider',
        'proxy_type': 'direct',
        'proxy_config': {
            'flaresolverr_url': 'http://192.168.68.116:8191'
        },
        'request_interval': (2, 5)  # 设置随机请求间隔，最小2秒，最大5秒
    })
    # 使用直接请求
    rest = lou.search("藏海传", 1)
    print(rest)
