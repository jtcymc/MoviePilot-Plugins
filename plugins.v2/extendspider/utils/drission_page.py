from app.utils.singleton import SingletonClass
from plugins.extendspider.utils.browser import create_drission_chromium


class DrissonBrowser(metaclass=SingletonClass):

    def __init__(self, proxy: bool = False, headless: bool = True):
        self._browser = create_drission_chromium(proxy=proxy, headless=headless)

    @property
    def browser(self):
        return self._browser

    @browser.setter
    def browser(self, value):
        self._browser = value


    def __del__(self):
        if self._browser:
            self._browser.quit()