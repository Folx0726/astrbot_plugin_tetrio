"""
截图模块
提供浏览器管理和截图功能
"""

from .browser import BrowserManager
from .capturer import ScreenshotCapturer
from .selectors import SECTION_SELECTORS, SECTION_NAMES
from .context_pool import BrowserContextPool, ContextPoolItem

__all__ = ['BrowserManager', 'ScreenshotCapturer', 'SECTION_SELECTORS', 'SECTION_NAMES', 'BrowserContextPool', 'ContextPoolItem']
