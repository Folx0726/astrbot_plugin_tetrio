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
                 screenshot_quality: int = 85,
                 page_zoom_full: float = 0.9,
                 page_zoom_section: float = 1.0):
        """
        初始化截图执行器
        
        Args:
            browser_manager: 浏览器管理器实例
            screenshot_dir: 截图保存目录
            screenshot_format: 截图格式（webp 或 png）
            screenshot_quality: 截图质量（1-100，仅对 webp 有效）
            page_zoom_full: 完整页面缩放级别
            page_zoom_section: 板块缩放级别
        """
        self.browser_manager = browser_manager
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_format = screenshot_format.lower()
        self.screenshot_quality = screenshot_quality
        self.page_zoom_full = page_zoom_full
        self.page_zoom_section = page_zoom_section
        
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
            
            # 设置页面缩放以获得更紧凑的布局
            await self._set_page_zoom(page, zoom_level=self.page_zoom_full)
            
            # 展开所有可展开的板块
            await self._expand_all_sections(page)
            
            # 检查是否有错误
            if await self._check_error(page):
                raise Exception(f"玩家 {username} 不存在或页面加载失败")
            
            # 生成文件名
            filename = self._generate_filename(username, "full")
            filepath = str(self.screenshot_dir / filename)
            
            # 截取整页（使用 PNG 格式以保证最高质量）
            if self.screenshot_format == 'webp':
                await page.screenshot(
                    path=filepath, 
                    full_page=True,
                    type='png'  # 使用 PNG 格式保证质量
                )
            else:
                await page.screenshot(path=filepath, full_page=True, type='png')
            
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
            
            # 设置页面缩放
            await self._set_page_zoom(page, zoom_level=self.page_zoom_section)
            
            # 展开所有可展开的板块
            await self._expand_all_sections(page)
            
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
                await sidebar.screenshot(path=filepath, type='png')
            else:
                await sidebar.screenshot(path=filepath, type='png')
            
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
            
            # 根据不同板块设置不同的缩放级别
            zoom_level = self._get_optimal_zoom_for_section(section)
            await self._set_page_zoom(page, zoom_level=zoom_level)
            
            # 展开所有可展开的板块
            await self._expand_all_sections(page)
            
            # 如果是 news 板块，进行额外的展开尝试
            if section == "news":
                await self._expand_news_section_specific(page)
            
            if await self._check_error(page):
                raise Exception(f"玩家 {username} 不存在或页面加载失败")
            
            # 定位目标板块
            selector = SECTION_SELECTORS[section]
            element = await page.query_selector(selector)
            
            if not element:
                raise Exception(f"无法找到板块: {SECTION_NAMES.get(section, section)}")
            
            filename = self._generate_filename(username, section)
            filepath = str(self.screenshot_dir / filename)
            
            # 截取板块
            if self.screenshot_format == 'webp':
                await element.screenshot(path=filepath, type='png')
            else:
                await element.screenshot(path=filepath, type='png')
            
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
        
        # 等待页面完全渲染
        await page.wait_for_timeout(1000)
    
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
    
    async def _set_page_zoom(self, page, zoom_level: float = 1.0):
        """
        设置页面缩放级别
        
        Args:
            page: Playwright 页面对象
            zoom_level: 缩放级别，1.0 为正常大小，0.9 为 90% 等
        """
        try:
            await page.evaluate(f'''
                () => {{
                    document.body.style.zoom = "{zoom_level}";
                }}
            ''')
            logger.info(f"设置页面缩放级别: {zoom_level}")
            # 等待页面重新渲染
            await page.wait_for_timeout(500)
        except Exception as e:
            logger.warning(f"设置页面缩放失败: {e}")
    
    def _get_optimal_zoom_for_section(self, section: str) -> float:
        """
        根据板块类型获取最佳缩放级别
        
        Args:
            section: 板块名称
            
        Returns:
            float: 缩放级别
        """
        # 为不同板块设置不同的缩放级别
        # 大部分板块使用配置的默认值，个别板块特殊处理
        zoom_settings = {
            'league': self.page_zoom_section,
            '40l': self.page_zoom_section,
            'blitz': self.page_zoom_section,
            'qp': self.page_zoom_section,
            'zen': self.page_zoom_section,
            'achievements': self.page_zoom_section * 0.95,  # 成就板块略微缩小
            'about': self.page_zoom_section,
            'news': self.page_zoom_section * 0.95,  # NEWS 板块略微缩小以显示更多内容
        }
        
        zoom = zoom_settings.get(section, self.page_zoom_section)
        logger.debug(f"板块 {section} 使用缩放级别: {zoom}")
        return zoom
    
    async def _expand_all_sections(self, page):
        """尝试展开所有可展开的板块"""
        try:
            # 多种选择器尝试查找展开按钮
            selectors = [
                'button:has-text("expand")',
                'a:has-text("expand")',
                'button:has-text("EXPAND")',
                'a:has-text("EXPAND")',
                '.expand-button',
                '[class*="expand"]',
                'button[onclick*="expand"]',
                # TETR.IO 特定的选择器
                '#usercard_news button',
                '#usercard_news a',
            ]
            
            clicked_count = 0
            for selector in selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        try:
                            # 检查元素是否可见且可点击
                            if await element.is_visible():
                                # 获取元素文本以判断是否为展开按钮
                                text = await element.inner_text()
                                if text and ('expand' in text.lower() or '展开' in text):
                                    await element.click()
                                    clicked_count += 1
                                    await page.wait_for_timeout(500)
                                    logger.info(f"已点击展开按钮: {text}")
                        except Exception as e:
                            logger.debug(f"点击元素失败: {e}")
                except Exception as e:
                    logger.debug(f"查找选择器 {selector} 失败: {e}")
            
            if clicked_count > 0:
                # 等待内容完全展开
                await page.wait_for_timeout(1000)
                logger.info(f"成功点击 {clicked_count} 个展开按钮")
            else:
                logger.warning("未找到任何展开按钮")
                
        except Exception as e:
            logger.warning(f"展开板块失败: {e}")
    
    async def _expand_news_section_specific(self, page):
        """专门针对 NEWS 板块的展开逻辑"""
        try:
            logger.info("尝试展开 NEWS 板块...")
            
            # 等待 news 板块加载
            try:
                await page.wait_for_selector(USERCARD_NEWS, state="visible", timeout=5000)
                logger.info("NEWS 板块已加载")
            except Exception as e:
                logger.warning(f"NEWS 板块未找到: {e}")
                return
            
            # 等待一下让 NEWS 板块完全渲染
            await page.wait_for_timeout(1000)
            
            # 获取 NEWS 板块的 HTML 内容用于调试
            try:
                news_html = await page.evaluate(f'''
                    () => {{
                        const newsCard = document.querySelector("{USERCARD_NEWS}");
                        return newsCard ? newsCard.innerHTML : null;
                    }}
                ''')
                if news_html:
                    logger.debug(f"NEWS 板块 HTML 长度: {len(news_html)}")
            except Exception as e:
                logger.debug(f"获取 HTML 失败: {e}")
            
            # 尝试多种方式查找并点击展开按钮
            expand_found = False
            
            # 方法1: 查找 NEWS 板块内的所有按钮和链接
            news_selectors = [
                f"{USERCARD_NEWS} button",
                f"{USERCARD_NEWS} a",
                f"{USERCARD_NEWS} [role='button']",
                f"{USERCARD_NEWS} .button",
                f"{USERCARD_NEWS} span[onclick]",
                f"{USERCARD_NEWS} div[onclick]",
            ]
            
            for selector in news_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        logger.debug(f"查找 {selector}, 找到 {len(elements)} 个元素")
                    
                    for element in elements:
                        try:
                            if await element.is_visible():
                                text = (await element.inner_text()).strip().lower()
                                logger.debug(f"元素文本: '{text}'")
                                
                                # 查找包含 expand 字样的元素
                                if 'expand' in text or '展开' in text:
                                    logger.info(f"找到展开按钮: {text}")
                                    await element.click()
                                    expand_found = True
                                    await page.wait_for_timeout(1500)
                                    logger.info("已点击 EXPAND 按钮")
                                    break
                        except Exception as e:
                            logger.debug(f"处理元素失败: {e}")
                    
                    if expand_found:
                        break
                except Exception as e:
                    logger.debug(f"查找 {selector} 失败: {e}")
            
            # 方法2: 使用 JavaScript 直接查找并点击
            if not expand_found:
                logger.info("尝试使用 JavaScript 查找 EXPAND 按钮...")
                try:
                    clicked = await page.evaluate(f'''
                        () => {{
                            const newsCard = document.querySelector("{USERCARD_NEWS}");
                            if (!newsCard) return false;
                            
                            // 查找所有可点击元素
                            const clickables = newsCard.querySelectorAll('button, a, [role="button"], [onclick]');
                            
                            for (let elem of clickables) {{
                                const text = elem.innerText.toLowerCase();
                                if (text.includes('expand') || text.includes('展开')) {{
                                    elem.click();
                                    console.log('Clicked expand button via JavaScript:', text);
                                    return true;
                                }}
                            }}
                            
                            return false;
                        }}
                    ''')
                    
                    if clicked:
                        expand_found = True
                        logger.info("通过 JavaScript 成功点击 EXPAND 按钮")
                        await page.wait_for_timeout(1500)
                except Exception as e:
                    logger.warning(f"JavaScript 点击失败: {e}")
            
            if expand_found:
                logger.info("✅ NEWS 板块已成功展开")
            else:
                logger.warning("⚠️ NEWS 板块未找到 EXPAND 按钮，可能已经展开或不存在此按钮")
            
        except Exception as e:
            logger.warning(f"展开 NEWS 板块失败: {e}")
    
    def _generate_filename(self, username: str, section: str) -> str:
        """生成截图文件名"""
        timestamp = int(time.time())
        ext = 'png'  # 统一使用 PNG 格式保证质量
        return f"{username}_{section}_{timestamp}.{ext}"
