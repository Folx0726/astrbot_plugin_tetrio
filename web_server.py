import os
import json
from aiohttp import web
from astrbot.api import logger
from .database import Database

class WebServer:
    def __init__(self, db: Database, port: int = 8081, plugin=None):
        self.db = db
        self.port = port
        self.plugin = plugin  # 引用回TetrioPlugin实例
        self.app = web.Application()
        self.setup_routes()
        self.runner = None
        self.site = None

    def setup_routes(self):
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/users', self.handle_get_users)
        self.app.router.add_get('/api/export', self.handle_export)
        self.app.router.add_post('/api/import', self.handle_import)
        self.app.router.add_get('/api/stats', self.handle_get_stats)
        self.app.router.add_delete('/api/users', self.handle_delete_all)
        self.app.router.add_post('/api/user/{user_id}/status/{status}', self.handle_update_status)
        self.app.router.add_delete('/api/user/{user_id}', self.handle_delete_user)
        self.app.router.add_post('/api/user/manual', self.handle_add_user_manual)

    async def handle_index(self, request):
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
        return web.FileResponse(template_path)

    async def handle_get_users(self, request):
        users = await self.db.get_all_users()
        return web.json_response(users)

    async def handle_get_stats(self, request):
        stats = await self.db.get_stats()
        return web.json_response(stats)

    async def handle_export(self, request):
        users = await self.db.get_all_users()
        return web.json_response(
            users,
            headers={
                'Content-Disposition': 'attachment; filename="tetrio_registrations.json"'
            }
        )

    async def handle_import(self, request):
        """导入JSON数据并更新数据库"""
        try:
            # 解析JSON数据
            data = await request.json()
            
            # 验证数据格式
            if not isinstance(data, list):
                return web.json_response({
                    'success': False,
                    'reason': '数据格式错误：应为JSON数组'
                }, status=400)
            
            # 验证每个用户数据
            valid_users = []
            for i, user_data in enumerate(data):
                if not isinstance(user_data, dict):
                    logger.warning(f"跳过第{i+1}条数据：不是字典格式")
                    continue
                
                if 'user_id' not in user_data:
                    logger.warning(f"跳过第{i+1}条数据：缺少user_id字段")
                    continue
                
                # 验证字段类型
                user_id = user_data.get('user_id')
                if not isinstance(user_id, str):
                    logger.warning(f"跳过用户{user_id}：user_id应为字符串")
                    continue
                
                # 验证可选字段类型
                field_types = {
                    'username': str,
                    'tetrio_id': str,
                    'league_rating': (int, float),
                    'rank': str,
                    'sprint_time': (int, float),
                    'is_registered': int
                }
                
                valid_user = {'user_id': user_id}
                for field, expected_type in field_types.items():
                    if field in user_data:
                        value = user_data[field]
                        if value is not None:
                            if not isinstance(value, expected_type):
                                logger.warning(f"用户{user_id}的{field}字段类型错误：期望{expected_type}，实际{type(value)}")
                                # 尝试转换类型
                                try:
                                    if field in ['league_rating', 'sprint_time']:
                                        valid_user[field] = float(value)
                                    elif field == 'is_registered':
                                        valid_user[field] = int(value)
                                    else:
                                        valid_user[field] = str(value)
                                except (ValueError, TypeError):
                                    logger.warning(f"用户{user_id}的{field}字段转换失败：{value}")
                                    valid_user[field] = None
                            else:
                                valid_user[field] = value
                
                valid_users.append(valid_user)
            
            if not valid_users:
                return web.json_response({
                    'success': False,
                    'reason': '没有有效的用户数据'
                }, status=400)
            
            # 导入数据到数据库
            result = await self.db.import_users(valid_users)
            
            return web.json_response({
                'success': True,
                'message': f'导入成功：新增{result["imported"]}条，更新{result["updated"]}条，总计{result["total"]}条',
                'result': result
            })
            
        except json.JSONDecodeError:
            return web.json_response({
                'success': False,
                'reason': '无效的JSON数据'
            }, status=400)
        except Exception as e:
            logger.error(f"导入数据失败: {e}")
            return web.json_response({
                'success': False,
                'reason': f'服务器错误: {str(e)}'
            }, status=500)

    async def handle_update_status(self, request):
        user_id = request.match_info['user_id']
        status = int(request.match_info['status'])
        await self.db.update_user_status(user_id, status)
        return web.json_response({'success': True})

    async def handle_delete_user(self, request):
        user_id = request.match_info['user_id']
        
        # 1. 在删除前获取用户信息
        user_info = None
        try:
            user_info = await self.db.get_user(user_id)
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
        
        # 2. 删除用户
        await self.db.delete_user(user_id)
        
        # 3. 发送删除通知
        if user_info and self.plugin:
            try:
                await self.plugin.send_deletion_notification(user_info)
            except Exception as e:
                logger.error(f"发送删除通知失败: {e}")
        
        return web.json_response({'success': True})

    async def handle_delete_all(self, request):
        await self.db.delete_all_users()
        return web.json_response({'success': True})

    async def handle_add_user_manual(self, request):
        """手动添加用户"""
        try:
            # 解析请求数据
            data = await request.json()
            user_id = data.get('user_id')
            tetrio_username = data.get('tetrio_username')
            
            if not user_id or not tetrio_username:
                return web.json_response({
                    'success': False,
                    'reason': '缺少必要参数：user_id 或 tetrio_username'
                }, status=400)
            
            # 导入tetrio_api模块
            from .tetrio_api import check_eligibility
            
            # 调用TETR.IO API获取用户信息
            result = await check_eligibility(tetrio_username)
            
            if not result['success']:
                return web.json_response({
                    'success': False,
                    'reason': result.get('reason', '无法获取TETR.IO用户信息')
                })
            
            # 获取用户信息
            tetrio_id = result['username']
            tr = result['tr']
            rank = result.get('rank', 'z')
            time_40l = result['time_40l']
            
            # 保存到数据库
            await self.db.register_user(
                user_id=user_id,
                league_rating=tr,
                rank=rank,
                sprint_time=time_40l,
                is_registered=1
            )
            
            # 同时更新用户名和tetrio_id
            await self.db.update_user_info(user_id, tetrio_id, tetrio_username)
            
            return web.json_response({
                'success': True,
                'user_id': user_id,
                'tetrio_id': tetrio_id,
                'username': tetrio_username,
                'tr': tr,
                'rank': rank,
                'time_40l': time_40l
            })
            
        except json.JSONDecodeError:
            return web.json_response({
                'success': False,
                'reason': '无效的JSON数据'
            }, status=400)
        except Exception as e:
            logger.error(f"手动添加用户失败: {e}")
            return web.json_response({
                'success': False,
                'reason': f'服务器错误: {str(e)}'
            }, status=500)

    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await self.site.start()
        logger.info(f"TCC Management Panel running at http://localhost:{self.port}")

    async def stop(self):
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
