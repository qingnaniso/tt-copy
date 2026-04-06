# tt-copy

在 TikTok 网页版刷视频时，一键下载当前播放的视频到本地。

## 安装

```bash
cd ~/Documents/Playground/tt-copy
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 启动

```bash
cd ~/Documents/Playground/tt-copy
source .venv/bin/activate
python -m ttcopy.main
```

指定下载目录：

```bash
python -m ttcopy.main --output ~/Videos/tiktok
```

## 操作

启动后会打开 Chrome 浏览器并导航到 TikTok：

1. 正常刷视频
2. 看到想下载的视频时，点击右下角**绿色下载按钮**，或按 **Cmd+Shift+D**
3. 按钮变橙色表示下载中，变回绿色表示完成
4. 视频保存在 `./downloads` 目录，文件名格式：`作者_视频ID_时间戳.mp4`

## 技术方案

Playwright 打开浏览器 → JS 注入识别当前视频 → yt-dlp 下载。
