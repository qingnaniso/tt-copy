# tt-copy

TikTok 视频一键下载 + 小红书自动发布工具。支持浏览器版、桌面版、CLI 三种使用方式。

## 功能

- **浏览器版** — Playwright 打开 TikTok，刷到喜欢的视频点一下就下载
- **桌面版** — Playwright + PyQt6 独立窗口，带控制面板和系统托盘
- **CLI 版** — 粘贴链接直接下载，支持下载后自动发布到小红书
- 快捷键 **Ctrl+Shift+D**（Mac: **Cmd+Shift+D**）
- 自动携带浏览器 Cookie，无需手动登录
- 小红书 Cookie 持久化，首次扫码后自动复用

## 快速开始

### 浏览器版

双击 `start.command`（Mac）或 `start.bat`（Windows），打开 Chromium 刷 TikTok，点击右下角按钮下载。

### 桌面版

双击 `start_desktop.command`（Mac）或 `start_desktop.bat`（Windows），Playwright 浏览器 + PyQt6 控制面板双窗口运行。

### CLI 版（下载 + 发布小红书）

双击 `start_cli.command`，粘贴 TikTok 链接：

```
 链接: https://vm.tiktok.com/xxx
 [1] 仅下载
 [2] 下载并发布到小红书
 选择 (1/2): 2
```

选择 `2` 后输入标题和描述，自动上传到小红书创作者中心发布。首次使用需扫码登录，之后自动复用 Cookie。

也可以直接命令行调用：

```bash
# 仅下载
python -m ttcopy.cli "https://vm.tiktok.com/xxx"

# 下载并发布到小红书
python -m ttcopy.cli "https://vm.tiktok.com/xxx" --publish
```

### 命令行手动安装

```bash
cd ~/Documents/Playground/tt-copy
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 项目结构

```
tt-copy/
├── start.command           # Mac 浏览器版启动脚本
├── start.bat               # Windows 浏览器版启动脚本
├── start_desktop.command   # Mac 桌面版启动脚本
├── start_desktop.bat       # Windows 桌面版启动脚本
├── start_cli.command       # Mac CLI 版启动脚本（下载+发布）
├── _run.py                 # Windows 嵌入式 Python 启动入口
├── _run_desktop.py         # Windows 桌面版启动入口
├── requirements.txt        # Python 依赖
├── ttcopy/
│   ├── __init__.py         # 版本号
│   ├── main.py             # 浏览器版主入口
│   ├── cli.py              # CLI 入口（yt-dlp 下载 + --publish 发布）
│   ├── publisher.py        # 小红书发布器（Playwright 自动化创作者中心）
│   ├── desktop.py          # 桌面版 PyQt6 主窗口
│   ├── desktop_shell.py    # 桌面版 Playwright + PyQt6 混合架构
│   ├── interceptor.py      # 网络请求拦截，捕获图片 CDN URL
│   ├── downloader.py       # 视频/图片下载（yt-dlp + 直接请求）
│   └── config.py           # 配置（下载目录、UA、viewport 等）
├── downloads/              # 默认下载目录
├── DESIGN.md               # 技术设计文档
└── README.md
```

## 三种模式对比

| 特性 | 浏览器版 | 桌面版 | CLI 版 |
|------|---------|--------|--------|
| 启动方式 | `start.command` | `start_desktop.command` | `start_cli.command` |
| 浏览 TikTok | 内置浏览器 | 内置浏览器 + 控制面板 | 不需要 |
| 下载方式 | 按钮/快捷键 | 按钮/快捷键 | 粘贴链接 |
| 发布小红书 | - | - | 支持 |
| 系统托盘 | - | 支持 | - |
| 依赖 | Playwright | Playwright + PyQt6 | yt-dlp + Playwright（发布时） |

## 技术方案

- **浏览器版/桌面版**: Playwright 启动 Chromium → JS 注入下载按钮和快捷键 → 导出 Cookie → yt-dlp 下载
- **CLI 下载**: yt-dlp 直接下载，无需浏览器
- **小红书发布**: Playwright 打开创作者中心 → `set_input_files` 上传视频 → 填写标题描述 → 点击发布，Cookie 持久化到 `~/.ttcopy/xhs_cookies.json`

## 常见问题

### Windows 双击 start.bat 一闪而过

路径包含中文或文件夹未解压。把项目放到纯英文路径下（如 `D:\tool`），确保是解压后的文件夹。

### 下载失败 403

通常是 Cookie 过期。关闭浏览器重新启动 tt-copy，重新登录 TikTok 后再试。

### Mac 提示"无法打开，因为来自身份不明的开发者"

右键点击 `.command` 文件 → 选择"打开" → 确认打开。或在终端执行：
```bash
chmod +x start.command start_desktop.command start_cli.command
```

### 小红书发布失败

- 首次使用需在弹出的浏览器中扫码登录，登录后 Cookie 自动保存
- Cookie 过期后会自动弹出浏览器重新登录
- 确保视频文件为 mp4 格式
