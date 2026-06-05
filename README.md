# Claude Manager

> Claude Code 托管代理管理后台 — 通过 Web 界面发送任务给本地 Claude CLI，实时跟踪执行状态、查看日志。

## 系统要求

| 资源 | 最低 | 推荐 |
|------|------|------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 10 GB | 20 GB+ |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + JavaScript |
| 后端 | FastAPI + SQLite + asyncio |
| Claude CLI | claude 2.x（需本地安装） |

## 功能特性

- **User / Project 管理** — User CRUD、按 User 过滤项目列表
- **异步任务执行** — 向 Claude CLI 发送消息，异步执行并实时返回结果
- **Session 管理** — 自动创建 / 恢复 / 失效检测（JSONL 文件检测）/ 自动重建
- **CAS 原子锁** — Compare-And-Swap + 5 分钟过期自动释放，支持并发安全
- **心跳检测** — 每分钟检查僵尸进程，自动清理并标记失败
- **日志查看** — 解析 Claude CLI 的 JSONL 日志文件，格式化展示最后 40 行
- **回复预览** — 查看 Claude 完整回复内容，支持一键复制
- **像素风头像** — 33 个 8x8 像素艺术头像（幽灵、恶魔、几何图形等）

## 目录结构

```
claude_manager/
├── backend/                  # FastAPI 后端
│   ├── api/                  # API 路由
│   │   ├── claude.py         # Claude CLI 异步执行 & 重试 & 日志
│   │   ├── database.py       # User / Project CRUD
│   │   └── __init__.py
│   ├── static/avatars/       # 头像图片（生成后存放）
│   ├── main.py               # FastAPI 应用入口 & PID 心跳
│   ├── db.py                 # SQLite 数据访问层
│   ├── response.py           # 统一响应格式
│   ├── generate_avatars.py   # 头像生成脚本
│   ├── __init__.py
│   └── pyproject.toml        # Python 依赖
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── api/              # API 客户端（fetch）
│   │   ├── components/       # Vue 组件
│   │   │   ├── SendForm.vue          # 发送表单（User / Project 选择）
│   │   │   ├── ProjectGrid.vue       # 项目卡片网格
│   │   │   ├── ProjectCard.vue       # 单个项目缩略卡片
│   │   │   ├── SelectedCard.vue      # 左侧概览详情卡片
│   │   │   ├── DetailModal.vue       # 项目详情弹窗
│   │   │   ├── LogModal.vue          # JSONL 日志查看器
│   │   │   ├── ReplyPreviewModal.vue # 回复内容预览
│   │   │   ├── Toast.vue             # 全局提示
│   │   │   └── ConfirmDialog.vue     # 确认对话框
│   │   ├── utils/            # 工具函数
│   │   ├── App.vue           # 主布局 & 状态管理
│   │   └── main.js           # 入口
│   ├── vite.config.js        # Vite 配置（含 API 代理）
│   └── package.json          # 前端依赖
├── data/                     # SQLite 数据库（自动创建）
├── log/                      # 运行日志（server.log, error.log）
├── tmp/                      # PID 文件（自动生成）
├── init.sh                   # 首次初始化
├── start.sh                  # 日常启动
├── stop.sh                   # 停止服务
├── .gitignore
└── README.md
```

## 快速开始

### 前置依赖

- **Python** >= 3.10
- **Node.js** >= 18 (含 npm)
- **claude CLI** — 本地安装 Claude Code

### 1. 初始化

```bash
cd claude_manager
bash init.sh
```

自动完成：

| 步骤 | 操作 |
|------|------|
| 0 | 检查 / 安装 `uv` |
| 1 | 创建 Python 虚拟环境（`.venv/`） |
| 2 | 安装后端依赖（从 `pyproject.toml`） |
| 3 | 安装前端 npm 依赖 |
| 4 | 生成头像 |
| 5 | 构建前端 |
| 6 | 清理缓存 |

### 2. 启动服务

```bash
bash start.sh
```

```
🚀 Claude Manager 启动完成
   前端: http://localhost:3112
   后端: http://localhost:8112
```

| 服务 | 地址 |
|------|------|
| 前端应用 | http://localhost:3112 |
| 后端 API 文档 | http://localhost:8112/docs |
| 健康检查 | http://localhost:8112/health |

### 3. 日常运维

```bash
bash start.sh       # 启动（含自动停止旧进程）
bash stop.sh        # 停止
bash stop.sh && bash start.sh   # 重启

tail -f log/server.log     # 查看后端日志
tail -f log/error.log      # 查看错误日志
```

- **修改代码**：后端 Uvicorn 和前端 Vite 均支持热更新
- **修改配置**：无外部配置文件，重启生效

## 交互流程

```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────┐
│   SendForm      │    │   ProjectGrid    │    │ DetailModal  │
│  (左上)          │    │  (右侧)           │    │  (弹窗)       │
│                 │    │                  │    │              │
│  - 选择 User    │    │  - 显示项目卡片  │    │  - 完整状态  │
│  - 选择 Project │    │  - 左键: 更新左侧│    │  - 重试 / 删除│
│  - 输入消息     │    │  - 右键: 打开详情│    │  - 日志 / 回复│
│  - 发送         │    │                  │    │              │
└────────┬────────┘    └──────────────────┘    └──────────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────┐
│   SelectedCard  │◀──▶│  Backend     │
│  (左下)          │    │  (FastAPI)   │
│                 │    │  - CAS 原子锁│
│  - 概览信息     │    │  - 异步执行  │
│  - 重试 / 删除  │    │  - 心跳检测  │
└─────────────────┘    └──────┬───────┘
                              │
                              ▼
                       ┌──────────────┐
                       │ Claude CLI   │
                       │ (本地进程)    │
                       │ --resume     │
                       │ session.jsonl│
                       └──────────────┘
```

### 关键交互规则

| 操作 | 行为 |
|------|------|
| 表单选择 User → Project | 左侧下部概览卡片自动更新 |
| 点击右侧卡片（左键） | 更新左侧表单 + 概览卡片 |
| 点击右侧卡片（右键） | 打开详情弹窗 |
| 点击概览卡片「详情」 | 打开详情弹窗（不改变左侧卡片） |
| 发送消息 | 异步执行，3 秒轮询更新状态 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/claude` | 发送消息，立即返回 project_id |
| GET | `/api/retry/{project_id}` | 重试失败的项目 |
| GET | `/api/claude-log/{project_id}` | 获取 JSONL 日志（解析后的数组） |
| GET | `/users` | 获取所有 User |
| DELETE | `/users/{user_id}` | 删除 User（级联删除项目） |
| GET | `/projects` | 获取项目列表（?user_id=xxx 过滤） |
| GET | `/projects/{project_id}` | 获取单个项目详情 |
| PATCH | `/projects/{project_id}` | 更新项目 |
| DELETE | `/projects/{project_id}` | 删除项目 |
| GET | `/avatar/{type}/{num}.png` | 获取头像图片 |
| GET | `/health` | 健康检查 |

## 数据库

SQLite WAL 模式，数据库文件位于 `data/claude_manager.db`。

### 表结构

| 表 | 字段 | 说明 |
|----|------|------|
| `user` | user_id, name, user_avatar_id, created_at, updated_at | 对接人 |
| `project` | project_id, user_id, folder_name, claude_path, session_id, user_input, is_finished, locked_at, subprocess_pid, status, claude_result, claude_output, total_inputTokens, total_outputTokens, created_at, updated_at | 项目 |

### 状态码

| status | 含义 |
|--------|------|
| 0 | 执行成功 |
| 1 | 用户中止 |
| 2 | 达到最大轮次 |
| 3 | 其他错误（session 失效等） |
| 4 | 超时 / PID 被杀 |
| 5 | 异常崩溃 / JSON 解析失败 |

### 备份

```bash
cp data/claude_manager.db data/claude_manager.db.bak
```

## 锁机制

采用 **CAS (Compare-And-Swap) + 超时自动释放** 方案：

```
send / retry 请求
    │
    ▼
lock_project()
    │  SQL: UPDATE project SET is_finished=0, locked_at=now()
    │      WHERE project_id=? AND (is_finished=1 OR locked_at < now()-5min)
    │
    ├── 成功 → 异步执行 _run_claude() → unlock_project()
    │                                   无论成功/失败/异常
    └── 失败 → HTTP 409 "session 使用中"
```

- `locked_at` 字段记录加锁时间
- 超过 5 分钟自动释放（僵尸锁）
- `is_finished=1` 表示空闲，`0` 表示运行中

## 会话管理

- 新建会话：直接调用 Claude CLI，返回 `session_id`
- Resume：`--resume <session_id>` 继续对话
- Session 失效检测：执行前检查 JSONL 文件是否存在
- 失效自动重建：JSONL 丢失时自动创建新 session
