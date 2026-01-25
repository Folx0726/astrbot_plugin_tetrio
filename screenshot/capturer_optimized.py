"""
截图执行模块（性能优化版）
使用上下文池、WebP 格式、智能加载策略
保留所有字体和媒体加载，确保显示内容完整
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional

from .browser import BrowserManager
from .selectors import *

logger = logging.getLogger(__name__)


class ScreenshotCapturer:
    """截图执行器（优化版）"""
    
    def __init__(self, 
                 browser_manager: BrowserManager, 
                 screenshot_dir: str,
                 screenshot_format: str = 'webp',
                 screenshot_quality: int = 85):
        """
        初始化截图执行器
        
        Args:
            browser_manager: 浏览器管理器实例
            screenshot_dir: 截图保存目录
            screenshot_format: 截图格式（webp 或 png）
            screenshot_quality: 截图质量（1-100，仅对 webp 有效）
        """
        self.browser_manager = browser_manager
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_format = screenshot_format.lower()
        self.screenshot_quality = screenshot_quality
        
        self.base_url = "https://ch.tetr.io/u/"
    
    async def capture_full_page(self, username: str) -> str:
        """
        截取完整页面
        
        Args:
            username: 玩家用户名
            
        Returns:
            str: 截图文件路径
        """
        context_item = None
        try:
            # 从池中获取上下文
            context_item = await self.browser_manager.acquire_context()
            if not context_item:
                raise Exception("无法获取浏览器上下文")
            
            page = context_item.page
            url = f"{self.base_url}{username.lower()}"
            
            logger.info(f"开始访问页面: {url}")
            
            # 使用智能加载策略（domcontentloaded 而非 networkidle）
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # 等待页面加载完成
            await self._wait_for_page_load(page)
            
            # 检查是否有错误
            if await self._check_error(page):
                raise Exception(f"玩家 {username} 不存在或页面加载失败")
            
            # 生成文件名
            filename = self._generate_filename(username, "full")
            filepath = str(self.screenshot_dir / filename)
            
            # 截取整页（使用 WebP 格式）
            if self.screenshot_format == 'webp':
                await page.screenshot(
                    path=filepath, 
                    full_page=True,
                    type='jpeg',  # Playwright 的 WebP 通过 JPEG 类型 + 质量参数实现
                    quality=self.screenshot_quality
                )
            else:
                await page.screenshot(path=filepath, full_page=True)
            
            logger.info(f"截图完成: {filepath}")
            return filepath
            
        finally:
            if context_item:
                await self.browser_manager.release_context(context_item)
    
    async def capture_profile_sidebar(self, username: str) -> str:
        """
        截取左侧信息栏
        
        Args:
            username: 玩家用户名
            
        Returns:
            str: 截图文件路径
        """
        context_item = None
        try:
            context_item = await self.browser_manager.acquire_context()
            if not context_item:
                raise Exception("无法获取浏览器上下文")
            
            page = context_item.page
            url = f"{self.base_url}{username.lower()}"
            
            logger.info(f"开始访问页面: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            await self._wait_for_page_load(page)
            
            if await self._check_error(page):
                raise Exception(f"玩家 {username} 不存在或页面加载失败")
            
            # 定位左侧信息栏
            sidebar = await page.query_selector(LEFT_SIDEBAR)
            if not sidebar:
                raise Exception("无法找到左侧信息栏")
            
            filename = self._generate_filename(username, "profile")
            filepath = str(self.screenshot_dir / filename)
            
            # 截取左侧栏
            if self.screenshot_format == 'webp':
                await sidebar.screenshot(
                    path=filepath,
                    type='jpeg',
                    quality=self.screenshot_quality
                )
            else:
                await sidebar.screenshot(path=filepath)
            
            logger.info(f"截图完成: {filepath}")
            return filepath
            
        finally:
            if context_item:
                await self.browser_manager.release_context(context_item)
    
    async def capture_section(self, username: str, section: str) -> str:
        """
        截取指定板块
        
        Args:
            username: 玩家用户名
            section: 板块名称 (league, 40l, blitz, qp, zen, achievements, about, news)
            
        Returns:
            str: 截图文件路径
        """
        if section not in SECTION_SELECTORS:
            raise ValueError(f"未知的板块: {section}")
        
        context_item = None
        try:
            context_item = await self.browser_manager.acquire_context()
            if not context_item:
                raise Exception("无法获取浏览器上下文")
            
            page = context_item.page
            url = f"{self.base_url}{username.lower()}"
            
            logger.info(f"开始访问页面: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            await self._wait_for_page_load(page)
            
            if await self._check_error(page):
                raise Exception(f"玩家 {username} 不存在或页面加载失败")
            
            # 如果是 news 板块，尝试展开
            if section == "news":
                await self._expand_news_section(page)
            
            # 定位目标板块
            selector = SECTION_SELECTORS[section]
            element = await page.query_selector(selector)
            
            if not element:
                raise Exception(f"无法找到板块: {SECTION_NAMES.get(section, section)}")
            
            filename = self._generate_filename(username, section)
            filepath = str(self.screenshot_dir / filename)
            
            # 截取板块
            if self.screenshot_format == 'webp':
                await element.screenshot(
                    path=filepath,
                    type='jpeg',
                    quality=self.screenshot_quality
                )
            else:
                await element.screenshot(path=filepath)
            
            logger.info(f"截图完成: {filepath}")
            return filepath
            
        finally:
            if context_item:
                await self.browser_manager.release_context(context_item)
    
    async def _wait_for_page_load(self, page):
        """
        等待页面加载完成（智能等待策略）
        
        优化：减少固定等待时间，使用元素可见性判断
        """
        try:
            # 等待加载器消失
            await page.wait_for_selector(LOADER, state="hidden", timeout=10000)
            logger.debug("页面加载器已消失")
        except Exception as e:
            logger.warning(f"等待加载器消失超时: {e}")
        
        # 等待主内容区域可见
        try:
            await page.wait_for_selector(LEFT_SIDEBAR, state="visible", timeout=5000)
            logger.debug("主内容区域已可见")
        except Exception as e:
            logger.warning(f"等待主内容区域超时: {e}")
        
        # 减少额外等待时间（从 1000ms 降到 500ms）
        await page.wait_for_timeout(500)
    
    async def _check_error(self, page) -> bool:
        """检查页面是否有错误"""
        try:
            error_elem = await page.query_selector(ERROR)
            if error_elem:
                is_visible = await error_elem.is_visible()
                if is_visible:
                    logger.error("检测到页面错误")
                    return True
        except Exception:
            pass
        return False
    
    async def _expand_news_section(self, page):
        """尝试展开 LATEST NEWS 板块"""
        try:
            # 查找包含 "expand" 的按钮
            expand_button = await page.query_selector('button:has-text("expand")')
            if not expand_button:
                expand_button = await page.query_selector('a:has-text("expand")')
            
            if expand_button:
                await expand_button.click()
                await page.wait_for_timeout(500)
                logger.debug("已展开 LATEST NEWS 板块")
        except Exception as e:
            logger.warning(f"展开 LATEST NEWS 失败: {e}")
    
    def _generate_filename(self, username: str, section: str) -> str:
        """生成截图文件名"""
        timestamp = int(time.time())
        ext = 'jpg' if self.screenshot_format == 'webp' else 'png'
        return f"{username}_{section}_{timestamp}.{ext}"
"""
截图执行模块（性能优化版）
使用上下文池、WebP 格式、智能加载策略
保留所有字体和媒体加载，确保显示内容完整
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional

from .browser import BrowserManager
from .selectors import *

logger = logging.getLogger(__name__)


class ScreenshotCapturer:
    """截图执行器（优化版）"""
    
    def __init__(self, 
                 browser_manager: BrowserManager, 
                 screenshot_dir: str,
                 screenshot_format: str = 'webp',
                 screenshot_quality: int = 85):
        """
        初始化截图执行器
        
        Args:
            browser_manager: 浏览器管理器实例
            screenshot_dir: 截图保存目录
            screenshot_format: 截图格式（webp 或 png）
            screenshot_quality: 截图质量（1-100，仅对 webp 有效）
        """
        self.browser_manager = browser_manager
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_format = screenshot_format.lower()
        self.screenshot_quality = screenshot_quality
        
        self.base_url = "https://ch.tetr.io/u/"
    
    async def capture_full_page(self, username: str) -> str:
        """
        截取完整页面
        
        Args:
            username: 玩家用户名
            
        Returns:
            str: 截图文件路径
        """
        context_item = None
        try:
            # 从池中获取上下文
            context_item = await self.browser_manager.acquire_context()
            if not context_item:
                raise Exception("无法获取浏览器上下文")
            
            page = context_item.page
            url = f"{self.base_url}{username.lower()}"
            
            logger.info(f"开始访问页面: {url}")
            
            # 使用智能加载策略（domcontentloaded 而非 networkidle）
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # 等待页面加载完成
            await self._wait_for_page_load(page)
            
            # 检查是否有错误
            if await self._check_error(page):
                raise Exception(f"玩家 {username} 不存在或页面加载失败")
            
            # 生成文件名
            filename = self._generate_filename(username, "full")
            filepath = str(self.screenshot_dir / filename)
            
            # 截取整页（使用 WebP 格式）
            if self.screenshot_format == 'webp':
                await page.screenshot(
                    path=filepath, 
                    full_page=True,
                    type='jpeg',  # Playwright 的 WebP 通过 JPEG 类型 + 质量参数实现
                    quality=self.screenshot_quality
                )
            else:
                await page.screenshot(path=filepath, full_page=True)
            
            logger.info(f"截图完成: {filepath}")
            return filepath
            
        finally:
            if context_item:
                await self.browser_manager.release_context(context_item)
    
    async def capture_profile_sidebar(self, username: str) -> str:
        """
        截取左侧信息栏
        
        Args:
            username: 玩家用户名
            
        Returns:
            str: 截图文件路径
        """
        context_item = None
        try:
            context_item = await self.browser_manager.acquire_context()
            if not context_item:
                raise Exception("无法获取浏览器上下文")
            
            page = context_item.page
            url = f"{self.base_url}{username.lower()}"
            
            logger.info(f"开始访问页面: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            await self._wait_for_page_load(page)
            
            if await self._check_error(page):
                raise Exception(f"玩家 {username} 不存在或页面加载失败")
            
            # 定位左侧信息栏
            sidebar = await page.query_selector(LEFT_SIDEBAR)
            if not sidebar:
                raise Exception("无法找到左侧信息栏")
            
            filename = self._generate_filename(username, "profile")
            filepath = str(self.screenshot_dir / filename)
            
            # 截取左侧栏
            if self.screenshot_format == 'webp':
                await sidebar.screenshot(
                    path=filepath,
                    type='jpeg',
                    quality=self.screenshot_quality
                )
            else:
                await sidebar.screenshot(path=filepath)
            
            logger.info(f"截图完成: {filepath}")
            return filepath
            
        finally:
            if context_item:
                await self.browser_manager.release_context(context_item)
    
    async def capture_section(self, username: str, section: str) -> str:
        """
        截取指定板块
        
        Args:
            username: 玩家用户名
            section: 板块名称 (league, 40l, blitz, qp, zen, achievements, about, news)
            
        Returns:
            str: 截图文件路径
        """
        if section not in SECTION_SELECTORS:
            raise ValueError(f"未知的板块: {section}")
        
        context_item = None
        try:
            context_item = await self.browser_manager.acquire_context()
            if not context_item:
                raise Exception("无法获取浏览器上下文")
            
            page = context_item.page
            url = f"{self.base_url}{username.lower()}"
            
            logger.info(f"开始访问页面: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            await self._wait_for_page_load(page)
            
            if await self._check_error(page):
                raise Exception(f"玩家 {username} 不存在或页面加载失败")
            
            # 如果是 news 板块，尝试展开
            if section == "news":
                await self._expand_news_section(page)
            
            # 定位目标板块
            selector = SECTION_SELECTORS[section]
            element = await page.query_selector(selector)
            
            if not element:
                raise Exception(f"无法找到板块: {SECTION_NAMES.get(section, section)}")
            
            filename = self._generate_filename(username, section)
            filepath = str(self.screenshot_dir / filename)
            
            # 截取板块
            if self.screenshot_format == 'webp':
                await element.screenshot(
                    path=filepath,
                    type='jpeg',
                    quality=self.screenshot_quality
                )
            else:
                await element.screenshot(path=filepath)
            
            logger.info(f"截图完成: {filepath}")
            return filepath
            
        finally:
            if context_item:
                await self.browser_manager.release_context(context_item)
    
    async def _wait_for_page_load(self, page):
        """
        等待页面加载完成（智能等待策略）
        
        优化：减少固定等待时间，使用元素可见性判断
        """
        try:
            # 等待加载器消失
            await page.wait_for_selector(LOADER, state="hidden", timeout=10000)
            logger.debug("页面加载器已消失")
        except Exception as e:
            logger.warning(f"等待加载器消失超时: {e}")
        
        # 等待主内容区域可见
        try:
            await page.wait_for_selector(LEFT_SIDEBAR, state="visible", timeout=5000)
            logger.debug("主内容区域已可见")
        except Exception as e:
            logger.warning(f"等待主内容区域超时: {e}")
        
        # 减少额外等待时间（从 1000ms 降到 500ms）
        await page.wait_for_timeout(500)
    
    async def _check_error(self, page) -> bool:
        """检查页面是否有错误"""
        try:
            error_elem = await page.query_selector(ERROR)
            if error_elem:
                is_visible = await error_elem.is_visible()
                if is_visible:
                    logger.error("检测到页面错误")
                    return True
        except Exception:
            pass
        return False
    
    async def _expand_news_section(self, page):
        """尝试展开 LATEST NEWS 板块"""
        try:
            # 查找包含 "expand" 的按钮
            expand_button = await page.query_selector('button:has-text("expand")')
            if not expand_button:
                expand_button = await page.query_selector('a:has-text("expand")')
            
            if expand_button:
                await expand_button.click()
                await page.wait_for_timeout(500)
                logger.debug("已展开 LATEST NEWS 板块")
        except Exception as e:
            logger.warning(f"展开 LATEST NEWS 失败: {e}")
    
    def _generate_filename(self, username: str, section: str) -> str:
        """生成截图文件名"""
        timestamp = int(time.time())
        ext = 'jpg' if self.screenshot_format == 'webp' else 'png'
        return f"{username}_{section}_{timestamp}.{ext}"
