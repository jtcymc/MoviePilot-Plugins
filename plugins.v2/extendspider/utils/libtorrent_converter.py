import libtorrent as lt

from log import logger


def get_simple_magnet(torrent_file):
    """
    从种子文件生成简洁版磁力链接

    Args:
        torrent_file: 种子文件路径

    Returns:
        str: 简洁版磁力链接
    """
    import os
    if not os.path.isfile(torrent_file):
        logger.error(f"文件不存在: {torrent_file}")
        return ""
    try:
        # 读取种子文件信息
        info = lt.torrent_info(torrent_file)

        # 获取磁力链接
        magnet_uri = lt.make_magnet_uri(info)

        return magnet_uri

    except Exception as e:
        logger.error(f"错误: {e}")
        return None


def get_minimal_magnet(torrent_file):
    """
    生成最简磁力链接（仅包含hash）

    Args:
        torrent_file: 种子文件路径

    Returns:
        str: 最简磁力链接
    """
    import os
    if not os.path.isfile(torrent_file):
        logger.error(f"文件不存在: {torrent_file}")
        return ""
    try:
        info = lt.torrent_info(torrent_file)
        info_hash = str(info.info_hash())
        magnet_link = f"magnet:?xt=urn:btih:{info_hash}"
        return magnet_link

    except Exception as e:
        logger.error(f"错误: {e}")
        return None


