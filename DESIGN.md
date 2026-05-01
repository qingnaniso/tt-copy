# TikTok 视频下载器 (tt-copy) — 技术设计

## 概述

TikTok 视频一键下载 + 小红书自动发布工具。提供浏览器版、桌面版、CLI 三种使用方式。

## 技术方案

**Python + Playwright + yt-dlp + PyQt6**

- 浏览器版：Playwright 启动 Chromium，注入 JS 提供下载按钮和快捷键，导出 Cookie 给 yt-dlp 下载
- 桌面版：Playwright 控制浏览器 + PyQt6 提供控制面板，信号/槽通信
- CLI 版：yt-dlp 直接下载，可选通过 Playwright 自动化小红书创作者中心发布

## 项目结构

```
tt-copy/
├── start.command           # Mac 浏览器版启动脚本
├── start.bat               # Windows 浏览器版启动脚本
├── start_desktop.command   # Mac 桌面版启动脚本
├── start_desktop.bat       # Windows 桌面版启动脚本
├── start_cli.command       # Mac CLI 版启动脚本（下载+发布交互）
├── _run.py                 # Windows 嵌入式 Python 启动入口
├── _run_desktop.py         # Windows 桌面版启动入口
├── requirements.txt        # playwright, yt-dlp, PyQt6, PyQt6-WebEngine
├── ttcopy/
│   ├── __init__.py         # 版本号
│   ├── main.py             # 浏览器版主入口
│   ├── cli.py              # CLI 入口（yt-dlp 下载 + --publish 发布）
│   ├── publisher.py        # 小红书发布器（Playwright 自动化）
│   ├── desktop.py          # 桌面版 QtWebEngine 方案
│   ├── desktop_shell.py    # 桌面版 Playwright + PyQt6 混合方案
│   ├── interceptor.py      # 网络请求拦截，捕获图片 CDN URL
│   ├── downloader.py       # 视频/图片下载（yt-dlp + 直接请求）
│   └── config.py           # 配置（下载目录、UA、viewport 等）
├── downloads/              # 默认下载目录
├── DESIGN.md
└── README.md
```

## 平台启动机制

### Mac (`start.command` / `start_desktop.command` / `start_cli.command`)

1. 检查系统 Python 3
2. 创建 `.venv` 虚拟环境
3. 按需安装依赖（检测缺失的才安装）
4. 启动对应模块

### Windows (`start.bat` / `start_desktop.bat` + `_run.py`)

1. 下载嵌入式 Python 3.11.9（免安装，约 12MB）
2. 安装 pip、依赖、Chromium
3. 通过 `_run.py` 启动（手动设置 `sys.path` 绕过 `._pth` 限制）

> `start.bat` 使用纯英文输出，避免 GBK/UTF-8 编码冲突。

## 模块设计

### 1. `config.py` — 配置模块

提供默认配置，根据平台自动切换 User-Agent，支持命令行参数覆盖：

```python
DEFAULT_CONFIG = {
    "download_dir": "./downloads",
    "filename_template": "{author}_{video_id}_{timestamp}",
    "hotkey": "ctrl+d",
    "auto_download": False,
    "user_agent": _default_user_agent(),
    "viewport": {"width": 1280, "height": 900},
}
```

### 2. `interceptor.py` — 网络请求拦截

监听页面网络响应，从 TikTok API 中提取图文帖图片 URL 列表，以 `video_id` 为 key 缓存。

### 3. `downloader.py` — 下载模块

| 内容类型 | 下载方式 | 说明 |
|---------|---------|------|
| 视频 | yt-dlp | 携带 Cookie 和浏览器 UA/Referer |
| 图文帖 | 优先直接请求 CDN URL，回退 yt-dlp | 支持多图 |

提供两种调用方式：
- `download()` — 异步，供浏览器版/桌面版使用
- `download_sync()` — 同步，供 CLI 使用，无需 asyncio 或浏览器

### 4. `main.py` — 浏览器版主入口

启动流程：
1. 初始化配置、拦截器、下载器
2. 启动 Playwright Chromium（headless=False）
3. 注入 JS（下载按钮 + 快捷键）
4. 监听 console 消息捕获 `__TTCOPY_DL__:` 下载指令
5. 导出 Cookie → 调用 downloader
6. 保持运行直到浏览器关闭

### 5. `desktop_shell.py` — 桌面版（Playwright + PyQt6）

架构：
- **浏览器**: Playwright 控制系统 Chromium（视频播放正常）
- **外壳**: PyQt6 提供控制面板、系统托盘、下载管理
- **通信**: 浏览器与外壳通过信号/槽实时同步

特点：
- 视频播放正常（系统 Chromium）
- 独立控制面板显示当前内容、下载状态
- 系统托盘常驻
- 实时同步浏览器状态
- 日志查看

### 6. `cli.py` — CLI 入口

```bash
python -m ttcopy.cli <url> [--output DIR] [--publish]
```

- 解析 TikTok URL，提取 author/video_id
- 调用 `downloader.download_sync()` 下载
- `--publish` 触发交互式输入标题/描述，调用 publisher 发布

### 7. `publisher.py` — 小红书发布器

`XHSPublisher` 类，Playwright 自动化小红书创作者中心：

**Cookie 持久化**:
- 使用 Playwright `storage_state` 保存/加载登录态
- 存储路径: `~/.ttcopy/xhs_cookies.json`
- 首次使用弹出浏览器扫码登录，之后自动复用
- Cookie 过期自动检测并重新登录

**发布流程**:
1. 打开 `https://creator.xiaohongshu.com/publish/publish`
2. `input[type="file"]` + `set_input_files` 上传视频
3. 等待视频处理完成（检测封面元素出现）
4. `keyboard.type` 填写标题和描述
5. 点击发布按钮
6. 检测发布成功状态

## 依赖

```
playwright>=1.40.0
yt-dlp>=2025.1.0
PyQt6>=6.6.0
PyQt6-WebEngine>=6.6.0
```

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 下载 403 | 重新导出浏览器 Cookie 重试 |
| 无法识别当前内容 | 按钮变红色提示，1 秒后恢复 |
| 图片直接下载失败 | 回退到 yt-dlp |
| 网络超时 | yt-dlp 内置 30 秒超时 |
| 小红书 Cookie 过期 | 自动检测并弹出浏览器重新登录 |
| 视频处理超时 | 等待 5 分钟后强制继续 |
