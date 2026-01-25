"""
并发控制和重试机制模块
提供信号量控制和智能重试功能
"""

import asyncio
import time
import logging
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class ConcurrencyController:
    """并发控制器"""
    
    def __init__(self, max_concurrent: int = 5):
        """
        初始化并发控制器
        
        Args:
            max_concurrent: 最大并发任务数
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.active_tasks = 0
        self.total_tasks = 0
        self.lock = asyncio.Lock()
    
    async def acquire(self, timeout: int = 30) -> bool:
        """
        获取并发许可
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否成功获取
        """
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=timeout)
            async with self.lock:
                self.active_tasks += 1
                self.total_tasks += 1
            return True
        except asyncio.TimeoutError:
            logger.warning(f"获取并发许可超时（最大并发: {self.max_concurrent}）")
            return False
    
    async def release(self):
        """释放并发许可"""
        self.semaphore.release()
        async with self.lock:
            self.active_tasks -= 1
    
    def get_stats(self) -> dict:
        """获取并发统计信息"""
        return {
            'max_concurrent': self.max_concurrent,
            'active_tasks': self.active_tasks,
            'total_tasks': self.total_tasks,
            'utilization': self.active_tasks / self.max_concurrent if self.max_concurrent > 0 else 0
        }


class RetryStrategy:
    """重试策略"""
    
    @staticmethod
    async def with_retry(
        func: Callable,
        *args,
        max_retries: int = 2,
        base_delay: float = 1.0,
        exponential_backoff: bool = True,
        retryable_exceptions: tuple = (Exception,),
        **kwargs
    ) -> Any:
        """
        带重试的函数执行
        
        Args:
            func: 要执行的异步函数
            *args: 函数参数
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
            exponential_backoff: 是否使用指数退避
            retryable_exceptions: 可重试的异常类型
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            最后一次执行的异常
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"第 {attempt} 次重试...")
                
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"重试成功（尝试次数: {attempt + 1}）")
                
                return result
                
            except retryable_exceptions as e:
                last_exception = e
                
                if attempt < max_retries:
                    # 计算延迟时间
                    if exponential_backoff:
                        delay = base_delay * (2 ** attempt)
                    else:
                        delay = base_delay
                    
                    logger.warning(f"执行失败: {str(e)}，{delay:.1f} 秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"达到最大重试次数 ({max_retries})，执行失败: {str(e)}")
        
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("未知错误")


def with_concurrency_control(controller: ConcurrencyController, timeout: int = 30):
    """
    并发控制装饰器
    
    Args:
        controller: 并发控制器实例
        timeout: 获取许可的超时时间
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取并发许可
            if not await controller.acquire(timeout):
                raise RuntimeError(f"并发控制：获取许可超时（{timeout}秒）")
            
            try:
                # 执行函数
                result = await func(*args, **kwargs)
                return result
            finally:
                # 释放许可
                await controller.release()
        
        return wrapper
    return decorator


def with_retry(
    max_retries: int = 2,
    base_delay: float = 1.0,
    exponential_backoff: bool = True,
    retryable_exceptions: tuple = (Exception,)
):
    """
    重试装饰器
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        exponential_backoff: 是否使用指数退避
        retryable_exceptions: 可重试的异常类型
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await RetryStrategy.with_retry(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                exponential_backoff=exponential_backoff,
                retryable_exceptions=retryable_exceptions,
                **kwargs
            )
        return wrapper
    return decorator


# 预定义的重试策略

# 网络超时重试（2次，指数退避）
def with_network_retry(func: Callable):
    """网络超时重试装饰器"""
    return with_retry(
        max_retries=2,
        base_delay=1.0,
        exponential_backoff=True,
        retryable_exceptions=(asyncio.TimeoutError, ConnectionError)
    )(func)


# 元素查找重试（1次，固定延迟）
def with_element_retry(func: Callable):
    """元素查找重试装饰器"""
    return with_retry(
        max_retries=1,
        base_delay=2.0,
        exponential_backoff=False,
        retryable_exceptions=(Exception,)
    )(func)


# 浏览器崩溃重试（1次，较长延迟）
def with_browser_retry(func: Callable):
    """浏览器崩溃重试装饰器"""
    return with_retry(
        max_retries=1,
        base_delay=5.0,
        exponential_backoff=False,
        retryable_exceptions=(Exception,)
    )(func)
"""
并发控制和重试机制模块
提供信号量控制和智能重试功能
"""

import asyncio
import time
import logging
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class ConcurrencyController:
    """并发控制器"""
    
    def __init__(self, max_concurrent: int = 5):
        """
        初始化并发控制器
        
        Args:
            max_concurrent: 最大并发任务数
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.active_tasks = 0
        self.total_tasks = 0
        self.lock = asyncio.Lock()
    
    async def acquire(self, timeout: int = 30) -> bool:
        """
        获取并发许可
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否成功获取
        """
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=timeout)
            async with self.lock:
                self.active_tasks += 1
                self.total_tasks += 1
            return True
        except asyncio.TimeoutError:
            logger.warning(f"获取并发许可超时（最大并发: {self.max_concurrent}）")
            return False
    
    async def release(self):
        """释放并发许可"""
        self.semaphore.release()
        async with self.lock:
            self.active_tasks -= 1
    
    def get_stats(self) -> dict:
        """获取并发统计信息"""
        return {
            'max_concurrent': self.max_concurrent,
            'active_tasks': self.active_tasks,
            'total_tasks': self.total_tasks,
            'utilization': self.active_tasks / self.max_concurrent if self.max_concurrent > 0 else 0
        }


class RetryStrategy:
    """重试策略"""
    
    @staticmethod
    async def with_retry(
        func: Callable,
        *args,
        max_retries: int = 2,
        base_delay: float = 1.0,
        exponential_backoff: bool = True,
        retryable_exceptions: tuple = (Exception,),
        **kwargs
    ) -> Any:
        """
        带重试的函数执行
        
        Args:
            func: 要执行的异步函数
            *args: 函数参数
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
            exponential_backoff: 是否使用指数退避
            retryable_exceptions: 可重试的异常类型
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            最后一次执行的异常
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"第 {attempt} 次重试...")
                
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"重试成功（尝试次数: {attempt + 1}）")
                
                return result
                
            except retryable_exceptions as e:
                last_exception = e
                
                if attempt < max_retries:
                    # 计算延迟时间
                    if exponential_backoff:
                        delay = base_delay * (2 ** attempt)
                    else:
                        delay = base_delay
                    
                    logger.warning(f"执行失败: {str(e)}，{delay:.1f} 秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"达到最大重试次数 ({max_retries})，执行失败: {str(e)}")
        
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("未知错误")


def with_concurrency_control(controller: ConcurrencyController, timeout: int = 30):
    """
    并发控制装饰器
    
    Args:
        controller: 并发控制器实例
        timeout: 获取许可的超时时间
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取并发许可
            if not await controller.acquire(timeout):
                raise RuntimeError(f"并发控制：获取许可超时（{timeout}秒）")
            
            try:
                # 执行函数
                result = await func(*args, **kwargs)
                return result
            finally:
                # 释放许可
                await controller.release()
        
        return wrapper
    return decorator


def with_retry(
    max_retries: int = 2,
    base_delay: float = 1.0,
    exponential_backoff: bool = True,
    retryable_exceptions: tuple = (Exception,)
):
    """
    重试装饰器
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        exponential_backoff: 是否使用指数退避
        retryable_exceptions: 可重试的异常类型
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await RetryStrategy.with_retry(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                exponential_backoff=exponential_backoff,
                retryable_exceptions=retryable_exceptions,
                **kwargs
            )
        return wrapper
    return decorator


# 预定义的重试策略

# 网络超时重试（2次，指数退避）
def with_network_retry(func: Callable):
    """网络超时重试装饰器"""
    return with_retry(
        max_retries=2,
        base_delay=1.0,
        exponential_backoff=True,
        retryable_exceptions=(asyncio.TimeoutError, ConnectionError)
    )(func)


# 元素查找重试（1次，固定延迟）
def with_element_retry(func: Callable):
    """元素查找重试装饰器"""
    return with_retry(
        max_retries=1,
        base_delay=2.0,
        exponential_backoff=False,
        retryable_exceptions=(Exception,)
    )(func)


# 浏览器崩溃重试（1次，较长延迟）
def with_browser_retry(func: Callable):
    """浏览器崩溃重试装饰器"""
    return with_retry(
        max_retries=1,
        base_delay=5.0,
        exponential_backoff=False,
        retryable_exceptions=(Exception,)
    )(func)
