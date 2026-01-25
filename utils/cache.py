"""
缓存管理模块（优化版）
实现智能缓存大小限制和 LRU 清理策略
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class CacheManager:
    """缓存管理器（优化版）"""
    
    def __init__(self, 
                 cache_dir: str, 
                 cache_ttl: int = 300,
                 max_cache_size_mb: int = 200,
                 max_cache_files: int = 500):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录
            cache_ttl: 缓存有效期（秒），默认 5 分钟
            max_cache_size_mb: 缓存最大大小（MB）
            max_cache_files: 缓存最大文件数
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = cache_ttl
        self.max_cache_size_mb = max_cache_size_mb
        self.max_cache_files = max_cache_files
        
        # 清理触发阈值
        self.size_threshold = max_cache_size_mb * 0.9  # 90% 时触发
        self.files_threshold = max_cache_files * 0.9  # 90% 时触发
    
    def get_cached_screenshot(self, username: str, section: str) -> Optional[str]:
        """
        获取缓存的截图
        
        Args:
            username: 玩家用户名
            section: 板块名称
            
        Returns:
            Optional[str]: 缓存文件路径，如果不存在或已过期则返回 None
        """
        # 查找匹配的缓存文件（支持 png 和 jpg）
        patterns = [f"{username}_{section}_*.png", f"{username}_{section}_*.jpg"]
        matching_files = []
        
        for pattern in patterns:
            matching_files.extend(list(self.cache_dir.glob(pattern)))
        
        if not matching_files:
            return None
        
        # 获取最新的缓存文件
        latest_file = max(matching_files, key=lambda p: p.stat().st_mtime)
        
        # 检查是否过期
        if self.is_cache_valid(str(latest_file)):
            logger.debug(f"缓存命中: {latest_file.name}")
            return str(latest_file)
        else:
            # 删除过期文件
            try:
                latest_file.unlink()
                logger.debug(f"删除过期缓存: {latest_file.name}")
            except Exception as e:
                logger.warning(f"删除过期缓存失败: {e}")
            return None
    
    def is_cache_valid(self, filepath: str) -> bool:
        """
        检查缓存是否有效
        
        Args:
            filepath: 缓存文件路径
            
        Returns:
            bool: 是否有效
        """
        if not os.path.exists(filepath):
            return False
        
        file_age = time.time() - os.path.getmtime(filepath)
        return file_age < self.cache_ttl
    
    def get_cache_stats(self) -> dict:
        """
        获取缓存统计信息
        
        Returns:
            dict: 包含文件数量、总大小等信息
        """
        cache_files = list(self.cache_dir.glob("*.png")) + list(self.cache_dir.glob("*.jpg"))
        total_size = sum(f.stat().st_size for f in cache_files)
        total_size_mb = total_size / (1024 * 1024)
        
        return {
            'total_files': len(cache_files),
            'total_size_mb': round(total_size_mb, 2),
            'size_utilization': total_size_mb / self.max_cache_size_mb if self.max_cache_size_mb > 0 else 0,
            'files_utilization': len(cache_files) / self.max_cache_files if self.max_cache_files > 0 else 0
        }
    
    def check_and_cleanup(self):
        """
        检查缓存并在必要时清理
        
        使用 LRU（最近最少使用）策略清理旧文件
        """
        stats = self.get_cache_stats()
        
        # 检查是否需要清理
        need_cleanup = False
        cleanup_reason = []
        
        if stats['total_size_mb'] > self.size_threshold:
            need_cleanup = True
            cleanup_reason.append(f"大小超过阈值 ({stats['total_size_mb']:.2f}/{self.size_threshold:.2f} MB)")
        
        if stats['total_files'] > self.files_threshold:
            need_cleanup = True
            cleanup_reason.append(f"文件数超过阈值 ({stats['total_files']}/{int(self.files_threshold)})")
        
        if need_cleanup:
            logger.info(f"触发缓存清理: {', '.join(cleanup_reason)}")
            self._cleanup_lru()
    
    def _cleanup_lru(self):
        """
        使用 LRU 策略清理缓存
        
        删除最旧的文件直到满足限制条件
        """
        # 获取所有缓存文件
        cache_files = list(self.cache_dir.glob("*.png")) + list(self.cache_dir.glob("*.jpg"))
        
        if not cache_files:
            return
        
        # 按修改时间排序（最旧的在前）
        cache_files.sort(key=lambda p: p.stat().st_mtime)
        
        cleaned_count = 0
        cleaned_size = 0
        
        # 目标：文件数降到 max_cache_files * 0.75，大小降到 max_cache_size_mb * 0.75
        target_files = int(self.max_cache_files * 0.75)
        target_size_mb = self.max_cache_size_mb * 0.75
        
        current_files = len(cache_files)
        current_size_mb = sum(f.stat().st_size for f in cache_files) / (1024 * 1024)
        
        for file_path in cache_files:
            # 检查是否已达到目标
            if current_files <= target_files and current_size_mb <= target_size_mb:
                break
            
            try:
                file_size = file_path.stat().st_size
                file_path.unlink()
                
                cleaned_count += 1
                cleaned_size += file_size
                current_files -= 1
                current_size_mb -= file_size / (1024 * 1024)
                
                logger.debug(f"删除旧缓存: {file_path.name}")
                
            except Exception as e:
                logger.warning(f"删除缓存文件失败 {file_path}: {e}")
        
        if cleaned_count > 0:
            cleaned_size_mb = cleaned_size / (1024 * 1024)
            logger.info(f"LRU 清理完成: 删除 {cleaned_count} 个文件，释放 {cleaned_size_mb:.2f} MB")
            logger.info(f"当前缓存: {current_files} 个文件，{current_size_mb:.2f} MB")
    
    def clean_expired_cache(self):
        """清理过期的缓存文件"""
        try:
            current_time = time.time()
            cleaned_count = 0
            
            cache_files = list(self.cache_dir.glob("*.png")) + list(self.cache_dir.glob("*.jpg"))
            
            for file_path in cache_files:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > self.cache_ttl:
                    try:
                        file_path.unlink()
                        cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"删除过期缓存失败 {file_path}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"清理了 {cleaned_count} 个过期缓存文件")
            
            # 清理过期后，检查是否需要 LRU 清理
            self.check_and_cleanup()
                
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
    
    def clear_all_cache(self):
        """清空所有缓存"""
        try:
            cache_files = list(self.cache_dir.glob("*.png")) + list(self.cache_dir.glob("*.jpg"))
            cleaned_count = 0
            
            for file_path in cache_files:
                try:
                    file_path.unlink()
                    cleaned_count += 1
                except Exception as e:
                    logger.warning(f"删除缓存文件失败 {file_path}: {e}")
            
            logger.info(f"清空缓存完成: 删除 {cleaned_count} 个文件")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            return 0
