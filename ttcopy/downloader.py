import re
import time
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
        }

        if cookies_file:
            opts['cookiefile'] = cookies_file

        # Run yt-dlp in a thread to avoid blocking asyncio
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: self._do_download(opts, video_url))
        return result

    def _do_download(self, opts: dict, url: str) -> str:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
