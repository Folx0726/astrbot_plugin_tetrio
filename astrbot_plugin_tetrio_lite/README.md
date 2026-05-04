# AstrBot TETR.IO 查询插件

通过网页截图查询 TETR.IO 玩家信息并以图片形式返回。

## 功能特性

- 📸 直接截取 TETR.IO 官方网页，保留精美样式
- 🎮 支持多种游戏模式查询（TETRA LEAGUE、40 LINES、BLITZ、QUICK PLAY、ZEN、成就等）
- 🔗 账号绑定系统，支持绑定后免输入查询
- 📋 用户管理后台（Web 面板），支持添加、激活、导入导出用户数据
- 💾 智能缓存机制，提高响应速度
- 🚀 异步处理，不阻塞其他操作

## 安装

1. 将插件文件夹复制到 AstrBot 的 `data/plugins/` 目录
2. 插件会自动安装依赖（Playwright）
3. 首次使用时会自动下载 Chromium 浏览器

## 使用方法

### 指令格式

```
/tetrio <子指令> [玩家名]
```

不提供玩家名时，将自动查询已绑定的账号。

### 查询指令

| 指令 | 别名 | 功能 |
| --- | --- | --- |
| `full` | - | 截取完整页面 |
| `profile` | `个人信息` | 截取左侧信息栏 |
| `league` | `排位`, `段位` | 截取 TETRA LEAGUE 板块 |
| `40l` | `40行`, `竞速` | 截取 40 LINES 板块 |
| `blitz` | `击块`, `闪电战` | 截取 BLITZ 板块 |
| `zen` | `禅模式` | 截取 ZEN 板块 |
| `achievements` | `成就` | 截取成就板块 |
| `ranklist` | `排行榜` | 截取 TETR.IO League 排行榜页面 |

### 账号指令

| 指令 | 别名 | 功能 |
| --- | --- | --- |
| `bind` | `绑定` | 绑定 TETR.IO 账号（截图确认后回复"是"完成） |

绑定后查询指令可不填玩家名，自动查询绑定账号。

### 管理指令

| 指令 | 功能 |
| --- | --- |
| `update_all` | 后台更新所有已激活用户数据 |

### Web 管理后台

插件启动后会在 `http://localhost:8081` 提供管理面板，支持：

- 查看用户列表及排名
- 手动添加用户（输入 QQ 号和 TETR.IO 用户名自动拉取数据）
- 激活/停用用户状态
- 导入/导出 JSON 数据
- 批量重置状态、清空数据

## 配置项

可在 AstrBot 管理面板中配置以下选项：

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `browser_headless` | bool | true | 是否使用无头浏览器模式 |
| `browser_timeout` | int | 30 | 浏览器操作超时时间（秒） |
| `viewport_width` | int | 2560 | 浏览器视口宽度 |
| `viewport_height` | int | 1440 | 浏览器视口高度 |
| `cache_enabled` | bool | true | 是否启用截图缓存 |
| `cache_ttl` | int | 300 | 缓存有效期（秒） |
| `context_pool_size` | int | 2 | 浏览器上下文池初始大小 |
| `max_pool_size` | int | 3 | 上下文池最大大小 |
| `screenshot_format` | string | "png" | 截图格式 |
| `screenshot_quality` | int | 85 | 截图质量（仅 webp） |
| `memory_limit_mb` | int | 512 | 浏览器内存限制（MB） |
| `max_cache_size_mb` | int | 200 | 缓存最大大小（MB） |
| `max_cache_files` | int | 500 | 缓存最大文件数 |
| `max_concurrent_tasks` | int | 5 | 最大并发截图任务数 |
| `page_zoom_full` | float | 0.9 | 完整页面缩放级别 |
| `page_zoom_section` | float | 1.0 | 板块截图缩放级别 |
| `notification_group_ids` | list | [] | 删除通知群聊 ID 列表 |

## 系统要求

- Python 3.8+
- AstrBot v3.4+
- 足够的磁盘空间（用于 Chromium 浏览器和缓存）

## 注意事项

1. 首次使用需要等待浏览器下载，可能需要几分钟
2. 截图操作需要一定时间，请耐心等待
3. 建议在服务器环境下使用无头模式
4. 缓存会占用磁盘空间，插件会自动清理过期缓存

## 项目结构

```
├── main.py                  # 插件主入口，指令定义
├── database.py              # SQLite 数据库操作
├── tetrio_api.py            # TETR.IO API 接口
├── web_server.py            # Web 管理后台
├── screenshot/
│   ├── browser.py           # 浏览器管理器
│   ├── capturer.py          # 截图执行器
│   ├── selectors.py         # 页面元素选择器
│   └── context_pool.py      # 浏览器上下文池
├── utils/
│   ├── cache.py             # 缓存管理
│   ├── validator.py         # 参数验证
│   └── concurrency.py       # 并发控制
├── templates/
│   └── index.html           # 管理后台页面
├── rank/                    # 段位图片资源
├── _conf_schema.json        # 配置定义
└── metadata.yaml            # 插件元数据
```

## 作者

**Folx**

## 许可证

MIT License

## 反馈

如遇到问题或有建议，请访问：<https://github.com/Folx0726/astrbot_plugin_tetrio>
