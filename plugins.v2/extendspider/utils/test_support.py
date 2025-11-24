from time import sleep
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page
from cf_clearance import sync_cf_retry, sync_stealth

from app.core.config import settings
from app.log import logger
from app.plugins.extendspider.utils.browser import create_drission_chromium
from app.plugins.extendspider.utils.pass_verify import pass_cloud_flare_verification, pass_turnstile_verification
from app.plugins.extendspider.utils.proxy import FlareSolverrProxy


def __pass_cloudflare(url: str, page: Page) -> bool:
    """
    尝试跳过cloudfare验证
    """
    sync_stealth(page, pure=True)
    page.goto(url)
    return sync_cf_retry(page)[0]


def main():
    main_url = "https://www.1lou.me/"
    keyword = "藏海传"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(user_agent=settings.USER_AGENT)
            page = context.new_page()

            try:
                # 访问主页并处理 Cloudflare
                if not __pass_cloudflare(main_url, page):
                    logger.warn("cloudflare challenge fail！")
                    return

                # 等待页面加载完成
                page.wait_for_load_state("networkidle", timeout=30 * 1000)
                logger.info(f"访问主页成功,开始搜索【{keyword}】...")
                sleep(0.6)
                # 执行搜索
                page.fill("input[name='keyword'][placeholder='关键词'].keyword", keyword)
                page.click("button[type='submit'].btn")
                page.wait_for_load_state("networkidle", timeout=30 * 1000)
                content = page.content()
                soup = BeautifulSoup(content, "html.parser")
                # 解析搜索结果
                logger.info(f"{main_url}支持搜索，开始解析结果...")
            except Exception as e:
                logger.error(f"搜索过程发生错误: {str(e)}")
            finally:
                browser.close()

    except Exception as e:
        logger.error(f"Playwright 初始化失败: {str(e)}")


def _get_cookie_and_ua(url: str):
    spider_proxy_client = FlareSolverrProxy(
        flaresolverr_url=settings.FLARESOLVERR_URL,
        session_id="test1"
    )

    # 发请求获取 cookies
    response = spider_proxy_client.request('GET', url)

    if not response.cookies:
        return [], ""

    parsed_url = urlparse(url)
    domain = parsed_url.hostname

    cookies = []
    for cookie in response.cookies:
        cookies.append({
            "name": cookie.name,
            "value": cookie.value,
            "domain": domain,
            "path": cookie.path or "/",
            "secure": cookie.secure,
            "httpOnly": getattr(cookie, "rest", {}).get("HttpOnly", False),
            "expires": cookie.expires if cookie.expires else -1  # Playwright 允许 -1 表示会话 cookie
        })

    return cookies, response.user_agent


def test_drission_page():
    # cookies, ua = _get_cookie_and_ua("https://www.1lou.me/")
    browser = create_drission_chromium(headless=True)
    # browser.set.cookies(cookies)
    tab1 = browser.latest_tab
    try:
        # tab1.set.cookies(cookies)
        tab1.set.load_mode.none()  # 设置加载模式为none

        tab1.get("https://www.dmit.io/cloudflare")
        # ele = tab1.ele('#search_form', timeout=20)  # 查找text包含“中国日报”的元素
        # tab1.stop_loading()  # 主动停止加载
        if not pass_turnstile_verification(tab1, True):
            print("验证失败")
            return

        # 初始化一个空字符串，用于拼接页面的cookie信息
        cookies = ''
        # 遍历页面获取到的所有cookie信息，每个cookie是一个字典形式，包含'name'（名称）和'value'（值）等字段
        for i in tab1.cookies():
            name = i['name']
            value = i['value']
            # 将每个cookie的名称和值按照'name=value;'的格式拼接起来
            cookies += f'{name}={value};'
        tab1.listen.start("api/v1/getVideoList")
        # 滚动到页面底部以触发更多数据加载
        tab1.scroll.to_bottom()

        tab1.get("https://www.6bt0.com/search?sb=%E8%97%8F%E6%B5%B7%E4%BC%A0")
        i = 0
        for packet in tab1.listen.steps():
            print(packet.url)  # 打印数据包url
            i += 1
            if i == 5:
                break
    finally:
        browser.quit()

def test_mouse():
    from DrissionPage import Chromium, ChromiumOptions
    import time
    import os
    co = ChromiumOptions()
    co.auto_port()

    co.set_timeouts(base=1)

    # change this to the path of the folder containing the extension
    EXTENSION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "turnstilePatch"))
    co.add_extension(EXTENSION_PATH)

    # uncomment this if you want to use headless mode
    """
    co.headless()

    from sys import platform
    if platform == "linux" or platform == "linux2":
        platformIdentifier = "X11; Linux x86_64"
    elif platform == "darwin":
        platformIdentifier = "Macintosh; Intel Mac OS X 10_15_7"
    elif platform == "win32":
        platformIdentifier = "Windows NT 10.0; Win64; x64"

    co.set_user_agent(f"Mozilla/5.0 ({platformIdentifier}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
    """

    browser = Chromium(co)
    page = browser.get_tabs()[-1]
    page.get("https://wuqiangb.top")

    def getTurnstileToken():
        page.run_js("try { turnstile.reset() } catch(e) { }")

        turnstileResponse = None

        for i in range(0, 15):
            try:
                turnstileResponse = page.run_js("try { return turnstile.getResponse() } catch(e) { return null }")
                if turnstileResponse:
                    return turnstileResponse

                challengeSolution = page.ele("@name=cf-turnstile-response")
                challengeWrapper = challengeSolution.parent()
                challengeIframe = challengeWrapper.shadow_root.ele("tag:iframe")
                challengeIframeBody = challengeIframe.ele("tag:body").shadow_root
                challengeButton = challengeIframeBody.ele("tag:input")
                challengeButton.click()
            except:
                pass
            time.sleep(1)
        page.refresh()
        raise Exception("failed to solve turnstile")

    while True:
        print(getTurnstileToken())
if __name__ == "__main__":
    test_mouse()
