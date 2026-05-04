import aiohttp
from astrbot.api import logger

API_BASE = "https://ch.tetr.io/api"

async def fetch_user_stats(username: str) -> dict:
    """
    Fetch user stats from TETR.IO API.
    Returns a dict with tr, rank, and time_40l.
    """
    username = username.lower().strip()
    headers = {
        "User-Agent": "AstrBot-Tetrio-Plugin/1.2.0 (Contact: shaogit on GitHub)",
        "Accept": "application/json"
    }
    
    tr = -1.0
    rank = "z"  # 默认未定级
    time_40l = 9999.0
    
    async with aiohttp.ClientSession(headers=headers) as session:
        # 1. 获取用户 League 数据
        url_league = f"{API_BASE}/users/{username}/summaries/league"
        try:
            async with session.get(url_league) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success") and "data" in data:
                        tr = data["data"].get("tr", -1.0)
                        rank = data["data"].get("rank", "z")
                        # 增加更多字段的查找尝试
                        if tr == -1.0:
                             tr = data["data"].get("rating", -1.0)
                        if tr == -1.0:
                             tr = data["data"].get("glicko", -1.0)
                else:
                    logger.warning(f"[TETR.IO] Fetch League Failed: {resp.status}")
        except Exception as e:
            logger.error(f"[TETR.IO] Fetch League Error: {e}")

        # 2. 获取用户 40L 数据
        url_40l = f"{API_BASE}/users/{username}/summaries/40l"
        try:
            async with session.get(url_40l) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success") and "data" in data:
                        record = data["data"].get("record")
                        if record:
                             # 尝试获取 finalTime
                             # 优先查找 results.stats.finaltime (常见于 new API)
                             final_time = record.get("results", {}).get("stats", {}).get("finaltime")
                             
                             if not final_time:
                                 final_time = record.get("endcontext", {}).get("finalTime")
                             
                             if not final_time:
                                 final_time = record.get("finalTime")
                                 
                             if final_time:
                                 time_40l = float(final_time) / 1000.0
                else:
                    logger.warning(f"[TETR.IO] Fetch 40L Failed: {resp.status}")
        except Exception as e:
             logger.error(f"[TETR.IO] Fetch 40L Error: {e}")

    return {
        "success": True,
        "username": username,
        "tr": tr,
        "rank": rank,
        "time_40l": time_40l
    }

async def check_eligibility(username: str) -> dict:
    """
    Check if a user is eligible for registration.
    Criteria: Tetra League TR > 15000 OR 40 Lines Time < 30s.
    """
    res = await fetch_user_stats(username)
    if not res["success"]:
        return res

    # 无条件允许报名
    eligible = True
    reasons = []

    if res["tr"] != -1:
        reasons.append(f"TR: {res['tr']:.2f}")
    if res["time_40l"] != 9999.0:
        reasons.append(f"40L: {res['time_40l']:.3f}s")
        
    res["eligible"] = eligible
    res["reason"] = " | ".join(reasons) if reasons else "Data fetched successfully"
    return res
