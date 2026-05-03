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
import base64

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
                 page_zoom_section: float = 1.0,
                 browser_timeout: int = 30):
        self.browser_manager = browser_manager
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_format = screenshot_format.lower()
        self.screenshot_quality = screenshot_quality
        self.page_zoom_full = page_zoom_full
        self.page_zoom_section = page_zoom_section
        self.browser_timeout = browser_timeout * 1000
        
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
            
            await page.goto(url, wait_until="domcontentloaded", timeout=self.browser_timeout)
            
            await self._wait_for_page_load(page)
            
            await self._set_page_zoom(page, zoom_level=1.25)
            
            await self._expand_all_sections(page)
            
            if await self._check_error(page):
                raise Exception(f"玩家 {username} 不存在或页面加载失败")
            
            await page.evaluate('''
                () => {
                    console.log('开始隐藏顶部内容');
                    
                    const headerSub = document.getElementById("header_sub");
                    if (headerSub) {
                        let element = headerSub;
                        while (element) {
                            const prevElement = element.previousElementSibling;
                            element.style.display = "none";
                            element.style.visibility = "hidden";
                            element.style.opacity = "0";
                            element.style.height = "0";
                            element.style.overflow = "hidden";
                            element = prevElement;
                        }
                    } else {
                        const topSelectors = ["#header", ".header", "header", "nav", "#navigation"];
                        topSelectors.forEach(selector => {
                            try {
                                const elements = document.querySelectorAll(selector);
                                elements.forEach(element => {
                                    element.style.display = "none";
                                    element.style.visibility = "hidden";
                                    element.style.opacity = "0";
                                    element.style.height = "0";
                                    element.style.overflow = "hidden";
                                });
                            } catch (e) {}
                        });
                    }
                    
                    const mainContentSelectors = [
                        '#userpage', '.userpage', '#usercard', '.usercard', 'main', 'section'
                    ];
                    
                    let mainContentFound = false;
                    mainContentSelectors.forEach(selector => {
                        if (!mainContentFound) {
                            try {
                                const elements = document.querySelectorAll(selector);
                                elements.forEach(element => {
                                    if (!mainContentFound) {
                                        let current = element.previousElementSibling;
                                        while (current) {
                                            const next = current.previousElementSibling;
                                            current.style.display = "none";
                                            current.style.visibility = "hidden";
                                            current.style.opacity = "0";
                                            current = next;
                                        }
                                        mainContentFound = true;
                                    }
                                });
                            } catch (e) {}
                        }
                    });
                }
            ''')
            
            await page.wait_for_timeout(1000)
            
            filename = self._generate_filename(username, "full")
            filepath = str(self.screenshot_dir / filename)
            
            await page.screenshot(
                path=filepath, 
                full_page=True, 
                type=self.screenshot_format,
                timeout=self.browser_timeout * 2
            )
            
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
            await page.goto(url, wait_until="domcontentloaded", timeout=self.browser_timeout)
            
            await self._wait_for_page_load(page)
            
            await self._set_page_zoom(page, zoom_level=self.page_zoom_section)
            
            await self._expand_all_sections(page)
            
            if await self._check_error(page):
                raise Exception(f"玩家 {username} 不存在或页面加载失败")
            
            await page.wait_for_timeout(500)
            
            sidebar = await page.query_selector(LEFT_SIDEBAR)
            if not sidebar:
                raise Exception("无法找到左侧信息栏")
            
            filename = self._generate_filename(username, "profile")
            filepath = str(self.screenshot_dir / filename)
            
            await sidebar.screenshot(path=filepath, type=self.screenshot_format, timeout=self.browser_timeout * 2)
            
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
            await page.goto(url, wait_until="domcontentloaded", timeout=self.browser_timeout)
            
            await self._wait_for_page_load(page)
            
            zoom_level = self._get_optimal_zoom_for_section(section)
            await self._set_page_zoom(page, zoom_level=zoom_level)
            
            await self._expand_all_sections(page)
            
            if section == "news":
                await self._expand_news_section_specific(page)
            
            if await self._check_error(page):
                raise Exception(f"玩家 {username} 不存在或页面加载失败")
            
            await page.wait_for_timeout(500)
            
            selector = SECTION_SELECTORS[section]
            element = await page.query_selector(selector)
            
            if not element:
                raise Exception(f"无法找到板块: {SECTION_NAMES.get(section, section)}")
            
            filename = self._generate_filename(username, section)
            filepath = str(self.screenshot_dir / filename)
            
            await element.screenshot(path=filepath, type=self.screenshot_format, timeout=self.browser_timeout * 2)
            
            logger.info(f"截图完成: {filepath}")
            return filepath
            
        finally:
            if context_item:
                await self.browser_manager.release_context(context_item)
    
    async def _wait_for_page_load(self, page):
        try:
            await page.wait_for_selector(LOADER, state="hidden", timeout=self.browser_timeout)
        except Exception as e:
            logger.warning(f"等待加载器消失超时: {e}")
        
        try:
            await page.wait_for_selector(LEFT_SIDEBAR, state="visible", timeout=self.browser_timeout)
        except Exception as e:
            logger.warning(f"等待主内容区域超时: {e}")
        
        await self._replace_taiwan_flag(page)
        
        # 处理banned元素：只隐藏带有hidden类的（未被ban的），保留真正被ban的
        await page.evaluate('''
            () => {
                // 1. 专门处理 id="user_banned" 元素
                const userBannedElement = document.getElementById('user_banned');
                if (userBannedElement) {
                    // 检查是否包含hidden类（未被ban的账户）
                    if (userBannedElement.classList.contains('hidden')) {
                        // 隐藏未被ban账户的banned元素
                        userBannedElement.style.display = 'none';
                        userBannedElement.style.visibility = 'hidden';
                        userBannedElement.style.opacity = '0';
                        userBannedElement.style.position = 'absolute';
                        userBannedElement.style.left = '-9999px';
                        userBannedElement.style.top = '-9999px';
                    } else {
                        // 保留真正被ban账户的banned元素（不做任何处理）
                        console.log('保留真正被ban账户的banned元素');
                    }
                }
                
                // 2. 清理其他可能的banned相关元素（只处理带有hidden类的）
                const bannedSelectors = [
                    '.banned.hidden', '[class*="banned"].hidden', '#banned.hidden', '[id*="banned"].hidden',
                    '.ban.hidden', '[class*="ban"].hidden', '#ban.hidden', '[id*="ban"].hidden',
                    '.suspended.hidden', '[class*="suspended"].hidden', '#suspended.hidden', '[id*="suspended"].hidden',
                    '.suspend.hidden', '[class*="suspend"].hidden', '#suspend.hidden', '[id*="suspend"].hidden',
                    '.eject_rest.hidden', '[class*="eject_rest"].hidden'
                ];
                
                bannedSelectors.forEach(selector => {
                    try {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(element => {
                            element.style.display = 'none';
                            element.style.visibility = 'hidden';
                            element.style.opacity = '0';
                        });
                    } catch (e) {
                        // 忽略无效选择器
                    }
                });
            }
        ''')
        
        # 等待页面完全渲染
        await page.wait_for_timeout(1000)
    
    async def _replace_taiwan_flag(self, page):
        """
        替换错误的台湾旗帜为中国台北旗
        """
        try:
            # 读取本地的中国台北旗文件并转换为base64
            taipei_flag_path = str(Path(__file__).parent.parent / "55e736d12f2eb9389b50cea23c3a9235e5dde711c110.webp")
            taipei_flag_base64 = ""
            if os.path.exists(taipei_flag_path):
                with open(taipei_flag_path, "rb") as f:
                    taipei_flag_base64 = base64.b64encode(f.read()).decode('utf-8')
                taipei_flag_data_url = f"data:image/webp;base64,{taipei_flag_base64}"
            else:
                # 如果本地文件不存在，使用默认的中国国旗
                taipei_flag_data_url = 'https://flagcdn.com/w40/cn.png'
            
            await page.evaluate('''
                (taipeiFlagDataUrl) => {
                    const flagElements = document.querySelectorAll(
                        '#flag_crumb, img.flag, img[class*="flag"], img[data-country], ' +
                        'img[src*="flag"], img[src*="taiwan"], img[src*="tw"], ' +
                        '[data-country="TW"]'
                    );
                    
                    const replacedContainers = new Set();
                    flagElements.forEach(element => {
                        try {
                            const src = element.src ? element.src.toLowerCase() : '';
                            const alt = (element.alt || '').toLowerCase();
                            const title = (element.title || '').toLowerCase();
                            const datasetCountry = (element.dataset.country || '').toLowerCase();
                            
                            if (src.includes('tw') || src.includes('taiwan') || 
                                alt.includes('tw') || alt.includes('taiwan') ||
                                title.includes('tw') || title.includes('taiwan') ||
                                datasetCountry === 'tw') {
                                element.src = taipeiFlagDataUrl;
                                element.alt = 'Chinese Taipei';
                                element.title = 'Chinese Taipei';
                                element.dataset.country = 'TW';
                                const container = element.closest('[data-href]') || element.parentElement;
                                if (container) replacedContainers.add(container);
                            }
                        } catch (e) {}
                    });
                    
                    replacedContainers.forEach(container => {
                        try {
                            const textNodes = container.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span, div');
                            textNodes.forEach(node => {
                                try {
                                    if (node.textContent && /country/i.test(node.textContent)) {
                                        node.textContent = node.textContent.replace(/COUNTRY/gi, 'REGION');
                                    }
                                } catch (e) {}
                            });
                        } catch (e) {}
                    });
                }
            ''', taipei_flag_data_url)
            logger.info("台湾旗帜替换为中国台北旗完成")
        except Exception as e:
            logger.warning(f"替换台湾旗帜失败: {e}")
    
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
            
            try:
                await page.wait_for_selector(USERCARD_NEWS, state="visible", timeout=self.browser_timeout)
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

    async def capture_league_page(self) -> str:
        """
        截取 TETR.IO League 页面
        
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
            url = "https://ch.tetr.io/league/"
            
            logger.info(f"开始访问 TETR.IO League 页面: {url}")
            
            await page.goto(url, wait_until="domcontentloaded", timeout=self.browser_timeout)
            
            await self._wait_for_league_page_load(page)
            
            await self._set_page_zoom(page, zoom_level=self.page_zoom_full)
            
            filename = self._generate_league_filename()
            filepath = str(self.screenshot_dir / filename)
            
            await page.screenshot(
                path=filepath, 
                full_page=True, 
                type=self.screenshot_format,
                timeout=self.browser_timeout * 2
            )
            
            logger.info(f"TETR.IO League 页面截图完成: {filepath}")
            return filepath
            
        finally:
            if context_item:
                await self.browser_manager.release_context(context_item)
    
    async def _wait_for_league_page_load(self, page):
        try:
            await page.wait_for_selector("body", state="visible", timeout=self.browser_timeout)
            
            try:
                await page.wait_for_selector("table", state="visible", timeout=self.browser_timeout)
            except Exception as e:
                logger.warning(f"等待排行榜表格超时: {e}")
            
            await page.wait_for_timeout(2000)
            
        except Exception as e:
            logger.warning(f"等待页面加载时出错: {e}")
    
    def _generate_league_filename(self) -> str:
        timestamp = int(time.time())
        return f"league_page_{timestamp}.{self.screenshot_format}"

    def _generate_filename(self, username: str, section: str) -> str:
        timestamp = int(time.time())
        return f"{username}_{section}_{timestamp}.{self.screenshot_format}"
    
    def get_rank_image_path(self, rank: str, rank_images_dir: str, show_z_rank: bool = False) -> Optional[str]:
        """
        根据玩家的段位获取对应的段位图片路径
        
        Args:
            rank: 玩家的段位（如 "x", "u", "ss", "s+", "s", "s-", "a+", "a", "a-", "b+", "b", "b-", "c+", "c", "c-", "d+", "d", "z"）
            rank_images_dir: 段位图片目录
            show_z_rank: 是否显示 z 段位（未定级）图片，默认为 False
            
        Returns:
            Optional[str]: 段位图片路径，如果未找到则返回 None
        """
        if not rank:
            return None
        
        # 如果不显示 z 段位且 rank 为 z，则返回 None
        if not show_z_rank and rank == "z":
            return None
        
        rank_dir = Path(rank_images_dir)
        
        # 根据段位名称查找对应的图片
        image_name = self._get_image_name_by_rank(rank)
        if image_name:
            image_path = rank_dir / image_name
            if image_path.exists():
                return str(image_path)
            else:
                logger.warning(f"段位图片不存在: {image_path}")
                return None
        
        return None
    
    def get_rank_name(self, rank: str) -> str:
        """
        根据玩家的段位获取段位显示名称
        
        Args:
            rank: 玩家的段位（如 "x", "u", "ss", "s+", "s", "s-", "a+", "a", "a-", "b+", "b", "b-", "c+", "c", "c-", "d+", "d", "z"）
            
        Returns:
            str: 段位显示名称
        """
        if not rank or rank == "z":
            return "未定级"
        
        # 将段位转换为大写显示
        rank_upper = rank.upper()
        
        # 特殊处理一些段位
        rank_display_map = {
            "X+": "X+",
            "X": "X",
            "U": "U",
            "SS": "SS",
            "S+": "S+",
            "S": "S",
            "S-": "S-",
            "A+": "A+",
            "A": "A",
            "A-": "A-",
            "B+": "B+",
            "B": "B",
            "B-": "B-",
            "C+": "C+",
            "C": "C",
            "C-": "C-",
            "D+": "D+",
            "D": "D",
        }
        
        return rank_display_map.get(rank_upper, rank_upper)
    
    def _get_image_name_by_rank(self, rank_name: str) -> Optional[str]:
        """
        根据段位名称获取对应的图片文件名
        
        Args:
            rank_name: 段位名称
            
        Returns:
            Optional[str]: 图片文件名，如果未找到则返回 None
        """
        # 段位名称到图片文件名的映射
        rank_image_map = {
            "X+": "x+.png",
            "X": "x.png",
            "U": "u.png",
            "SS": "ss.png",
            "S+": "s+.png",
            "S": "s.png",
            "S-": "s-.png",
            "A+": "a+.png",
            "A": "a.png",
            "A-": "a-.png",
            "B+": "b+.png",
            "B": "b.png",
            "B-": "b-.png",
            "C+": "c+.png",
            "C": "c.png",
            "C-": "c-.png",
            "D+": "d+.png",
            "D": "d.png",
            "Z": "z.png",  # 未定级段位
        }
        
        return rank_image_map.get(rank_name.upper())