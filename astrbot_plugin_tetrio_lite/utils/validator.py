"""
参数验证模块
验证用户输入的玩家名等参数
"""

import re


def validate_username(username: str) -> tuple[bool, str]:
    """
    验证玩家名格式
    
    Args:
        username: 玩家用户名
        
    Returns:
        tuple[bool, str]: (是否有效, 错误消息)
    """
    if not username:
        return False, "玩家名不能为空"
    
    if len(username) > 16:
        return False, "玩家名长度不能超过 16 个字符"
    
    # 允许字母、数字、下划线
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "玩家名只能包含字母、数字和下划线"
    
    return True, ""


def normalize_username(username: str) -> str:
    """
    规范化用户名（转小写）
    
    Args:
        username: 玩家用户名
        
    Returns:
        str: 规范化后的用户名
    """
    return username.lower().strip()
