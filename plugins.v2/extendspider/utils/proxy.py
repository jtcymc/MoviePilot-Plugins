import json
from abc import ABC, abstractmethod
from http.cookiejar import CookieJar, Cookie
import requests
from typing import Optional, Dict, Tuple
from requests.models import Response
from requests.structures import CaseInsensitiveDict
import time
import random
from app.log import logger

class ProxyBase(ABC):
    """代理基类"""

    def __init__(self, request_interval: Tuple[float, float] = (0, 0)):
        """
        初始化代理基类
        :param request_interval: 请求间隔时间范围（秒），格式为 (最小间隔, 最大间隔)
        """
        self._min_interval, self._max_interval = request_interval
        self._last_request_time = 0

    def _wait_for_interval(self):
        """等待请求间隔"""
        if self._max_interval > 0:
            current_time = time.time()
            elapsed = current_time - self._last_request_time
            if elapsed < self._min_interval:
                # 生成随机等待时间
                wait_time = random.uniform(self._min_interval, self._max_interval)
                time.sleep(wait_time - elapsed)
            self._last_request_time = time.time()

    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        pass

    @abstractmethod
    def get_proxy(self) -> Optional[Dict[str, str]]:
        """获取代理配置"""
        pass

    @abstractmethod
    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """发送请求"""
        pass


class DirectProxy(ProxyBase):
    """直接请求代理"""

    def __init__(self, headers: Dict[str, str] = None, request_interval: Tuple[float, float] = (0, 0)):
        super().__init__(request_interval)
        self._headers = headers or {}

    def get_headers(self) -> Dict[str, str]:
        return self._headers

    def get_proxy(self) -> Optional[Dict[str, str]]:
        return None

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        self._wait_for_interval()
        headers = {**self._headers, **kwargs.get('headers', {})}
        return requests.request(method, url, headers=headers, **kwargs)


class FlareSolverrProxy(ProxyBase):
    """FlareSolverr代理"""

    def __init__(self, flaresolverr_url: str, session_id: str = None, headers: Dict[str, str] = None,
                 request_interval: Tuple[float, float] = (0, 0)):
        super().__init__(request_interval)
        self._flaresolverr_url = flaresolverr_url
        self._headers = headers or {}
        self._session_id = session_id

    def get_headers(self) -> Dict[str, str]:
        return self._headers

    def get_proxy(self) -> Optional[Dict[str, str]]:
        return None

    def _create_session(self) -> None:
        """创建FlareSolverr会话"""
        self._wait_for_interval()
        response = requests.post(
            f"{self._flaresolverr_url}/v1",
            json={
                "cmd": "sessions.create",
                "session": self._session_id if self._session_id else "moviepilot"
            }
        )
        if response.status_code == 200:
            self._session_id = response.json().get("session")

    def _destroy_session(self) -> None:
        """销毁FlareSolverr会话"""
        if not self._session_id:
            return

        self._wait_for_interval()
        try:
            response = requests.post(
                f"{self._flaresolverr_url}/v1",
                json={
                    "cmd": "sessions.destroy",
                    "session": self._session_id
                }
            )
            if response.status_code == 200:
                self._session_id = None
        except Exception as e:
            logger.error(f"销毁会话失败: {str(e)}")

    @staticmethod
    def _parse_cookies(cookies_list: list) -> CookieJar:
        """解析cookie列表为CookieJar对象"""
        cookie_jar = CookieJar()
        if not cookies_list:
            return cookie_jar

        for cookie_dict in cookies_list:
            try:
                cookie = Cookie(
                    version=0,
                    name=cookie_dict.get('name', ''),
                    value=cookie_dict.get('value', ''),
                    port=None,
                    port_specified=False,
                    domain=cookie_dict.get('domain', ''),
                    domain_specified=True,
                    domain_initial_dot=cookie_dict.get('domain', '').startswith('.'),
                    path=cookie_dict.get('path', '/'),
                    path_specified=True,
                    secure=cookie_dict.get('secure', False),
                    expires=cookie_dict.get('expiry'),
                    discard=False,
                    comment=None,
                    comment_url=None,
                    rest={
                        'httpOnly': cookie_dict.get('httpOnly', False),
                        'sameSite': cookie_dict.get('sameSite', 'Lax')
                    }
                )
                cookie_jar.set_cookie(cookie)
            except Exception as e:
                logger.error(f"解析cookie失败: {str(e)}")
        return cookie_jar

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """发送请求到FlareSolverr"""
        if not self._session_id:
            self._create_session()

        data = kwargs.get('json', {}) or kwargs.get('data', {})

        request_data = {
            "cmd": "request.get" if method.upper() == "GET" else "request.post",
            "session": self._session_id,
            "url": url,
        }

        # 添加请求体数据
        if method.upper() == "POST":
            if isinstance(data, dict):
                request_data["postData"] = json.dumps(data)
            else:
                request_data["postData"] = str(data)

        response = requests.post(
            f"{self._flaresolverr_url}/v1",
            json=request_data
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "ok":
                solution = result.get("solution", {})
                # 创建一个新的Response对象
                new_response = Response()
                new_response.status_code = solution.get("status", 200)
                new_response._content = solution.get("response", "").encode('utf-8')
                new_response.encoding = 'utf-8'
                new_response.headers = CaseInsensitiveDict(solution.get("headers", {}))
                # 处理cookies
                cookies_list = solution.get("cookies", [])
                new_response.cookies = self._parse_cookies(cookies_list)

                new_response.url = url
                return new_response

        return response

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """发送请求"""
        try:
            self._wait_for_interval()
            return self._make_request(method, url, **kwargs)
        except Exception as e:
            logger.error(f"请求失败: {str(e)}")
            # 如果请求失败，尝试重新创建会话
            self._destroy_session()
            self._create_session()
            return self._make_request(method, url, **kwargs)

    def __del__(self):
        """析构函数，确保会话被销毁"""
        self._destroy_session()


class ProxyFactory:
    """代理工厂类"""

    @staticmethod
    def create_proxy(proxy_type: str, **kwargs) -> ProxyBase:
        """
        创建代理实例
        :param proxy_type: 代理类型 ('direct' 或 'flaresolverr')
        :param kwargs: 代理配置参数
        :return: 代理实例
        """
        if proxy_type == 'direct':
            return DirectProxy(**kwargs)
        elif proxy_type == 'flaresolverr':
            return FlareSolverrProxy(**kwargs)
        else:
            raise ValueError(f"不支持的代理类型: {proxy_type}")
