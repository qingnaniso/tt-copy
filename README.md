# tt-copy

TikTok / 抖音视频一键下载 + AI 生成文案 + 小红书自动发布工具。

支持 **Claude Code Skill**（主要）、浏览器版、桌面版、CLI 三种使用方式。

---

## 快速安装（推荐）

```bash
git clone https://github.com/qingnaniso/tt-copy.git
cd tt-copy
chmod +x install.sh && ./install.sh
```

脚本会自动完成：Homebrew → Python → ffmpeg → 虚拟环境 → Chromium → 配置文件 → Claude Code Skill 注册。

**唯一需要手动准备：** 安装过程中会提示输入 Kimi API Key（`sk-kimi-...`）。

> 没有终端习惯？直接在 GitHub 下载 ZIP 解压，双击 `install.sh` 也可以。

---

## 使用方式

### 方式一：Claude Code Skill（主推）

安装完成后，在 Claude Code 中粘贴 TikTok / 抖音链接，自动完成：

```
下载视频 → 抽取关键帧 → AI 识图 → 生成小红书文案 → 发布到小红书
```

首次发布小红书时会弹出浏览器扫码登录，之后自动复用 Cookie。

---

### 方式二：CLI 版

双击 `start_cli.command`，粘贴链接交互式操作：

```
链接: https://vm.tiktok.com/xxx
[1] 仅下载
[2] 下载并发布到小红书
选择 (1/2):
```

或命令行直接调用：

```bash
# 仅下载
.venv/bin/python -m ttcopy.cli "https://vm.tiktok.com/xxx"

# 下载并发布小红书
.venv/bin/python -m ttcopy.cli "https://vm.tiktok.com/xxx" --publish
```

---

### 方式三：浏览器版

双击 `start.command`，Chromium 打开 TikTok，刷到喜欢的视频点右下角按钮下载，或按 **Cmd+Shift+D**。

---

### 方式四：桌面版

双击 `start_desktop.command`，Playwright 浏览器 + PyQt6 控制面板双窗口，带系统托盘。

需额外安装桌面依赖：

```bash
.venv/bin/pip install -r requirements-desktop.txt
```

---

## 配置文件

首次安装后会在项目根目录生成 `.env`，可按需修改：

```bash
# AI 识图 & 文案生成（必填）
KIMI_API_URL=https://api.kimi.com/coding/v1/messages
KIMI_API_KEY=sk-kimi-...

# 项目路径（install.sh 自动填写）
TTCOPY_DIR=/path/to/tt-copy

# 小红书多账号（可选，留空用默认账号）
XHS_ACCOUNT=

# 飞书自动流水线（默认关闭）
# LARK_NOTIFY=true
```

---

## 项目结构

```
tt-copy/
├── install.sh              # 一键安装脚本
├── .env.example            # 配置模板（复制为 .env 后填写）
├── SKILL.md                # Claude Code Skill 定义（install.sh 自动注册）
├── auto_pipeline.sh        # 飞书监听 → 全自动流水线（进阶用法）
├── start.command           # 浏览器版启动（Mac）
├── start_desktop.command   # 桌面版启动（Mac）
├── start_cli.command       # CLI 版启动（Mac）
├── requirements.txt        # 核心依赖（yt-dlp, playwright）
├── requirements-desktop.txt # 桌面版额外依赖（PyQt6）
└── ttcopy/
    ├── cli.py              # CLI 入口
    ├── downloader.py       # 视频下载（yt-dlp）
    ├── frame_extractor.py  # 关键帧提取（ffmpeg）
    ├── vision.py           # Kimi Vision API（识图 + 文案生成）
    ├── publisher.py        # 小红书自动发布（Playwright）
    ├── main.py             # 浏览器版主入口
    ├── desktop.py          # 桌面版 PyQt6 主窗口
    └── config.py           # 配置管理
```

---

## 常见问题

**Mac 提示"无法打开，因为来自身份不明的开发者"**

```bash
chmod +x install.sh start.command start_desktop.command start_cli.command
```

或右键点击文件 → 选择"打开"。

**下载失败 403**

Cookie 过期。重新启动浏览器版登录 TikTok 后重试。

**小红书发布失败**

- 首次使用需扫码登录，Cookie 自动保存后续复用
- 确保视频为 mp4 格式
- Cookie 过期会自动弹出浏览器重新登录
