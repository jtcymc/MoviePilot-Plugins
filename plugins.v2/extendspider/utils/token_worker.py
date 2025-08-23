import queue
import os
import random
import re
import threading
import time
import traceback

from app.log import logger


class TokenWorker(threading.Thread):
    """单线程串行操控 DrissionPage，避免多线程争抢 WebSocket/CDP。"""
    def __init__(self, spider, tmp_folder: str, max_retries: int = 2, token_timeout: float = 12.0):
        super().__init__(daemon=True)
        self.spider = spider                # Bt1louSpider 实例（含 browser / drission_browser / logger）
        self.tmp_folder = tmp_folder
        self.max_retries = max_retries
        self.token_timeout = token_timeout
        self.queue: "queue.Queue[dict|None]" = queue.Queue()
        self.downloaded_files: list[str] = []
        self._running = True

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    def stop(self):
        self._running = False
        # 放一个哨兵元素让线程跳出
        self.queue.put(None)
    @staticmethod
    def _with_jitter( a: float = 0.3, b: float = 0.9):
        time.sleep(random.uniform(a, b))

    def _get_token_with_retry(self, tab) -> bool:
        """获取 TurnstileToken，带重试和退避。"""
        for attempt in range(1, self.max_retries + 1):
            try:
                ok = self.spider.drission_browser.getTurnstileToken(tab)
                if ok:
                    return True
            except Exception as e:
                logger.warning(f"{self.spider.spider_name}-Token 获取异常[{attempt}/{self.max_retries}]: {e}")
            # 退避 + 抖动
            self._with_jitter(0.8, 1.6)
        return False

    def run(self):
        while self._running:
            task = None
            try:
                task = self.queue.get(timeout=1)
            except queue.Empty:
                continue

            if task is None:  # 哨兵
                self.queue.task_done()
                break

            url = task["url"]
            raw_title = task["title"]
            title = self._sanitize_filename(raw_title)

            tab = None
            try:
                # 打开新页签（单线程，无争抢）
                tab = self.spider.browser.new_tab(url)
                tab.set.when_download_file_exists('skip')

                # 可选：等待页面稳定（避免 ContextLostError）
                tab.wait.doc_loaded(timeout=self.token_timeout)

                # 获取 Turnstile token（带重试）
                if not self._get_token_with_retry(tab):
                    logger.warning(f"{self.spider.spider_name}-获取TurnstileToken失败 url={url}")
                    continue

                # 等下载按钮元素出现
                if not tab.wait.ele_displayed("css:fieldset a[href]", timeout=10):
                    logger.warning(f"{self.spider.spider_name}-下载链接未出现 url={url}")
                    continue

                down = tab.ele("css:fieldset a[href]")
                if not down:
                    logger.warning(f"{self.spider.spider_name}-未找到下载元素 url={url}")
                    continue

                down.set.attr("target", "_self")
                self._with_jitter(0.05, 0.15)
                tab.set.download_path(self.tmp_folder)

                # 触发下载
                mission = down.click.to_download(
                    self.tmp_folder,
                    timeout=30,
                    new_tab=True,
                    rename=title,
                    suffix="torrent",
                    by_js=True
                )
                if mission:
                    mission.wait()
                    # 由于 rename 已指定，命名是可预期的
                    file_path = os.path.join(self.tmp_folder, f"{title}.torrent")
                    if os.path.exists(file_path):
                        self.downloaded_files.append(file_path)
                        logger.info(f"{self.spider.spider_name}-下载成功: {file_path}")
                else:
                    logger.warning(f"{self.spider.spider_name}-下载任务未创建 url={url}")

            except Exception as e:
                logger.error(
                    f"{self.spider.spider_name}-TokenWorker 处理失败: {e}\n{traceback.format_exc()}"
                )
            finally:
                try:
                    if tab:
                        tab.close()
                except Exception:
                    pass
                self.queue.task_done()
                # 轻微间隔，降低被风控概率
                self._with_jitter(0.3, 0.8)
