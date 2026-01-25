"""
AstrBot TETR.IO 查询插件主文件
通过网页截图查询 TETR.IO 玩家信息
"""

import os
import asyncio
from pathlib import Path

from astrbot.api.star import Star, Context, register, StarTools
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig

from .screenshot import BrowserManager, ScreenshotCapturer, SECTION_NAMES
from .utils import CacheManager, validate_username, normalize_username, ConcurrencyController, RetryStrategy


@register(
    "tetrio",
    "shaogit",
    "通过网页截图查询 TETR.IO 玩家信息并以图片形式返回",
    "1.0.0",
    "https://github.com/shaogit/astrbot_plugin_tetrio"
)
class TetrioPlugin(Star):
    """TETR.IO 玩家查询插件"""
    
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        
        # 初始化配置
        self.config = config or {}
        self.cache_enabled = self.config.get("cache_enabled", True)
        self.cache_ttl = self.config.get("cache_ttl", 300)
        self.browser_headless = self.config.get("browser_headless", True)
        self.viewport_width = self.config.get("viewport_width", 2560)
        self.viewport_height = self.config.get("viewport_height", 1440)
        
        # 性能优化配置
        self.context_pool_size = self.config.get("context_pool_size", 2)
        self.max_pool_size = self.config.get("max_pool_size", 3)
        self.screenshot_format = self.config.get("screenshot_format", "png")
        self.screenshot_quality = self.config.get("screenshot_quality", 85)
        self.memory_limit_mb = self.config.get("memory_limit_mb", 512)
        
        # 缓存优化配置
        self.max_cache_size_mb = self.config.get("max_cache_size_mb", 200)
        self.max_cache_files = self.config.get("max_cache_files", 500)
        
        # 并发控制配置
        self.max_concurrent_tasks = self.config.get("max_concurrent_tasks", 5)
        
        # 页面缩放配置
        self.page_zoom_full = self.config.get("page_zoom_full", 0.9)
        self.page_zoom_section = self.config.get("page_zoom_section", 1.0)
        
        # 设置截图目录
        # 使用 StarTools.get_data_dir() 获取插件专属数据目录
        plugin_data_dir = StarTools.get_data_dir("tetrio")
        self.screenshot_dir = plugin_data_dir / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化组件
        self.browser_manager = BrowserManager()
        self.capturer = ScreenshotCapturer(
            self.browser_manager, 
            str(self.screenshot_dir),
            screenshot_format=self.screenshot_format,
            screenshot_quality=self.screenshot_quality,
            page_zoom_full=self.page_zoom_full,
            page_zoom_section=self.page_zoom_section
        )
        self.cache_manager = CacheManager(
            str(self.screenshot_dir), 
            self.cache_ttl,
            max_cache_size_mb=self.max_cache_size_mb,
            max_cache_files=self.max_cache_files
        )
        
        # 初始化并发控制器
        self.concurrency_controller = ConcurrencyController(max_concurrent=self.max_concurrent_tasks)
        
        # 启动浏览器
        self._browser_ready = asyncio.Event()
        asyncio.create_task(self._init_browser())
        
        logger.info("TETR.IO 查询插件已加载（优化版：上下文池化）")
    
    async def _init_browser(self):
        """异步初始化浏览器（优化版）"""
        try:
            await self.browser_manager.init_browser(
                headless=self.browser_headless,
                viewport_width=self.viewport_width,
                viewport_height=self.viewport_height,
                context_pool_size=self.context_pool_size,
                max_pool_size=self.max_pool_size,
                memory_limit_mb=self.memory_limit_mb
            )
            self._browser_ready.set()
            logger.info("浏览器初始化完成")
        except Exception as e:
            logger.error(f"初始化浏览器失败: {e}")
            self._browser_ready.set()  # 即使失败也设置，避免死锁

    async def _init_services(self):
        """初始化数据库和 Web 服务"""
        if not HAS_EXTRA_DEPS or not self.db or not self.web_server:
            return
            
        try:
            await self.db.init_db()
            await self.web_server.start()
            logger.info("数据库和 Web 服务初始化完成")
        except Exception as e:
            logger.error(f"初始化服务失败: {e}")
    
    async def terminate(self):
        """插件卸载时清理资源"""
        logger.info("正在清理 TETR.IO 插件资源...")
        await self.web_server.stop()
        await self.browser_manager.close_browser()
        if self.cache_enabled:
            self.cache_manager.clean_expired_cache()
        
        # 输出缓存统计信息
        stats = self.cache_manager.get_cache_stats()
        logger.info(f"缓存统计: {stats['total_files']} 个文件, {stats['total_size_mb']} MB")
        
        logger.info("TETR.IO 插件资源清理完成")
    
    @filter.command_group("tetrio")
    def tetrio_group(self):
        """TETR.IO 查询指令组"""
        pass
    
    @tetrio_group.command("full")
    async def cmd_full(self, event: AstrMessageEvent, username: str):
        """截取玩家完整页面"""
        async for result in self._handle_screenshot(event, username, "full", "完整页面"):
            yield result
    
    @tetrio_group.command("profile")
    async def cmd_profile(self, event: AstrMessageEvent, username: str):
        """截取玩家信息侧栏"""
        async for result in self._handle_screenshot(event, username, "profile", "玩家信息"):
            yield result
    
    @tetrio_group.command("league")
    async def cmd_league(self, event: AstrMessageEvent, username: str):
        """截取 TETRA LEAGUE 板块"""
        async for result in self._handle_screenshot(event, username, "league", "TETRA LEAGUE"):
            yield result
    
    @tetrio_group.command("40l")
    async def cmd_40l(self, event: AstrMessageEvent, username: str):
        """截取 40 LINES 板块"""
        async for result in self._handle_screenshot(event, username, "40l", "40 LINES"):
            yield result
    
    @tetrio_group.command("blitz")
    async def cmd_blitz(self, event: AstrMessageEvent, username: str):
        """截取 BLITZ 板块"""
        async for result in self._handle_screenshot(event, username, "blitz", "BLITZ"):
            yield result
    
    @tetrio_group.command("qp")
    async def cmd_qp(self, event: AstrMessageEvent, username: str):
        """截取 QUICK PLAY 板块"""
        async for result in self._handle_screenshot(event, username, "qp", "QUICK PLAY"):
            yield result
    
    @tetrio_group.command("zen")
    async def cmd_zen(self, event: AstrMessageEvent, username: str):
        """截取 ZEN 板块"""
        async for result in self._handle_screenshot(event, username, "zen", "ZEN"):
            yield result
    
    @tetrio_group.command("achievements")
    async def cmd_achievements(self, event: AstrMessageEvent, username: str):
        """截取成就板块"""
        async for result in self._handle_screenshot(event, username, "achievements", "成就"):
            yield result
    
    @tetrio_group.command("about")
    async def cmd_about(self, event: AstrMessageEvent, username: str):
        """截取 ABOUT ME 板块"""
        async for result in self._handle_screenshot(event, username, "about", "关于我"):
            yield result
    
    @tetrio_group.command("news")
    async def cmd_news(self, event: AstrMessageEvent, username: str):
        """截取 LATEST NEWS 板块"""
        async for result in self._handle_screenshot(event, username, "news", "最新动态"):
            yield result
    
    @tetrio_group.command("clearcache")
    async def cmd_clear_cache(self, event: AstrMessageEvent):
        """清空所有截图缓存"""
        try:
            cleaned_count = self.cache_manager.clear_all_cache()
            yield event.plain_result(f"✅ 已清空缓存，删除了 {cleaned_count} 个文件")
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            yield event.plain_result(f"❌ 清空缓存失败: {e}")
    
    async def _handle_screenshot(self, event: AstrMessageEvent, username: str, section: str, section_display: str):
        """
        处理截图请求（带并发控制和重试）
        
        Args:
            event: 消息事件
            username: 玩家用户名
            section: 板块类型
            section_display: 板块显示名称
        """
        # 等待浏览器初始化完成
        await self._browser_ready.wait()
        
        # 验证用户名
        is_valid, error_msg = validate_username(username)
        if not is_valid:
            yield event.plain_result(f"❌ {error_msg}")
            return
        
        # 规范化用户名
        username = normalize_username(username)
        
        # 获取并发许可
        if not await self.concurrency_controller.acquire(timeout=45):
            yield event.plain_result("❌ 当前请求过多，请稍后重试")
            return
        
        try:
            # 发送提示
            yield event.plain_result(f"🔍 正在查询玩家 {username} 的{section_display}信息...")
            
            # 检查缓存
            screenshot_path = None
            if self.cache_enabled:
                screenshot_path = self.cache_manager.get_cached_screenshot(username, section)
                if screenshot_path:
                    logger.info(f"使用缓存截图: {screenshot_path}")
            
            # 如果没有缓存，执行截图（带重试）
            if not screenshot_path:
                screenshot_path = await self._capture_with_retry(username, section)
            
            # 发送截图
            if os.path.exists(screenshot_path):
                yield event.image_result(screenshot_path)
                logger.info(f"成功发送 {username} 的{section_display}截图")
            else:
                yield event.plain_result(f"❌ 截图文件不存在")
                
        except Exception as e:
            error_message = str(e)
            logger.error(f"查询失败 ({username}/{section}): {error_message}")
            
            # 根据错误类型返回友好提示
            if "不存在" in error_message or "无法找到" in error_message:
                yield event.plain_result(f"❌ 未找到玩家 {username}，请检查用户名是否正确")
            elif "timeout" in error_message.lower() or "超时" in error_message:
                yield event.plain_result(f"❌ 查询超时，请稍后重试")
            else:
                yield event.plain_result(f"❌ 查询失败: {error_message}")
        
        finally:
            # 释放并发许可
            await self.concurrency_controller.release()
    
    async def _capture_with_retry(self, username: str, section: str) -> str:
        """
        带重试的截图执行
        
        Args:
            username: 玩家用户名
            section: 板块类型
            
        Returns:
            str: 截图文件路径
        """
        async def capture():
            if section == "full":
                return await self.capturer.capture_full_page(username)
            elif section == "profile":
                return await self.capturer.capture_profile_sidebar(username)
            else:
                return await self.capturer.capture_section(username, section)
        
        # 使用重试策略：最多 2 次重试，指数退避
        return await RetryStrategy.with_retry(
            capture,
            max_retries=2,
            base_delay=1.0,
            exponential_backoff=True,
            retryable_exceptions=(asyncio.TimeoutError, Exception)
        )