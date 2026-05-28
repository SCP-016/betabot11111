# Telegram 媒体分类机器人

简约好用的 Telegram 媒体管理机器人，支持文件夹管理、媒体分类存储，数据持久化到 **Turso**（libSQL 云数据库），部署在 **Render Web Service**。

---

## 功能

| 功能 | 说明 |
|------|------|
| 📁 创建文件夹 | 按名称新建分类文件夹 |
| ✏️ 重命名文件夹 | 随时修改文件夹名称 |
| 🗑 删除文件夹 | 含二次确认，防止误触 |
| 📥 媒体入库 | 发送/转发图片、视频、文件、音频、GIF，选择目标文件夹存入 |
| 📋 查看媒体 | 打开文件夹查看所有媒体列表 |
| 🗑 删除媒体 | 含二次确认，防止误触 |

---

## 部署步骤

### 第一步：创建 Telegram Bot

1. 在 Telegram 中找 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`，按提示操作
3. 记录下 **Bot Token**

### 第二步：创建 Turso 数据库

```bash
# 安装 Turso CLI
curl -sSfL https://get.tur.so/install.sh | bash

# 登录
turso auth login

# 创建数据库
turso db create media-bot-db

# 获取数据库 URL
turso db show media-bot-db --url

# 创建 Auth Token
turso db tokens create media-bot-db
```

记录 `TURSO_DATABASE_URL`（格式：`libsql://xxx.turso.io`）和 `TURSO_AUTH_TOKEN`。

### 第三步：部署到 Render

1. 将本项目推送到 GitHub
2. 登录 [Render](https://render.com)，点击 **New → Web Service**
3. 连接你的 GitHub 仓库
4. 配置如下：
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
5. 在 **Environment Variables** 中填入：

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | BotFather 给的 Token |
| `TURSO_DATABASE_URL` | `libsql://xxx.turso.io` |
| `TURSO_AUTH_TOKEN` | Turso 生成的 token |
| `WEBHOOK_URL` | `https://你的服务名.onrender.com` |
| `PORT` | `10000` |

6. 点击 **Deploy**，等待部署完成。

> **WEBHOOK_URL** 填写 Render 分配给你的域名，格式为 `https://tg-media-bot.onrender.com`（不带末尾斜杠）。

### 第四步：验证

打开 Telegram，向你的 Bot 发送 `/start`，看到主菜单即部署成功 ✅

---

## 本地调试

```bash
# 安装依赖
pip install -r requirements.txt

# 本地不设 WEBHOOK_URL，自动走 polling 模式
export BOT_TOKEN=xxx
export TURSO_DATABASE_URL=libsql://xxx.turso.io
export TURSO_AUTH_TOKEN=xxx

python bot.py
```

---

## 项目结构

```
tg-media-bot/
├── bot.py           # 主逻辑：命令、回调、会话处理
├── database.py      # Turso 数据库操作封装
├── requirements.txt
├── render.yaml      # Render 一键部署配置
└── README.md
```

---

## 数据库表结构

```sql
users   (id)
folders (id, user_id, name)
medias  (id, folder_id, file_id, media_type, caption, created_at)
```
