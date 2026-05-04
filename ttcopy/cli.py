"""TT-Copy CLI: download TikTok videos by URL without opening a browser."""

import argparse
import re
import sys

from .config import DEFAULT_CONFIG
from .downloader import VideoDownloader


def parse_url(url: str):
    """Extract author and video_id from a TikTok URL."""
    m = re.search(r'/@([\w.]+)/(video|photo)/(\d+)', url)
    if m:
        return m.group(1), m.group(3)
    return None, None


def progress_hook(d):
    if d['status'] == 'downloading':
        pct = d.get('_percent_str', '?%').strip()
        speed = d.get('_speed_str', '?').strip()
        print(f"\r  下载中: {pct}  速度: {speed}", end='', flush=True)
    elif d['status'] == 'finished':
        print(f"\n  下载完成，正在处理...")


def main():
    parser = argparse.ArgumentParser(
        description="TT-Copy CLI - 直接通过链接下载 TikTok 视频/图文",
        usage="python -m ttcopy.cli <url> [--output DIR] [--publish]",
    )
    parser.add_argument("url", help="TikTok 视频或图文链接")
    parser.add_argument("--output", "-o", default="./downloads", help="下载目录 (默认: ./downloads)")
    parser.add_argument("--publish", action="store_true", help="下载后自动发布到小红书")
    args = parser.parse_args()

    url = args.url.strip()
    if not url:
        print("错误: 请提供 TikTok 链接")
        sys.exit(1)

    author, video_id = parse_url(url)
    if author:
        print(f"作者: @{author}  ID: {video_id}")
    else:
        print("解析元数据中...")

    config = DEFAULT_CONFIG.copy()
    config["download_dir"] = args.output

    downloader = VideoDownloader(config)

    try:
        result = downloader.download_sync(url, author, video_id, progress_hook=progress_hook)
        video_path = result if isinstance(result, str) else result['filepath']
        print(f"已保存: {video_path}")
    except Exception as e:
        print(f"\n下载失败: {e}")
        print("提示: 如果视频需要登录才能查看，请使用浏览器版 (start.command)")
        sys.exit(1)

    if args.publish and video_path:
        print("\n--- 发布到小红书 ---")
        print("请输入笔记标题:")
        title = sys.stdin.buffer.readline().decode('utf-8').rstrip('\n').strip()
        if not title:
            print("标题不能为空，跳过发布。")
            sys.exit(0)
        print("请输入笔记描述:")
        description = sys.stdin.buffer.readline().decode('utf-8').rstrip('\n').strip()

        from .publisher import XHSPublisher

        publisher = XHSPublisher()
        try:
            publisher.publish(video_path, title, description)
        except Exception as e:
            print(f"发布失败: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
