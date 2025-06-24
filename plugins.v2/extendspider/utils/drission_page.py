from DrissionPage._pages.chromium_page import ChromiumPage
from DrissionPage._pages.chromium_tab import ChromiumTab
from DrissionPage._pages.mix_tab import MixTab

from app.utils.singleton import SingletonClass
from app.log import logger
from DrissionPage import ChromiumOptions
import time
import os

from plugins.extendspider.utils.browser import find_chromium_path
from plugins.extendspider.utils.pass_verify import is_cloud_flare_verification_page
from app.utils.system import SystemUtils


class DrissonBrowser(metaclass=SingletonClass):

    def __init__(self, proxy: bool = False, headless: bool = True):
        self._headless = headless
        self._proxy = proxy
        self._browser = self.create_drission_chromium()

    def create_drission_chromium(self):

        co = ChromiumOptions()
        co.auto_port()
        # co.set_timeouts(base=1)
        # change this to the path of the folder containing the extension
        EXTENSION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "turnstilePatch"))
        co.add_extension(EXTENSION_PATH)
        co.set_user_data_path('/tmp')
        if self._headless:
            from sys import platform
            platform_identifier = "X11; Linux x86_64"
            if platform == "linux" or platform == "linux2":
                platform_identifier = "X11; Linux x86_64"
            elif platform == "darwin":
                platform_identifier = "Macintosh; Intel Mac OS X 10_15_7"
            elif platform == "win32":
                platform_identifier = "Windows NT 10.0; Win64; x64"
            co.headless(self._headless)
            co.set_user_agent(
                f"Mozilla/5.0 ({platform_identifier}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.126 Safari/537.36")
        if SystemUtils.is_docker():
            co.set_argument("--no-sandbox")
            co.set_argument('--disable-dev-shm-usage')
            co.set_argument('--disable-software-rasterizer')
            co.set_argument('--disable-gpu')
            co.set_argument('--headless=new')
        path = find_chromium_path()
        logger.info(f"使用自定义的 Chromium 路径：{path}")
        if path:
            co.set_browser_path(path)
        return ChromiumPage(co)

    @property
    def browser(self):
        return self._browser

    @browser.setter
    def browser(self, value):
        self._browser = value

    @staticmethod
    def getTurnstileToken(page: ChromiumPage | MixTab | ChromiumTab):
        if not page or not is_cloud_flare_verification_page(page.html):
            return True
        logger.info('Starting Cloudflare bypass.')
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
            if i % 5 == 0:
                page.refresh()
                # page.wait.ele_displayed("@name=cf-turnstile-response", timeout=15)
        page.refresh()
        return None

    def __del__(self):
        if self._browser:
            self._browser.quit()
