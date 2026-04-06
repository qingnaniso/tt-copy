import asyncio
import json
import tempfile
from pathlib import Path
from playwright.async_api import async_playwright
from ttcopy.config import get_config
from ttcopy.interceptor import VideoInterceptor
from ttcopy.downloader import VideoDownloader


def log(msg):
    print(msg, flush=True)


INJECT_JS = r"""
(function() {
    function findPostLinkFromElement(startEl) {
        let el = startEl;
        for (let i = 0; i < 20; i++) {
            if (!el.parentElement) break;
            el = el.parentElement;
            const link = el.querySelector('a[href*="/video/"], a[href*="/photo/"]');
            if (link) {
                const m = link.href.match(/@([^/]+)\/(video|photo)\/(\d+)/);
                if (m) return { author: m[1], videoId: m[3], type: m[2] };
                const m2 = link.href.match(/\/(video|photo)\/(\d+)/);
                if (m2) return { author: 'unknown', videoId: m2[2], type: m2[1] };
            }
        }
        return null;
    }

    function getCurrentContentInfo() {
        // Strategy 1: URL path (user is viewing a specific post)
        const pathMatch = location.pathname.match(/@([^/]+)\/(video|photo)\/(\d+)/);
        if (pathMatch) {
            return { author: pathMatch[1], videoId: pathMatch[3], type: pathMatch[2] };
        }

        // Strategy 2: Find visible video element in feed (video posts)
        const videos = document.querySelectorAll('video');
        for (const v of videos) {
            const rect = v.getBoundingClientRect();
            if (rect.top >= -200 && rect.top < window.innerHeight * 0.7 && rect.height > 200) {
                const info = findPostLinkFromElement(v);
                if (info) return info;
            }
        }

        // Strategy 3: Find visible photo post links in feed
        const links = document.querySelectorAll('a[href*="/photo/"]');
        for (const link of links) {
            const m = link.href.match(/@([^/]+)\/photo\/(\d+)/);
            if (!m) continue;
            const rect = link.getBoundingClientRect();
            if (rect.top >= -200 && rect.top < window.innerHeight * 0.7 && rect.width > 100) {
                return { author: m[1], videoId: m[2], type: 'photo' };
            }
        }

        return null;
    }

    function triggerDownload() {
        const info = getCurrentContentInfo();
        const btn = document.getElementById('__ttcopy_btn__');

        if (!info || !info.videoId) {
            console.log('__TTCOPY_ERR__:Could not identify current content');
            if (btn) {
                btn.style.background = '#f44336';
                setTimeout(() => { btn.style.background = '#25c554'; btn.style.transform = 'scale(1)'; }, 1000);
            }
            return;
        }

        console.log('__TTCOPY_DL__:' + JSON.stringify(info));
        if (btn) {
            btn.style.background = '#ff9800';
            btn.style.transform = 'scale(0.9)';
        }
    }

    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'D') {
            e.preventDefault();
            e.stopPropagation();
            triggerDownload();
        }
    }, true);

    function injectButton() {
        if (document.getElementById('__ttcopy_btn__')) return;
        const btn = document.createElement('div');
        btn.id = '__ttcopy_btn__';
        btn.title = 'Download (Cmd+Shift+D)';
        btn.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 16l-6-6h4V4h4v6h4l-6 6z" fill="white"/><rect x="4" y="18" width="16" height="2" rx="1" fill="white"/></svg>';
        Object.assign(btn.style, {
            position: 'fixed', bottom: '40px', right: '40px',
            width: '56px', height: '56px', borderRadius: '50%',
            background: '#25c554', display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', zIndex: '2147483647',
            boxShadow: '0 4px 14px rgba(0,0,0,0.35)',
            userSelect: 'none', transition: 'all 0.15s ease',
        });
        btn.addEventListener('click', triggerDownload);
        document.body.appendChild(btn);
    }

    if (document.body) injectButton();
    else document.addEventListener('DOMContentLoaded', injectButton);

    new MutationObserver(() => {
        if (!document.getElementById('__ttcopy_btn__') && document.body) injectButton();
    }).observe(document.documentElement, { childList: true, subtree: true });
})();
"""


async def export_cookies(context, path: str):
    """Export browser cookies to Netscape format for yt-dlp."""
    cookies = await context.cookies()
    with open(path, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            domain = c.get("domain", "")
            flag = "TRUE" if domain.startswith(".") else "FALSE"
            path_val = c.get("path", "/")
            secure = "TRUE" if c.get("secure") else "FALSE"
            expires = str(int(c.get("expires", 0)))
            name = c.get("name", "")
            value = c.get("value", "")
            f.write(f"{domain}\t{flag}\t{path_val}\t{secure}\t{expires}\t{name}\t{value}\n")


async def handle_console(msg, interceptor, downloader, context, config, cookies_path):
    try:
        text = msg.text
    except Exception:
        return

    if text.startswith("__TTCOPY_ERR__:"):
        log(f"[tt-copy] {text[15:]}")
        return

    if not text.startswith("__TTCOPY_DL__:"):
        return

    try:
        info = json.loads(text[len("__TTCOPY_DL__:"):])
    except Exception:
        return

    author = info.get("author", "unknown")
    video_id = info.get("videoId")
    content_type = info.get("type", "video")

    if not video_id:
        log("[tt-copy] No content ID found")
        return

    content_url = f"https://www.tiktok.com/@{author}/{content_type}/{video_id}"

    # Export fresh cookies from browser
    try:
        await export_cookies(context, cookies_path)
    except Exception:
        pass

    if content_type == "photo":
        # Try intercepted image URLs first, fall back to yt-dlp
        metadata = interceptor.get_metadata(video_id)
        image_urls = metadata.get("image_urls", [])

        if image_urls:
            log(f"[tt-copy] Downloading photo ({len(image_urls)} images): {content_url}")
            try:
                saved = await downloader.download_images(image_urls, author, video_id)
                for f in saved:
                    log(f"[tt-copy] Saved: {f}")
                if not saved:
                    log("[tt-copy] No images saved, trying yt-dlp fallback...")
                    filepath = await downloader.download(content_url, author, video_id, cookies_path)
                    log(f"[tt-copy] Saved: {filepath}")
            except Exception as e:
                error_msg = str(e)[:200]
                log(f"[tt-copy] Download failed: {error_msg}")
        else:
            log(f"[tt-copy] Downloading photo (yt-dlp): {content_url}")
            try:
                filepath = await downloader.download(content_url, author, video_id, cookies_path)
                log(f"[tt-copy] Saved: {filepath}")
            except Exception as e:
                error_msg = str(e)[:200]
                log(f"[tt-copy] Download failed: {error_msg}")
    else:
        log(f"[tt-copy] Downloading video: {content_url}")
        try:
            filepath = await downloader.download(content_url, author, video_id, cookies_path)
            log(f"[tt-copy] Saved: {filepath}")
        except Exception as e:
            error_msg = str(e)[:200]
            log(f"[tt-copy] Download failed: {error_msg}")


async def update_button_state(page, state):
    """Update button color: green=ready, orange=downloading, red=error."""
    colors = {"ready": "#25c554", "downloading": "#ff9800", "error": "#f44336"}
    color = colors.get(state, "#25c554")
    try:
        await page.evaluate(f"""
            (() => {{
                const btn = document.getElementById('__ttcopy_btn__');
                if (btn) {{
                    btn.style.background = '{color}';
                    btn.style.transform = 'scale(1)';
                }}
            }})()
        """)
    except Exception:
        pass


async def main():
    config = get_config()

    log("🎬 tt-copy started (video + photo)")
    log(f"📁 Download dir: {config['download_dir']}")
    log("⌨️  Hotkey: Cmd+Shift+D (Mac) / Ctrl+Shift+D")
    log("🌐 Opening TikTok...")

    interceptor = VideoInterceptor()
    downloader = VideoDownloader(config)
    cookies_path = str(Path(tempfile.mkdtemp()) / "cookies.txt")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent=config["user_agent"],
                viewport=config["viewport"],
            )
            page = await context.new_page()

            page.on("response", interceptor.on_response)
            page.on("console", lambda msg: asyncio.ensure_future(
                handle_console(msg, interceptor, downloader, context, config, cookies_path)
            ))

            await page.add_init_script(INJECT_JS)
            await page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=60000)

            log("[tt-copy] Ready! Browse and click green button to download video or photo.")

            try:
                await page.wait_for_event("close", timeout=0)
            except Exception:
                pass

    finally:
        # Cleanup cookies file
        try:
            Path(cookies_path).unlink(missing_ok=True)
        except Exception:
            pass
        log("[tt-copy] Bye!")


if __name__ == "__main__":
    asyncio.run(main())
