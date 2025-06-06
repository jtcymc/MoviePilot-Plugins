from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from app.core.config import settings
from playwright_stealth import stealth_sync

def create_browser(proxy: bool = False) -> tuple[Browser, BrowserContext]:
    """
    创建浏览器实例和上下文
    
    Args:
        proxy: 是否使用代理
        
    Returns:
        tuple[Browser, BrowserContext]: 浏览器实例和上下文
    """
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=True,
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
            '--disable-gpu'
        ]
    )
    
    context = browser.new_context(
        user_agent=settings.USER_AGENT,
        proxy=settings.PROXY_SERVER if proxy else None,
        viewport={'width': 1920, 'height': 1080},
        locale='zh-CN',
        timezone_id='Asia/Shanghai',
        device_scale_factor=1,
        has_touch=False,
        is_mobile=False,
        java_script_enabled=True,
        ignore_https_errors=True,
        permissions=['geolocation'],
        extra_http_headers={
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        },
    )
    
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