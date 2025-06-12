import os

from DrissionPage import ChromiumPage, ChromiumOptions, Chromium
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, ViewportSize
from app.core.config import settings
from playwright_stealth import stealth_sync

from app.log import logger


def create_browser(proxy: bool = False, headless: bool = True) -> tuple[Browser, BrowserContext]:
    """
    创建浏览器实例和上下文
    
    Args:
        proxy: 是否使用代理
        headless: 无头模式
        
    Returns:
        tuple[Browser, BrowserContext]: 浏览器实例和上下文
    """
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=headless,
        slow_mo=60,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-site-isolation-trials',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-software-rasterize',
            '--enable-javascript',
            '--enable-scripts',
            '--enable-javascript-harmony'
        ]
    )

    context = browser.new_context(
        user_agent=settings.USER_AGENT,
        proxy=settings.PROXY_SERVER if proxy else None,
        viewport=ViewportSize({'width': 1920, 'height': 1080}),
        locale='zh-CN',
        timezone_id='Asia/Shanghai',
        device_scale_factor=1,
        has_touch=False,
        is_mobile=False,
        java_script_enabled=True,
        ignore_https_errors=True,
    )

    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
        Object.defineProperty(navigator, 'platform', { get: () => 'Linux armv8l' });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    """)

    return browser, context


def create_stealth_page(context: BrowserContext) -> Page:
    """
    创建带有反检测功能的页面
    
    Args:
        context: 浏览器上下文
        
    Returns:
        Page: 页面实例
    """
    page = context.new_page()
    stealth_sync(page)
    return page


def create_drission_chromium(proxy: bool = False, headless: bool = True) -> Chromium:
    """
    创建带有反检测功能的页面

    Args:
        proxy: 是否使用代理
        headless: 无头模式

    Returns:
        ChromiumPage: 页面实例
    """
    co = ChromiumOptions()
    co.headless(headless)
    # 设置代理
    if proxy:
        co.set_proxy(settings.PROXY_HOST)
    # 匿名模式
    co.incognito()
    co.set_user_agent(settings.USER_AGENT)
    # 无沙盒模式
    co.set_argument('--no-sandbox')
    # 禁用gpu，提高加载速度
    co.set_argument('--disable-gpu')
    path = find_chromium_path()
    if is_running_in_docker() and path:
        logger.info(f"使用自定义的 Chromium 路径：{path}")
        co.set_browser_path(path)
    return Chromium(co)


def is_running_in_docker():
    try:
        # 方式一：检查特殊文件
        if os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv'):
            return True
        # 方式二：检查 cgroup 内容
        with open('/proc/1/cgroup', 'rt') as f:
            content = f.read()
            return 'docker' in content or 'kubepods' in content or 'containerd' in content
    except Exception as _:
        return False


def find_chromium_path():
    # 优先使用环境变量指定的路径
    custom_path = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH")
    if custom_path and os.path.exists(custom_path):
        return custom_path
    search_paths = "/moviepilot/.cache/ms-playwright"

    for base in search_paths:
        if os.path.exists(base):
            for name in os.listdir(base):
                if name.startswith("chromium-"):
                    chromium_path = os.path.join(base, name, "chrome")
                    if os.path.exists(chromium_path):
                        return chromium_path

    return None
