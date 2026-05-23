# Claude Manager — 完整计划

---

## 一、数据库结构

### 仅保留两张表：user + project

**设计理念**：Claude CLI 返回的 JSON 信息非常丰富（session_id、uuid、num_turns、total_cost_usd、usage、modelUsage 等），拆成单独字段太繁琐。project 表直接存完整的 Claude 返回 JSON，需要提取的字段用后端代码抽取。

### 1.1 user 表

| 字段名 | 类型 | 说明 |
|---|---|---|
| `user_id` | TEXT (PRIMARY KEY) | 32 位 UUID（`uuid.uuid4().hex`） |
| `name` | TEXT (UNIQUE, NOT NULL) | 用户名，如 LQC |
| `user_avatar_id` | INTEGER | 用户头像编号（1-20，对应 static/avatars/user/ 下的 PNG） |
| `created_at` | REAL | Unix 时间戳 |
| `updated_at` | REAL | Unix 时间戳 |

### 1.2 project 表

| 字段名 | 类型 | 说明 |
|---|---|---|
| `project_id` | TEXT (PRIMARY KEY) | 32 位 UUID（`uuid.uuid4().hex`） |
| `user_id` | TEXT (FK → user.user_id) | 所属用户 UUID |
| `folder_name` | TEXT | 项目磁盘完整路径，如 `/data/test` |
| `claude_path` | TEXT | Claude JSONL 存放路径，如 `~/.claude/projects/-data-test` |
| `session_id` | TEXT | Claude Code 原生 session UUID，用于 `--resume`，初始为空 |
| `user_input` | TEXT | 用户发送的原始消息 |
| `is_finished` | INTEGER | 0=活跃中（subprocess 还在跑）、1=已终止 |
| `subprocess_pid` | INTEGER | subprocess PID，用于 kill + 进程管理 |
| `status` | INTEGER | 仅 `is_finished=1` 时有意义：<br>0=正常完成（`subtype=="success"`, `is_error==false`, `stop_reason=="end_turn"`）<br>1=API 临时错误（`subtype=="success"`, `is_error==true`, `stop_reason=="stop_sequence"`）<br>2=max_turns 超限（`subtype=="error_max_turns"`, `is_error==true`, `stop_reason=="tool_use"`）<br>3=子进程异常（其他错误分支）<br>4=超时（`proc.kill()` returncode=-9）<br>5=子进程 crash（async 异常） |
| `claude_result` | TEXT | **Claude 完整返回 JSON**（`json.dumps()` 后存入），包含所有字段 |
| `claude_output` | TEXT | Claude 回复文本摘要（`result` 字段） |
| `session_avatar_id` | INTEGER | 会话头像编号（1-100，对应 static/avatars/session/ 下的 PNG） |
| `total_inputTokens` | INTEGER | 累计输入 token 数 |
| `total_outputTokens` | INTEGER | 累计输出 token 数 |
| `retries` | INTEGER | 重试次数 |
| `created_at` | REAL | Unix 时间戳 |
| `updated_at` | REAL | Unix 时间戳 |
| **UNIQUE** | `(user_id, folder_name)` | 同一用户不能重复添加同一项目 |

### 1.3 关系图

```
user ────< project
  1 ──── N
```

一张 project 记录 = 一个 Claude 会话，每次交互更新同一条记录（追加 `claude_result`、更新 `is_finished`/`status`/`claude_output`）。

### 1.4 索引

| 索引名 | 表 | 字段 |
|---|---|---|
| `idx_project_user` | project | user_id |
| `idx_project_path` | project | folder_name |
| `idx_project_session` | project | session_id |
| `idx_project_finish` | project | is_finished |
| `idx_project_updated` | project | updated_at |

### 1.5 `claude_result` JSON 结构示例

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "num_turns": 6,
  "result": "完整回复文本...",
  "session_id": "ec37823e-decc-405a-a5e0-f26d97798536",
  "uuid": "df2206d4-b78c-447c-a7cb-23471de61a4e",
  "total_cost_usd": 0.825925,
  "terminal_reason": "completed",
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 161834, "output_tokens": 445 },
  "modelUsage": { "qwen3.6-35b-a3b": { "costUSD": 0.825925 } }
}
```

---

## 二、后端 API（FastAPI，端口 8112）

路由分两个模块：`claude.py`（Claude 执行相关）和 `database.py`（CRUD 操作）。

### 2.1 GET /health
- 返回: `{"status": "ok"}`

### 2.2 GET /users
- 返回: `[{user_id, name, user_avatar_id, created_at, updated_at}, ...]`

### 2.3 GET /projects?user_id=xxx
- 列出项目（可选按 user 过滤）
- 返回: `[{project_id, user_id, folder_name, claude_path, session_id, user_input, is_finished, status, claude_result, claude_output, ...}, ...]`

### 2.4 GET /projects/{project_id}
- 获取项目详情（含完整 `claude_result`）

### 2.5 PATCH /projects/{project_id}
- 更新项目字段

### 2.6 DELETE /projects/{project_id}
- 删除项目：
  1. 获取 `subprocess_pid`，如果 > 0 则 `os.kill(pid, 9)` 终止进程
  2. 清理项目文件：删除 `session_id.jsonl`、`claude_path` 目录、项目文件夹
  3. 清理 `~/.claude/projects` 下的空子目录
  4. 删除 DB 记录

### 2.7 DELETE /users/{user_id}
- 删除用户：
  1. 遍历该用户所有项目，逐个项目删除（同 DELETE /projects/{id}）
  2. 清理空目录
  3. 删除 DB 记录

### 2.8 POST /api/claude
- 发送消息：查/建 user → 查/建 project → 创建 session（如无）→ 异步执行 Claude subprocess → 立即返回 `project_id`
- 请求体: `{user, dir, message}`
- 返回: `{"success":true,"code":["project_id"],"detail":{"project_id":"..."}}`

### 2.9 GET /api/retry/{project_id}
- 重试项目：获取已有 `session_id` 和 `user_input` → 追加 `"继续完成未完成的内容。"` → 异步执行 → 返回 `project_id`

### 2.10 GET /api/claude-log/{project_id}
- 获取项目对应的 Claude session JSONL 日志
- 读取 `~/.claude/projects/{session_id}.jsonl` 文件最后 40 行

### 2.11 异步执行流程（`_run_claude`）

```
1. 创建 subprocess: claude -p --dangerously-skip-permissions --output-format json --resume <session_id> "<message>"
2. 写入 subprocess_pid 到 DB（标记 is_finished=0）
3. await 进程完成（timeout=1200s）
4. 解析 stdout JSON
5. 根据 subtype/is_error/stop_reason 推导 status（0~5）
6. 更新 DB：claude_output、claude_result、status、is_finished、token 用量
7. 记录日志：[CALLBACK] success=true/false project_id=xxx
```

### 2.12 日志格式
- 统一用 `[CALLBACK]` 前缀：
  - 成功：`[CALLBACK] success=True project_id={id} result={result[:200]}`
  - 失败：`[CALLBACK] success=False project_id={id} msg={error}`

---

## 三、前端页面（Vue 3 + Vite，端口 3112）

### 3.1 整体布局

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
├────────────────┤                              │
│  底部：选中项目详情 │                              │
│  [Avatar] 状态    │                              │
│  路径            │                              │
│  Message/Reply   │                              │
│  [详情] [日志] [重试] [删除] │                              │
└────────────────┴─────────────────────────────┘
```

### 3.2 左侧面板

#### 3.2.1 发送表单（SendForm.vue）

- **User**：下拉选择 + 输入，`v-model="form.user"`
  - 从后端 `/users` 加载
  - 选择后 localStorage 缓存
  - 选择后自动刷新 Project 下拉列表（只列该 User 的项目）
- **Project**：下拉选择 + 输入，`v-model="form.dir"`，依赖 User 选择
  - 从 `/projects?user_id={uid}` 获取该 User 的 `folder_name`
  - localStorage 缓存
  - 选择后触发左侧底部卡片更新
- **Message**：textarea，Ctrl+Enter 快捷发送
- **发送按钮**：`发送 ▶` / `发送中...`，disabled 条件：user/dir/message 任一为空

#### 3.2.2 左侧底部选中卡片（selected card）

显示选中项目的详情：
- 头部：头像 + 状态标签
- 路径：`folder_name`
- 内容区：Message 和 Reply
  - 活跃状态显示黄色"等待 Claude 回复..."
  - 完成状态显示实际回复
  - 失败状态红色背景
- 底部按钮：详情 → 打开 Modal、日志 → 打开 LogModal、重试 → 重试、删除 → 删除项目
- **样式**：卡片居中按钮，重试用紫色（`.btn-continue`），其余用灰色（`.btn-default`/`.btn-delete`）

#### 3.2.3 左侧卡片操作
- 发送后：自动更新 `selectedProject`，左侧卡片自动出现
- 全局轮询：每 3s 自动刷新 `selectedProject`

### 3.3 右侧面板

#### 3.3.1 项目网格（ProjectCard.vue）

- 瀑布流网格布局，自适应列数（`minmax(130px, 1fr)`）
- **缩略卡片**显示：
  - 头像（session_avatar_id）
  - 状态标签：完成=绿色、活跃=黄色、失败=红色
  - Reply 预览：最多 6 行，活跃时显示黄色"等待 Claude 回复..."
  - 底部路径名
- **交互**：
  - **左键单击**：同步左侧 User/Project 卡片
  - **右键单击**：打开 DetailModal（阻止默认右键菜单）
  - 选中状态：高亮边框

### 3.4 Modal 弹窗

#### 3.4.1 详情 Modal（DetailModal.vue）

- 顶部 header：
  - 左：用户头像 → 用户名 → 项目头像 → 项目名
  - 右：状态标签（与卡片同样式）、重试数、关闭按钮（✕）
  - header 底部分隔线
- 第一行：`Session: {session_id}`
- 双面板：
  - Message：原始用户输入
  - Reply：实际回复文本，固定 12 行高度，活跃时显示黄色"等待 Claude 回复..."
  - 失败面板红色背景
- 元信息行：
  - 创建时间 + 轮次
  - 更新时间 + 用时
- 底部 footer：
  - 左侧：总 token（M/K 显示）
  - 右侧：重试 ▶（紫色）、日志（深红）、删除项目（深红）、删除用户（深红）
- footer 顶部分隔线

#### 3.4.2 日志 Modal（LogModal.vue）

- 顶部：标题 + 日志文件名、刷新、复制、关闭
- 主体：JSONL 日志文本（最后 40 行，自动滚动到底部）
- 每 5 秒自动刷新，关闭时清除定时器
- 数据来源：`GET /api/claude-log/{project_id}`

### 3.5 数据流

```
页面加载：
  getUsers() → 填充用户下拉
  getProjects() → 填充项目网格 + 恢复上次选择的 user/dir → 左侧卡片自动显示

发送消息：
  form.user + form.dir + message
    → POST /api/claude
    → 刷新 projects 列表
    → 找到新 project → selectedProject 赋值 → 左侧卡片自动显示
    → 每 3s 轮询更新项目状态

选中项目：
  左侧卡片 ← 双击右侧卡片（同步 User/Project）
  左侧卡片 ← 选择 User + Project
  右侧卡片左键 → 同步左侧
  右侧卡片右键 → 打开 Modal
```

### 3.6 API 封装（api/index.js）

```js
const API = ''  // 空字符串，vite proxy 转发

getHealth()                    → GET /health
getUsers()                     → GET /users
getProjects(user_id?)          → GET /projects
getProject(id)                 → GET /projects/{id}
sendChat(user, dir, message)   → POST /api/claude
retryProject(id)               → GET /api/retry/{id}
updateProject(id, fields)      → PATCH /projects/{id}
deleteProject(id)              → DELETE /projects/{id}
deleteUser(userId)             → DELETE /users/{userId}
getClaudeLog(projectId)        → GET /api/claude-log/{id}
```

### 3.7 头像（utils/avatar.js）

- 根据 `avatarId` 返回静态资源路径：`/static/avatars/{user,session}/{id}.png`
- 默认头像 ID：user=1, session=1

### 3.8 样式

- **主题**：深色科技风
- **背景**：`#0a0a1a` / `#111128` / `#1a1a3e`
- **主色**：`#7c3aed` 紫色光效
- **状态**：完成=绿 `#22c55e`，活跃=黄 `#f59e0b`，失败=红 `#ef4444`
- **字体**：等宽字体（JetBrains Mono / Fira Code / Consolas）
- **背景纹理**：CSS grid 紫色透明线
- **三卡片风格统一**：
  - 状态标签：`.thumb-status`（小卡片）、`.card-status`（左侧）、`.status-badge`（Modal header 复用 `.thumb-status`）
  - 三卡片状态颜色一致：完成=绿色，活跃=黄色，失败=红色

### 3.9 Toast 通知

- 顶部居中弹窗，2s 自动消失
- 样式：红色背景（`var(--error)`），入场动画
- 触发：发送失败、重试失败等

### 3.10 Confirm Dialog

- 模态确认框（删除项目、删除用户）
- 样式：紫色光晕，确认按钮红色，取消按钮灰色
- 通过 `showConfirm(message, callback)` 调用

---

## 四、全局轮询机制

- 每 3s 自动调用 `refreshProjects()` 刷新所有项目
- 同步更新 `selectedProject`（左侧卡片）和 `modalProject`（Modal）
- 发送消息后立即手动刷新一次

---

## 五、localStorage 缓存

| Key | 说明 |
|---|---|
| `pref_user` | 上次选择的用户名 |
| `pref_dir` | 上次选择的项目目录 |
| 页面加载时自动恢复，用户选择时自动更新 |

---

## 六、删除清理逻辑

### 删除项目：
1. 终止 subprocess（如 `subprocess_pid > 0`）
2. 删除 `~/.claude/projects/{session_id}.jsonl` 文件
3. 删除 `~/.claude/projects/{claude_path_basename}` 目录（如 `-data-test`）
4. 删除项目文件夹（如为空）
5. 清理 `~/.claude/projects` 下空子目录
6. 删除 DB 记录

### 删除用户：
1. 逐个删除该用户所有项目（同上）
2. 清理 `~/.claude/projects` 下空子目录
3. 删除 DB 记录
