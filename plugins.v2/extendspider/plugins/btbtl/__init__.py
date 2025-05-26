from concurrent.futures import as_completed, ThreadPoolExecutor
from bs4 import BeautifulSoup
from app.log import logger
from plugins.extendspider.base import _ExtendSpiderBase
import requests

from utils.string import StringUtils


class BtBtlSpider(_ExtendSpiderBase):
    #  网站搜索接口Cookie
    spider_cookie = ""

    def __init__(self, config: dict = None):
        super(BtBtlSpider, self).__init__(config)

    def init_spider(self, config: dict = None):
        self.spider_url = "https://www.btbtl.com"
        self.spider_search_url = f"{self.spider_url}/search/$key$"
        self.spider_cookie = ""

    def get_search_url(self, keyword: str, page: int) -> str:
        if not keyword:
            return ""
        return self.spider_search_url.replace("$key$", keyword)


    def _do_search(self, keyword: str, page: int):
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
            response = self.spider_proxy_client.request('GET', search_url)
            if response.status_code != 200:
                logger.error(f"{self.spider_name}-抓取第 {page} 页失败: HTTP {response.status_code}")
                return []
            return self._parse_search_result(response)
        except Exception as e:
            logger.error(f"{self.spider_name}-抓取第 {page} 页时发生错误: {str(e)}")
            return []

    def _parse_search_result(self, response: requests.Response):
        # 初始化已处理标题集合
        _processed_torrent_titles = set()

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            detail_tags = soup.select_one("div.module-list  div.module-items")
            # 判断是否有搜索结果
            if not detail_tags:
                return []
            detail_urls = []
            for detail_tag in detail_tags.select("div.module-item-titlebox a.module-item-title"):
                detail_url = detail_tag['href'].strip()
                if not detail_url.startswith("http"):
                    detail_url = f"{self.spider_url}/{detail_url}"
                detail_urls.append(detail_url)
            results = []
            if detail_urls:
                with ThreadPoolExecutor(max_workers=min(8, len(detail_urls))) as executor:
                    futures = [executor.submit(self._get_down_urls, url) for url in detail_urls]
                    for future in as_completed(futures):
                        state, torrents = future.result()
                        if state:
                            results.extend(torrents)
            logger.info(f"{self.spider_name}-搜索结果解析完成，共找到 {len(results)} 个种子")
            return results
        except Exception as e:
            logger.error(f"{self.spider_name}-解析搜索结果失败: {str(e)}")
            return []

    def _get_down_urls(self, detail_url):
        # 使用线程池并发获取种子信息
        logger.info(f"{self.spider_name}-开始获取详情页: {detail_url}")
        try:
            response = self.spider_proxy_client.request('GET', detail_url)
            if response.status_code != 200:
                return False, []

            soup = BeautifulSoup(response.text, "html.parser")
            a_tags = soup.select("div.module-downlist div.module-row-info a[title].btn-down")

            seen_titles = set()
            seen_links = set()
            down_urls = []

            for a_tag in a_tags:
                title = a_tag['title'].strip()
                if ".torrent" not in title:
                    continue
                link = a_tag['href'].strip()
                if not link.startswith("http"):
                    link = f"{self.spider_url}/{link}"
                if title in seen_titles or link in seen_links:
                    logger.debug(f"{self.spider_name}-跳过重复项: {title} / {link}")
                    continue
                seen_titles.add(title)
                seen_links.add(link)
                down_urls.append(link)

            if not down_urls:
                return False, []
            logger.info(f"{self.spider_name}-详情页解析完成，共找到 {len(down_urls)} 个下载链接")
            results = []
            with ThreadPoolExecutor(max_workers=min(8, len(down_urls))) as executor:
                futures = [executor.submit(self._parse_torrent, url) for url in down_urls]
                for future in as_completed(futures):
                    state, data = future.result()
                    if state:
                        results.append(data)
            return True, results

        except Exception as e:
            logger.error(f"{self.spider_name}-处理详情页失败: {str(e)}")
            return False, []

    def _parse_torrent(self, down_url):
        try:
            logger.info(f"{self.spider_name}-解析下载页: {down_url}")
            response = self.spider_proxy_client.request('GET', down_url)
            if response.status_code != 200:
                return False, None

            soup = BeautifulSoup(response.text, "html.parser")
            info_main = soup.select_one("div.box.view-heading.tinfo div.video-info-main")
            if not info_main:
                logger.warning(f"{self.spider_name}-找不到视频信息块")
                return False, None

            title = info_main.select_one("span.video-info-itemtitle + div.video-info-item")
            title = title.get_text(strip=True) if title else ""
            title = title[1:] if title.startswith("/") else title

            torrent_hash = info_main.select_one(
                "span.video-info-itemtitle:-soup-contains('Hash:') + div.video-info-item")
            torrent_hash = torrent_hash.get_text(strip=True) if torrent_hash else ""

            size = info_main.select_one("span.video-info-itemtitle:-soup-contains('影片大小:') + div.video-info-item")
            size = size.get_text(strip=True) if size else "0"

            publish_time = info_main.select_one(
                "span.video-info-itemtitle:-soup-contains('种子时间:') + div.video-info-item")
            publish_time = publish_time.get_text(strip=True) if publish_time else ""

            enclosure = ""
            magnet = soup.select_one("div.video-info-footer.display a[href]:not([target='_blank'])")
            if magnet and magnet['href'].startswith('magnet:?'):
                enclosure = magnet['href'].strip()
            else:
                for a in soup.select("div.video-info-footer.display a[href][target='_blank']"):
                    href = a['href'].strip()
                    enclosure = href if href.startswith("http") else f"{self.spider_url}{href}"
                    break

            if not enclosure:
                logger.warning(f"{self.spider_name}-未获取到有效下载链接")
                return False, None

            result = {
                "title": title,
                "enclosure": enclosure,
                "description": f"{title} | 大小: {size} | 时间: {publish_time} | Hash: {torrent_hash}",
                "page_url": down_url,
                "size": StringUtils.num_filesize(size),
                "pubdate": publish_time
            }

            logger.info(f"{self.spider_name}-成功解析: {title}")
            return True, result
        except Exception as e:
            logger.error(f"{self.spider_name}-解析下载链接失败: {str(e)}", exc_info=True)
            return False, None


if __name__ == "__main__":
    lou = BtBtlSpider({
        'spider_proxy': True,
        'spider_enable': True,
        'spider_name': 'BtBtlSpider',
        'proxy_type': 'flaresolverr',
        'proxy_config': {
            'flaresolverr_url': 'http://192.168.68.116:8191'
        },
        'request_interval': (1, 3)  # 设置随机请求间隔，最小2秒，最大5秒
    })
    # 使用直接请求
    rest = lou.search("藏海传", 1)
    print(rest)
