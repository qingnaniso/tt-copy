import asyncio
import re
import time
import urllib.request
from pathlib import Path
import yt_dlp


class VideoDownloader:
    def __init__(self, config: dict):
        self.config = config

    async def download(self, video_url: str, author: str, video_id: str, cookies_file: str = None) -> str:
        safe_author = re.sub(r'[^\w\-.]', '_', author or "unknown")
        filename = f"{safe_author}_{video_id}_{int(time.time())}"

        download_dir = Path(self.config["download_dir"])
        download_dir.mkdir(parents=True, exist_ok=True)

        opts = {
            'format': 'best',
            'outtmpl': str(download_dir / f"{filename}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'http_headers': {
                'User-Agent': self.config.get('user_agent', ''),
                'Referer': 'https://www.tiktok.com/',
            },
        }

        if cookies_file:
            opts['cookiefile'] = cookies_file

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: self._do_download(opts, video_url))
        return result

    async def download_images(self, image_urls: list[str], author: str, post_id: str) -> list[str]:
        """Download multiple images from direct URLs. Returns list of saved file paths."""
        safe_author = re.sub(r'[^\w\-.]', '_', author or "unknown")
        ts = int(time.time())

        download_dir = Path(self.config["download_dir"])
        download_dir.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()
        saved = await loop.run_in_executor(
            None, lambda: self._do_download_images(image_urls, download_dir, safe_author, post_id, ts)
        )
        return saved

    def _do_download_images(self, urls, download_dir, author, post_id, ts):
        saved = []
        for i, url in enumerate(urls, 1):
            filepath = download_dir / f"{author}_{post_id}_{ts}_{i}.jpg"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    filepath.write_bytes(resp.read())
                saved.append(str(filepath))
            except Exception:
                pass
        return saved

    def download_sync(self, video_url: str, author: str = None, video_id: str = None,
                       progress_hook=None) -> str:
        """Synchronous download for CLI usage. No asyncio or browser needed.
        Uses a single yt-dlp pass: extract info + download in one call,
        then rename the file with proper metadata."""
        download_dir = Path(self.config["download_dir"])
        download_dir.mkdir(parents=True, exist_ok=True)

        # Use yt-dlp default naming for the single-pass download
        ts = int(time.time())
        temp_template = str(download_dir / f"%(uploader)s_%(id)s_{ts}.%(ext)s")

        opts = {
            'format': 'best',
            'outtmpl': temp_template,
            'noplaylist': True,
            'socket_timeout': 30,
            'http_headers': {
                'User-Agent': self.config.get('user_agent', ''),
                'Referer': 'https://www.tiktok.com/',
            },
        }

        if progress_hook:
            opts['progress_hooks'] = [progress_hook]

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            return filename

    def _do_download(self, opts: dict, url: str) -> str:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
