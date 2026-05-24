# Claude Manager

Claude Code 托管代理管理后台，支持多用户、多项目、实时状态监控与交互。

## 功能特性

- **多用户管理** — 支持多个用户，每个用户独立管理自己的项目
- **多项目支持** — 每个用户下可创建多个项目（对话会话），实时追踪状态
- **实时交互** — 支持发送消息、重试失败会话、查看完整日志
- **像素风头像** — 33 个用户头像 + 100 个会话头像，全部 8x8 像素画
- **消息预览** — 支持回复预览和一键复制
- **确认弹窗** — 删除操作需二次确认
- **Toast 通知** — 操作成功/失败即时反馈

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+ / npm
- uv（可选，初始化脚本会自动安装）

### 一键安装

```bash
# 1. 初始化（安装依赖、生成头像、构建前端）
bash init.sh

# 2. 启动服务
bash start.sh

# 3. 访问
#    前端: http://localhost:3112
#    后端: http://localhost:8112
```

### 手动安装

```bash
# 后端
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn httpx loguru

# 生成头像
python backend/generate_avatars.py

# 启动后端
uvicorn backend.main:app --host 0.0.0.0 --port 8112

# 前端（另一个终端）
cd frontend
npm install
npx vite --host 0.0.0.0 --port 3112
```

### 重启 / 停止

```bash
# 重启（自动清理旧进程）
bash start.sh

# 查看 PID
ls tmp/*.pid

# 手动停止
kill -9 $(cat tmp/claude_manager_backend.pid)
kill -9 $(cat tmp/claude_manager_frontend.pid)
```

## 使用指南

### 创建项目

1. 左侧面板顶部选择或输入 **User**
2. 选择或输入 **Project**（项目目录路径）
3. 输入消息内容
4. 点击发送按钮即可创建新项目

### 管理项目

- **查看详情** — 左键点击右侧项目卡片，打开详情弹窗
- **重试** — 失败的项目可以点击重试恢复
- **查看日志** — 弹窗底部「日志」按钮查看完整对话日志
- **删除** — 支持单个项目删除和用户级删除（连同该用户所有项目）
- **复制** — 支持复制用户消息和 AI 回复内容
- **回复预览** — 完成的 AI 回复可一键预览完整内容

### 头像管理

```bash
# 重新生成头像（修改模板后）
python backend/generate_avatars.py
```

头像存储在 `backend/static/avatars/` 目录，通过后端 API `/avatar/{type}/{id}.png` 访问。

- **用户头像** — 33 个（A-Z + * + 0-6），像素画风格（幽灵、表情、符号等）
- **会话头像** — 100 个，16 种配色交替使用

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + uvicorn + SQLite |
| 前端 | Vue 3 + Vite |
| 头像 | 8x8 像素画生成（Python） |

## 目录结构

```
├── backend/                  # FastAPI 后端
│   ├── api/                  # API 路由
│   │   ├── claude.py         # Claude 代理交互（发送、重试、日志）
│   │   └── database.py       # 数据管理 API（CRUD）
│   ├── main.py               # 应用入口
│   ├── db.py                 # 数据库模型
│   ├── generate_avatars.py   # 头像生成脚本（33 用户 + 100 会话）
│   ├── pyproject.toml        # Python 依赖
│   └── static/avatars/       # 生成的头像文件
│       ├── user/             # 用户头像 (33个)
│       └── session/          # 会话头像 (100个)
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── components/       # Vue 组件
│   │   │   ├── SendForm.vue        # 发送表单
│   │   │   ├── ProjectCard.vue     # 项目缩略卡片
│   │   │   ├── ProjectGrid.vue     # 项目网格
│   │   │   ├── SelectedCard.vue    # 选中项概览
│   │   │   ├── DetailModal.vue     # 详情弹窗
│   │   │   ├── LogModal.vue        # 日志弹窗
│   │   │   ├── ConfirmDialog.vue   # 确认弹窗
│   │   │   ├── ReplyPreviewModal.vue # 回复预览
│   │   │   └── Toast.vue           # 提示框
│   │   ├── utils/
│   │   │   └── avatar.js     # 头像路径工具
│   │   └── App.vue           # 主布局
│   ├── vite.config.js        # Vite 配置（含 API 代理）
│   └── package.json
├── data/                     # 数据库文件
│   └── claude_manager.db     # SQLite 数据库
├── log/                      # 运行日志（server.log, error.log）
├── tmp/                      # PID 文件（自动生成）
├── init.sh                   # 一键初始化
├── start.sh                  # 一键启动
├── README.md                 # 本文件
└── PLAN.md                   # 完整设计文档
```

## 数据库

使用 SQLite 存储数据，数据库文件位于 `data/claude_manager.db`。

### 表结构

- **user** — 用户信息（user_id、name、user_avatar_id、created_at、updated_at）
- **project** — 项目信息（project_id、user_id、folder_name、claude_path、session_id、user_input、is_finished、status、claude_result、claude_output、session_avatar_id、total_tokens、retries、created_at、updated_at）

### 备份

```bash
cp data/claude_manager.db data/claude_manager.db.bak
```

## API 接口

### 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /health | 健康检查 |
| GET | /avatar/{type}/{id}.png | 头像图片（user/session） |
| GET/POST | /api/users | 用户列表 / 创建用户 |
| DELETE | /api/users/{id} | 删除用户（含其所有项目） |
| GET/POST | /api/projects | 项目列表 / 创建项目 |
| DELETE | /api/projects/{id} | 删除项目 |
| POST | /api/claude | 发送消息（异步执行） |
| GET | /api/retry/{id} | 重试项目 |
| GET | /api/claude-log/{id} | 获取对话日志 |
| POST | /api/continue/{id} | 继续对话 |

### 数据格式

所有接口返回统一 JSON 格式：

```json
{ "success": true, "code": 200, "detail": { ... } }
```

失败时：

```json
{ "success": false, "code": 400, "detail": { "error": "错误信息" } }
```

## 前端交互

### 布局

```
┌──────────────────────────────────────────────┐
│  ⬡ Claude Manager                            │
├────────────────┬─────────────────────────────┤
│  左侧面板 (320px) │       右侧面板             │
├────────────────┼─────────────────────────────┤
│  顶部：发送表单   │  项目网格                    │
│  - User ▼       │  [缩略卡片1] [缩略卡片2] ...  │
│  - Project ▼    │                              │
│  - Message       │                              │
│  - 发送 ▶        │                              │
├────────────────┼─────────────────────────────┤
│  底部：选中项目详情 │                              │
│  [Avatar] 状态    │                              │
│  路径 / Message   │                              │
│  [详情] [日志] [重试] [删除] │                              │
└────────────────┴─────────────────────────────┘
```

### 交互规则

- **左键点击**右侧卡片 → 打开详情弹窗（不改变左侧面板）
- **右键点击**右侧卡片 → 同步左侧面板（User + Project）
- 左侧面板卡片操作：详情/日志/重试/删除

## 配置

### 端口

- 后端: `8112`（修改 `start.sh` 中的 `uvicorn` 参数）
- 前端: `3112`（修改 `start.sh` 中 `vite --port` 参数）
- 前端 Vite 代理配置见 `frontend/vite.config.js`，所有 `/avatar`、`/api`、`/users`、`/projects` 等路径均代理到后端 8112

### 头像数量

修改 `backend/generate_avatars.py` 中的 `CHAR_LIST`（用户头像）、`COLOR_PALETTES`（配色）和 `SESSION_TEMPLATES`（会话头像）可自定义。

### 日志

后端日志位于 `backend/log/`：

| 文件 | 级别 | 内容 |
|---|---|---|
| `server.log` | INFO | 核心流程 |
| `error.log` | ERROR | 错误记录 |

## License

MIT
