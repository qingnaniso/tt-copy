# TikTok 视频下载器 (tt-copy) — 技术设计

## 概述

在 TikTok 网页版刷视频时，一键下载当前播放的视频或图文帖到本地。

## 技术方案

**Python + Playwright + yt-dlp**：用 Playwright 启动 Chromium 浏览器打开 TikTok，注入 JS 提供下载按钮和快捷键，用户触发后导出浏览器 Cookie 给 yt-dlp 完成下载。图文帖优先通过拦截的 CDN URL 直接下载。

## 项目结构

```
tt-copy/
├── start.command          # Mac 一键启动（zsh 脚本）
├── start.bat              # Windows 一键启动（自动下载嵌入式 Python）
├── _run.py                # Windows 启动入口（绕过嵌入式 Python 模块路径限制）
├── requirements.txt       # playwright, yt-dlp
├── ttcopy/
│   ├── __init__.py        # 版本号
│   ├── main.py            # 入口：启动浏览器、注入 JS、事件循环
│   ├── interceptor.py     # 网络请求拦截，捕获图片 CDN URL
│   ├── downloader.py      # 视频下载（yt-dlp）+ 图片直接下载
│   └── config.py          # 配置（下载目录、UA、viewport 等）
└── downloads/             # 默认下载目录
```

## 平台启动机制

### Mac (`start.command`)

1. 检查系统 Python 3 是否存在
2. 创建 `.venv` 虚拟环境
3. 安装依赖 + Chromium
4. 通过 `python -m ttcopy.main` 启动

### Windows (`start.bat` + `_run.py`)

1. 下载嵌入式 Python 3.11.9（免安装，约 12MB）
2. 安装 pip、依赖、Chromium
3. 通过 `_run.py` 启动（嵌入式 Python 的 `._pth` 文件会忽略 PYTHONPATH，需要在代码中手动设置 `sys.path`）

> `start.bat` 使用纯英文输出，避免 GBK/UTF-8 编码冲突导致命令解析失败。

## 模块设计

### 1. `config.py` — 配置模块

提供默认配置，根据平台自动切换 User-Agent，支持命令行参数覆盖：

```python
DEFAULT_CONFIG = {
    "download_dir": "./downloads",
    "filename_template": "{author}_{video_id}_{timestamp}",
    "hotkey": "ctrl+d",
    "auto_download": False,
    "user_agent": _default_user_agent(),  # 按平台自动选择
    "viewport": {"width": 1280, "height": 900},
}
```

命令行参数：
- `--output`：指定下载目录
- `--auto`：自动下载所有刷到的视频
- `--hotkey`：自定义快捷键

### 2. `interceptor.py` — 网络请求拦截

监听页面所有网络响应，从 TikTok API 响应中提取图文帖的图片 URL 列表，缓存供下载时使用。

核心逻辑：
- 拦截 `/api/` 相关响应
- 从 JSON 中提取 `imagePost.images[].imageURL.urlList`
- 以 `video_id` 为 key 缓存到 `metadata_cache`

### 3. `downloader.py` — 下载模块

两种下载方式：

| 内容类型 | 下载方式 | 说明 |
|---------|---------|------|
| 视频 | yt-dlp | 携带 Cookie 和浏览器 UA/Referer |
| 图文帖 | 优先直接请求拦截到的 CDN URL，失败回退 yt-dlp | 支持多图下载 |

yt-dlp 配置要点：
- `cookiefile`：从浏览器导出的 Netscape 格式 Cookie
- `http_headers`：User-Agent 与浏览器一致，Referer 设为 TikTok
- `format: best`，`noplaylist: True`

### 4. `main.py` — 主入口

**启动流程**：
1. 初始化配置、拦截器、下载器
2. 启动 Playwright Chromium（headless=False）
3. 创建浏览器上下文（设置 UA、viewport）
4. 注册 `interceptor.on_response` 监听网络响应
5. 注入 JS 脚本（下载按钮 + 快捷键监听）
6. 导航到 `https://www.tiktok.com`
7. 监听 console 消息，捕获 `__TTCOPY_DL__:` 前缀的下载指令
8. 触发下载时：导出 Cookie → 调用 downloader
9. 保持运行直到浏览器关闭

**注入 JS 功能**：
- 右下角固定绿色圆形下载按钮
- 监听 Ctrl+Shift+D / Cmd+Shift+D 快捷键
- 识别当前可见内容：优先 URL 路径匹配，其次遍历可见 video/photo 元素
- 通过 `console.log` 传递下载指令给 Python 端

**Cookie 导出**：
- 从 Playwright browser context 获取所有 Cookie
- 转换为 Netscape 格式写入临时文件
- Session Cookie（expires=-1）导出时 expires 设为 0，避免 yt-dlp 跳过

## 依赖

```
playwright>=1.40.0
yt-dlp>=2025.1.0
```

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 下载 403 | 重新导出浏览器 Cookie 重试 |
| 无法识别当前内容 | 按钮变红色提示，1 秒后恢复 |
| 图片直接下载失败 | 回退到 yt-dlp |
| 网络超时 | yt-dlp 内置 30 秒超时 |
