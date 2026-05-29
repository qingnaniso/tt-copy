"""小红书视频发布器 - 通过 Playwright 自动化创作者中心发布视频笔记。"""

import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

_account = os.environ.get("XHS_ACCOUNT", "")
_suffix = f"_{_account}" if _account else ""
COOKIE_PATH = os.path.expanduser(f"~/.ttcopy/xhs_cookies{_suffix}.json")
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

    async def _scroll_page_for_real(self, page):
        """找到页面上真正可滚动的元素并做来回滚动。

        小红书发布页选文件前 maxScroll=0，window.scrollBy 无效。
        必须等上传UI出现后，找到实际的可滚动容器来滚。
        """
        result = await page.evaluate('''() => {
            let scrolled = 0;
            // 遍历所有元素找可滚动容器
            document.querySelectorAll('*').forEach(el => {
                if (el.scrollHeight > el.clientHeight + 5) {
                    // 滚下去
                    el.scrollBy(0, el.clientHeight * 0.6);
                    // 异步滚回来
                    setTimeout(() => {
                        el.scrollBy(0, -el.clientHeight * 0.5);
                    }, 150);
                    scrolled++;
                }
            });
            // 同时尝试 window 滚动（兜底）
            if (document.documentElement.scrollHeight > window.innerHeight) {
                window.scrollBy(0, window.innerHeight * 0.6);
                setTimeout(() => window.scrollBy(0, -window.innerHeight * 0.5), 150);
                scrolled++;
            }
            return scrolled;
        }''')
        return result

    async def _upload_and_publish(self, video_path: str, title: str, description: str):
        """上传视频并填写标题、描述，然后发布。"""
        page = self._page

        # 导航到发布页
        if XHS_PUBLISH_URL not in page.url:
            await page.goto(XHS_PUBLISH_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

        # === Step 1: 选择文件 ===
        print("上传视频中...")
        file_input = page.locator('input[type="file"]').first
        await file_input.set_input_files(video_path)

        # === Step 2: 等上传UI出现 → 立刻做真正滚动激活上传 ===
        print("等待上传UI出现...")
        ui_seen = False
        for i in range(10):
            await page.wait_for_timeout(1000)
            has_ui = await page.evaluate(
                '!!document.querySelector("[class*=\\"progress\\"]")'
            )
            if has_ui and not ui_seen:
                ui_seen = True
                print("  上传UI已出现，执行来回滚动激活...")
                # 等UI渲染完（100ms），然后滚动
                await asyncio.sleep(0.2)
                n = await self._scroll_page_for_real(page)
                print(f"  滚动 {n} 个容器")
                await asyncio.sleep(0.5)
                # 再做一次反向滚动确保
                await self._scroll_page_for_real(page)
                break

        if not ui_seen:
            print("  未检测到上传UI")

        # === Step 3: 等上传进度变化（同时做保活） ===
        print("等待上传进度...")
        upload_ok = await self._wait_for_upload_start(page, timeout=20)

        if not upload_ok:
            # 再试一次滚动
            print("  进度未变化，再次尝试滚动...")
            await self._scroll_page_for_real(page)
            await asyncio.sleep(1)
            upload_ok = await self._wait_for_upload_start(page, timeout=15)

        # === Step 4: 大滚动保活，等待处理完成 ===
        keep_alive_task = asyncio.create_task(self._keep_page_active(page))
        try:
            await self._wait_for_processing_complete(page, timeout=600)
        finally:
            keep_alive_task.cancel()
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                pass

        # === Step 4: 填写标题和描述 ===
        print("填写标题和描述...")
        title_input = page.locator('#publishInput, input[placeholder*="标题"], input[class*="title"]').first
        await title_input.click()
        await title_input.fill("")
        await page.keyboard.type(title, delay=50)

        desc_editor = page.locator('div[contenteditable="true"], div[class*="ql-editor"], div[class*="desc"] [contenteditable]').first
        await desc_editor.click()
        await page.keyboard.type(description, delay=30)

        await page.wait_for_timeout(1000)

        # === Step 5: 发布 ===
        print("发布中...")
        await page.wait_for_timeout(1500)

        # 先 dump 所有按钮文本，便于调试
        btn_texts = await page.evaluate("""
            () => Array.from(document.querySelectorAll('button, [role=button]'))
                        .map(b => b.innerText.trim())
                        .filter(t => t.length > 0)
        """)
        print(f"  页面按钮: {btn_texts}")

        # 尝试多种方式找发布按钮（XHS 用 div.btn-wrapper 而非 button）
        clicked = False
        for selector in [
            'div.btn-wrapper:has-text("发布笔记")',
            'div.btn-inner:has-text("发布笔记")',
            'span.btn-text:has-text("发布笔记")',
            '[class*="btn"]:has-text("发布笔记")',
            'button:has-text("发布")',
            'button:has-text("发布笔记")',
            'button[class*="publish"]',
            '.publish-btn',
        ]:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    await btn.scroll_into_view_if_needed()
                    await btn.click(timeout=5000)
                    print(f"  点击成功: {selector}")
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            # JS 兜底：找包含"发布"文字的按钮
            result = await page.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll('button, [role=button], a'));
                    const target = btns.find(b => b.innerText.includes('发布') && !b.disabled);
                    if (target) { target.click(); return target.innerText.trim(); }
                    return null;
                }
            """)
            if result:
                print(f"  JS 点击成功: {result}")
                clicked = True

        if not clicked:
            print("  未找到发布按钮，请手动在浏览器中点击发布。")
            await page.wait_for_timeout(30000)

        for _ in range(8):
            await page.wait_for_timeout(3000)
            current_url = page.url
            # 检查成功文字（XHS 可能用不同措辞）
            success_texts = await page.evaluate("""
                () => document.body.innerText
            """)
            if any(kw in success_texts for kw in ["发布成功", "已发布", "发布完成", "笔记发布"]):
                print("发布成功！")
                return
            # URL 跳走也算成功
            if "publish/publish" not in current_url:
                print(f"发布成功！（跳转至 {current_url}）")
                return

        print("发布状态未确认，请在浏览器中检查。（按钮已点击，大概率已发布）")

    async def _keep_page_active(self, page):
        """上传确认后的正常保活 —— 大滚动防止处理过程中页面休眠。

        每 2 秒一轮：PageDown → JS scrollBy → wheel → 鼠标位移。
        注意：此方法在上传已确认启动后才使用，避免滚动干扰上传UI。
        """
        vp = page.viewport_size or {"width": 1280, "height": 800}
        w, h = vp["width"], vp["height"]
        for i in range(400):
            try:
                await page.keyboard.press("PageDown")
                await asyncio.sleep(0.6)
                await page.evaluate(f"window.scrollBy(0, {h // 2})")
                await asyncio.sleep(0.2)
                await page.mouse.wheel(0, 400)
                await asyncio.sleep(0.2)
                x = w // 2 + ((i * 37) % 11 - 5) * 50
                y = h // 3 + ((i * 53) % 13) * 25
                await page.mouse.move(x, y)
                await page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            except Exception:
                pass
            await asyncio.sleep(1.0)

    async def _wait_for_upload_start(self, page, timeout: int = 15) -> bool:
        """等待上传开始（进度从0%开始变动）。

        返回 True 表示上传已启动，False 表示超时或上传UI消失（被放弃）。
        """
        stuck_at_zero_since = -1
        upload_ui_seen = False

        for i in range(timeout):
            await page.wait_for_timeout(1000)
            text = await page.evaluate('''() => {
                const els = document.querySelectorAll('[class*="progress"]');
                for (const el of els) {
                    const t = el.textContent || "";
                    if (t.includes("上传中") || /\\d+%/.test(t)) {
                        return t.trim().substring(0, 120);
                    }
                }
                return "";
            }''')

            if not text:
                if upload_ui_seen:
                    # 上传UI出现过但消失了 → 页面放弃了上传
                    print(f"  上传UI已消失（页面放弃上传）")
                    return False
                if i % 5 == 0 and i > 0:
                    print(f"  等待上传UI出现... ({i}s)")
                continue

            upload_ui_seen = True
            has_zero = "0%" in text
            progressing = any(
                p in text for p in
                ["1%", "2%", "3%", "4%", "5%", "6%", "7%", "8%", "9%", "100%"]
            )

            if progressing:
                print(f"  上传已启动: {text[:100]}")
                return True

            if has_zero:
                if stuck_at_zero_since < 0:
                    stuck_at_zero_since = i
                elif i - stuck_at_zero_since >= 4:
                    # 卡在0%超过4秒
                    print(f"  上传卡在0%（已{i - stuck_at_zero_since}秒）")
                    return False

        if upload_ui_seen and stuck_at_zero_since >= 0:
            print(f"  上传UI存在但进度始终为0%")
        return False

    async def _wait_for_processing_complete(self, page, timeout: int = 600):
        """等待上传+转码处理完成（检测封面/标题输入框出现）。"""
        for i in range(timeout // 5):
            cover = await page.locator(
                'div.coverImg, div.cover-img, img[class*="cover"], '
                'div[class*="thumbnail"], video, '
                'div[class*="poster"], div[class*="preview"], '
                'div[class*="upload-success"], div[class*="uploaded"]'
            ).count()
            title_ready = await page.locator(
                '#publishInput, input[placeholder*="标题"]'
            ).count()
            if cover > 0 or title_ready > 0:
                print("视频处理完成。")
                return
            if i % 10 == 0 and i > 0:
                print(f"  仍在处理中... ({i * 5}s)")
            await page.wait_for_timeout(5000)
        print("警告: 视频处理超时，尝试继续...")

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
