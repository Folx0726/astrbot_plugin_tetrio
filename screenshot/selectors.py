"""
TETR.IO 页面元素选择器定义
基于实际 HTML 结构分析的 CSS 选择器常量
"""

# 页面结构选择器
PAGE_CONTAINER = ".columns"
LEFT_SIDEBAR = ".column:first-child"
RIGHT_CONTENT = ".column:last-child"

# 左侧信息栏元素
PROFILE_AVATAR = "#profile_avatar"
USER_TAGS = "#user-tags"
SUPPORTER_TAG = "#supporter-tag"
FEATURED_ACHIEVEMENTS = "#featured-achievements"
PROFILE_BADGES = "#profile_badges"
PROFILE_STATS = "#profile_stats"
PROFILE_CONNECTIONS = "#profile_connections"
PROFILE_OLDUSERNAMES = "#profile_oldusernames"
PROFILE_USERID = "#profile_userid"

# 游戏模式板块选择器
USERCARD_BIO = "#usercard_bio"
USERCARD_NEWS = "#usercard_news"
USERCARD_LEAGUE = "#usercard_league"
USERCARD_ZENITH = "#usercard_zenith"
USERCARD_40L = "#usercard_40l"
USERCARD_BLITZ = "#usercard_blitz"
USERCARD_ACHIEVEMENTS = "#usercard_achievements"
USERCARD_ZEN = "#usercard_zen"

# 页面状态元素
LOADER = "#loader"
ERROR = "#error"
ERROR_TITLE = "#error_title"

# 特殊状态标识
USER_ISANON = "#user_isanon"
USER_BANNED = "#user_banned"
USER_HIDDEN = "#user_hidden"
USER_ISBOT = "#user_isbot"

# "Never played" 标识
USER_LEAGUE_NP = "#user_league_np"
USER_ZENITH_NP = "#user_zenith_np"
USER_40L_NP = "#user_40l_np"
USER_BLITZ_NP = "#user_blitz_np"
USER_ZEN_NP = "#user_zen_np"
USER_ACHIEVEMENTS_NP = "#user_achievements_np"

# 板块映射字典
SECTION_SELECTORS = {
    "profile": LEFT_SIDEBAR,
    "league": USERCARD_LEAGUE,
    "40l": USERCARD_40L,
    "blitz": USERCARD_BLITZ,
    "qp": USERCARD_ZENITH,
    "zen": USERCARD_ZEN,
    "achievements": USERCARD_ACHIEVEMENTS,
    "about": USERCARD_BIO,
    "news": USERCARD_NEWS,
}

# 板块名称映射
SECTION_NAMES = {
    "profile": "玩家信息",
    "league": "TETRA LEAGUE",
    "40l": "40 LINES",
    "blitz": "BLITZ",
    "qp": "QUICK PLAY",
    "zen": "ZEN",
    "achievements": "成就",
    "about": "关于我",
    "news": "最新动态",
}
