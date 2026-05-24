# Claude Manager

Claude Code 托管代理管理后台，支持多用户、多项目、实时状态监控与交互。

## 功能特性

- **多用户管理** — 支持多个用户，每个用户独立管理自己的项目
- **多项目支持** — 每个用户下可创建多个项目（对话会话），实时追踪状态
- **实时交互** — 支持发送消息、重试失败会话、查看完整日志
- **像素风头像** — 33 个用户头像 + 100 个会话头像，全部 8x8 像素画
- **消息预览** — 支持回复预览和一键复制

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

1. 左侧面板顶部选择或输入 **User**（对接人）
2. 选择或输入 **Project**（项目目录）
3. 点击发送按钮即可创建新项目

### 管理项目

- **查看详情** — 点击右侧项目卡片，打开详情弹窗
- **重试** — 失败的项目可以点击重试恢复
- **查看日志** — 弹窗底部「日志」按钮查看完整对话日志
- **删除** — 支持单个项目删除和用户级删除（连同该用户所有项目）
- **复制** — 支持复制用户消息和 AI 回复内容

### 头像管理

```bash
# 重新生成头像（修改模板后）
python backend/generate_avatars.py
```

头像存储在 `backend/static/avatars/` 目录，通过后端 API `/avatar/{type}/{id}.png` 访问。

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
│   │   ├── claude.py         # Claude 代理交互
│   │   └── database.py       # 数据管理 API
│   ├── main.py               # 应用入口
│   ├── db.py                 # 数据库模型
│   ├── generate_avatars.py   # 头像生成脚本
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
├── init.sh                   # 一键初始化
├── start.sh                  # 一键启动
├── README.md                 # 本文件
└── tmp/                      # PID 文件（自动生成）
```

## 数据库

使用 SQLite 存储数据，数据库文件位于 `data/claude_manager.db`。

### 表结构

- **user** — 用户信息（ID、名称、头像 ID）
- **project** — 项目信息（关联用户、目录名、Claude 路径、会话状态、输入输出等）

### 备份

```bash
cp data/claude_manager.db data/claude_manager.db.bak
```

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /health | 健康检查 |
| GET | /avatar/{type}/{id}.png | 头像图片 |
| GET/POST | /api/users | 用户列表 / 创建用户 |
| DELETE | /api/users/{id} | 删除用户 |
| GET/POST | /api/projects | 项目列表 / 创建项目 |
| GET/POST | /api/claude/{id} | 发送消息 |
| GET | /api/claude/{id}/log | 获取日志 |
| POST | /api/continue/{id} | 继续对话 |
| DELETE | /api/projects/{id} | 删除项目 |

## 配置

### 端口

- 后端: `8112`（修改 `backend/main.py` 中的 `uvicorn` 参数）
- 前端: `3112`（修改 `start.sh` 中 `vite --port` 参数）
- 前端 Vite 代理配置见 `frontend/vite.config.js`

### 头像数量

修改 `backend/generate_avatars.py` 中的 `CHAR_LIST` 和 `COLOR_PALETTES` 可自定义头像数量和配色。

## License

MIT
