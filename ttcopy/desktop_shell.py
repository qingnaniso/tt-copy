"""
TT-Copy Desktop Shell - 基于 Playwright + PyQt6 的真桌面版
Playwright 控制系统 Chromium（视频播放正常）
PyQt6 提供桌面壳（控制面板、系统托盘、下载管理）
"""
import sys
import json
import time
import asyncio
import threading
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QSystemTrayIcon, QMenu, QStyle,
    QFileDialog, QMessageBox, QLineEdit, QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QObject, QThread, QSize, QTimer
from PyQt6.QtGui import QIcon, QAction, QKeySequence, QShortcut, QFont

from ttcopy.config import get_config
from ttcopy.downloader import VideoDownloader


class PlaywrightWorker(QThread):
    """后台运行 Playwright 的线程"""
    log_message = pyqtSignal(str)
    download_requested = pyqtSignal(dict)
    browser_ready = pyqtSignal(bool)
    page_info = pyqtSignal(dict)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.loop = None
        self.browser = None
        self.context = None
        self.page = None
        self.running = True
        self.cookies_path = str(Path(config["download_dir"]) / ".cookies.txt")
    
    def run(self):
        """在线程中运行异步事件循环"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main())
    
    async def _main(self):
        """主协程"""
        try:
            from playwright.async_api import async_playwright
            
            self.log_message.emit("正在启动 Chromium...")
            
            async with async_playwright() as p:
                # 启动系统 Chromium（视频播放正常）
                self.browser = await p.chromium.launch(
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--window-size=1280,800",
                        "--window-position=100,100",
                    ]
                )
                
                self.context = await self.browser.new_context(
                    user_agent=self.config.get("user_agent"),
                    viewport={"width": 1280, "height": 800},
                )
                
                self.page = await self.context.new_page()
                
                # 设置拦截和注入
                self.page.on("response", self._on_response)
                self.page.on("console", self._on_console)
                
                # 注入反检测和下载按钮脚本
                await self.page.add_init_script(self._get_inject_js())
                
                # 导航到 TikTok
                await self.page.goto("https://www.tiktok.com", wait_until="domcontentloaded")
                
                self.log_message.emit("浏览器已就绪")
                self.browser_ready.emit(True)
                
                # 保持运行
                while self.running:
                    await asyncio.sleep(0.5)
                    
        except Exception as e:
            self.log_message.emit(f"错误: {str(e)[:200]}")
            self.browser_ready.emit(False)
    
    def _on_response(self, response):
        """拦截响应获取图文信息"""
        url = response.url
        if "/api/" in url or "/item/" in url:
            asyncio.create_task(self._parse_response(response))
    
    async def _parse_response(self, response):
        try:
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                return
            data = await response.json()
            
            # 提取视频信息
            items = []
            if isinstance(data, dict):
                items = data.get("itemList", []) or data.get("items", [])
                if not items and "itemInfo" in data:
                    items = [data["itemInfo"].get("itemStruct", {})]
            
            for item in items:
                if not isinstance(item, dict):
                    continue
                vid = str(item.get("id", ""))
                if not vid:
                    continue
                
                author_info = item.get("author", {})
                author = author_info.get("uniqueId") or author_info.get("nickname", "")
                
                # 提取图片 URL
                image_urls = []
                image_post = item.get("imagePost", {})
                if isinstance(image_post, dict):
                    for img in image_post.get("images", []):
                        if isinstance(img, dict):
                            url_list = img.get("imageURL", {}).get("urlList", [])
                            if url_list:
                                image_urls.append(url_list[0])
                
                content_type = "photo" if image_urls else "video"
                
                self.page_info.emit({
                    "video_id": vid,
                    "author": author,
                    "type": content_type,
                    "image_urls": image_urls
                })
        except:
            pass
    
    def _on_console(self, msg):
        """处理 console 消息"""
        text = msg.text
        if text.startswith("__TTCOPY_DL__:"):
            try:
                data = json.loads(text[len("__TTCOPY_DL__:"):])
                self.download_requested.emit(data)
            except:
                pass
        elif text.startswith("__TTCOPY_CURRENT__:"):
            try:
                data = json.loads(text[len("__TTCOPY_CURRENT__:"):])
                self.page_info.emit(data)
            except:
                pass
    
    def _get_inject_js(self):
        """注入的 JS 代码"""
        return r"""
        (function() {
            if (window.__ttcopy_injected__) return;
            window.__ttcopy_injected__ = true;
            
            // 反检测
            delete Object.getPrototypeOf(navigator).webdriver;
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            
            // 查找当前内容
            function getCurrentContent() {
                const pathMatch = location.pathname.match(/@([^/]+)/(video|photo)/(\d+)/);
                if (pathMatch) {
                    return { author: pathMatch[1], videoId: pathMatch[3], type: pathMatch[2] };
                }
                
                const videos = document.querySelectorAll('video');
                for (const v of videos) {
                    const rect = v.getBoundingClientRect();
                    if (rect.top >= -200 && rect.top < window.innerHeight * 0.7) {
                        let el = v;
                        for (let i = 0; i < 20; i++) {
                            if (!el.parentElement) break;
                            el = el.parentElement;
                            const link = el.querySelector('a[href*="/video/"], a[href*="/photo/"]');
                            if (link) {
                                const m = link.href.match(/@([^/]+)/(video|photo)/(\d+)/);
                                if (m) return { author: m[1], videoId: m[3], type: m[2] };
                            }
                        }
                    }
                }
                return null;
            }
            
            // 定期报告当前内容
            let lastVideoId = null;
            setInterval(() => {
                const info = getCurrentContent();
                if (info && info.videoId !== lastVideoId) {
                    lastVideoId = info.videoId;
                    console.log('__TTCOPY_CURRENT__:' + JSON.stringify(info));
                }
            }, 500);
            
            // 下载函数
            window.__ttcopy_download = function() {
                const info = getCurrentContent();
                if (info) {
                    console.log('__TTCOPY_DL__:' + JSON.stringify(info));
                    return true;
                }
                return false;
            };
            
            console.log('[TT-Copy] Injected');
        })();
        """
    
    async def download_current(self):
        """触发下载当前视频"""
        if self.page:
            await self.page.evaluate("window.__ttcopy_download && window.__ttcopy_download()")
    
    async def navigate(self, url):
        """导航到指定 URL"""
        if self.page:
            await self.page.goto(url, wait_until="domcontentloaded")
    
    async def refresh(self):
        """刷新页面"""
        if self.page:
            await self.page.reload()
    
    async def go_back(self):
        """后退"""
        if self.page:
            await self.page.go_back()
    
    async def go_forward(self):
        """前进"""
        if self.page:
            await self.page.go_forward()
    
    async def export_cookies(self):
        """导出 cookies"""
        if self.context:
            cookies = await self.context.cookies()
            with open(self.cookies_path, "w") as f:
                f.write("# Netscape HTTP Cookie File\n")
                for c in cookies:
                    domain = c.get("domain", "")
                    flag = "TRUE" if domain.startswith(".") else "FALSE"
                    path_val = c.get("path", "/")
                    secure = "TRUE" if c.get("secure") else "FALSE"
                    expires = str(max(int(c.get("expires", 0)), 0))
                    name = c.get("name", "")
                    value = c.get("value", "")
                    f.write(f"{domain}\t{flag}\t{path_val}\t{secure}\t{expires}\t{name}\t{value}\n")
            return self.cookies_path
        return None
    
    def stop(self):
        """停止 Playwright"""
        self.running = False
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._cleanup(), self.loop)
    
    async def _cleanup(self):
        """清理资源"""
        try:
            if self.browser:
                await self.browser.close()
        except:
            pass


class DownloadWorker(QThread):
    """下载线程"""
    progress = pyqtSignal(str)
    finished_with_result = pyqtSignal(bool, str)
    
    def __init__(self, downloader, video_url, author, video_id, content_type, cookies_file=None):
        super().__init__()
        self.downloader = downloader
        self.video_url = video_url
        self.author = author
        self.video_id = video_id
        self.content_type = content_type
        self.cookies_file = cookies_file
    
    def run(self):
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            self.progress.emit("下载中...")
            filepath = loop.run_until_complete(
                self.downloader.download(self.video_url, self.author, self.video_id, self.cookies_file)
            )
            self.finished_with_result.emit(True, f"已保存: {filepath}")
        except Exception as e:
            self.finished_with_result.emit(False, str(e)[:200])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.downloader = VideoDownloader(self.config)
        
        self.playwright_worker = None
        self.current_video_info = {}
        self.download_worker = None
        
        self.setWindowTitle("TT-Copy Desktop Shell")
        self.setMinimumSize(400, 600)
        
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_tray()
        
        # 启动 Playwright
        self._start_playwright()
    
    def _setup_ui(self):
        """设置界面"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 样式
        self.setStyleSheet("""
            QMainWindow {
                background: #1a1a1a;
            }
            QWidget {
                background: #1a1a1a;
                color: #fff;
            }
            QPushButton {
                background: #25c554;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background: #1ea345; }
            QPushButton:pressed { background: #178a3a; }
            QPushButton:disabled { background: #666; }
            QPushButton.secondary {
                background: #444;
            }
            QPushButton.secondary:hover { background: #555; }
            QLabel {
                color: #ccc;
                font-size: 13px;
            }
            QLabel.title {
                color: #25c554;
                font-size: 18px;
                font-weight: bold;
            }
            QLabel.status {
                color: #888;
                font-size: 12px;
            }
            QLineEdit {
                background: #2a2a2a;
                color: #fff;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 8px;
            }
            QTextEdit {
                background: #2a2a2a;
                color: #aaa;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 8px;
                font-family: monospace;
                font-size: 11px;
            }
            QProgressBar {
                border: none;
                background: #333;
                height: 4px;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #25c554;
                border-radius: 2px;
            }
        """)
        
        # 标题
        title = QLabel("TT-Copy Desktop Shell")
        title.setProperty("class", "title")
        layout.addWidget(title)
        
        # 状态
        self.status_label = QLabel("正在启动...")
        self.status_label.setProperty("class", "status")
        layout.addWidget(self.status_label)
        
        layout.addSpacing(20)
        
        # 当前内容信息
        info_group = QWidget()
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(5)
        info_layout.setContentsMargins(10, 10, 10, 10)
        info_group.setStyleSheet("background: #252525; border-radius: 8px;")
        
        self.current_author = QLabel("作者: -")
        self.current_type = QLabel("类型: -")
        self.current_id = QLabel("ID: -")
        
        info_layout.addWidget(QLabel("当前内容:"))
        info_layout.addWidget(self.current_author)
        info_layout.addWidget(self.current_type)
        info_layout.addWidget(self.current_id)
        
        layout.addWidget(info_group)
        
        layout.addSpacing(20)
        
        # 下载按钮
        self.download_btn = QPushButton("⬇ 下载当前视频")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._on_download)
        layout.addWidget(self.download_btn)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        layout.addSpacing(10)
        
        # 导航控制
        nav_group = QWidget()
        nav_layout = QHBoxLayout(nav_group)
        nav_layout.setSpacing(10)
        
        self.back_btn = QPushButton("◀")
        self.back_btn.setToolTip("后退")
        self.back_btn.setProperty("class", "secondary")
        self.back_btn.clicked.connect(self._on_back)
        
        self.forward_btn = QPushButton("▶")
        self.forward_btn.setToolTip("前进")
        self.forward_btn.setProperty("class", "secondary")
        self.forward_btn.clicked.connect(self._on_forward)
        
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setToolTip("刷新")
        self.refresh_btn.setProperty("class", "secondary")
        self.refresh_btn.clicked.connect(self._on_refresh)
        
        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.forward_btn)
        nav_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(nav_group)
        
        # 地址栏
        self.address_bar = QLineEdit()
        self.address_bar.setPlaceholderText("输入 TikTok 链接或关键词...")
        self.address_bar.returnPressed.connect(self._on_navigate)
        layout.addWidget(self.address_bar)
        
        layout.addSpacing(10)
        
        # 下载目录按钮
        self.folder_btn = QPushButton("📁 选择下载目录")
        self.folder_btn.setProperty("class", "secondary")
        self.folder_btn.clicked.connect(self._on_select_folder)
        layout.addWidget(self.folder_btn)
        
        layout.addStretch()
        
        # 日志区域
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(150)
        self.log_area.setPlaceholderText("运行日志...")
        layout.addWidget(self.log_area)
    
    def _setup_shortcuts(self):
        """设置快捷键"""
        shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        shortcut.activated.connect(self._on_download)
        
        shortcut_f5 = QShortcut(QKeySequence("F5"), self)
        shortcut_f5.activated.connect(self._on_refresh)
    
    def _setup_tray(self):
        """设置系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        
        tray_menu = QMenu()
        
        show_action = QAction("显示控制面板", self)
        show_action.triggered.connect(self.show)
        
        download_action = QAction("下载当前视频", self)
        download_action.triggered.connect(self._on_download)
        
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._on_quit)
        
        tray_menu.addAction(show_action)
        tray_menu.addAction(download_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
    
    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
    
    def _start_playwright(self):
        """启动 Playwright"""
        self.playwright_worker = PlaywrightWorker(self.config)
        self.playwright_worker.log_message.connect(self._on_log)
        self.playwright_worker.download_requested.connect(self._on_download_requested)
        self.playwright_worker.browser_ready.connect(self._on_browser_ready)
        self.playwright_worker.page_info.connect(self._on_page_info)
        self.playwright_worker.start()
    
    def _on_log(self, msg):
        """接收日志"""
        self.log_area.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
    
    def _on_browser_ready(self, ready):
        """浏览器就绪"""
        if ready:
            self.status_label.setText("浏览器已就绪")
            self.download_btn.setEnabled(True)
            self.tray_icon.showMessage(
                "TT-Copy", 
                "浏览器已启动，可以开始浏览和下载了",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
        else:
            self.status_label.setText("浏览器启动失败")
    
    def _on_page_info(self, info):
        """页面信息更新"""
        self.current_video_info = info
        author = info.get("author", "-")
        content_type = info.get("type", "video")
        vid = info.get("video_id", "-")
        
        self.current_author.setText(f"作者: @{author}")
        self.current_type.setText(f"类型: {'图文' if content_type == 'photo' else '视频'}")
        self.current_id.setText(f"ID: {vid[:20]}..." if len(str(vid)) > 20 else f"ID: {vid}")
        
        self.status_label.setText(f"当前: @{author}")
    
    def _on_download(self):
        """触发下载"""
        if self.playwright_worker and self.playwright_worker.loop:
            asyncio.run_coroutine_threadsafe(
                self.playwright_worker.download_current(),
                self.playwright_worker.loop
            )
    
    def _on_download_requested(self, data):
        """处理下载请求"""
        author = data.get("author", "unknown")
        video_id = data.get("videoId")
        content_type = data.get("type", "video")
        
        if not video_id:
            QMessageBox.warning(self, "下载失败", "无法获取视频 ID")
            return
        
        content_url = f"https://www.tiktok.com/@{author}/{content_type}/{video_id}"
        
        # 导出 cookies
        cookies_file = None
        if self.playwright_worker and self.playwright_worker.loop:
            future = asyncio.run_coroutine_threadsafe(
                self.playwright_worker.export_cookies(),
                self.playwright_worker.loop
            )
            try:
                cookies_file = future.result(timeout=5)
            except:
                pass
        
        # 禁用按钮
        self.download_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        # 启动下载线程
        self.download_worker = DownloadWorker(
            self.downloader, content_url, author, video_id, content_type, cookies_file
        )
        self.download_worker.progress.connect(self.status_label.setText)
        self.download_worker.finished_with_result.connect(self._on_download_finished)
        self.download_worker.start()
    
    def _on_download_finished(self, success, message):
        """下载完成"""
        self.download_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.status_label.setText(f"✓ {message}")
            self.tray_icon.showMessage("下载完成", message, QSystemTrayIcon.MessageIcon.Information, 3000)
        else:
            self.status_label.setText(f"✗ {message}")
    
    def _on_back(self):
        """后退"""
        if self.playwright_worker and self.playwright_worker.loop:
            asyncio.run_coroutine_threadsafe(
                self.playwright_worker.go_back(),
                self.playwright_worker.loop
            )
    
    def _on_forward(self):
        """前进"""
        if self.playwright_worker and self.playwright_worker.loop:
            asyncio.run_coroutine_threadsafe(
                self.playwright_worker.go_forward(),
                self.playwright_worker.loop
            )
    
    def _on_refresh(self):
        """刷新"""
        if self.playwright_worker and self.playwright_worker.loop:
            asyncio.run_coroutine_threadsafe(
                self.playwright_worker.refresh(),
                self.playwright_worker.loop
            )
    
    def _on_navigate(self):
        """导航"""
        text = self.address_bar.text().strip()
        if not text:
            return
        
        if not text.startswith(("http://", "https://")):
            text = "https://" + text
        
        if self.playwright_worker and self.playwright_worker.loop:
            asyncio.run_coroutine_threadsafe(
                self.playwright_worker.navigate(text),
                self.playwright_worker.loop
            )
    
    def _on_select_folder(self):
        """选择下载目录"""
        folder = QFileDialog.getExistingDirectory(self, "选择下载目录", self.config["download_dir"])
        if folder:
            self.config["download_dir"] = folder
            self.downloader = VideoDownloader(self.config)
            self.status_label.setText(f"下载目录: {folder}")
    
    def _on_quit(self):
        """退出"""
        if self.playwright_worker:
            self.playwright_worker.stop()
            self.playwright_worker.wait(5000)
        QApplication.quit()
    
    def closeEvent(self, event):
        """关闭窗口时最小化到托盘"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "TT-Copy",
            "已最小化到系统托盘，双击图标显示控制面板",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("TT-Copy Desktop Shell")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
