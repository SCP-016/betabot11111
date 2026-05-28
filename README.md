# 📁 Telegram 媒体管理机器人

用 Telegram 机器人对图片和视频进行文件夹分类管理。  
**媒体源文件不保存在云端** — 只存储 Telegram 的 `file_id` 引用。

---

## ✨ 功能

| 功能 | 说明 |
|------|------|
| 📥 接收媒体 | 转发或发送图片/视频，机器人询问存入哪个文件夹 |
| 📁 文件夹管理 | 新建 / 重命名 / 删除文件夹 |
| 🗑️ 删除媒体 | 在文件夹预览页逐条删除 |
| 📤 发送全部 | 一键将文件夹内所有媒体重新发送给你 |
| 📄 分页浏览 | 文件夹内容分页展示，每页 5 条 |

---

## 🚀 快速部署到 Render

### 1. 创建 Telegram Bot

1. 在 Telegram 找 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`，按提示填写名称
3. 保存返回的 **Bot Token**（格式：`123456:ABCdef...`）

### 2. 上传代码到 GitHub

```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/你的用户名/tg-media-bot.git
git push -u origin main
```

### 3. 在 Render 部署

1. 登录 [render.com](https://render.com) → **New → Background Worker**
2. 连接你的 GitHub 仓库
3. 设置如下：

   | 字段 | 值 |
   |------|----|
   | Environment | Python 3 |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `python bot.py` |

4. 在 **Environment Variables** 添加：

   | Key | Value |
   |-----|-------|
   | `BOT_TOKEN` | 你的 Bot Token |
   | `DB_PATH` | `/var/data/media_bot.db` |

5. 在 **Disks** 添加持久化磁盘：
   - Mount Path: `/var/data`
   - Size: 1 GB

   > ⚠️ 持久化磁盘需要 Render **Starter** 计划（$7/月）。  
   > 免费计划每次重启会丢失数据库，如果只是测试可先省略磁盘。

6. 点击 **Create Worker** 即可！

---

## 💬 使用方法

| 操作 | 方式 |
|------|------|
| 打开主菜单 | 发送 `/start` 或 `/menu` |
| 分类媒体 | 直接发送/转发图片或视频 |
| 新建文件夹 | 主菜单 → ➕ 新建文件夹 |
| 重命名 | 主菜单 → ✏️ 重命名 |
| 删除文件夹 | 主菜单 → 🗑️ 删除文件夹 |
| 查看内容 | 主菜单 → 📁 查看所有文件夹 → 点击文件夹 |
| 删除单条 | 文件夹详情页 → 点击对应的 🗑️ |
| 取消当前操作 | 发送 `/cancel` |

---

## 🗂️ 项目结构

```
tg-media-bot/
├── bot.py          # 机器人主逻辑
├── database.py     # SQLite 数据库封装
├── requirements.txt
├── render.yaml     # Render 部署配置（可选）
└── README.md
```

---

## 🔒 隐私说明

- 机器人**只保存** Telegram 内部的 `file_id`，不下载也不上传任何媒体文件
- 所有数据存储在部署服务器的本地 SQLite 数据库中
