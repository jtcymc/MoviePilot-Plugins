from time import sleep


from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page
from cf_clearance import sync_cf_retry, sync_stealth

from app.core.config import settings
from app.log import logger
from plugins.extendspider.utils.browser import create_drission_chromium
from plugins.extendspider.utils.pass_verify import pass_cloud_flare_verification


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


def test_drission_page():
    browser = create_drission_chromium(headless=False)
    tab1 = browser.latest_tab
    try:
        tab1.get("https://www.1lou.me/")
        tab1.wait(2)
        if not pass_cloud_flare_verification(tab1):
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
        tab1.close()
        browser.quit()


if __name__ == "__main__":
    test_drission_page()
