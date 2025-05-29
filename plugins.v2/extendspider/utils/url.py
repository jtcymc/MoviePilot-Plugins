import re
import urllib.parse
from typing import Tuple, Optional
from urllib.parse import unquote, parse_qs, urlparse

import requests

from app.core.config import settings
from playwright.sync_api import  Page
from cf_clearance import sync_cf_retry, sync_stealth

from log import logger
from app.utils.ratelimit import rate_limit


def xn_url_encode(s):
    # 使用 encodeURIComponent 的 Python 等价操作
    s = urllib.parse.quote(s)

    # 替换字符为特定编码
    replacements = {
        '_': '%5f',
        '-': '%2d',
        '.': '%2e',
        '~': '%7e',
        '!': '%21',
        '*': '%2a',
        '(': '%28',
        ')': '%29',
        '%': '_'
    }

    for char, replacement in replacements.items():
        s = s.replace(char, replacement)

    return s
def pass_cloudflare(url: str, page: Page) -> bool:
    """
    尝试跳过cloudfare验证
    """
    sync_stealth(page, pure=True)
    page.goto(url)
    return sync_cf_retry(page)[0]

def xn_url_decode(s):
    # 将下划线替换回百分号
    s = s.replace('_', '%')

    # 解码 URL 编码
    decoded = urllib.parse.unquote(s)

    return decoded


def get_dn(magnet_link):
    parsed = urlparse(magnet_link)
    query_params = parse_qs(parsed.query)
    # 获取 dn 参数并解码
    return unquote(query_params.get('dn', [''])[0])

def format_episode_title(filename: str) -> Tuple[Optional[int], Optional[str]]:
    """ 已知 btdx8 btbuluo
    解析文件名中的剧集信息，并格式化为指定格式。
    仅支持至少两位数字的集数命名，并自动补零到两位显示：
    - 藏海传09.mp4      --> 藏海传[第09集].mp4
    - 藏海传12-.mp4     --> 藏海传[第12集].mp4

    :param filename: 原始文件名
    :return: (集数, 格式化后的文件名)
    """
    # 匹配至少两位数字开头，在扩展名前的部分（允许后缀非数字字符）
    match = re.search(r'(\d{2,}[a-zA-Z0-9\-]*)(?=\.\w+$)', filename)
    if match:
        episode_part = match.group(1)
        # 提取开头的至少两位数字作为集数
        episode_number_match = re.match(r'^\d{2,}', episode_part)
        if episode_number_match:
            episode_number = int(episode_number_match.group())
            # 格式化为两位数的字符串，不足补零
            formatted_episode = f"{episode_number:02d}"
            # 替换为指定格式
            formatted_filename = re.sub(
                r'\d{2,}[a-zA-Z0-9\-]*(?=\.\w+$)',
                f'[第{formatted_episode}集]',
                filename
            )
            return episode_number, formatted_filename

    return None, filename  # 如果没有找到匹配的两位以上数字，则返回原始文件名
whats_link = "https://whatslink.info/api/v1/link"

@rate_limit(
    max_calls=5,      # 10秒内最多调用10次
    time_window=60.0,  # 时间窗口为10秒
    min_interval=12.0,  # 两次调用之间至少间隔2秒
    wait_on_limit=True,    # 启用等待功能
    max_wait_time=60.0,    # 最多等待30秒
    raise_on_limit=True,   # 超时后抛出异常
    source="API调用",      # 自定义标识
    enable_logging=True    # 启用日志记录
)
def get_magnet_info_from_url(magnet_url: str):
    """
     查询磁力信息
    """
    if not magnet_url:
        return None
    if magnet_url.startswith("magnet:"):
        logger.debug(f"正在获取种子信息: {magnet_url}")
        res = requests.get(whats_link, params={"url": magnet_url}, headers={"User-Agent": settings.USER_AGENT})
        if res.status_code == 200:
            return res.json()
    return None


