import os

from DrissionPage import ChromiumPage, ChromiumOptions
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, ViewportSize
from app.core.config import settings
from playwright_stealth import stealth_sync
from app.log import logger
from utils.system import SystemUtils


def create_browser(proxy: bool = False, headless: bool = True, ua=None) -> tuple[Browser, BrowserContext]:
    """
    创建浏览器实例和上下文

    Args:
        proxy: 是否使用代理
        headless: 无头模式
        ua: user-agent
    Returns:
        tuple[Browser, BrowserContext]: 浏览器实例和上下文
    """
    playwright = sync_playwright().start()
    args = [
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
        '--enable-javascript-harmony',
        '--no-sandbox'
    ]
    if SystemUtils.is_docker():
        args.append('--headless=new')
    browser = playwright.chromium.launch(
        headless=headless,
        slow_mo=60,
        args=args,
    )

    context = browser.new_context(
        user_agent=ua or settings.USER_AGENT,
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


def create_drission_chromium(proxy: bool = False, headless: bool = True, ua=None) -> ChromiumPage:
    """
    创建带有反检测功能的页面

    Args:
        proxy: 是否使用代理
        headless: 无头模式
        ua: 指纹

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
    co.set_user_agent(ua or settings.USER_AGENT)
    # Arguments to make the browser better for automation and less detectable.
    arguments = [
        # "--no-first-run",
        # "--force-color-profile=srgb",
        # "--metrics-recording-only",
        # "--password-store=basic",
        # "--use-mock-keychain",
        # "--export-tagged-pdf",
        # "--no-default-browser-check",
        # "--disable-background-mode",
        # "--enable-features=NetworkService,NetworkServiceInProcess,LoadCryptoTokenExtension,PermuteTLSExtensions",
        # "--disable-features=FlashDeprecationWarning,EnablePasswordsAccountStorage",
        # "--deny-permission-prompts",
        "--disable-gpu",  # 禁用gpu，提高加载速度
        "--no-sandbox",
        # "---accept-lang=en-US",

    ]
    # 阻止“自动保存密码”的提示气泡
    co.set_pref('credentials_enable_service', False)

    # 阻止“要恢复页面吗？Chrome未正确关闭”的提示气泡
    co.set_argument('--hide-crash-restore-bubble')
    if SystemUtils.is_docker():
        arguments.append('--headless=new')
    for argument in arguments:
        co.set_argument(argument)
    path = find_chromium_path()
    logger.info(f"使用自定义的 Chromium 路径：{path}")
    if path:
        co.set_browser_path(path)
    co.auto_port()
    return ChromiumPage(co)


def find_chromium_path():
    if not SystemUtils.is_docker():
        return None
    logger.info("正在寻找Docker容器中 Chromium 浏览器路径...")
    # usr_path = "/usr/bin/google-chrome"
    # if os.path.exists(usr_path):
    #     return usr_path
    search_paths = "/moviepilot/.cache/ms-playwright"
    if os.path.exists(search_paths):
        for name in os.listdir(search_paths):
            if name.startswith("chromium-"):
                chromium_path = os.path.join(search_paths, name, "chrome-linux", "chrome")
                if os.path.exists(chromium_path):
                    return chromium_path
    return None
