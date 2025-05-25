import urllib.parse
from urllib.parse import unquote, parse_qs, urlparse


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
