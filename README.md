# AstrBot TETR.IO 查询插件

通过网页截图查询 TETR.IO 玩家信息并以图片形式返回。

## 功能特性

- 📸 直接截取 TETR.IO 官方网页，保留精美样式
- 🎮 支持多种游戏模式查询（TETRA LEAGUE、40 LINES、BLITZ、QUICK PLAY、ZEN等）
- 💾 智能缓存机制，提高响应速度
- 🚀 异步处理，不阻塞其他操作

## 安装

1. 将插件文件夹复制到 AstrBot 的 `data/plugins/` 目录
2. 插件会自动安装依赖（Playwright）
3. 首次使用时会自动下载 Chromium 浏览器

## 使用方法

### 指令格式

```
/tetrio <子指令> <玩家名>
```

### 支持的子指令

| 指令 | 功能 | 示例 |
|------|------|------|
| `full` | 截取完整页面 | `/tetrio full folx` |
| `profile` | 截取左侧信息栏 | `/tetrio profile folx` |
| `league` | 截取 TETRA LEAGUE 板块 | `/tetrio league folx` |
| `40l` | 截取 40 LINES 板块 | `/tetrio 40l folx` |
| `blitz` | 截取 BLITZ 板块 | `/tetrio blitz folx` |
| `qp` | 截取 QUICK PLAY 板块 | `/tetrio qp folx` |
| `zen` | 截取 ZEN 板块 | `/tetrio zen folx` |
| `achievements` | 截取成就板块 | `/tetrio achievements folx` |
| `about` | 截取个人简介 | `/tetrio about folx` |
| `news` | 截取最新动态 | `/tetrio news folx` |

## 配置项

可在 AstrBot 管理面板中配置以下选项：

- **browser_headless**: 是否使用无头浏览器模式（默认：true）
- **browser_timeout**: 浏览器操作超时时间（默认：30秒）
- **viewport_width**: 浏览器视口宽度（默认：1920）
- **viewport_height**: 浏览器视口高度（默认：1080）
- **cache_enabled**: 是否启用缓存（默认：true）
- **cache_ttl**: 缓存有效期（默认：300秒）

## 系统要求

- Python 3.8+
- AstrBot v3.4+
- 足够的磁盘空间（用于 Chromium 浏览器和缓存）

## 注意事项

1. 首次使用需要等待浏览器下载，可能需要几分钟
2. 截图操作需要一定时间，请耐心等待
3. 建议在服务器环境下使用无头模式
4. 缓存会占用磁盘空间，插件会自动清理过期缓存

## 作者

**shaogit**

## 许可证

MIT License

## 反馈

如遇到问题或有建议，请访问：https://github.com/shaogit/astrbot_plugin_tetrio
# AstrBot TETR.IO 查询插件

通过网页截图查询 TETR.IO 玩家信息并以图片形式返回。

## 功能特性

- 📸 直接截取 TETR.IO 官方网页，保留精美样式
- 🎮 支持多种游戏模式查询（TETRA LEAGUE、40 LINES、BLITZ、QUICK PLAY、ZEN等）
- 💾 智能缓存机制，提高响应速度
- 🚀 异步处理，不阻塞其他操作

## 安装

1. 将插件文件夹复制到 AstrBot 的 `data/plugins/` 目录
2. 插件会自动安装依赖（Playwright）
3. 首次使用时会自动下载 Chromium 浏览器

## 使用方法

### 指令格式

```
/tetrio <子指令> <玩家名>
```

### 支持的子指令

| 指令 | 功能 | 示例 |
|------|------|------|
| `full` | 截取完整页面 | `/tetrio full folx` |
| `profile` | 截取左侧信息栏 | `/tetrio profile folx` |
| `league` | 截取 TETRA LEAGUE 板块 | `/tetrio league folx` |
| `40l` | 截取 40 LINES 板块 | `/tetrio 40l folx` |
| `blitz` | 截取 BLITZ 板块 | `/tetrio blitz folx` |
| `qp` | 截取 QUICK PLAY 板块 | `/tetrio qp folx` |
| `zen` | 截取 ZEN 板块 | `/tetrio zen folx` |
| `achievements` | 截取成就板块 | `/tetrio achievements folx` |
| `about` | 截取个人简介 | `/tetrio about folx` |
| `news` | 截取最新动态 | `/tetrio news folx` |

## 配置项

可在 AstrBot 管理面板中配置以下选项：

- **browser_headless**: 是否使用无头浏览器模式（默认：true）
- **browser_timeout**: 浏览器操作超时时间（默认：30秒）
- **viewport_width**: 浏览器视口宽度（默认：1920）
- **viewport_height**: 浏览器视口高度（默认：1080）
- **cache_enabled**: 是否启用缓存（默认：true）
- **cache_ttl**: 缓存有效期（默认：300秒）

## 系统要求

- Python 3.8+
- AstrBot v3.4+
- 足够的磁盘空间（用于 Chromium 浏览器和缓存）

## 注意事项

1. 首次使用需要等待浏览器下载，可能需要几分钟
2. 截图操作需要一定时间，请耐心等待
3. 建议在服务器环境下使用无头模式
4. 缓存会占用磁盘空间，插件会自动清理过期缓存

## 作者

**shaogit**

## 许可证

MIT License

## 反馈

如遇到问题或有建议，请访问：https://github.com/shaogit/astrbot_plugin_tetrio
