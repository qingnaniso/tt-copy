"""小红书视频发布器 - 通过 Playwright 自动化创作者中心发布视频笔记。"""

import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

COOKIE_PATH = os.path.expanduser("~/.ttcopy/xhs_cookies.json")
XHS_LOGIN_URL = "https://creator.xiaohongshu.com/login"
XHS_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"


class XHSPublisher:
    """使用 Playwright 自动化小红书创作者中心，上传视频并发布笔记。"""

    def __init__(self):
        self._browser = None
        self._context = None
        self._page = None

    async def _ensure_cookie_dir(self):
        os.makedirs(os.path.dirname(COOKIE_PATH), exist_ok=True)

    async def _load_or_login(self, pw):
        """加载已有 Cookie 或引导用户扫码登录。"""
        await self._ensure_cookie_dir()

        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--deny-permission-prompts",
        ]

        if os.path.exists(COOKIE_PATH):
            print("加载已保存的登录态...")
            self._browser = await pw.chromium.launch(headless=False, args=browser_args)
            self._context = await self._browser.new_context(
                storage_state=COOKIE_PATH,
                geolocation={"latitude": 31.2304, "longitude": 121.4737},  # 上海坐标，静默授予定位权限
                permissions=["geolocation"],
            )
            self._page = await self._context.new_page()

            # 验证 Cookie 是否仍有效
            await self._page.goto(XHS_PUBLISH_URL, wait_until="domcontentloaded")
            await self._page.wait_for_timeout(2000)

            if "/login" not in self._page.url:
                print("登录态有效。")
                return

            # Cookie 已失效，关闭并重新登录
            print("登录态已过期，需要重新登录。")
            await self._context.close()
            await self._browser.close()

        # 首次登录 / Cookie 失效
        print("请在浏览器中扫码登录小红书...")
        self._browser = await pw.chromium.launch(headless=False, args=browser_args)
        self._context = await self._browser.new_context(
            geolocation={"latitude": 31.2304, "longitude": 121.4737},
            permissions=["geolocation"],
        )
        self._page = await self._context.new_page()
        await self._page.goto(XHS_LOGIN_URL, wait_until="domcontentloaded")

        # 等待用户完成登录（URL 离开登录页）
        print("等待登录完成...")
        while "/login" in self._page.url:
            await self._page.wait_for_timeout(1000)

        # 保存登录态
        await self._context.storage_state(path=COOKIE_PATH)
        print(f"登录态已保存到 {COOKIE_PATH}")

    async def _upload_and_publish(self, video_path: str, title: str, description: str):
        """上传视频并填写标题、描述，然后发布。"""
        page = self._page

        # 导航到发布页
        if XHS_PUBLISH_URL not in page.url:
            await page.goto(XHS_PUBLISH_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

        # 上传视频文件
        print("上传视频中...")
        file_input = page.locator('input[type="file"]').first
        await file_input.set_input_files(video_path)

        # 等待视频上传和处理完成
        print("等待视频上传及处理...")

        # 持续与页面交互，防止小红书前端因无用户活动而暂停处理
        # 小红书检测页面活跃度：滚动距离、鼠标轨迹、页面可见性
        # 光靠 JS 事件不够，必须用 Playwright 真实模拟鼠标/滚轮操作
        async def keep_page_alive():
            vp = page.viewport_size or {"width": 1280, "height": 800}
            w, h = vp["width"], vp["height"]
            for i in range(180):  # 最多保持 15 分钟活跃
                try:
                    # 1. 大幅滚轮滚动（Playwright 真实滚动，不是 JS dispatch）
                    await page.mouse.wheel(0, 200 + (i % 4) * 100)
                    await asyncio.sleep(0.3)
                    await page.mouse.wheel(0, -(200 + (i % 4) * 100))
                    # 2. 鼠标在页面中心不规则移动
                    x = w // 2 + (i % 7 - 3) * 40
                    y = h // 3 + (i % 9) * 30
                    await page.mouse.move(x, y)
                    # 3. 再派发 JS 事件作为补充
                    await page.evaluate("""
                        document.dispatchEvent(new Event('visibilitychange'));
                        window.dispatchEvent(new Event('focus'));
                        window.dispatchEvent(new Event('scroll'));
                    """)
                except Exception:
                    pass
                await asyncio.sleep(2)

        keep_alive_task = asyncio.create_task(keep_page_alive())

        try:
            # 策略：等待视频封面/缩略图出现，说明处理完毕（最多等 5 分钟）
            for i in range(60):
                # 检查是否出现视频封面（处理完成的标志）
                cover = await page.locator('div.coverImg, div.cover-img, img[class*="cover"], div[class*="thumbnail"], video').count()
                if cover > 0:
                    print("视频处理完成。")
                    break
                # 打印进度避免用户以为卡死
                if i % 6 == 0 and i > 0:
                    print(f"  仍在处理中... ({i * 5}s)")
                await page.wait_for_timeout(5000)
            else:
                print("警告: 视频处理超时，尝试继续...")
        finally:
            keep_alive_task.cancel()
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                pass

        # 填写标题 — 小红书标题输入框
        print("填写标题和描述...")
        title_input = page.locator('#publishInput, input[placeholder*="标题"], input[class*="title"]').first
        await title_input.click()
        await title_input.fill("")
        await page.keyboard.type(title, delay=50)

        # 填写描述 — contenteditable 区域
        desc_editor = page.locator('div[contenteditable="true"], div[class*="ql-editor"], div[class*="desc"] [contenteditable]').first
        await desc_editor.click()
        await page.keyboard.type(description, delay=30)

        await page.wait_for_timeout(1000)

        # 点击发布按钮
        print("发布中...")
        publish_btn = page.locator('button:has-text("发布"), button[class*="publish"]').first
        await publish_btn.click()

        # 等待发布结果（最多 15 秒）
        for _ in range(5):
            await page.wait_for_timeout(3000)
            success = await page.locator('text=/发布成功|已发布/').count()
            if success > 0 or "publish" not in page.url:
                print("发布成功！")
                return

        print("发布状态未确认，请在浏览器中检查。")

    async def publish_async(self, video_path: str, title: str, description: str):
        """异步发布视频到小红书。"""
        video_path = str(Path(video_path).resolve())
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        async with async_playwright() as pw:
            try:
                await self._load_or_login(pw)
                await self._upload_and_publish(video_path, title, description)
            finally:
                if self._context:
                    # 发布后再次保存 Cookie
                    try:
                        await self._context.storage_state(path=COOKIE_PATH)
                    except Exception:
                        pass
                if self._browser:
                    await self._browser.close()

    def publish(self, video_path: str, title: str, description: str):
        """同步接口：发布视频到小红书。"""
        asyncio.run(self.publish_async(video_path, title, description))
