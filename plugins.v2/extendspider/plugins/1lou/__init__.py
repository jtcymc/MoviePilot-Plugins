from typing import Tuple

from bs4 import BeautifulSoup
from app.log import logger
from plugins.extendspider.base import _ExtendSpiderBase
from plugins.extendspider.utils.proxy import ProxyFactory
from plugins.extendspider.utils.url import xn_url_encode
import requests


class Bt1louSpider(_ExtendSpiderBase):
    #   网站搜索接口请求头
    spider_headers = {}
    #  网站搜索接口
    spider_search_url = ""
    #  网站搜索接口Cookie
    spider_cookie = ""

    def __init__(self, config: dict = None):
        super(Bt1louSpider, self).__init__(config)
        logger.info(f"初始化 {self.spider_name} 爬虫")

    def init_spider(self, config: dict = None):
        self.spider_url = "https://www.1lou.me"
        # self.spider_name = "1lou"
        # self.spider_desc = "BT之家1LOU站-回归初心，追求极简"
        self.spider_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Referer": self.spider_url,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
        }
        self.spider_search_url = f"{self.spider_url}/search-$key$-$page$.htm"
        self.spider_cookie = ""
        if self.spider_proxy:
            proxy_type = 'flaresolverr'
        else:
            proxy_type = 'direct'
        # 初始化代理
        proxy_config = {
            'flaresolverr_url': 'http://192.168.68.116:8191',
            'request_interval': self.spider_request_interval
        }

        self.spider_proxy_client = ProxyFactory.create_proxy(proxy_type, headers=self.spider_request_interval,
                                                             **proxy_config)
        logger.info(f"初始化代理类型: {proxy_type}, 配置: {proxy_config}")

    def _get_cookie(self):
        # 访问主页获取 cookie
        try:
            logger.info(f"正在获取 {self.spider_name} 的 Cookie...")
            response = self.spider_proxy_client.request('GET', self.spider_url)
            if response.cookies:
                self.spider_cookie = "; ".join([f"{cookie.name}={cookie.value}" for cookie in response.cookies])
                self.spider_headers["Cookie"] = self.spider_cookie
                logger.info(f"成功获取 Cookie: {self.spider_cookie}")
            else:
                logger.warning("未获取到 Cookie")
        except Exception as e:
            logger.error(f"获取 Cookie 失败: {str(e)}")

    def _do_search(self, keyword: str, page: int):
        if not keyword:
            logger.warning("搜索关键词为空")
            return []
        # 确保已经初始化并获取了 cookie
        if not self.spider_cookie:
            self._get_cookie()
        results = []
        try:
            # 如果起始页大于1，只抓取指定页
            if page > self.spider_page_start:
                logger.info(f"指定页码 {page} 大于起始页 {self.spider_page_start}，只抓取指定页")
                return self._search_page(keyword, page)

            # 获取总页数
            search_url = self.get_search_url(keyword, 1)
            if not search_url:
                logger.error("生成搜索URL失败")
                return []

            logger.info(f"开始搜索: {keyword}, 页码: 1, URL: {search_url}")
            response = self.spider_proxy_client.request('GET', search_url)
            if response.status_code != 200:
                logger.error(f"搜索请求失败: HTTP {response.status_code}")
                return []

            # 解析总页数
            total_pages = self._parse_total_pages(response)
            if not total_pages:
                logger.warning("未找到分页信息，只抓取第一页")
                return self._parse_search_result(response)

            # 计算需要抓取的页数
            pages_to_fetch = min(total_pages, self.spider_max_load_page)
            logger.info(f"总页数: {total_pages}, 将抓取前 {pages_to_fetch} 页")

            # 抓取第一页
            results.extend(self._parse_search_result(response))

            # 抓取后续页面
            for current_page in range(2, pages_to_fetch + 1):
                page_results = self._search_page(keyword, current_page)
                results.extend(page_results)

            logger.info(f"搜索完成，共找到 {len(results)} 个结果")
            return results
        except Exception as e:
            logger.error(f"搜索过程发生错误: {str(e)}")
            return []

    def _search_page(self, keyword: str, page: int):
        """抓取指定页的数据"""
        try:
            search_url = self.get_search_url(keyword, page)
            if not search_url:
                logger.error(f"生成第 {page} 页搜索URL失败")
                return []

            logger.info(f"正在抓取第 {page} 页: {search_url}")
            response = self.spider_proxy_client.request('GET', search_url)
            if response.status_code != 200:
                logger.error(f"抓取第 {page} 页失败: HTTP {response.status_code}")
                return []

            results = self._parse_search_result(response)
            logger.info(f"第 {page} 页抓取完成，找到 {len(results)} 个结果")
            return results
        except Exception as e:
            logger.error(f"抓取第 {page} 页时发生错误: {str(e)}")
            return []

    @staticmethod
    def _parse_total_pages(response: requests.Response) -> int:
        """解析总页数"""
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            pagination = soup.find("ul", class_="pagination")
            if not pagination:
                return 0

            # 获取所有页码链接
            page_items = pagination.find_all("li", class_="page-item")
            if not page_items:
                return 0

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
                return 0

        except Exception as e:
            logger.error(f"解析总页数失败: {str(e)}")
            return 0

    def _parse_search_result(self, response: requests.Response):
        results = []
        # 初始化已处理标题集合
        _processed_titles = set()
        _processed_torrent_titles = set()

        _processed_urls = set()
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            for result in soup.find_all("li", class_="media thread tap"):
                # 不是磁力或者种子的链接
                if not result.find("div", class_="subject break-all").find("i", class_="icon small filetype other"):
                    continue
                title_link = result.find("div", class_="subject break-all").find("a")
                if title_link and title_link['href']:
                    # 处理标题中的 text-danger 标签
                    title = ""
                    for content in title_link.contents:
                        if content.name == "span" and "text-danger" in content.get("class", []):
                            title += content.text
                        elif isinstance(content, str):
                            title += content
                    title = title.strip()

                    # 检查标题是否已处理过
                    if title in _processed_titles:
                        logger.info(f"跳过重复标题: {title}")
                        continue

                    if title_link['href'].startswith("http"):
                        detail_url = title_link['href']
                    else:
                        detail_url = f"{self.spider_url}/{title_link['href']}"
                        logger.info(f"正在获取详情页: {detail_url}")
                    if detail_url in _processed_urls:
                        logger.info(f"跳过已处理详情页: {detail_url}")
                    state, res = self._get_torrent(_processed_torrent_titles, detail_url)
                    if state:
                        # 添加到已处理集合
                        _processed_titles.add(title)
                        _processed_urls.add(detail_url)
                        results.extend(res)
                        logger.info(f"成功获取种子信息: {len(res)} 个")
                    else:
                        logger.error(f"获取种子失败：{res}")
                        return results
        except Exception as e:
            logger.error(f"解析搜索结果失败: {str(e)}")
        return results

    def _get_torrent(self, _processed_torrent_titles: set, detail_url: str) -> Tuple[bool, list]:
        results = []
        try:
            logger.debug(f"正在请求详情页: {detail_url}")
            response = self.spider_proxy_client.request('GET', detail_url)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                fieldset = soup.find("fieldset", class_="fieldset")
                if fieldset:
                    for li in fieldset.find_all("li"):
                        if li.find("i", class_="icon filetype torrent"):
                            title = li.find("a").text.strip()
                            if title in _processed_torrent_titles:
                                logger.info(f"跳过已处理种子：{title}")
                                continue
                            href = li.find("a")['href']
                            # 判断是否是磁力链接
                            if href.startswith('magnet:?'):
                                enclosure = href
                                logger.debug(f"找到磁力链接: {enclosure}")
                            else:
                                # 处理普通下载链接
                                if href.startswith('http'):
                                    enclosure = href
                                else:
                                    enclosure = f"{self.spider_url}/{href}"
                                logger.debug(f"找到下载链接: {enclosure}")

                            torrent_info = {
                                "title": title,
                                "enclosure": enclosure,
                                'description': title,
                                'page_url': detail_url,
                            }
                            results.append(torrent_info)
                            _processed_torrent_titles.add(title)
                            logger.info(f"找到种子: {title}")
                else:
                    logger.warning(f"未找到种子信息: {detail_url}")
            else:
                logger.error(f"请求详情页失败: HTTP {response.status_code}")
            return True, results
        except Exception as e:
            logger.error(f"获取种子链接失败: {str(e)}")
            return False, results

    def _get_page(self, page: int) -> str:
        if page <= self.spider_page_start:
            page = self.spider_page_start
        return f"1-{page}"

    def get_search_url(self, keyword: str, page: int) -> str:
        if not keyword:
            return ""
        return self.spider_search_url.replace("$key$", xn_url_encode(keyword)).replace("$page$", self._get_page(page))

    def search(self, keyword: str, page: int):
        """
        搜索资源，支持限速控制。
        :param keyword: 搜索关键词
        :param page: 分页页码
        :return: 匹配的种子资源列表
        """
        # 检查是否触发限速
        state, msg = self.check_ratelimit()
        if state:
            return []
        return self._do_search(keyword, page)


if __name__ == "__main__":
    lou = Bt1louSpider({
        'proxy_type': 'flaresolverr',
        'proxy_config': {
            'flaresolverr_url': 'http://192.168.68.116:8191'
        },
        'request_interval': (2, 5)  # 设置随机请求间隔，最小2秒，最大5秒
    })
    # 使用直接请求
    lou.search("藏海传", 1)
