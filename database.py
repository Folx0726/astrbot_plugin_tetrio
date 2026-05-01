import aiosqlite
import os
from astrbot.api import logger

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # 创建表（如果不存在）
            await db.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    tetrio_id TEXT,
                    league_rating REAL DEFAULT -1.0,
                    rank TEXT DEFAULT 'z',
                    sprint_time REAL DEFAULT 9999.0,
                    is_registered INTEGER DEFAULT 0
                )
            """)
            await db.commit()
            
            # 检查并添加缺失的列（用于已有数据库的迁移）
            await self._add_missing_columns(db)

    async def _add_missing_columns(self, db):
        """检查并添加缺失的列到现有表"""
        try:
            # 首先检查表是否存在
            async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='registrations'") as cursor:
                table_exists = await cursor.fetchone()
            
            if not table_exists:
                logger.info("表 'registrations' 不存在，无需添加列")
                return
            
            # 获取表的列信息
            async with db.execute("PRAGMA table_info(registrations)") as cursor:
                columns = await cursor.fetchall()
                existing_columns = [col[1] for col in columns]  # col[1] 是列名
            
            logger.info(f"现有列: {existing_columns}")
            
            # 检查并添加缺失的列
            columns_to_add = [
                ("rank", "TEXT DEFAULT 'z'"),
                ("league_rating", "REAL DEFAULT -1.0"),
                ("sprint_time", "REAL DEFAULT 9999.0"),
                ("is_registered", "INTEGER DEFAULT 0")
            ]
            
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    logger.info(f"添加缺失的列: {column_name} {column_type}")
                    await db.execute(f"ALTER TABLE registrations ADD COLUMN {column_name} {column_type}")
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"添加缺失列时出错: {e}")
            raise  # 重新抛出异常，以便调用者知道出了问题
    
    async def _ensure_rank_column(self, db):
        """确保表有rank列（安全修复）"""
        try:
            # 检查表是否存在
            async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='registrations'") as cursor:
                table_exists = await cursor.fetchone()
            
            if not table_exists:
                # 表不存在，创建它
                await db.execute("""
                    CREATE TABLE registrations (
                        user_id TEXT PRIMARY KEY,
                        username TEXT,
                        tetrio_id TEXT,
                        league_rating REAL DEFAULT -1.0,
                        rank TEXT DEFAULT 'z',
                        sprint_time REAL DEFAULT 9999.0,
                        is_registered INTEGER DEFAULT 0
                    )
                """)
                await db.commit()
                logger.info("表 'registrations' 创建成功（包含rank列）")
                return
            
            # 检查是否有rank列
            async with db.execute("PRAGMA table_info(registrations)") as cursor:
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
            
            if 'rank' not in column_names:
                logger.info("添加缺失的 'rank' 列（安全修复）")
                await db.execute("ALTER TABLE registrations ADD COLUMN rank TEXT DEFAULT 'z'")
                await db.commit()
                logger.info("'rank' 列添加成功")
        
        except Exception as e:
            logger.error(f"确保rank列时出错: {e}")
            # 不重新抛出，让调用继续

    async def bind_user(self, user_id: str, tetrio_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            # 确保表有rank列（安全修复）
            await self._ensure_rank_column(db)
            
            # 检查用户是否已绑定
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT tetrio_id FROM registrations WHERE user_id = ?", (user_id,)) as cursor:
                existing_user = await cursor.fetchone()
                
            if existing_user:
                # 用户已绑定，返回当前绑定的账号
                return dict(existing_user)['tetrio_id']
            
            # 用户未绑定，执行绑定
            await db.execute("""
                INSERT OR REPLACE INTO registrations (user_id, tetrio_id)
                VALUES (?, ?)
            """, (user_id, tetrio_id))
            await db.commit()
            return None

    async def get_user(self, user_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM registrations WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def register_user(self, user_id: str, league_rating: float, rank: str, sprint_time: float, is_registered: int = 1):
        async with aiosqlite.connect(self.db_path) as db:
            # 首先确保表有rank列（安全修复）
            await self._ensure_rank_column(db)
            
            # 检查用户是否存在
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT user_id FROM registrations WHERE user_id = ?", (user_id,)) as cursor:
                existing_user = await cursor.fetchone()
            
            if existing_user:
                # 用户存在，执行UPDATE
                await db.execute("""
                    UPDATE registrations 
                    SET league_rating = ?, rank = ?, sprint_time = ?, is_registered = ?
                    WHERE user_id = ?
                """, (league_rating, rank, sprint_time, is_registered, user_id))
            else:
                # 用户不存在，执行INSERT
                await db.execute("""
                    INSERT INTO registrations (user_id, league_rating, rank, sprint_time, is_registered)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, league_rating, rank, sprint_time, is_registered))
            
            await db.commit()

    async def get_all_users(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM registrations") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def update_user_status(self, user_id: str, is_registered: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE registrations SET is_registered = ? WHERE user_id = ?", (is_registered, user_id))
            await db.commit()
    
    async def update_user_info(self, user_id: str, tetrio_id: str, username: str):
        """更新用户的TETR.IO ID和用户名"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE registrations 
                SET tetrio_id = ?, username = ?
                WHERE user_id = ?
            """, (tetrio_id, username, user_id))
            await db.commit()

    async def delete_user(self, user_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM registrations WHERE user_id = ?", (user_id,))
            await db.commit()

    async def delete_all_users(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM registrations")
            await db.commit()

    async def import_users(self, users_data: list):
        """批量导入用户数据
        
        Args:
            users_data: 用户数据列表，每个元素是一个字典，包含以下字段：
                - user_id: 用户ID
                - username: 用户名（可选）
                - tetrio_id: TETR.IO ID（可选）
                - league_rating: TR值（可选）
                - rank: 段位（可选）
                - sprint_time: 40L时间（可选）
                - is_registered: 报名状态（可选）
        """
        if not users_data:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            # 确保表有rank列（安全修复）
            await self._ensure_rank_column(db)
            
            imported_count = 0
            updated_count = 0
            
            for user_data in users_data:
                user_id = user_data.get('user_id')
                if not user_id:
                    logger.warning(f"跳过无效用户数据：缺少user_id字段")
                    continue
                
                # 检查用户是否存在
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT user_id FROM registrations WHERE user_id = ?", (user_id,)) as cursor:
                    existing_user = await cursor.fetchone()
                
                if existing_user:
                    # 用户存在，执行UPDATE
                    # 构建UPDATE语句，只更新提供的字段
                    update_fields = []
                    update_values = []
                    
                    # 检查并添加每个字段
                    field_mapping = {
                        'username': 'username',
                        'tetrio_id': 'tetrio_id',
                        'league_rating': 'league_rating',
                        'rank': 'rank',
                        'sprint_time': 'sprint_time',
                        'is_registered': 'is_registered'
                    }
                    
                    for json_field, db_field in field_mapping.items():
                        if json_field in user_data and user_data[json_field] is not None:
                            update_fields.append(f"{db_field} = ?")
                            update_values.append(user_data[json_field])
                    
                    if update_fields:
                        update_values.append(user_id)  # WHERE条件
                        update_sql = f"UPDATE registrations SET {', '.join(update_fields)} WHERE user_id = ?"
                        await db.execute(update_sql, update_values)
                        updated_count += 1
                else:
                    # 用户不存在，执行INSERT
                    # 使用默认值填充缺失的字段
                    username = user_data.get('username', '')
                    tetrio_id = user_data.get('tetrio_id', '')
                    league_rating = user_data.get('league_rating', -1.0)
                    rank = user_data.get('rank', 'z')
                    sprint_time = user_data.get('sprint_time', 9999.0)
                    is_registered = user_data.get('is_registered', 0)
                    
                    await db.execute("""
                        INSERT INTO registrations 
                        (user_id, username, tetrio_id, league_rating, rank, sprint_time, is_registered)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, username, tetrio_id, league_rating, rank, sprint_time, is_registered))
                    imported_count += 1
            
            await db.commit()
            logger.info(f"批量导入完成：新增{imported_count}条，更新{updated_count}条")
            return {
                "imported": imported_count,
                "updated": updated_count,
                "total": imported_count + updated_count
            }

    async def get_all_registered_users_sorted(self):
        """获取所有已报名用户，并按 league_rating 降序排序"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM registrations 
                WHERE is_registered = 1 
                ORDER BY league_rating DESC
            """) as cursor:
                rows = await cursor.fetchall()
                users = [dict(row) for row in rows]
                
                # 为每个用户添加头像URL
                for user in users:
                    user_id = user['user_id']
                    # 生成QQ头像URL
                    user['avatar_url'] = f"http://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=100&img_type=jpg"
                
                return users

    async def get_stats(self):
        """获取统计数据：绑定玩家数量和报名玩家数量"""
        async with aiosqlite.connect(self.db_path) as db:
            # 统计绑定玩家数量（有 tetrio_id 的用户）
            async with db.execute("SELECT COUNT(*) as bound_count FROM registrations WHERE tetrio_id IS NOT NULL AND tetrio_id != ''") as cursor:
                bound_result = await cursor.fetchone()
                bound_count = bound_result[0] if bound_result else 0
            
            # 统计报名玩家数量（is_registered = 1）
            async with db.execute("SELECT COUNT(*) as registered_count FROM registrations WHERE is_registered = 1") as cursor:
                registered_result = await cursor.fetchone()
                registered_count = registered_result[0] if registered_result else 0
            
            return {
                "bound_count": bound_count,
                "registered_count": registered_count
            }
