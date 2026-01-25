"""
浏览器上下文池管理模块
实现上下文复用，减少创建销毁开销
"""

import asyncio
import time
import logging
from typing import Optional, List
from playwright.async_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class ContextPoolItem:
    """上下文池中的单个项"""
    
    def __init__(self, context: BrowserContext, page: Page):
        self.context = context
        self.page = page
        self.use_count = 0
        self.last_used = time.time()
        self.in_use = False
    
    async def reset(self):
        """重置页面状态"""
        try:
            # 清除所有 cookies
            await self.context.clear_cookies()
            # 清除本地存储
            await self.page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            logger.debug("页面状态已重置")
        except Exception as e:
            logger.warning(f"重置页面状态失败: {e}")
    
    async def close(self):
        """关闭上下文和页面"""
        try:
            await self.context.close()
            logger.debug("上下文已关闭")
        except Exception as e:
            logger.error(f"关闭上下文失败: {e}")


class BrowserContextPool:
    """浏览器上下文池"""
    
    def __init__(self, 
                 browser: Browser,
                 min_size: int = 1,
                 max_size: int = 3,
                 max_use_count: int = 50,
                 idle_timeout: int = 60,
                 viewport_width: int = 1920,
                 viewport_height: int = 1080):
        """
        初始化上下文池
        
        Args:
            browser: 浏览器实例
            min_size: 最小池容量
            max_size: 最大池容量
            max_use_count: 单个上下文最大使用次数
            idle_timeout: 空闲超时时间（秒）
            viewport_width: 默认视口宽度
            viewport_height: 默认视口高度
        """
        self.browser = browser
        self.min_size = min_size
        self.max_size = max_size
        self.max_use_count = max_use_count
        self.idle_timeout = idle_timeout
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        
        self.pool: List[ContextPoolItem] = []
        self.lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """初始化上下文池"""
        if self._initialized:
            return
        
        async with self.lock:
            if self._initialized:
                return
            
            logger.info(f"初始化上下文池，容量: {self.min_size}-{self.max_size}")
            
            # 创建最小数量的上下文
            for _ in range(self.min_size):
                item = await self._create_context_item()
                if item:
                    self.pool.append(item)
            
            self._initialized = True
            logger.info(f"上下文池初始化完成，当前大小: {len(self.pool)}")
    
    async def _create_context_item(self, 
                                   viewport_width: Optional[int] = None,
                                   viewport_height: Optional[int] = None) -> Optional[ContextPoolItem]:
        """创建新的上下文项"""
        try:
            width = viewport_width or self.viewport_width
            height = viewport_height or self.viewport_height
            
            context = await self.browser.new_context(
                viewport={'width': width, 'height': height},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            page.set_default_timeout(30000)
            
            logger.debug(f"创建新上下文（视口: {width}x{height}）")
            return ContextPoolItem(context, page)
            
        except Exception as e:
            logger.error(f"创建上下文失败: {e}")
            return None
    
    async def acquire(self, 
                     viewport_width: Optional[int] = None,
                     viewport_height: Optional[int] = None,
                     timeout: int = 30) -> Optional[ContextPoolItem]:
        """
        获取可用的上下文
        
        Args:
            viewport_width: 可选的视口宽度
            viewport_height: 可选的视口高度
            timeout: 超时时间（秒）
            
        Returns:
            ContextPoolItem: 上下文项，如果超时返回 None
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            async with self.lock:
                # 查找空闲的上下文
                for item in self.pool:
                    if not item.in_use:
                        # 检查是否需要替换
                        if item.use_count >= self.max_use_count:
                            logger.debug(f"上下文使用次数达上限（{item.use_count}），替换新上下文")
                            await item.close()
                            self.pool.remove(item)
                            new_item = await self._create_context_item(viewport_width, viewport_height)
                            if new_item:
                                self.pool.append(new_item)
                                new_item.in_use = True
                                new_item.last_used = time.time()
                                logger.debug("获取新创建的上下文")
                                return new_item
                            continue
                        
                        # 标记为使用中
                        item.in_use = True
                        item.use_count += 1
                        item.last_used = time.time()
                        logger.debug(f"从池中获取上下文（使用次数: {item.use_count}）")
                        return item
                
                # 如果池未满，创建新上下文
                if len(self.pool) < self.max_size:
                    new_item = await self._create_context_item(viewport_width, viewport_height)
                    if new_item:
                        self.pool.append(new_item)
                        new_item.in_use = True
                        new_item.last_used = time.time()
                        logger.debug(f"池未满，创建新上下文（当前大小: {len(self.pool)}）")
                        return new_item
            
            # 等待一段时间后重试
            await asyncio.sleep(0.1)
        
        logger.warning("获取上下文超时")
        return None
    
    async def release(self, item: ContextPoolItem):
        """
        归还上下文到池中
        
        Args:
            item: 要归还的上下文项
        """
        async with self.lock:
            if item not in self.pool:
                logger.warning("尝试归还不在池中的上下文")
                await item.close()
                return
            
            # 重置页面状态
            await item.reset()
            
            # 标记为空闲
            item.in_use = False
            item.last_used = time.time()
            logger.debug("上下文已归还到池")
    
    async def cleanup_idle(self):
        """清理空闲超时的上下文"""
        async with self.lock:
            current_time = time.time()
            to_remove = []
            
            for item in self.pool:
                if not item.in_use:
                    idle_time = current_time - item.last_used
                    if idle_time > self.idle_timeout and len(self.pool) > self.min_size:
                        to_remove.append(item)
            
            for item in to_remove:
                logger.debug(f"清理空闲上下文（空闲时间: {current_time - item.last_used:.1f}秒）")
                await item.close()
                self.pool.remove(item)
            
            if to_remove:
                logger.info(f"清理了 {len(to_remove)} 个空闲上下文，当前池大小: {len(self.pool)}")
    
    async def close_all(self):
        """关闭所有上下文"""
        async with self.lock:
            logger.info(f"关闭所有上下文（共 {len(self.pool)} 个）")
            for item in self.pool:
                await item.close()
            self.pool.clear()
            self._initialized = False
    
    def get_stats(self) -> dict:
        """获取池的统计信息"""
        in_use_count = sum(1 for item in self.pool if item.in_use)
        return {
            'total': len(self.pool),
            'in_use': in_use_count,
            'idle': len(self.pool) - in_use_count,
            'utilization': in_use_count / max(len(self.pool), 1)
        }
"""
浏览器上下文池管理模块
实现上下文复用，减少创建销毁开销
"""

import asyncio
import time
import logging
from typing import Optional, List
from playwright.async_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class ContextPoolItem:
    """上下文池中的单个项"""
    
    def __init__(self, context: BrowserContext, page: Page):
        self.context = context
        self.page = page
        self.use_count = 0
        self.last_used = time.time()
        self.in_use = False
    
    async def reset(self):
        """重置页面状态"""
        try:
            # 清除所有 cookies
            await self.context.clear_cookies()
            # 清除本地存储
            await self.page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            logger.debug("页面状态已重置")
        except Exception as e:
            logger.warning(f"重置页面状态失败: {e}")
    
    async def close(self):
        """关闭上下文和页面"""
        try:
            await self.context.close()
            logger.debug("上下文已关闭")
        except Exception as e:
            logger.error(f"关闭上下文失败: {e}")


class BrowserContextPool:
    """浏览器上下文池"""
    
    def __init__(self, 
                 browser: Browser,
                 min_size: int = 1,
                 max_size: int = 3,
                 max_use_count: int = 50,
                 idle_timeout: int = 60,
                 viewport_width: int = 1920,
                 viewport_height: int = 1080):
        """
        初始化上下文池
        
        Args:
            browser: 浏览器实例
            min_size: 最小池容量
            max_size: 最大池容量
            max_use_count: 单个上下文最大使用次数
            idle_timeout: 空闲超时时间（秒）
            viewport_width: 默认视口宽度
            viewport_height: 默认视口高度
        """
        self.browser = browser
        self.min_size = min_size
        self.max_size = max_size
        self.max_use_count = max_use_count
        self.idle_timeout = idle_timeout
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        
        self.pool: List[ContextPoolItem] = []
        self.lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """初始化上下文池"""
        if self._initialized:
            return
        
        async with self.lock:
            if self._initialized:
                return
            
            logger.info(f"初始化上下文池，容量: {self.min_size}-{self.max_size}")
            
            # 创建最小数量的上下文
            for _ in range(self.min_size):
                item = await self._create_context_item()
                if item:
                    self.pool.append(item)
            
            self._initialized = True
            logger.info(f"上下文池初始化完成，当前大小: {len(self.pool)}")
    
    async def _create_context_item(self, 
                                   viewport_width: Optional[int] = None,
                                   viewport_height: Optional[int] = None) -> Optional[ContextPoolItem]:
        """创建新的上下文项"""
        try:
            width = viewport_width or self.viewport_width
            height = viewport_height or self.viewport_height
            
            context = await self.browser.new_context(
                viewport={'width': width, 'height': height},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            page.set_default_timeout(30000)
            
            logger.debug(f"创建新上下文（视口: {width}x{height}）")
            return ContextPoolItem(context, page)
            
        except Exception as e:
            logger.error(f"创建上下文失败: {e}")
            return None
    
    async def acquire(self, 
                     viewport_width: Optional[int] = None,
                     viewport_height: Optional[int] = None,
                     timeout: int = 30) -> Optional[ContextPoolItem]:
        """
        获取可用的上下文
        
        Args:
            viewport_width: 可选的视口宽度
            viewport_height: 可选的视口高度
            timeout: 超时时间（秒）
            
        Returns:
            ContextPoolItem: 上下文项，如果超时返回 None
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            async with self.lock:
                # 查找空闲的上下文
                for item in self.pool:
                    if not item.in_use:
                        # 检查是否需要替换
                        if item.use_count >= self.max_use_count:
                            logger.debug(f"上下文使用次数达上限（{item.use_count}），替换新上下文")
                            await item.close()
                            self.pool.remove(item)
                            new_item = await self._create_context_item(viewport_width, viewport_height)
                            if new_item:
                                self.pool.append(new_item)
                                new_item.in_use = True
                                new_item.last_used = time.time()
                                logger.debug("获取新创建的上下文")
                                return new_item
                            continue
                        
                        # 标记为使用中
                        item.in_use = True
                        item.use_count += 1
                        item.last_used = time.time()
                        logger.debug(f"从池中获取上下文（使用次数: {item.use_count}）")
                        return item
                
                # 如果池未满，创建新上下文
                if len(self.pool) < self.max_size:
                    new_item = await self._create_context_item(viewport_width, viewport_height)
                    if new_item:
                        self.pool.append(new_item)
                        new_item.in_use = True
                        new_item.last_used = time.time()
                        logger.debug(f"池未满，创建新上下文（当前大小: {len(self.pool)}）")
                        return new_item
            
            # 等待一段时间后重试
            await asyncio.sleep(0.1)
        
        logger.warning("获取上下文超时")
        return None
    
    async def release(self, item: ContextPoolItem):
        """
        归还上下文到池中
        
        Args:
            item: 要归还的上下文项
        """
        async with self.lock:
            if item not in self.pool:
                logger.warning("尝试归还不在池中的上下文")
                await item.close()
                return
            
            # 重置页面状态
            await item.reset()
            
            # 标记为空闲
            item.in_use = False
            item.last_used = time.time()
            logger.debug("上下文已归还到池")
    
    async def cleanup_idle(self):
        """清理空闲超时的上下文"""
        async with self.lock:
            current_time = time.time()
            to_remove = []
            
            for item in self.pool:
                if not item.in_use:
                    idle_time = current_time - item.last_used
                    if idle_time > self.idle_timeout and len(self.pool) > self.min_size:
                        to_remove.append(item)
            
            for item in to_remove:
                logger.debug(f"清理空闲上下文（空闲时间: {current_time - item.last_used:.1f}秒）")
                await item.close()
                self.pool.remove(item)
            
            if to_remove:
                logger.info(f"清理了 {len(to_remove)} 个空闲上下文，当前池大小: {len(self.pool)}")
    
    async def close_all(self):
        """关闭所有上下文"""
        async with self.lock:
            logger.info(f"关闭所有上下文（共 {len(self.pool)} 个）")
            for item in self.pool:
                await item.close()
            self.pool.clear()
            self._initialized = False
    
    def get_stats(self) -> dict:
        """获取池的统计信息"""
        in_use_count = sum(1 for item in self.pool if item.in_use)
        return {
            'total': len(self.pool),
            'in_use': in_use_count,
            'idle': len(self.pool) - in_use_count,
            'utilization': in_use_count / max(len(self.pool), 1)
        }
