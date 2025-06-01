from time import sleep

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page
from cf_clearance import sync_cf_retry, sync_stealth

from app.core.config import settings
from app.log import logger


def __pass_cloudflare(url: str, page: Page) -> bool:
    """
    尝试跳过cloudfare验证
    """
    sync_stealth(page, pure=True)
    page.goto(url)
    return sync_cf_retry(page)[0]

def main():
    main_url = "https://www.1lou.me/"
    keyword ="藏海传"
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

if __name__ == "__main__":
    main()