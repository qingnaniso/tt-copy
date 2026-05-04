"""Kimi Vision API 封装 — 替代 codex 做图像分析和文案生成。
Kimi Coding API 使用 Anthropic Messages 兼容格式。"""

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

CONFIG_PATH = os.path.expanduser("~/.ttcopy/kimi_config.json")


def _load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Kimi 配置文件不存在: {CONFIG_PATH}")
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    return cfg["api_url"], cfg["api_key"]


API_URL, API_KEY = _load_config()


def encode_image(image_path: str) -> dict:
    """读取图片并转为 Anthropic 格式的 base64 source block。"""
    path = Path(image_path)
    ext = path.suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")
    data = base64.b64encode(path.read_bytes()).decode()
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": f"image/{mime}",
            "data": data,
        },
    }


def chat(prompt: str, image_path: str = None, max_tokens: int = 500) -> str:
    """调用 Kimi API（Anthropic 兼容格式）。返回回答文本。"""
    content = []

    if image_path:
        content.append({"type": "text", "text": prompt})
        content.append(encode_image(image_path))
    else:
        content.append({"type": "text", "text": prompt})

    payload = json.dumps({
        "model": "kimi-for-coding",
        "messages": [
            {"role": "user", "content": content},
        ],
        "max_tokens": max_tokens,
    }).encode()

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        },
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())

    # Anthropic 格式返回
    return data["content"][0]["text"].strip()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Kimi Vision API CLI")
    parser.add_argument("--image", "-i", help="图片路径（可选，不传则为纯文本模式）")
    parser.add_argument("--prompt", "-p", help="提示词（也可从 stdin 读取）")
    parser.add_argument("--max-tokens", "-m", type=int, default=500)
    parser.add_argument("--extract-only", action="store_true",
                        help="只输出 Kimi 回答正文，去掉调试信息")
    args = parser.parse_args()

    # prompt 来源：命令行 > stdin
    prompt = args.prompt
    if not prompt:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        if not prompt:
            print("错误: 请通过 --prompt 或 stdin 提供提示词", file=sys.stderr)
            sys.exit(1)

    try:
        result = chat(prompt, args.image, args.max_tokens)
        print(result)
    except Exception as e:
        print(f"Kimi API 调用失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
