"""
TikTok Desktop Downloader - 桌面版
基于 PyQt6 + QtWebEngine，浏览器嵌入桌面窗口
"""
import sys
import json
import time
import re
from pathlib import Path
from urllib.parse import urlencode, parse_qs, urlparse

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QSystemTrayIcon, QMenu, QStyle,
    QFileDialog, QMessageBox, QLineEdit
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QObject, QThread, QSize
from PyQt6.QtGui import QIcon, QAction, QKeySequence, QShortcut

from ttcopy.config import get_config
from ttcopy.downloader import VideoDownloader


class DownloadWorker(QThread):
    """后台下载线程"""
    progress = pyqtSignal(str)
    finished_with_result = pyqtSignal(bool, str)
    
    def __init__(self, downloader, video_url, author, video_id, content_type, image_urls=None):
        super().__init__()
        self.downloader = downloader
        self.video_url = video_url
        self.author = author
        self.video_id = video_id
        self.content_type = content_type
        self.image_urls = image_urls or []
    
    def run(self):
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            if self.content_type == "photo" and self.image_urls:
                self.progress.emit(f"下载图文帖 ({len(self.image_urls)} 张)...")
                saved = loop.run_until_complete(
                    self.downloader.download_images(self.image_urls, self.author, self.video_id)
                )
                if saved:
                    self.finished_with_result.emit(True, f"已保存 {len(saved)} 张图片")
                else:
                    # 回退到 yt-dlp
                    self.progress.emit("直接下载失败，尝试 yt-dlp...")
                    filepath = loop.run_until_complete(
                        self.downloader.download(self.video_url, self.author, self.video_id, None)
                    )
                    self.finished_with_result.emit(True, f"已保存: {filepath}")
            else:
                self.progress.emit("下载视频中...")
                filepath = loop.run_until_complete(
                    self.downloader.download(self.video_url, self.author, self.video_id, None)
                )
                self.finished_with_result.emit(True, f"已保存: {filepath}")
        except Exception as e:
            self.finished_with_result.emit(False, str(e)[:200])


class WebBridge(QObject):
    """Python 与 JS 通信的桥接"""
    download_requested = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def process_message(self, message: str):
        """处理从 JS 发来的消息"""
        try:
            data = json.loads(message)
            if data.get("action") == "download":
                self.download_requested.emit(data)
        except json.JSONDecodeError:
            pass


class TikTokWebPage(QWebEnginePage):
    """自定义 WebPage 拦截 console 消息和处理导航"""
    console_message = pyqtSignal(str)
    
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.bridge = WebBridge(self)
        self.profile = profile
        
        # 安装 URL 请求拦截器
        profile.setUrlRequestInterceptor(self._create_interceptor())
    
    def _create_interceptor(self):
        """创建请求拦截器来修改请求头"""
        from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestInfo
        
        class Interceptor(QWebEngineUrlRequestInterceptor):
            def interceptRequest(self, info: QWebEngineUrlRequestInfo):
                # 添加 Accept-Language 头
                info.setHttpHeader(b"Accept-Language", b"zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7")
                # 添加 Accept 头
                info.setHttpHeader(b"Accept", b"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8")
                # 添加 Sec-Fetch 头
                info.setHttpHeader(b"Sec-Fetch-Dest", b"document")
                info.setHttpHeader(b"Sec-Fetch-Mode", b"navigate")
                info.setHttpHeader(b"Sec-Fetch-Site", b"none")
                info.setHttpHeader(b"Sec-Fetch-User", b"?1")
                # 升级 insecure requests
                info.setHttpHeader(b"Upgrade-Insecure-Requests", b"1")
        
        return Interceptor()
    
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """拦截 console.log"""
        self.console_message.emit(message)
        # 检查是否是 tt-copy 的消息
        if message.startswith("__TTCOPY_DL__:"):
            try:
                data = json.loads(message[len("__TTCOPY_DL__:"):])
                data["action"] = "download"
                self.bridge.download_requested.emit(data)
            except:
                pass
    
    def acceptNavigationRequest(self, url, type, isMainFrame):
        """接受所有导航请求"""
        return True
    
    def certificateError(self, certificateError):
        """忽略证书错误"""
        return True


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.downloader = VideoDownloader(self.config)
        self.current_video_info = None
        self.download_worker = None
        
        self.setWindowTitle("TT-Copy Desktop")
        self.setMinimumSize(1200, 800)
        
        # 初始化 UI
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_tray()
        
        # 加载 TikTok
        self.web_view.load(QUrl("https://www.tiktok.com"))
    
    def _setup_ui(self):
        """设置界面"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # ========== 顶部导航栏 ==========
        nav_bar = QWidget()
        nav_bar.setFixedHeight(44)
        nav_bar.setStyleSheet("""
            QWidget {
                background: #1a1a1a;
                border-bottom: 1px solid #333;
            }
            QPushButton {
                background: transparent;
                color: #ccc;
                border: none;
                padding: 6px 12px;
                font-size: 16px;
                min-width: 32px;
            }
            QPushButton:hover { color: white; background: #333; }
            QPushButton:disabled { color: #555; }
            QLineEdit {
                background: #2a2a2a;
                color: #fff;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #25c554;
                outline: none;
            }
        """)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setSpacing(8)
        nav_layout.setContentsMargins(10, 0, 10, 0)
        
        # 后退按钮
        self.back_btn = QPushButton("◀")
        self.back_btn.setToolTip("后退 (Alt+←)")
        self.back_btn.clicked.connect(self._go_back)
        nav_layout.addWidget(self.back_btn)
        
        # 前进按钮
        self.forward_btn = QPushButton("▶")
        self.forward_btn.setToolTip("前进 (Alt+→)")
        self.forward_btn.clicked.connect(self._go_forward)
        nav_layout.addWidget(self.forward_btn)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setToolTip("刷新 (F5)")
        self.refresh_btn.clicked.connect(self._refresh)
        nav_layout.addWidget(self.refresh_btn)
        
        nav_layout.addSpacing(10)
        
        # 地址栏
        self.address_bar = QLineEdit()
        self.address_bar.setPlaceholderText("输入网址...")
        self.address_bar.returnPressed.connect(self._on_address_entered)
        nav_layout.addWidget(self.address_bar, 1)
        
        nav_layout.addSpacing(10)
        
        # 主页按钮
        self.home_btn = QPushButton("🏠")
        self.home_btn.setToolTip("主页 (Alt+Home)")
        self.home_btn.clicked.connect(self._go_home)
        nav_layout.addWidget(self.home_btn)
        
        layout.addWidget(nav_bar)
        
        # ========== 下载进度条 ==========
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #2a2a2a;
            }
            QProgressBar::chunk {
                background: #25c554;
            }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # ========== 工具栏 ==========
        toolbar = QWidget()
        toolbar.setFixedHeight(50)
        toolbar.setStyleSheet("""
            QWidget {
                background: #1a1a1a;
                border-bottom: 1px solid #333;
            }
            QPushButton {
                background: #25c554;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1ea345; }
            QPushButton:pressed { background: #178a3a; }
            QPushButton:disabled { background: #666; }
            QLabel { color: #ccc; font-size: 13px; }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(15, 0, 15, 0)
        
        # 标题
        title = QLabel("TT-Copy Desktop")
        title.setStyleSheet("color: #25c554; font-size: 16px; font-weight: bold;")
        toolbar_layout.addWidget(title)
        
        toolbar_layout.addStretch()
        
        # 状态标签
        self.status_label = QLabel("准备就绪")
        toolbar_layout.addWidget(self.status_label)
        
        toolbar_layout.addSpacing(20)
        
        # 下载按钮
        self.download_btn = QPushButton("⬇ 下载当前")
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.clicked.connect(self._on_download_clicked)
        toolbar_layout.addWidget(self.download_btn)
        
        toolbar_layout.addSpacing(10)
        
        # 选择目录按钮
        self.folder_btn = QPushButton("📁 下载目录")
        self.folder_btn.setStyleSheet("""
            QPushButton {
                background: #444;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #555; }
        """)
        self.folder_btn.clicked.connect(self._on_select_folder)
        toolbar_layout.addWidget(self.folder_btn)
        
        layout.addWidget(toolbar)
        
        # ========== 浏览器视图 ==========
        profile = QWebEngineProfile("ttcopy_profile", self)
        
        # 使用 Chrome 的 User-Agent（QtWebEngine 基于 Chromium）
        chrome_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        profile.setHttpUserAgent(chrome_ua)
        
        # 启用持久化存储，避免每次启动都重新登录
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        
        # 启用 HTTP 缓存
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        profile.setHttpCacheMaximumSize(100 * 1024 * 1024)  # 100MB
        
        self.web_page = TikTokWebPage(profile, self)
        self.web_page.bridge.download_requested.connect(self._on_download_requested)
        self.web_page.console_message.connect(self._on_console_message)
        
        # 配置浏览器设置 - 启用视频播放所需功能
        settings = self.web_page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, True)
        
        self.web_view = QWebEngineView()
        self.web_view.setPage(self.web_page)
        self.web_view.loadFinished.connect(self._on_load_finished)
        self.web_view.urlChanged.connect(self._on_url_changed)
        self.web_view.loadProgress.connect(self._on_load_progress)
        self.web_view.loadStarted.connect(self._on_load_started)
        
        # 设置深色背景
        self.web_view.setStyleSheet("background: #000;")
        
        layout.addWidget(self.web_view, 1)
        
        # 底部状态栏
        self.statusBar().showMessage("快捷键: Ctrl+D 下载 | Alt+← → 前进后退 | 可直接在地址栏输入抖音链接")
        self.statusBar().setStyleSheet("background: #1a1a1a; color: #888;")
    
    def _setup_shortcuts(self):
        """设置快捷键"""
        # Ctrl+D 下载
        shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        shortcut.activated.connect(self._on_download_clicked)
        
        # F5 刷新
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self._refresh)
        
        # Alt+Home 主页
        home_shortcut = QShortcut(QKeySequence("Alt+Home"), self)
        home_shortcut.activated.connect(self._go_home)
    
    def _setup_tray(self):
        """设置系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        
        tray_menu = QMenu()
        show_action = QAction("显示", self)
        show_action.triggered.connect(self.show)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.quit)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
    
    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
    
    # ========== 导航功能 ==========
    def _go_back(self):
        """后退"""
        self.web_view.back()
    
    def _go_forward(self):
        """前进"""
        self.web_view.forward()
    
    def _refresh(self):
        """刷新"""
        self.web_view.reload()
    
    def _go_home(self):
        """主页"""
        self.web_view.load(QUrl("https://www.tiktok.com"))
    
    def _on_address_entered(self):
        """地址栏回车"""
        text = self.address_bar.text().strip()
        if not text:
            return
        
        # 自动补全协议
        if not text.startswith(('http://', 'https://')):
            text = 'https://' + text
        
        url = QUrl(text)
        if url.isValid():
            self.web_view.load(url)
        else:
            self.status_label.setText("无效的网址")
    
    def _on_url_changed(self, url):
        """URL 改变时更新地址栏"""
        self.address_bar.setText(url.toString())
        self._update_nav_buttons()
    
    def _on_load_started(self):
        """开始加载"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
    
    def _on_load_progress(self, progress):
        """加载进度"""
        self.progress_bar.setValue(progress)
    
    def _on_load_finished(self, ok):
        """页面加载完成后"""
        self.progress_bar.setVisible(False)
        if ok:
            self._inject_js()
            self.status_label.setText("已就绪")
        else:
            self.status_label.setText("加载失败")
        self._update_nav_buttons()
    
    def _update_nav_buttons(self):
        """更新前进/后退按钮状态"""
        self.back_btn.setEnabled(self.web_view.history().canGoBack())
        self.forward_btn.setEnabled(self.web_view.history().canGoForward())
    
    # ========== JS 注入 ==========
    def _inject_js(self):
        """注入反检测和下载检测 JS"""
        js_code = r"""
        (function() {
            if (window.__ttcopy_injected__) return;
            window.__ttcopy_injected__ = true;
            
            // ========== 反检测：隐藏自动化特征 ==========
            
            // 1. 删除 webdriver 属性
            delete Object.getPrototypeOf(navigator).webdriver;
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // 2. 模拟真实插件
            const mockPlugins = [
                {name: "Chrome PDF Plugin", filename: "internal-pdf-viewer", description: "Portable Document Format"},
                {name: "Chrome PDF Viewer", filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai", description: ""},
                {name: "Native Client", filename: "internal-nacl-plugin", description: ""}
            ];
            Object.defineProperty(navigator, 'plugins', {
                get: () => mockPlugins,
                configurable: true
            });
            
            // 3. 语言设置
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en'],
                configurable: true
            });
            
            // 4. 覆盖 permissions.query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = function(parameters) {
                if (parameters.name === 'notifications' || parameters.name === 'clipboard-read' || parameters.name === 'clipboard-write') {
                    return Promise.resolve({ state: 'prompt', onchange: null });
                }
                return originalQuery.call(navigator.permissions, parameters);
            };
            
            // 5. 覆盖 chrome 对象
            window.chrome = window.chrome || {};
            window.chrome.runtime = window.chrome.runtime || {};
            
            // 6. 覆盖 Notification 权限
            if (window.Notification) {
                Object.defineProperty(Notification, 'permission', {
                    get: () => 'default'
                });
            }
            
            // 7. 模拟 WebGL 指纹
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris Xe Graphics';
                }
                return getParameter(parameter);
            };
            
            // 8. 覆盖 toString 防止检测
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === window.navigator.permissions.query) {
                    return 'function query() { [native code] }';
                }
                return originalToString.call(this);
            };
            
            // ========== 监听滚动，自动识别当前内容 ==========
            let lastVideoId = null;
            let checkInterval = null;
            
            function findPostLinkFromElement(startEl) {
                let el = startEl;
                for (let i = 0; i < 20; i++) {
                    if (!el.parentElement) break;
                    el = el.parentElement;
                    const link = el.querySelector('a[href*="/video/"], a[href*="/photo/"]');
                    if (link) {
                        const m = link.href.match(/@([^/]+)\/(video|photo)\/(\d+)/);
                        if (m) return { author: m[1], videoId: m[3], type: m[2] };
                        const m2 = link.href.match(/\/(video|photo)\/(\d+)/);
                        if (m2) return { author: 'unknown', videoId: m[2], type: m2[1] };
                    }
                }
                return null;
            }
            
            function getCurrentContentInfo() {
                // Strategy 1: URL path
                const pathMatch = location.pathname.match(/@([^/]+)\/(video|photo)\/(\d+)/);
                if (pathMatch) {
                    return { author: pathMatch[1], videoId: pathMatch[3], type: pathMatch[2] };
                }
                
                // Strategy 2: Find visible video
                const videos = document.querySelectorAll('video');
                for (const v of videos) {
                    const rect = v.getBoundingClientRect();
                    if (rect.top >= -200 && rect.top < window.innerHeight * 0.7 && rect.height > 200) {
                        const info = findPostLinkFromElement(v);
                        if (info) return info;
                    }
                }
                
                // Strategy 3: Find visible photo
                const links = document.querySelectorAll('a[href*="/photo/"]');
                for (const link of links) {
                    const m = link.href.match(/@([^/]+)\/photo\/(\d+)/);
                    if (!m) continue;
                    const rect = link.getBoundingClientRect();
                    if (rect.top >= -200 && rect.top < window.innerHeight * 0.7 && rect.width > 100) {
                        return { author: m[1], videoId: m[2], type: 'photo' };
                    }
                }
                
                return null;
            }
            
            // 定期检查当前内容
            function checkCurrentContent() {
                const info = getCurrentContentInfo();
                if (info && info.videoId !== lastVideoId) {
                    lastVideoId = info.videoId;
                    // 通知 Python 当前内容
                    console.log('__TTCOPY_CURRENT__:' + JSON.stringify(info));
                }
            }
            
            // 滚动时检测
            window.addEventListener('scroll', checkCurrentContent, { passive: true });
            // 定期检查
            checkInterval = setInterval(checkCurrentContent, 500);
            
            // 下载函数
            window.__ttcopy_download = function() {
                const info = getCurrentContentInfo();
                if (info && info.videoId) {
                    console.log('__TTCOPY_DL__:' + JSON.stringify(info));
                    return true;
                }
                console.log('__TTCOPY_ERR__:Could not identify current content');
                return false;
            };
            
            console.log('[TT-Copy] Injected successfully');
        })();
        """
        self.web_view.page().runJavaScript(js_code)
    
    def _on_console_message(self, message):
        """处理 console 消息"""
        if message.startswith("__TTCOPY_CURRENT__:"):
            try:
                data = json.loads(message[len("__TTCOPY_CURRENT__:"):])
                self.current_video_info = data
                author = data.get("author", "unknown")
                content_type = "图文" if data.get("type") == "photo" else "视频"
                self.status_label.setText(f"当前: @{author} ({content_type})")
            except:
                pass
        elif message.startswith("__TTCOPY_ERR__:"):
            self.status_label.setText("无法识别当前内容")
    
    # ========== 下载功能 ==========
    def _on_download_clicked(self):
        """点击下载按钮"""
        self.web_view.page().runJavaScript("window.__ttcopy_download && window.__ttcopy_download()")
    
    def _on_download_requested(self, data):
        """处理下载请求"""
        author = data.get("author", "unknown")
        video_id = data.get("videoId")
        content_type = data.get("type", "video")
        
        if not video_id:
            QMessageBox.warning(self, "下载失败", "无法获取视频 ID")
            return
        
        content_url = f"https://www.tiktok.com/@{author}/{content_type}/{video_id}"
        
        # 禁用按钮，显示进度
        self.download_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)  # 无限模式表示下载中
        self.status_label.setText("下载中...")
        
        # 启动后台下载线程
        self.download_worker = DownloadWorker(
            self.downloader, content_url, author, video_id, content_type
        )
        self.download_worker.progress.connect(self.status_label.setText)
        self.download_worker.finished_with_result.connect(self._on_download_finished)
        self.download_worker.start()
    
    def _on_download_finished(self, success, message):
        """下载完成回调"""
        self.download_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        
        if success:
            self.status_label.setText(f"✓ {message}")
            self.tray_icon.showMessage("下载完成", message, QSystemTrayIcon.MessageIcon.Information, 3000)
        else:
            self.status_label.setText(f"✗ {message}")
            QMessageBox.critical(self, "下载失败", message)
    
    def _on_select_folder(self):
        """选择下载目录"""
        folder = QFileDialog.getExistingDirectory(self, "选择下载目录", self.config["download_dir"])
        if folder:
            self.config["download_dir"] = folder
            self.downloader = VideoDownloader(self.config)
            self.status_label.setText(f"下载目录: {folder}")


def main():
    # PyQt6 默认启用高 DPI 支持，无需手动设置
    # Qt 6 已经内置了高 DPI 支持，AA_EnableHighDpiScaling 已被移除
    
    app = QApplication(sys.argv)
    app.setApplicationName("TT-Copy Desktop")
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出，托盘保持运行
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
