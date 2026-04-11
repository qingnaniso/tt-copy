#!/usr/bin/env python3
"""调试 TikTok 视频播放问题"""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from PyQt6.QtCore import QUrl, pyqtSignal

class DebugPage(QWebEnginePage):
    console_message = pyqtSignal(str)
    
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        level_str = ["Debug", "Info", "Warning", "Error"][min(level, 3)]
        msg = f"[{level_str}] {message}"
        self.console_message.emit(msg)
        print(f"Console [{level_str}]: {message}")

app = QApplication(sys.argv)

# 创建主窗口
window = QMainWindow()
window.setWindowTitle("TikTok Debug")
window.setGeometry(100, 100, 1280, 800)

# 创建中心部件
central = QWidget()
layout = QVBoxLayout(central)
layout.setContentsMargins(0, 0, 0, 0)

# 创建浏览器
profile = QWebEngineProfile("debug")
profile.setHttpUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

page = DebugPage(profile)
view = QWebEngineView()
view.setPage(page)

# 启用所有视频相关设置
settings = page.settings()
settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)

# 注入反检测代码
def on_load_finished(ok):
    if ok:
        js = """
        (function() {
            // 隐藏 webdriver
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            
            // 覆盖 permissions
            const original = navigator.permissions.query;
            navigator.permissions.query = function(p) {
                return Promise.resolve({state: 'prompt'});
            };
            
            console.log('[Anti-detect] Injected');
        })();
        """
        page.runJavaScript(js)
        print("反检测代码已注入")

page.loadFinished.connect(on_load_finished)

layout.addWidget(view)
window.setCentralWidget(central)

# 加载 TikTok
print("加载 TikTok...")
view.load(QUrl("https://www.tiktok.com"))

window.show()

print("\n=== 调试说明 ===")
print("1. 观察控制台输出")
print("2. 尝试播放视频")
print("3. 如果出现播放错误，查看控制台的具体错误信息")
print("4. 按 Ctrl+C 退出")

sys.exit(app.exec())
