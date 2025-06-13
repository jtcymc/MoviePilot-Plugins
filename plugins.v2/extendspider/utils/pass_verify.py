import random
import time

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


def pass_slider_verification(tab: MixTab):
    """
    处理滑块验证

    :param tab: 浏览器标签页对象，用于操作网页
    :return: 如果未触发验证或验证通过，则返回True，否则返回False
    """
    # 检查当前页面是否为验证页面
    if not tab or not is_slider_verification_page(tab.html):
        return True
    logger.info("触发滑块验证码，正在处理...")
    # 获取滑块起始和结束位置
    handler = tab.ele("#handler")
    input_box = tab.ele("#input")
    # 定位滑块元素并鼠标左键按住
    tab.actions.hold(handler)
    # 定位class变化后的滑块元素并向右拖动500像素
    tab.actions.hold(handler).right(500).release()
    tab.wait(0.5, 2.5)
    # 再次校验页面是否仍为验证页面
    return not is_slider_verification_page(tab.html)


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
    # # e3.click()
    # # tab.refresh()
    # # tab.set.load_mode.none()  # 设置加载模式为none
    # # tab.wait.ele_displayed(".main-content", timeout=20)
    # wrapper = tab.ele(".main-content", timeout=5)
    # if not wrapper:
    #     return False
    # div1 = wrapper.ele("tag:div", timeout=5)
    # div2 = div1.ele("tag:div", timeout=5)
    #
    # # iframe = div2.shadow_root.ele("tag:iframe", timeout=15)
    # iframeRoot = div2.sr("t:iframe")
    # # iframeRoot = iframe("tag:body").shadow_root
    # cbLb = iframeRoot.ele(".cb-lb", timeout=5)
    #
    # # 获取位置
    # pos = cbLb.ele("tag:input", timeout=10).rect.screen_click_point
    #
    # tab.wait(2)
    #
    # # 移动鼠标
    # tab.actions.move(pos[0], pos[1] + 61, duration=0.5)
    # # 点击右键
    # tab.actions.click()
    wrapper = tab.ele(".cf-turnstile-wrapper")
    shadow_root = wrapper.shadow_root
    iframe = shadow_root.ele("tag=iframe", timeout=15)
    verify_element = iframe.ele("Verify you are human", timeout=25)
    time.sleep(random.uniform(2, 5))

    # 2024-07-05
    # 直接在element上执行click(通过CDP协议)无法通过cloudflare challenge
    # 原因:
    # CDP命令执行的event中client_x, client_y与screen_x, screen_y是一样的，而手动点击触发的事件两者是不一样的,所以无法使用CDP模拟出鼠标点击通过验证
    # 解决方法:
    # 先获取点击的坐标，使用pyautogui模拟鼠标点击
    # CDP参考 https://chromedevtools.github.io/devtools-protocol/tot/Input/
    # verify_element.click()
    def generate_biased_random(n):
        weights = [min(i, n - i + 1) for i in range(1, n + 1)]
        return random.choices(range(1, n + 1), weights=weights)[0]

    screen_x, screen_y = verify_element.rect.screen_location
    page_x, page_y = tab.rect.page_location
    width, height = verify_element.rect.size
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
    # pyautogui.moveTo(
    #     click_x, click_y, duration=0.5, tween=pyautogui.easeInElastic
    # )
    # pyautogui.click()
    tab.wait.load_start(timeout=20)
    # 再次校验页面是否仍为验证页面
    return not is_cloud_flare_verification_page(tab.html)
