import argparse
import platform

def _default_user_agent():
    if platform.system() == "Windows":
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

DEFAULT_CONFIG = {
    "download_dir": "./downloads",
    "filename_template": "{author}_{video_id}_{timestamp}",
    "hotkey": "ctrl+d",
    "auto_download": False,
    "user_agent": _default_user_agent(),
    "viewport": {"width": 1280, "height": 900},
}


def parse_args():
    parser = argparse.ArgumentParser(description="TikTok video downloader")
    parser.add_argument("--output", help="Download directory")
    parser.add_argument("--auto", action="store_true", help="Auto-download all videos")
    parser.add_argument("--hotkey", help="Download hotkey (default: ctrl+d)")
    return parser.parse_args()


def get_config(args=None):
    config = DEFAULT_CONFIG.copy()
    if args is None:
        args = parse_args()
    if args.output:
        config["download_dir"] = args.output
    if args.auto:
        config["auto_download"] = True
    if args.hotkey:
        config["hotkey"] = args.hotkey
    return config
