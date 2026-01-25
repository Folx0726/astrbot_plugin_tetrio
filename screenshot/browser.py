"""
浏览器管理模块
管理 Playwright 浏览器实例的生命周期
"""

import asyncio
from playwright.async_api import async_playwright, Browser
from typing import Optional
import logging

from .context_pool import BrowserContextPool, ContextPoolItem

logger = logging.getLogger(__name__)


class BrowserManager:
    """浏览器管理器（线程安全单例模式）"""
    
    _instance: Optional['BrowserManager'] = None
    _browser: Optional[Browser] = None
    _playwright = None
    _context_pool: Optional[BrowserContextPool] = None
    _init_lock = asyncio.Lock()
    _init_event = asyncio.Event()
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def init_browser(self, 
                          headless: bool = True, 
                          viewport_width: int = 1920, 
                          viewport_height: int = 1080,
                          context_pool_size: int = 2,
                          max_pool_size: int = 3,
                          memory_limit_mb: int = 512):
        """
        初始化浏览器实例（线程安全）
        
        Args:
            headless: 是否使用无头模式
            viewport_width: 默认视口宽度
            viewport_height: 默认视口高度
            context_pool_size: 上下文池初始大小
            max_pool_size: 上下文池最大大小
            memory_limit_mb: 内存限制（MB）
        """
        # 双重检查锁定模式
        if self._initialized:
            await self._init_event.wait()
            return
        
        async with self._init_lock:
            if self._initialized:
                return
            
            try:
                logger.info("开始初始化浏览器...")
                
                self._playwright = await async_playwright().start()
                
                # 构建启动参数（保留字体和媒体加载）
                launch_args = [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    f'--max-old-space-size={memory_limit_mb}',
                    '--disable-dev-shm-usage',
                ]
                
                self._browser = await self._playwright.chromium.launch(
                    headless=headless,
                    args=launch_args
                )
                
                # 初始化上下文池
                self._context_pool = BrowserContextPool(
                    browser=self._browser,
                    min_size=context_pool_size,
                    max_size=max_pool_size,
                    viewport_width=viewport_width,
                    viewport_height=viewport_height
                )
                
                await self._context_pool.initialize()
                
                self._initialized = True
                self._init_event.set()
                
                logger.info(f"浏览器初始化成功 (无头模式: {headless}, 上下文池: {context_pool_size}-{max_pool_size})")
                
            except Exception as e:
                logger.error(f"浏览器初始化失败: {e}")
                self._init_event.set()  # 即使失败也要设置事件，避免死锁
                raise
    
    def get_browser(self) -> Optional[Browser]:
        """获取浏览器实例"""
        return self._browser
    
    def get_context_pool(self) -> Optional[BrowserContextPool]:
        """获取上下文池"""
        return self._context_pool
    
    async def acquire_context(self, 
                             viewport_width: Optional[int] = None,
                             viewport_height: Optional[int] = None,
                             timeout: int = 30) -> Optional[ContextPoolItem]:
        """
        从池中获取浏览器上下文
        
        Args:
            viewport_width: 可选的视口宽度
            viewport_height: 可选的视口高度
            timeout: 超时时间（秒）
            
        Returns:
            ContextPoolItem: 上下文项，如果超时返回 None
        """
        # 确保浏览器已初始化
        if not self._initialized:
            await self._init_event.wait()
        
        if self._context_pool is None:
            logger.error("上下文池未初始化")
            return None
        
        return await self._context_pool.acquire(viewport_width, viewport_height, timeout)
    
    async def release_context(self, context_item: ContextPoolItem):
        """
        将上下文归还到池中
        
        Args:
            context_item: 要归还的上下文项
        """
        if self._context_pool is None:
            logger.warning("上下文池未初始化，无法归还")
            await context_item.close()
            return
        
        await self._context_pool.release(context_item)
    
    async def cleanup_idle_contexts(self):
        """清理空闲的上下文"""
        if self._context_pool:
            await self._context_pool.cleanup_idle()
    
    def get_pool_stats(self) -> dict:
        """获取上下文池统计信息"""
        if self._context_pool:
            return self._context_pool.get_stats()
        return {'total': 0, 'in_use': 0, 'idle': 0, 'utilization': 0}
    
    async def close_browser(self):
        """关闭浏览器实例"""
        async with self._init_lock:
            # 先关闭上下文池
            if self._context_pool is not None:
                await self._context_pool.close_all()
                self._context_pool = None
            
            # 关闭浏览器
            if self._browser is not None:
                try:
                    await self._browser.close()
                    if self._playwright is not None:
                        await self._playwright.stop()
                    self._browser = None
                    self._playwright = None
                    self._initialized = False
                    self._init_event.clear()
                    logger.info("浏览器已关闭")
                except Exception as e:
                    logger.error(f"关闭浏览器失败: {e}")
"""
浏览器管理模块
管理 Playwright 浏览器实例的生命周期
"""

import asyncio
from playwright.async_api import async_playwright, Browser
from typing import Optional
import logging

from .context_pool import BrowserContextPool, ContextPoolItem

logger = logging.getLogger(__name__)


class BrowserManager:
    """浏览器管理器（线程安全单例模式）"""
    
    _instance: Optional['BrowserManager'] = None
    _browser: Optional[Browser] = None
    _playwright = None
    _context_pool: Optional[BrowserContextPool] = None
    _init_lock = asyncio.Lock()
    _init_event = asyncio.Event()
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def init_browser(self, 
                          headless: bool = True, 
                          viewport_width: int = 1920, 
                          viewport_height: int = 1080,
                          context_pool_size: int = 2,
                          max_pool_size: int = 3,
                          memory_limit_mb: int = 512):
        """
        初始化浏览器实例（线程安全）
        
        Args:
            headless: 是否使用无头模式
            viewport_width: 默认视口宽度
            viewport_height: 默认视口高度
            context_pool_size: 上下文池初始大小
            max_pool_size: 上下文池最大大小
            memory_limit_mb: 内存限制（MB）
        """
        # 双重检查锁定模式
        if self._initialized:
            await self._init_event.wait()
            return
        
        async with self._init_lock:
            if self._initialized:
                return
            
            try:
                logger.info("开始初始化浏览器...")
                
                self._playwright = await async_playwright().start()
                
                # 构建启动参数（保留字体和媒体加载）
                launch_args = [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    f'--max-old-space-size={memory_limit_mb}',
                    '--disable-dev-shm-usage',
                ]
                
                self._browser = await self._playwright.chromium.launch(
                    headless=headless,
                    args=launch_args
                )
                
                # 初始化上下文池
                self._context_pool = BrowserContextPool(
                    browser=self._browser,
                    min_size=context_pool_size,
                    max_size=max_pool_size,
                    viewport_width=viewport_width,
                    viewport_height=viewport_height
                )
                
                await self._context_pool.initialize()
                
                self._initialized = True
                self._init_event.set()
                
                logger.info(f"浏览器初始化成功 (无头模式: {headless}, 上下文池: {context_pool_size}-{max_pool_size})")
                
            except Exception as e:
                logger.error(f"浏览器初始化失败: {e}")
                self._init_event.set()  # 即使失败也要设置事件，避免死锁
                raise
    
    def get_browser(self) -> Optional[Browser]:
        """获取浏览器实例"""
        return self._browser
    
    def get_context_pool(self) -> Optional[BrowserContextPool]:
        """获取上下文池"""
        return self._context_pool
    
    async def acquire_context(self, 
                             viewport_width: Optional[int] = None,
                             viewport_height: Optional[int] = None,
                             timeout: int = 30) -> Optional[ContextPoolItem]:
        """
        从池中获取浏览器上下文
        
        Args:
            viewport_width: 可选的视口宽度
            viewport_height: 可选的视口高度
            timeout: 超时时间（秒）
            
        Returns:
            ContextPoolItem: 上下文项，如果超时返回 None
        """
        # 确保浏览器已初始化
        if not self._initialized:
            await self._init_event.wait()
        
        if self._context_pool is None:
            logger.error("上下文池未初始化")
            return None
        
        return await self._context_pool.acquire(viewport_width, viewport_height, timeout)
    
    async def release_context(self, context_item: ContextPoolItem):
        """
        将上下文归还到池中
        
        Args:
            context_item: 要归还的上下文项
        """
        if self._context_pool is None:
            logger.warning("上下文池未初始化，无法归还")
            await context_item.close()
            return
        
        await self._context_pool.release(context_item)
    
    async def cleanup_idle_contexts(self):
        """清理空闲的上下文"""
        if self._context_pool:
            await self._context_pool.cleanup_idle()
    
    def get_pool_stats(self) -> dict:
        """获取上下文池统计信息"""
        if self._context_pool:
            return self._context_pool.get_stats()
        return {'total': 0, 'in_use': 0, 'idle': 0, 'utilization': 0}
    
    async def close_browser(self):
        """关闭浏览器实例"""
        async with self._init_lock:
            # 先关闭上下文池
            if self._context_pool is not None:
                await self._context_pool.close_all()
                self._context_pool = None
            
            # 关闭浏览器
            if self._browser is not None:
                try:
                    await self._browser.close()
                    if self._playwright is not None:
                        await self._playwright.stop()
                    self._browser = None
                    self._playwright = None
                    self._initialized = False
                    self._init_event.clear()
                    logger.info("浏览器已关闭")
                except Exception as e:
                    logger.error(f"关闭浏览器失败: {e}")
