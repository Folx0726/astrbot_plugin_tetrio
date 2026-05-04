import asyncio
import os
import time
from pathlib import Path

from astrbot.api.all import *
from astrbot.api.event import filter
import astrbot.api.message_components as Comp

from .screenshot import BrowserManager, ScreenshotCapturer
from .utils import CacheManager, validate_username, normalize_username, ConcurrencyController, RetryStrategy
from .database import Database
from .tetrio_api import check_eligibility
from .web_server import WebServer

@register(
    "tetrio",
    "Folx",
    "TETR.IO 插件：支持截图查询、账号绑定与比赛报名",
    "1.2.0",
    "https://github.com/Folx0726/astrbot_plugin_tetrio"
)
class TetrioPlugin(Star):
    """TETR.IO 综合插件"""
    
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        
        # 初始化配置
        self.config = config or {}
        self.cache_enabled = self.config.get("cache_enabled", True)
        self.cache_ttl = self.config.get("cache_ttl", 300)
        self.browser_headless = self.config.get("browser_headless", True)
        self.browser_timeout = self.config.get("browser_timeout", 30)
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
        
        # 插件数据目录 - 使用持久化存储位置
        # 获取插件目录的父目录（即 AstrBot 的 data/plugins 目录）
        plugin_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        # 向上两级，到达 AstrBot 的 data 目录
        astrbot_data_dir = plugin_dir.parent.parent
        # 在 AstrBot 的 data 目录下创建 tetrio 子目录
        persistent_data_dir = astrbot_data_dir / "tetrio"
        self.data_dir = persistent_data_dir  # 存储为实例属性
        # 确保持久化数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir = self.data_dir / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # 数据库与 Web 服务初始化
        self.db_path = self.data_dir / "tcc.db"
        self.db = Database(str(self.db_path))
        self.web_server = WebServer(self.db, port=8081, plugin=self)
        
        # 截图相关组件
        self.browser_manager = BrowserManager()
        self.capturer = ScreenshotCapturer(
            self.browser_manager, 
            str(self.screenshot_dir),
            screenshot_format=self.screenshot_format,
            screenshot_quality=self.screenshot_quality,
            page_zoom_full=self.page_zoom_full,
            page_zoom_section=self.page_zoom_section,
            browser_timeout=self.browser_timeout
        )
        self.cache_manager = CacheManager(
            str(self.screenshot_dir), 
            self.cache_ttl,
            max_cache_size_mb=self.max_cache_size_mb,
            max_cache_files=self.max_cache_files
        )
        
        self.concurrency_controller = ConcurrencyController(max_concurrent=self.max_concurrent_tasks)
        
        # 异步初始化
        self._browser_ready = asyncio.Event()
        asyncio.create_task(self._init_browser())
        asyncio.create_task(self._init_services())
        
        logger.info("TETR.IO 综合插件已加载")

    async def _init_browser(self):
        """异步初始化浏览器"""
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
            self._browser_ready.set()

    async def _init_services(self):
        """初始化数据库和 Web 服务"""
        try:
            await self.db.init_db()
            await self.web_server.start()
            logger.info("数据库和 Web 服务初始化完成")
            
            # 启动每日自动更新任务
            asyncio.create_task(self._daily_update_task())
        except Exception as e:
            logger.error(f"初始化服务失败: {e}")

    async def _daily_update_task(self):
        """每日定时更新任务"""
        logger.info("[TETR.IO] 每日自动更新任务已启动")
        while True:
            try:
                # 计算距离次日凌晨 4:00 的时间
                now = time.localtime()
                # 目标时间：明天凌晨 4 点 (避开高峰期)
                target_hour = 4
                
                # 如果当前已经过了今天的 4 点，就定在明天 4 点
                # 如果当前还没到今天的 4 点，就定在今天 4 点 (可选，或者统一明天)
                # 这里简单起见，统一等待到下一个 4 点
                
                current_timestamp = time.time()
                # 获取当天 4:00 的时间戳
                today_target = time.mktime(time.struct_time((
                    now.tm_year, now.tm_mon, now.tm_mday,
                    target_hour, 0, 0, 0, 0, -1
                )))
                
                if current_timestamp < today_target:
                    sleep_seconds = today_target - current_timestamp
                else:
                    # 如果今天已经过了 4 点，则是明天 4 点
                    sleep_seconds = today_target + 86400 - current_timestamp
                
                logger.info(f"[TETR.IO] 下次自动更新将在 {sleep_seconds/3600:.2f} 小时后执行")
                await asyncio.sleep(sleep_seconds)
                
                # 执行更新
                logger.info("[TETR.IO] 开始执行每日自动更新...")
                
                # 更新所有用户数据
                logger.info("[TETR.IO] 更新用户数据...")
                await self._update_all_users_task(event=None) # event 为 None 表示自动触发
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TETR.IO] 每日自动更新任务异常: {e}")
                # 出错后等待 1 小时重试，避免死循环刷屏
                await asyncio.sleep(3600)

    async def terminate(self):
        """清理资源"""
        logger.info("正在清理 TETR.IO 插件资源...")
        await self.web_server.stop()
        await self.browser_manager.close_browser()
        if self.cache_enabled:
            self.cache_manager.clean_expired_cache()
    
    async def send_deletion_notification(self, user_info):
        """记录用户删除操作
        
        Args:
            user_info: 用户信息字典
        """
        try:
            # 1. 从配置中获取群聊ID列表
            group_ids = self.config.get("notification_group_ids", [])
            
            # 2. 构建用户信息
            user_id = user_info.get('user_id', '未知')
            tetrio_id = user_info.get('tetrio_id', '未知')
            username = user_info.get('username', '未知')
            league_rating = user_info.get('league_rating', -1.0)
            rank = user_info.get('rank', 'z')
            sprint_time = user_info.get('sprint_time', 9999.0)
            avatar_url = f"http://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=100&img_type=jpg"
            
            # 3. 构建通知消息
            message_text = f"⚠️ 用户数据已删除 ⚠️\n"
            message_text += f"QQ号: {user_id}\n"
            message_text += f"TETR.IO用户名: {tetrio_id}\n"
            message_text += f"昵称: {username}\n"
            message_text += f"TR: {league_rating if league_rating != -1.0 else 'N/A'}\n"
            message_text += f"段位: {rank}\n"
            message_text += f"40L时间: {sprint_time if sprint_time != 9999.0 else 'N/A'}s\n"
            message_text += f"头像: {avatar_url}"
            
            # 4. 记录删除操作
            logger.info(f"用户数据已删除:\n{message_text}")
            
            # 5. 关于主动消息的说明
            if group_ids:
                logger.info(f"配置的通知群聊: {group_ids}")
                logger.info("注意：根据AstrBot文档，主动发送群聊消息需要event.unified_msg_origin")
                logger.info("由于这是通过Web API触发的操作，没有event对象，无法发送主动消息")
                logger.info("建议：")
                logger.info("1. 当有用户在群聊中发言时，保存event.unified_msg_origin")
                logger.info("2. 使用保存的unified_msg_origin发送主动消息")
                logger.info("3. 或等待AstrBot提供直接发送群聊消息的API")
            
        except Exception as e:
            logger.error(f"记录删除操作失败: {e}")

    @filter.command_group("tetrio")
    def tetrio_group(self):
        """TETR.IO 指令组"""
        pass

    @tetrio_group.command("bind", alias=["绑定"])
    async def cmd_bind(self, event: AstrMessageEvent, username: str):
        """绑定 TETR.IO 账号（需确认）"""
        user_id = event.get_sender_id()
        username = normalize_username(username)
        
        # 检查用户是否已绑定
        existing_user = await self.db.get_user(user_id)
        if existing_user and existing_user['tetrio_id']:
            yield event.plain_result(f"❌ 您已经绑定了账号：{existing_user['tetrio_id']}\n如需更换账号，请联系管理员。")
            return
        
        # 1. 发送截图进行确认
        yield event.plain_result(f"正在查询玩家 {username} 信息，请稍候...")
        
        screenshot_path = await self._capture_with_retry(username, "full")
        if not screenshot_path or not os.path.exists(screenshot_path):
            yield event.plain_result("❌ 未找到该用户或获取信息失败，请检查用户名。")
            return
            
        yield event.image_result(screenshot_path)
        yield event.plain_result("请确认这是您的账号吗？(是/否)\n(30秒内回复)")

        # 2. 注册一个临时监听器来等待用户确认
        # 由于 Context 没有 wait_for_event，我们需要使用 Star 的注册机制或手动管理状态
        # 这里采用手动管理状态的方式，更稳妥
        
        # 记录待确认状态
        if not hasattr(self, "pending_binds"):
            self.pending_binds = {}
            
        self.pending_binds[user_id] = {
            "username": username,
            "timestamp": time.time()
        }
        
        async def timeout_cleanup():
            await asyncio.sleep(30)
            if user_id in self.pending_binds and \
               self.pending_binds[user_id]["timestamp"] + 30 <= time.time() + 0.1:
                if user_id in self.pending_binds:
                    del self.pending_binds[user_id]
                    logger.info(f"[TETR.IO] 用户 {user_id} 的绑定确认已超时（{username}）")
        
        asyncio.create_task(timeout_cleanup())

    @filter.event_message_type(filter.EventMessageType.ALL, priority=100)
    async def handle_bind_confirmation(self, event: AstrMessageEvent):
        """处理绑定确认消息"""
        if not hasattr(self, "pending_binds"):
            return

        user_id = event.get_sender_id()
        if user_id not in self.pending_binds:
            return

        # 获取消息内容
        msg = event.message_str.strip()
        if not msg:
            return

        bind_info = self.pending_binds[user_id]
        username = bind_info["username"]

        # 使用关键词匹配判断意图
        intent = "UNKNOWN"
        if msg in ["是", "确认", "yes", "y", "对", "ok", "对的", "是的", "好的", "确认绑定"]:
            intent = "YES"
        elif msg in ["否", "取消", "no", "n", "不", "不是", "不对", "取消绑定"]:
            intent = "NO"
        
        logger.info(f"[TETR.IO] 意图判断结果: {intent}")
        
        if "YES" in intent:
            del self.pending_binds[user_id]
            existing_tetrio_id = await self.db.bind_user(user_id, username)
            if existing_tetrio_id:
                yield event.plain_result(f"❌ 绑定失败！您已经绑定了账号：{existing_tetrio_id}\n如需更换账号，请联系管理员。")
            else:
                await self.db.update_user_info(user_id, username, username)
                yield event.plain_result(f"✅ 绑定成功！已关联账号: {username}")
            # event.stop_event_propagation() # 移除不支持的方法
            
        elif "NO" in intent:
            del self.pending_binds[user_id]
            yield event.plain_result("已取消绑定操作。")
            # event.stop_event_propagation() # 移除不支持的方法
            
        # UNKNOWN 则忽略，允许用户继续对话或重试

    @tetrio_group.command("update_all", alias=["更新所有数据"])
    async def cmd_update_all(self, event: AstrMessageEvent):
        """后台更新所有已报名用户数据（每5秒一个）"""
        
        # 鉴权：简单检查是否是管理员（如果有 AstrBot 权限系统最好对接，这里暂时所有人可用或通过配置控制）
        # 建议实际使用中加上权限判断，例如：
        # if not event.get_sender_id() in self.config.get("admin_users", []):
        #     return
        
        yield event.plain_result("开始后台更新已报名用户数据，请稍候...")
        
        # 启动后台任务，不阻塞当前命令
        asyncio.create_task(self._update_all_users_task(event))

    async def _update_all_users_task(self, event: AstrMessageEvent):
        """后台更新任务逻辑"""
        try:
            # 获取所有已报名的用户
            users = await self.db.get_all_registered_users_sorted()
            if not users:
                logger.info("[TETR.IO] 没有已报名用户需要更新")
                return

            total = len(users)
            success_count = 0
            fail_count = 0
            
            logger.info(f"[TETR.IO] 开始更新 {total} 名用户数据...")
            
            for idx, user in enumerate(users):
                tetrio_id = user['tetrio_id']
                user_id = user['user_id']
                
                try:
                    logger.info(f"[TETR.IO] ({idx+1}/{total}) 正在更新 {tetrio_id} ...")
                    
                    # 重新查询 API
                    result = await check_eligibility(tetrio_id)
                    
                    if result['success']:
                        # 更新数据库
                        await self.db.register_user(
                            user_id, 
                            result['tr'], 
                            result.get('rank', 'z'),  # 添加 rank 字段
                            result['time_40l'], 
                            is_registered=1 # 保持已报名状态
                        )
                        success_count += 1
                        logger.info(f"[TETR.IO] {tetrio_id} 更新成功: TR={result['tr']}, 40L={result['time_40l']}")
                    else:
                        fail_count += 1
                        logger.warning(f"[TETR.IO] {tetrio_id} 更新失败: {result.get('reason')}")
                        
                except Exception as e:
                    fail_count += 1
                    logger.error(f"[TETR.IO] 更新用户 {tetrio_id} 时发生异常: {e}")
                
                # 每 5 秒处理一个，避免速率限制，同时不阻塞主线程
                if idx < total - 1: # 最后一个不需要等待
                    await asyncio.sleep(5)
            
            logger.info(f"[TETR.IO] 全量更新完成。成功: {success_count}, 失败: {fail_count}")
            # 可选：更新完成后通知用户（如果是私聊触发）
            # 由于 event 可能已过期，这里仅打日志。若需通知，需保存引用或使用其他通知机制。
            
        except Exception as e:
            logger.error(f"[TETR.IO] 后台更新任务异常: {e}")





    @tetrio_group.command("register", alias=["报名"])
    async def cmd_register(self, event: AstrMessageEvent):
        """报名参加比赛（将根据 TR 自动排名）"""
        user_id = event.get_sender_id()
        
        # 检查是否已绑定
        user_record = await self.db.get_user(user_id)
        if not user_record or not user_record['tetrio_id']:
            yield event.plain_result("❌ 您还没有绑定账号，请先发送 /tetrio bind <用户名> 进行绑定。")
            return
            
        tetrio_id = user_record['tetrio_id']
        yield event.plain_result(f"正在检查 {tetrio_id} 的报名资格...")
        
        # 检查资格
        result = await check_eligibility(tetrio_id)
        if not result['success']:
            yield event.plain_result(f"❌ 获取数据失败: {result.get('reason')}")
            return

        if result['eligible']:
            # 记录数据并标记为已报名
            await self.db.register_user(
                user_id, 
                result['tr'], 
                result.get('rank', 'z'),  # 添加 rank 字段
                result['time_40l'], 
                is_registered=1
            )
            
            # 获取所有已报名用户并计算当前排名
            all_users = await self.db.get_all_registered_users_sorted()
            
            # 计算当前用户排名
            rank = -1
            for idx, user in enumerate(all_users):
                if user['user_id'] == user_id:
                    rank = idx + 1
                    break
            
            rank_text = f"（当前排名：第 {rank} 名）" if rank > 0 else ""
            
            # 发送报名成功消息
            yield event.plain_result(f"报名成功！{rank_text}\nTR: {result['tr']:.2f}\n40L: {result['time_40l']:.3f}s\n{result['reason']}")
        else:
            # 记录数据但标记为未报名
            await self.db.register_user(
                user_id, 
                result['tr'], 
                result.get('rank', 'z'),  # 添加 rank 字段
                result['time_40l'], 
                is_registered=0
            )
            yield event.plain_result(f"报名失败：未达到要求。\n{result['reason']}")

    # --- 原有的截图指令保持不变 ---

    @tetrio_group.command("full")
    async def cmd_full(self, event: AstrMessageEvent, username: str = None):
        """截取玩家完整页面"""
        async for result in self._handle_screenshot(event, username, "full", "完整页面"):
            yield result
    
    @tetrio_group.command("profile", alias=["个人信息"])
    async def cmd_profile(self, event: AstrMessageEvent, username: str = None):
        """查询玩家个人信息面板"""
        async for result in self._handle_screenshot(event, username, "profile", "个人信息"):
            yield result

    @tetrio_group.command("league", alias=["排位", "段位"])
    async def cmd_league(self, event: AstrMessageEvent, username: str = None):
        """查询玩家排位信息"""
        async for result in self._handle_screenshot(event, username, "league", "排位数据"):
            yield result

    @tetrio_group.command("40l", alias=["40行", "竞速"])
    async def cmd_40l(self, event: AstrMessageEvent, username: str = None):
        """查询玩家 40行竞速数据"""
        async for result in self._handle_screenshot(event, username, "40l", "40行竞速数据"):
            yield result

    @tetrio_group.command("blitz", alias=["击块", "闪电战"])
    async def cmd_blitz(self, event: AstrMessageEvent, username: str = None):
        """查询玩家 Blitz 模式数据"""
        async for result in self._handle_screenshot(event, username, "blitz", "Blitz 数据"):
            yield result

    @tetrio_group.command("zen", alias=["禅模式"])
    async def cmd_zen(self, event: AstrMessageEvent, username: str = None):
        """查询玩家 Zen 模式数据"""
        async for result in self._handle_screenshot(event, username, "zen", "Zen 模式数据"):
            yield result

    @tetrio_group.command("achievements", alias=["成就"])
    async def cmd_achievements(self, event: AstrMessageEvent, username: str = None):
        """查询玩家成就"""
        async for result in self._handle_screenshot(event, username, "achievements", "成就数据"):
            yield result

    @tetrio_group.command("ranklist", alias=["排行榜", "联赛排行榜"])
    async def cmd_ranklist(self, event: AstrMessageEvent):
        """截取 TETR.IO League 排行榜页面"""
        await self._browser_ready.wait()
        
        if not await self.concurrency_controller.acquire(timeout=45):
            yield event.plain_result("❌ 当前请求过多，请稍后重试")
            return
        
        try:
            yield event.plain_result("🔍 正在截取 TETR.IO League 页面...")
            
            screenshot_path = None
            if self.cache_enabled:
                screenshot_path = self.cache_manager.get_cached_league_page()
            
            if not screenshot_path:
                screenshot_path = await self._capture_league_page_with_retry()
            
            if os.path.exists(screenshot_path):
                yield event.image_result(screenshot_path)
            else:
                yield event.plain_result("❌ 截图文件不存在")
                
        except Exception as e:
            logger.error(f"截取 TETR.IO League 页面失败: {e}")
            yield event.plain_result(f"❌ 截取 TETR.IO League 页面失败: {str(e)}")
        finally:
            await self.concurrency_controller.release()

    async def _handle_screenshot(self, event: AstrMessageEvent, username: str, section: str, section_display: str):
        """处理截图请求"""
        await self._browser_ready.wait()
        
        # 如果没有提供用户名，尝试使用用户绑定的账号
        if not username:
            user_id = event.get_sender_id()
            user_info = await self.db.get_user(user_id)
            if user_info and user_info['tetrio_id']:
                username = user_info['tetrio_id']
                yield event.plain_result(f"🔍 正在查询您绑定的账号 {username} 的{section_display}信息...")
            else:
                yield event.plain_result("❌ 您还未绑定 TETR.IO 账号，请先使用 /tetrio bind 命令绑定账号")
                return
        else:
            is_valid, error_msg = validate_username(username)
            if not is_valid:
                yield event.plain_result(f"❌ {error_msg}")
                return
            
            username = normalize_username(username)
            yield event.plain_result(f"🔍 正在查询玩家 {username} 的{section_display}信息...")
        
        if not await self.concurrency_controller.acquire(timeout=45):
            yield event.plain_result("❌ 当前请求过多，请稍后重试")
            return
        
        try:
            screenshot_path = None
            if self.cache_enabled:
                screenshot_path = self.cache_manager.get_cached_screenshot(username, section)
            
            if not screenshot_path:
                screenshot_path = await self._capture_with_retry(username, section)
            
            if os.path.exists(screenshot_path):
                yield event.image_result(screenshot_path)
            else:
                yield event.plain_result(f"❌ 截图文件不存在")
                
        except Exception as e:
            logger.error(f"查询失败: {e}")
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
        finally:
            await self.concurrency_controller.release()

    async def _capture_with_retry(self, username: str, section: str) -> str:
        async def capture():
            if section == "full":
                return await self.capturer.capture_full_page(username)
            elif section == "profile":
                return await self.capturer.capture_profile_sidebar(username)
            else:
                return await self.capturer.capture_section(username, section)
        
        return await RetryStrategy.with_retry(capture, max_retries=2)
    
    async def _capture_league_page_with_retry(self) -> str:
        async def capture():
            return await self.capturer.capture_league_page()
        
        return await RetryStrategy.with_retry(capture, max_retries=2)
