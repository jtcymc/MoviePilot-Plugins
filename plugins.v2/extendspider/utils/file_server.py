import os
from abc import abstractmethod, ABC
from typing import Dict, Any, Tuple
from urllib.parse import urlparse, unquote
import requests
from app.log import logger
from app.utils.common import retry
from app.utils.ratelimit import rate_limit


class FileServer(ABC):
    def __init__(self, url) -> None:
        self.url = url.rstrip('/')
        self.server = None

    @abstractmethod
    def upload_file(self, file_path: str) -> Dict[str, str]:
        """获取请求头"""
        pass

    def upload_file_by_yrl(self, url: str, dir_path: str) -> Dict[str, str]:
        """获取请求头"""
        # 先下载文件

        # 再上传
        return self.upload_file(url)

    def _download_file(self, url: str, save_path: str, timeout: int = 30) -> Dict[str, Any]:
        """下载远程文件到本地"""
        try:
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()

            # 获取实际下载的文件名
            content_disposition = response.headers.get('content-disposition')
            downloaded_filename = "downloaded_file"

            if content_disposition and 'filename=' in content_disposition:
                downloaded_filename = content_disposition.split('filename=')[1].strip('"\'')
            else:
                # 如果没有在响应头中找到文件名，从URL解析
                parsed_url = urlparse(url)
                filename = os.path.basename(parsed_url.path)
                if filename:
                    downloaded_filename = filename

            # 确保有文件扩展名
            if '.' not in downloaded_filename:
                _, ext = os.path.splitext(url)
                if ext:
                    downloaded_filename += ext

            # 保存完整路径
            full_save_path = os.path.join(save_path, downloaded_filename)

            # 下载文件
            with open(full_save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return {
                "success": True,
                "file_path": full_save_path,
                "file_name": downloaded_filename
            }
        except Exception as e:
            logger.error(f"下载文件失败：{str(e)}")
            return {"success": False, "error": f"下载失败：{str(e)}"}


class FileCodeBox(FileServer):
    def __init__(self, url) -> None:
        super().__init__(url)
        self.server = "filecodebox"
    @rate_limit(max_calls=3, time_window=10, min_interval=5, raise_on_limit=False, wait_on_limit=True, max_wait_time=20)
    @retry(Exception, 2, 2, 2, logger=logger)
    async def upload_file(self, file_path: str, expire_value: int = 1, expire_style: str = 'day') -> Tuple[
        bool, str, str]:
        """
        上传文件到文件共享服务并返回分享信息

        Args:
            file_path (str): 要上传的文件路径
            expire_value (int): 过期时间值
            expire_style (str): 过期单位，可选 'day', 'hour', 'minute'

        Returns:
            Tuple[bool, str, str]: (成功与否, 文件名, 分享链接)
        """
        url = f"{self.url}/share/file/"
        if not os.path.isfile(file_path):
            logger.error(f"文件不存在: {file_path}")
            return False, "", ""

        try:
            import aiofiles
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with aiofiles.open(file_path, 'rb') as f:
                    file_content = await f.read()
                if len(file_content) <= 0:
                    return False, "", ""
                form = aiohttp.FormData()
                form.add_field('file',
                               file_content,
                               filename=os.path.basename(file_path),
                               content_type='application/octet-stream')
                form.add_field('expire_value', str(expire_value))
                form.add_field('expire_style', str(expire_style))
                headers = {
                    'Accept': 'application/json',

                }
                # 发起 POST 请求
                async with session.post(url, data=form, headers=headers) as response:
                    if response.status == 200:
                        res = await response.json()
                        if res.get("code") == 200 and "detail" in res:
                            code = res["detail"].get("code", "")
                            name = unquote(res["detail"].get("name", ""))
                            share_link = f"{self.url}/share/select?code={code}"
                            logger.info(f"文件上传成功: {name}, 分享链接: {share_link}")
                            return True, name, share_link
                        else:
                            logger.warning(f"接口返回异常数据: {res}")
                    else:
                        logger.warning(f"上传失败，状态码: {response.status}, 响应: {await response.text()}")

        except Exception as e:
            logger.error(f"上传文件失败: {e}")

        return False, "", ""
