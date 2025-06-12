from DrissionPage._pages.mix_tab import MixTab

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
    判断当前页面是否为CloudFlare验证页面

    :param html: 页面源代码
    :return: 如果页面包含特定的验证码标识，则返回True，否则返回False
    """
    return (
            'class="cb-container error-message-wrapper"' in html and
            'cf-turnstile-response' in html or
            'data-testid="challenge-widget-container"' in html
    )


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
    tab.refresh()
    tab.set.load_mode.none()  # 设置加载模式为none
    tab.wait.ele_displayed(".main-content", timeout=20)
    wrapper = tab.ele(".main-content")
    if not wrapper:
        return False
    spacer = wrapper.ele(".spacer")
    div1 = spacer.ele("tag:div")
    div2 = div1.ele("tag:div")

    iframe = div2.shadow_root.ele("tag:iframe", timeout=15)
    tab.wait(2)
    iframeRoot = iframe("tag:body").shadow_root
    cbLb = iframeRoot.ele(".cb-lb", timeout=10)

    # 获取位置
    pos = cbLb.ele("tag:input", timeout=10).rect.screen_click_point

    tab.wait(2)

    # 移动鼠标
    tab.actions.move(pos[0], pos[1] + 61, duration=0.5)
    # 点击右键
    tab.actions.click()
    # 再次校验页面是否仍为验证页面
    return not is_cloud_flare_verification_page(tab.html)
