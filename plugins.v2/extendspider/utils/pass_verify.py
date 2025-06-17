import random

from DrissionPage._pages.chromium_page import ChromiumPage
from DrissionPage._pages.chromium_tab import ChromiumTab
from DrissionPage._pages.mix_tab import MixTab
from bs4 import BeautifulSoup

from app.log import logger


def is_slider_verification_page(html: str) -> bool:
    """
    判断当前页面是否为滑块验证页面

    :param html: 页面源代码
    :return: 如果页面包含特定的验证码标识，则返回True，否则返回False
    """
    return (
            ('GOEDGE_WAF_CAPTCHA_ID' in html and
             'ui-handler' in html) or
            '滑动上面方块到右侧解锁' in html
    )


def pass_slider_verification(tab: ChromiumPage | MixTab | ChromiumTab):
    """
    处理滑块验证

    :param tab: 浏览器标签页对象，用于操作网页
    :return: 如果未触发验证或验证通过，则返回True，否则返回False
    """
    tab1 = tab.latest_tab
    # 检查当前页面是否为验证页面
    if not tab1 or not is_slider_verification_page(tab1.html):
        return True
    logger.info("触发滑块验证码，正在处理...")
    # 获取滑块起始和结束位置
    handler = tab1.ele("#handler")
    if not handler:
        return True
    input_box = tab1.ele("#input")
    # 定位滑块元素并鼠标左键按住
    tab1.actions.hold(handler)
    # 定位class变化后的滑块元素并向右拖动500像素
    tab1.actions.hold(handler).right(500).release()
    tab1.wait(0.5, 2.5)
    # 再次校验页面是否仍为验证页面
    return not is_slider_verification_page(tab1.html)


def is_cloud_flare_verification_page(html: str) -> bool:
    """
    判断页面是否为 Cloudflare 的验证页（如5秒盾、Turnstile验证码等）
    """
    soup = BeautifulSoup(html, "html.parser")

    # 特征 1：标题
    title = soup.title.string.strip().lower() if soup.title and soup.title.string else ""
    if "just a moment..." in title or "checking your browser" in title:
        return True

    # 特征 2：iframe 指向 challenges.cloudflare.com
    if soup.find("iframe", src=lambda s: s and "challenges.cloudflare.com" in s):
        return True

    # 特征 4：页面内包含 Turnstile 验证容器
    if soup.find(attrs={"data-testid": "challenge-widget-container"}) or 'cf-turnstile-response' in html:
        return True

    return False


def pass_turnstile_verification(driver: ChromiumPage, headless: bool = True):
    if not driver or not is_cloud_flare_verification_page(driver.html):
        return True
    display = None
    try:
        if headless:
            from pyvirtualdisplay import Display
            display = Display(visible=False, size=(1920, 1080))
            display.start()
        # Where the bypass starts
        logger.info('Starting Cloudflare bypass.')
        cf_bypasser = CloudflareBypasser(driver)

        # If you are solving an in-page captcha (like the one here: https://seleniumbase.io/apps/turnstile), use cf_bypasser.click_verification_button() directly instead of cf_bypasser.bypass().
        # It will automatically locate the button and click it. Do your own check if needed.
        cf_bypasser.bypass()

        logger.info("Enjoy the content!")
        logger.info("Title of the page: %s", driver.title)

        # Sleep for a while to let the user see the result if needed
        time.sleep(5)
        return True
    except Exception as e:
        logger.error("An error occurred: %s", str(e))
    finally:
        if display:
            display.stop()
    return False


def pass_cloud_flare_verification(tab: MixTab):
    """
    处理滑块验证

    :param tab: 浏览器标签页对象，用于操作网页
    :return: 如果未触发验证或验证通过，则返回True，否则返回False
    """
    # 检查当前页面是否为验证页面
    if not tab or not is_cloud_flare_verification_page(tab.html):
        return True
    logger.info("触发CloudFlare验证码，正在处理...")
    max_retries = 5
    retries = 0
    if not tab.wait.ele_displayed("x://iframe", timeout=25):
        return False
    while retries < max_retries:
        try:
            if tab.ele('x://div[@id="eIfwt6"]', timeout=15):
                # 查找并操作 iframe 中的复选框
                iframe = tab.ele('x://div[@id="eIfwt6"]/div/div').sr('x://iframe', timeout=15)  # 获取 iframe 元素
                tab.stop_loading()
                if iframe:
                    # 尝试获取 body 元素和复选框元素
                    body = iframe.ele('x://body', timeout=15)
                    if body:
                        checkbox = body.sr('x://input[@type="checkbox"]', timeout=15)
                        if checkbox:
                            screen_x, screen_y = checkbox.rect.screen_location
                            page_x, page_y = tab.rect.page_location
                            width, height = checkbox.rect.size
                            offset_x, offset_y = generate_biased_random(
                                int(width - 1)
                            ), generate_biased_random(int(height - 1))

                            click_x, click_y = (
                                screen_x + page_x + offset_x,
                                screen_y + page_y + offset_y,
                            )

                            logger.info(
                                f"[CloudflareBypass.try_to_click_challenge] Screen point [{screen_x}, {screen_y}]"
                            )
                            logger.info(
                                f"[CloudflareBypass.try_to_click_challenge] Page point[{page_x}, {page_y}]"
                            )
                            logger.info(
                                f"[CloudflareBypass.try_to_click_challenge] Click point [{click_x}, {click_y}]"
                            )
                            import pyautogui
                            pyautogui.moveTo(
                                click_x, click_y, duration=2, tween=pyautogui.easeInElastic
                            )
                            pyautogui.click()
                            # tab.actions.move_to(checkbox, duration=2)
                            # tab.actions.click(checkbox)
                            print("复选框可点击")
                            # checkbox.click()
                            print("已点击 Cloudflare 验证框")
                            # tab.wait(3)
                            break  # 成功点击后跳出循环
                    else:
                        print("iframe 内部的 body 元素未找到")
                        break  # 如果 body 元素没有找到，则跳出循环
        finally:
            retries += 1

    # 2024-07-05
    # 直接在element上执行click(通过CDP协议)无法通过cloudflare challenge
    # 原因:
    # CDP命令执行的event中client_x, client_y与screen_x, screen_y是一样的，而手动点击触发的事件两者是不一样的,所以无法使用CDP模拟出鼠标点击通过验证
    # 解决方法:
    # 先获取点击的坐标，使用pyautogui模拟鼠标点击
    # CDP参考 https://chromedevtools.github.io/devtools-protocol/tot/Input/
    # verify_element.click()
    tab.wait.load_start(timeout=20)
    # 再次校验页面是否仍为验证页面
    return not is_cloud_flare_verification_page(tab.html)


def generate_biased_random(n):
    weights = [min(i, n - i + 1) for i in range(1, n + 1)]
    return random.choices(range(1, n + 1), weights=weights)[0]


import time
from DrissionPage import ChromiumPage


class CloudflareBypasser:
    def __init__(self, driver: ChromiumPage, max_retries=-1, log=True):
        self.driver = driver
        self.max_retries = max_retries
        self.log = log

    def search_recursively_shadow_root_with_iframe(self, ele):
        if ele.shadow_root:
            if ele.shadow_root.child().tag == "iframe":
                return ele.shadow_root.child()
        else:
            for child in ele.children():
                result = self.search_recursively_shadow_root_with_iframe(child)
                if result:
                    return result
        return None

    def search_recursively_shadow_root_with_cf_input(self, ele):
        if ele.shadow_root:
            if ele.shadow_root.ele("tag:input"):
                return ele.shadow_root.ele("tag:input")
        else:
            for child in ele.children():
                result = self.search_recursively_shadow_root_with_cf_input(child)
                if result:
                    return result
        return None

    def locate_cf_button(self):
        button = None
        eles = self.driver.eles("tag:input")
        for ele in eles:
            if "name" in ele.attrs.keys() and "type" in ele.attrs.keys():
                if "turnstile" in ele.attrs["name"] and ele.attrs["type"] == "hidden":
                    button = ele.parent().shadow_root.child()("tag:body").shadow_root("tag:input")
                    break

        if button:
            return button
        else:
            # If the button is not found, search it recursively
            self.log_message("Basic search failed. Searching for button recursively.")
            ele = self.driver.ele("tag:body")
            iframe = self.search_recursively_shadow_root_with_iframe(ele)
            if iframe:
                button = self.search_recursively_shadow_root_with_cf_input(iframe("tag:body"))
            else:
                self.log_message("Iframe not found. Button search failed.")
            return button

    def log_message(self, message):
        if self.log:
            print(message)

    def click_verification_button(self):
        try:
            button = self.locate_cf_button()
            if button:
                self.log_message("Verification button found. Attempting to click.")
                button.click()
            else:
                self.log_message("Verification button not found.")

        except Exception as e:
            self.log_message(f"Error clicking verification button: {e}")

    def is_bypassed(self):
        try:
            title = self.driver.title.lower()
            return "just a moment" not in title
        except Exception as e:
            self.log_message(f"Error checking page title: {e}")
            return False

    def bypass(self):

        try_count = 0

        while not self.is_bypassed():
            if 0 < self.max_retries + 1 <= try_count:
                self.log_message("Exceeded maximum retries. Bypass failed.")
                break

            self.log_message(f"Attempt {try_count + 1}: Verification page detected. Trying to bypass...")
            self.click_verification_button()

            try_count += 1
            time.sleep(2)

        if self.is_bypassed():
            self.log_message("Bypass successful.")
        else:
            self.log_message("Bypass failed.")
