# tt-copy

TikTok 网页版一键下载工具。刷视频时点一下就能保存到本地，支持视频和图文帖。

> **桌面版已上线** — 浏览器嵌入独立窗口，滑动时自动识别，随时下载。见下方 [桌面版](#桌面版) 说明。

## 功能

- 浏览器内一键下载当前播放的视频/图文
- 快捷键 **Ctrl+Shift+D**（Mac: **Cmd+Shift+D**）
- 右下角绿色悬浮按钮，点击即下载
- 自动携带浏览器 Cookie，无需手动登录
- 支持 Mac 和 Windows，双击启动，无需预装任何环境

## 快速开始

### Mac

1. 下载项目到本地
2. 双击 `start.command` 启动

首次启动会自动完成以下步骤（需要网络）：
- 创建 Python 虚拟环境
- 安装依赖（playwright + yt-dlp）
- 下载 Chromium 浏览器（约 150MB）

> 前提：需要系统已安装 Python 3。没有的话先执行 `brew install python`。

### Windows

1. 将项目文件夹放到一个**不含中文**的路径下（如 `D:\tool`）
2. 双击 `start.bat` 启动

首次启动会自动完成以下步骤（需要网络）：
- 下载嵌入式 Python 3.11（约 12MB）
- 安装 pip 和依赖
- 下载 Chromium 浏览器（约 150MB）

> 无需预装 Python 或 Chrome，所有环境自动配置。

### 命令行启动（Mac）

如果你熟悉命令行，也可以手动操作：

```bash
cd ~/Documents/Playground/tt-copy
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python -m ttcopy.main
```

指定下载目录：

```bash
python -m ttcopy.main --output ~/Videos/tiktok
```

## 使用方法

启动后会自动打开 Chromium 浏览器并导航到 TikTok：

1. 正常刷视频
2. 看到想下载的内容时，点击右下角**绿色下载按钮**，或按快捷键
3. 按钮变橙色 = 下载中，变回绿色 = 完成，变红色 = 失败
4. 文件保存在项目目录下的 `downloads/` 文件夹

文件名格式：`作者_视频ID_时间戳.mp4`（图文帖为 `.jpg`）

## 桌面版 (Desktop Shell)

**`start_desktop.command` / `start_desktop.bat`** — Playwright + PyQt6 桌面壳，视频播放正常。

**架构：**
- **浏览器**: Playwright 控制系统 Chromium（视频播放完美）
- **外壳**: PyQt6 提供控制面板、系统托盘、下载管理
- **通信**: 浏览器与外壳通过信号/槽实时同步

**桌面版特点：**
- ✅ **视频播放正常**（使用系统 Chromium，非 QtWebEngine）
- ✅ **独立控制面板** — PyQt6 窗口显示当前内容、下载状态
- ✅ **系统托盘** — 关闭控制面板不退出，托盘保持运行
- ✅ **实时同步** — 浏览器滑动时，控制面板自动显示当前作者
- ✅ **快捷键** — Ctrl+D 下载，F5 刷新
- ✅ **导航控制** — 前进/后退/刷新按钮
- ✅ **日志查看** — 实时显示运行日志

**Mac 启动桌面版：**
```bash
double-click start_desktop.command
# 或命令行
python -m ttcopy.desktop_shell
```

**Windows 启动桌面版：**
```bash
double-click start_desktop.bat
```

**界面说明：**
```
┌─────────────────────────────────────┐  ┌───────────────────────────────┐
│  Chromium 浏览器窗口 (Playwright)    │  │  PyQt6 控制面板               │
│                                     │  │                               │
│  ┌─────────────────────────────┐   │  │  ┌─────────────────────┐     │
│  │                             │   │  │  │ 当前: @author       │     │
│  │   TikTok 网页               │   │  │  │ 类型: 视频          │     │
│  │   (视频播放正常)            │   │  │  │ ID: 7627...         │     │
│  │                             │   │  │  └─────────────────────┘     │
│  │   [滑动浏览视频]            │   │  │                              │
│  │                             │   │  │  [⬇ 下载当前视频]           │
│  └─────────────────────────────┘   │  │                              │
│                                     │  │  [← → ↻ 导航控制]            │
└─────────────────────────────────────┘  │                              │
                                         │  [📁 选择下载目录]           │
                                         │                              │
                                         │  ┌─────────────────────┐     │
                                         │  │ 日志:               │     │
                                         │  │ [14:32:01] 已就绪   │     │
                                         │  └─────────────────────┘     │
                                         └───────────────────────────────┘
```

---

## 项目结构

```
tt-copy/
├── start.command           # Mac 浏览器版启动脚本
├── start.bat               # Windows 浏览器版启动脚本
├── start_desktop.command   # Mac 桌面版启动脚本
├── start_desktop.bat       # Windows 桌面版启动脚本
├── _run.py                 # Windows 嵌入式 Python 启动入口
├── _run_desktop.py         # Windows 桌面版启动入口
├── requirements.txt        # Python 依赖
├── ttcopy/
│   ├── __init__.py
│   ├── main.py             # 浏览器版主入口
│   ├── desktop.py          # 桌面版主窗口
│   ├── interceptor.py      # 网络请求拦截
│   ├── downloader.py       # 视频/图片下载
│   └── config.py           # 配置
├── downloads/              # 默认下载目录
├── DESIGN.md               # 技术设计文档
└── README.md
```

## 技术方案

Playwright 启动 Chromium → JS 注入下载按钮和快捷键 → 用户触发下载 → 导出浏览器 Cookie → yt-dlp 下载视频 / 直接请求下载图片。

## 常见问题

### Windows 双击 start.bat 一闪而过

路径包含中文或文件夹未解压。把项目放到纯英文路径下（如 `D:\tool`），确保是解压后的文件夹。

如需查看详细错误，打开 cmd 手动运行：
```
cd /d D:\tool
start.bat
```

### 下载失败 403

通常是 Cookie 过期。关闭浏览器重新启动 tt-copy，重新登录 TikTok 后再试。

### Mac 提示"无法打开，因为来自身份不明的开发者"

右键点击 `start.command` → 选择"打开" → 确认打开。或在终端执行：
```bash
chmod +x start.command
```
