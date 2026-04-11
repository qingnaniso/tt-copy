#!/usr/bin/env python3
"""测试 QtWebEngine 视频支持"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
from PyQt6.QtCore import QUrl

app = QApplication(sys.argv)

# 创建测试窗口
view = QWebEngineView()
profile = QWebEngineProfile("test")

# 检查设置
settings = view.settings()
print("=== QtWebEngine 视频支持检测 ===\n")

attrs = [
    ("JavascriptEnabled", QWebEngineSettings.WebAttribute.JavascriptEnabled),
    ("WebGLEnabled", QWebEngineSettings.WebAttribute.WebGLEnabled),
    ("PlaybackRequiresUserGesture", QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture),
    ("LocalStorageEnabled", QWebEngineSettings.WebAttribute.LocalStorageEnabled),
]

for name, attr in attrs:
    value = settings.testAttribute(attr)
    print(f"{name}: {'✓' if value else '✗'}")

# 加载测试页面
print("\n正在加载视频测试页面...")
view.load(QUrl("https://www.youtube.com/html5"))
view.show()

# 或者使用更简单的测试
# view.load(QUrl("https://videojs.github.io/video.js/"))

print("\n如果页面加载成功且能看到视频播放器，说明视频支持正常。")
print("请检查窗口中的视频是否可以播放。")

sys.exit(app.exec())
