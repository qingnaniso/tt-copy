# TikTok 视频下载器 (tt-copy)

## 概述

在 TikTok 网页版刷视频时，一键下载当前播放的视频到本地，尽量去除水印。

## 技术方案

**Python + Playwright**：用 Playwright 启动有头浏览器打开 TikTok，后台拦截网络请求捕获视频 CDN URL，用户按快捷键或点击注入的下载按钮保存视频。

## 项目结构

```
tt-copy/
├── ttcopy/
│   ├── __init__.py          # 版本号
│   ├── main.py              # 入口：启动浏览器、事件循环
│   ├── interceptor.py       # 网络请求拦截，捕获视频 URL
│   ├── downloader.py        # 视频下载 + 去水印逻辑
│   └── config.py            # 配置（下载目录、快捷键等）
├── requirements.txt
├── DESIGN.md
├── README.md
└── downloads/               # 默认下载目录
```

## 模块设计

### 1. `config.py` — 配置模块

提供默认配置，支持运行时覆盖：

```python
DEFAULT_CONFIG = {
    "download_dir": "./downloads",
    "filename_template": "{author}_{video_id}_{timestamp}",
    "hotkey": "ctrl+d",           # 下载快捷键
    "auto_download": False,        # 自动下载所有刷到的视频
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "viewport": {"width": 1280, "height": 900},
}
```

### 2. `interceptor.py` — 网络请求拦截

**职责**：监听页面所有网络请求/响应，提取视频信息。

**核心类 `VideoInterceptor`**：

```python
class VideoInterceptor:
    def __init__(self):
        self.video_cache = {}  # video_id → VideoInfo
    
    async def on_response(self, response):
        """Playwright response 事件回调"""
        url = response.url
        
        # 1. 拦截视频 CDN URL
        if self._is_video_cdn(url):
            video_id = self._extract_video_id(url)
            self._cache_video_url(video_id, url, watermark=True)
        
        # 2. 拦截 TikTok API 响应，提取无水印 URL
        if self._is_tiktok_api(url):
            await self._parse_api_response(response)
    
    def get_current_video(self, video_id) -> Optional[VideoInfo]:
        """获取指定视频的下载信息"""
        return self.video_cache.get(video_id)
```

**CDN URL 匹配模式**：
- `*tiktokcdn.com*` 域名下的视频请求
- `*tiktokcdn-*.com*`
- Content-Type 为 `video/mp4`

**API 拦截目标**：
- `/api/item/detail` — 单个视频详情
- `/api/recommend/item_list` — 推荐列表
- 从响应 JSON 提取 `download_addr`（无水印）和 `play_addr`（有水印）

### 3. `downloader.py` — 下载模块

**职责**：根据视频信息下载文件到本地。

```python
class VideoDownloader:
    def __init__(self, config):
        self.config = config
        self.client = httpx.AsyncClient(...)
    
    async def download(self, video_info: VideoInfo) -> str:
        """下载视频，返回保存路径"""
        # 优先无水印 URL，回退到有水印 URL
        url = video_info.no_watermark_url or video_info.watermark_url
        
        filename = self._make_filename(video_info)
        filepath = Path(self.config["download_dir"]) / filename
        
        # 流式下载，显示进度
        async with self.client.stream("GET", url, headers=HEADERS) as resp:
            with open(filepath, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
        
        return str(filepath)
```

**去水印策略优先级**：
1. API 响应中的 `download_addr`（无水印）
2. CDN URL 中带 `watermark=0` 参数的版本
3. 兜底：直接下载 CDN 拦截到的 URL（可能带水印）

**HTTP Headers**：
- `Referer: https://www.tiktok.com/`
- `User-Agent`: 与浏览器一致
- 从浏览器 context 复制 cookies

### 4. `main.py` — 主入口

**职责**：串联所有模块，管理浏览器生命周期。

**流程**：
1. 初始化配置
2. 启动 Playwright chromium（headless=False）
3. 创建浏览器上下文（设置 UA、viewport）
4. 注册 `interceptor.on_response` 到页面 response 事件
5. 注入 JS 脚本（下载按钮 + 快捷键）
6. 导航到 `https://www.tiktok.com`
7. 监听页面 console 消息，捕获下载指令
8. 收到下载指令时调用 `downloader.download()`
9. 保持运行直到浏览器关闭

**注入 JS 脚本功能**：
- 在视频右侧添加悬浮下载按钮（绿色圆形，下载图标）
- 监听 `Ctrl+D`（Mac 为 `Cmd+D`）快捷键
- 从当前视频 DOM 元素提取 video_id（URL 路径或 data 属性）
- 通过 `console.log("__TTCOPY_DOWNLOAD__:" + JSON.stringify({videoId, author}))` 传递下载指令
- 下载按钮跟随当前可见视频位置

### 5. `__init__.py`

```python
__version__ = "0.1.0"
```

## 依赖

```
playwright>=1.40.0
httpx>=0.27.0
```

安装：
```bash
pip install -r requirements.txt
playwright install chromium
```

## 使用方式

```bash
# 启动
python -m ttcopy.main

# 或指定下载目录
python -m ttcopy.main --output ~/Videos/tiktok

# 自动下载模式（刷到的都下载）
python -m ttcopy.main --auto
```

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 视频 CDN URL 过期 | 重新从缓存获取最新 URL |
| 403 下载被拒 | 从浏览器获取最新 cookies 重试 |
| 无法提取无水印 URL | 回退到有水印版本，终端提示 |
| 网络超时 | 重试 2 次，失败后提示 |
| 磁盘空间不足 | 捕获 OSError，提示用户 |

## 任务拆分

| # | 模块 | 文件 | 依赖 |
|---|------|------|------|
| T1 | 配置模块 | `config.py` | 无 |
| T2 | 网络拦截 | `interceptor.py` | T1 |
| T3 | 下载模块 | `downloader.py` | T1 |
| T4 | 主入口+注入JS | `main.py` | T1, T2, T3 |
| T5 | 项目文件 | `requirements.txt`, `__init__.py`, `README.md` | 无 |
