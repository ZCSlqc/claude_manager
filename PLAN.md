# Claude Code Proxy — 完整计划

---

## 一、数据库结构

### 仅保留两张表：user + project

**设计理念**：Claude CLI 返回的 JSON 信息非常丰富（session_id、uuid、num_turns、total_cost_usd、usage、modelUsage、terminal_reason、stop_reason、errors 等），拆成单独字段太繁琐。project 表直接存完整的 Claude 返回 JSON，需要提取的字段用 SQL 表达式或后端代码抽取。

### 1.1 user 表

| 字段名 | 类型 | 说明 |
|---|---|---|
| `user_id` | TEXT (PRIMARY KEY) | 32 位 UUID（`uuid.uuid4().hex`） |
| `name` | TEXT (UNIQUE, NOT NULL) | 用户名，如 ZCS |
| `user_avatar_id` | INTEGER | 用户头像编号（1-20，对应 static/avatars/user/ 下的 PNG，生成时确定，永久不变） |
| `created_at` | REAL | Unix 时间戳 |
| `updated_at` | REAL | Unix 时间戳 |

### 1.2 project 表

| 字段名 | 类型 | 说明 |
|---|---|---|
| `project_id` | TEXT (PRIMARY KEY) | 32 位 UUID（`uuid.uuid4().hex`） |
| `user_id` | TEXT (FK → user.user_id) | 所属用户 UUID |
| `folder_name` | TEXT | 项目磁盘完整路径，如 `/data/openclaw/test` |
| `claude_path` | TEXT | Claude JSONL 存放路径，如 `~/.claude/projects/-data-openclaw-test` |
| `session_avatar_id` | INTEGER | 会话头像编号（1-100，对应 static/avatars/session/ 下的 PNG，生成时确定，永久不变） |
| `session_id` | TEXT | Claude Code 原生 session UUID，用于 `--resume`，初始为空 |
| `user_input` | TEXT | 用户发送的原始消息 |
| `is_finished` | INTEGER | 0=活跃中（subprocess 还在跑）、1=已终止（subprocess 已结束） |
| `subprocess_pid` | INTEGER | 仅当 `is_finished=0` 时有意义：`subprocess.Popen().pid`，用于超时 kill + 进程管理，完成后（无论成功/失败）重置为 0 |
| `status` | INTEGER | 仅当 `is_finished=1` 时有意义：<br>0=正常完成（`subtype=="success"`, `is_error==false`, `stop_reason=="end_turn"` 或 `null`）<br>1=API 临时错误（`subtype=="success"`, `is_error==true`, `stop_reason=="stop_sequence"`）→ 发 `"Don't read too much once, continue your work."` 自愈<br>2=max_turns 超限（`subtype=="error_max_turns"`, `is_error==true`, `stop_reason=="tool_use"`）→ 发 `Continue.` 自愈<br>3=subprocess 超时（3600s 未返回，`proc.kill()` kill 进程，returncode=-9，stdout 无可靠 JSON）→ 发 `"Too much time, give me a summary of what you have done."` 自愈<br>4=JSON 解析失败（stdout 不是合法 JSON）→ 发 `"Repeat what you have done."` 自愈<br>5=子进程异常死亡（周期性 PID 检测发现进程已死，但 `is_finished` 仍为 0）→ 不自愈，仅标记终止 |
| `claude_result` | TEXT | **Claude 完整返回 JSON（`json.dumps()` 后存入）**，包含 session_id、uuid、num_turns、total_cost_usd、usage、modelUsage 等全部字段 |
| `created_at` | REAL | Unix 时间戳 |
| `updated_at` | REAL | Unix 时间戳 |
| **UNIQUE** | `(user_id, folder_name)` | 同一用户不能重复添加同一项目 |


### 1.3 关系图

```
user ────< project
  1 ──── N
```

一张 project 记录 = 一次 Claude 调用 + 一次完整回复。一个用户可以有多个项目，每个项目可以多次交互（每次交互更新同一条 project 记录）。

### 1.4 索引

| 索引名 | 表 | 字段 |
|---|---|---|
| `idx_project_user` | project | user_id |
| `idx_project_path` | project | folder_path |
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
  "usage": { "input_tokens": 161834, "output_tokens": 445, ... },
  "modelUsage": { "qwen3.6-35b-a3b": { "costUSD": 0.825925, ... } }
}
```

需要提取子字段时用 SQL：
```sql
-- 提取 session_id
json_extract(claude_result, '$.session_id')
-- 提取 cost
json_extract(claude_result, '$.total_cost_usd')
-- 提取 num_turns
json_extract(claude_result, '$.num_turns')
```

---

## 二、后端 API（FastAPI，端口 8112）

### 2.1 GET /health

- 返回: `{"status": "ok"}`

### 2.2 GET /users

- 返回: `[ {user_id, name, user_avatar_id, created_at, updated_at}, ... ]`

### 2.3 POST /chat

- 请求体:
```json
{
  "user": "ZCS",
  "dir": "/data/openclaw/test",
  "message": "你好"
}
```

- 逻辑:
  1. **查找/新建 user**
     - `database.get_user(user)` → 返回 user dict 或 None
     - 如果 None → `database.add_user(user)` → 拿到 `user_id`、`user_avatar_id`（随机）
     - 如果已存在 → 直接取 `user_id`、`user_avatar_id`
  2. **查找/新建 project**
     - `database.get_project_by_path(user_id, dir)` → 按 `user_id + folder_name`（完整目录路径）查找
     - 如果返回 None（不存在）→ `database.add_project(user_id, dir)`
       - 内部逻辑：
           - `project_id` = `uuid.uuid4().hex`（32 位字符串）
           - `session_avatar_id` = `随机`（生成时确定，永久不变）
           - `ts` = `time.time()`
           - `folder_name` = `dir`（完整目录路径，如 `/data/openclaw/test`）
           - `claude_path` = `Path(os.path.expanduser('~/.claude/projects/-' + dir.replace('/', '-')))`.as_posix()（JSONL 存放路径）
           - `session_id` = `""`（初始为空）
           - `user_input` = `""`
           - `is_finished` = `1`（新创建即标记已终止，首次 chat 后根据结果更新为 0 或 1）
           - `status` = `0`（见下方 status 分类表，仅当 `is_finished=1` 时有意义）
           - `claude_result` = `""`
           - `subprocess_pid` = `0`（subprocess PID，用于 kill）
           - `created_at` = `ts`
           - `updated_at` = `ts`
     - 如果已存在 → 取已有 `project_id`、`folder_name`、`session_id`、`is_finished`、`status`、`session_avatar_id`
  3. **验证目录**
     - `Path(dir).exists()` → 不存在则 `Path(dir).mkdir(parents=True, exist_ok=True)`
     - 目录不存在说明磁盘异常，记 `log.error`
  4. **检查项目状态**
     - `project.is_finished == 0` and pid不为空→ session 正活跃（subprocess 还在跑），直接返回
       ```json
       {"status":"failed","error":"session 使用中，请勿重复发送","retries":0} pid也返回
       ```
       记 `log.info(f"session busy: user={user}, dir={dir}")`
     - `project.is_finished == 1` → 正常继续
  5. **决定 CLI 参数和策略**
     - 重试计数 `retries` = 0
     - **场景 A：已有 `session_id`（非空字符串）**
       - 发送前更新：`database.update_project(project_id, user_input=message, is_finished=0)`
       - CLI 命令：`claude --dangerously-skip-permissions -p --output-format json --resume <session_id> "<message>"`
       - 无额外控制参数
       - subprocess 参数：`cwd=dir`（Claude CLI 没有 `--dir` 参数，靠 CWD 定位项目目录），`timeout=3600`
       - `subprocess.Popen` 创建进程后立即拿到 `pid`，写入 DB（此时进程运行中，周期性检测器能抓到）
     - **场景 B：无 `session_id`（空字符串）**
       - Step A（创建会话）：`claude --dangerously-skip-permissions -p --output-format json "你好"`
         - 无 session 参数，仅用于快速拿到 session_id，结果丢弃
         - `cwd=dir`，`timeout=3600`
         - 解析 stdout JSON 拿到 `session_id`
       - 更新 project：`database.update_project(project_id, session_id=new_sid, claude_result=json.dumps(stdout_json), is_finished=1, subprocess_pid=0)`
       - Step C（发真实消息）：`claude --dangerously-skip-permissions -p --output-format json --resume <session_id> "<message>"`
         - `cwd=dir`，`timeout=3600`
         - `subprocess.Popen` 创建进程后立即拿到 `pid`，写入 DB
         - `session_id` = Step A 拿到的值
  6. **执行 Claude subprocess（同步 Popen）**
     - Python 实现：
       ```python
       cmd = ["claude", "--dangerously-skip-permissions", "-p", "--output-format", "json"]
       if has_session_id:
           cmd.extend(["--resume", session_id])
       cmd.append(message)
       proc = subprocess.Popen(cmd, capture_output=True, text=True, cwd=dir)
       pid = proc.pid  # 立即拿到 PID
       database.update_project(project_id, subprocess_pid=pid)  # 立即写 DB（进程运行中）
       try:
           stdout, stderr = proc.communicate(timeout=3600)
       except subprocess.TimeoutExpired:
           proc.kill()
           proc.communicate()
           # 超时逻辑 → 走步骤 8
       ```
     - 时序：**创建进程 → 立即 PID 写 DB → communicate → 解析结果**
     - 超时处理：`proc.kill()` 杀掉进程 + `proc.communicate()` 回收（SIGKILL → returncode=-9，stdout 无可靠 JSON）
     - PID 意义：写 DB 时进程正在运行，周期性检测器通过 `os.kill(pid, 0)` 能检测到存活/死亡
     - stderr 处理：`capture_output=True`（stdout 只含 JSON），stderr 丢弃
  7. **解析 stdout JSON**
     - 尝试 `stdout_json = json.loads(stdout.strip())`
     - 如果 JSON 解析失败：
       - `is_finished` = `1`（终止）
       - `status` = `4`（JSON 解析失败）
       - `error` = `"stdout JSON 解析失败"`
       - `output` = `stdout[:500]`（返回原始内容供调试）
       - 跳到步骤 9 更新记录
     - 成功解析后提取：
       - `session_id` = `stdout_json.get("session_id", "")`
       - `result` = `stdout_json.get("result", "")`
       - `num_turns` = `stdout_json.get("num_turns", 0)`
       - `total_cost_usd` = `stdout_json.get("total_cost_usd", 0)`
       - `subtype` = `stdout_json.get("subtype", "")`
       - `is_error` = `stdout_json.get("is_error", False)`
       - `stop_reason` = `stdout_json.get("stop_reason", "")`
       - `terminal_reason` = `stdout_json.get("terminal_reason", "")`
       - `errors` = `stdout_json.get("errors", [])`
  8. **决定 is_finished 和 status**
     - **status 分类**：
       | status | 含义 | 触发条件 | 自愈消息 |
       |---|---|---|---|
       | 0 | 正常完成 | `subtype=="success"` 且 `is_error==false` 且 `stop_reason=="end_turn"` 或 `null` | - |
       | 1 | API 临时错误 | `subtype=="success"` 且 `is_error==true` 且 `stop_reason=="stop_sequence"` | `"Don't read too much once, continue your work."` |
       | 2 | max_turns 超限 | `subtype=="error_max_turns"` 且 `is_error==true` 且 `stop_reason=="tool_use"` | `"Continue."` |
       | 3 | subprocess 超时 | 3600s 未返回，`proc.kill()` | `"Too much time, give me a summary of what you have done."` |
       | 4 | JSON 解析失败 | stdout 不是合法 JSON | `"Repeat what you have done."` |
       | 5 | 子进程异常死亡 | 周期性 PID 检测发现进程已死 | 不自愈，仅标记终止 |
     - 全部 → `is_finished = 1`，`status` 按上表赋值
     - `stop_reason == null` 且 `result == ""` 且 `num_turns == 0`（`/new` 清空上下文）→ `status = 0`（算正常）

  9. **更新 project 记录**（`database.update_project(project_id, **fields)`）
     - `session_id` = 本次返回的 `session_id`
     - `claude_result` = `json.dumps(stdout_json, ensure_ascii=False)`（完整 JSON 存入 TEXT）
     - `user_input` = 原始 `message`
     - `is_finished` = 步骤 8 的结果
     - `status` = 步骤 8 的结果
     - `updated_at` = `time.time()`

  10. **自动自愈（核心容错机制）**
      - **触发条件**：`is_finished == 1` 且 `status` 在 1~4 之间 且 `session_id` 非空
      - **自愈方式（全部 resume 发指令继续，不删 session）**：
        - **status == 1**（API 临时错误）→ 发 `"Don't read too much once, continue your work."`
          - `subprocess.run([... , "--resume", session_id, "Don't read too much once, continue your work."], timeout=3600, cwd=dir)`
          - 解析 stdout JSON，结果不入库
          - 成功 → `{"status":"success","output":新result,"retries":1}`
          - 失败 → `{"status":"failed","error":"重试后仍失败","retries":1}`
        - **status == 2**（max_turns 超限）→ 发 `Continue.`
          - `subprocess.run([... , "--resume", session_id, "Continue."], timeout=3600, cwd=dir)`
          - 同上，结果不入库
        - **status == 3**（subprocess 超时）→ 先 kill 进程（SIGKILL → returncode=-9，stdout 无可靠 JSON），再 resume 发摘要请求
          - `os.kill(subprocess_pid, 9)` 强制 kill 进程（如果还在）
          - `subprocess.run([... , "--resume", session_id, "Too much time, give me a summary of what you have done."], timeout=3600, cwd=dir)`
          - 结果不入库
        - **status == 4**（JSON 解析失败）→ 发 `"Repeat what you have done."`
          - `subprocess.run([... , "--resume", session_id, "Repeat what you have done."], timeout=3600, cwd=dir)`
          - 同上，结果不入库
      - **重试上限**：最多重试 1 次
      - **锚定原始 message**：自愈不篡改原始需求
      - **无前端 /continue 入口**：全靠后台静默自愈

  11. **构建返回**
      ```json
      {
        "session_id": "<session_id>",
        "status": "success" | "failed",
        "output": "<result 文本，截取或完整取决于长度>",
        "error": "<失败原因字符串或 null>",
        "retries": "<0 或重试次数>",
        "claude_result": <完整 stdout JSON 对象>
      }
      ```
  12. **记录日志**
      - 成功：`log.info(f"chat ok: user={user}, dir={dir}, cost={cost:.4f}, turns={turns}, result_len={len(result)}")` → `log/server.log`
      - 失败：`log.error(f"chat fail: user={user}, dir={dir}, is_finished={is_finished}, status={status}, error={error}")` → `log/error.log`
      - 自愈：`log.warning(f"auto-retry: user={user}, dir={dir}, retries={retries}, reason={error}")` → `log/server.log`

- 返回:
```json
{
  "session_id": "4170b6ccee074929904246f01f27bf71",
  "status": "success",
  "output": "你好！有什么可以帮你的吗？",
  "error": null,
  "retries": 0,
  "claude_result": { ... }  // 完整 JSON
}
```

### 2.4 GET /projects?user_id=xxx

- 列出项目（可选按 user 过滤）
- 返回: `[ {project_id, user_id, folder_name, folder_path, session_id, user_input, is_finished, status, claude_result, created_at, updated_at}, ... ]`

### 2.5 GET /projects/{project_id}

- 获取项目详情（含完整 `claude_result`）

### 2.6 PATCH /projects/{project_id}

- 更新项目：`session_avatar_id`、`is_finished`、`status`
- 请求体: `{"session_avatar_id": 42}`

### 2.7 DELETE /projects/{project_id}

- 删除 project → 同时删除对应 Claude JSONL 文件
- 逻辑: 获取 `session_id` → `rm ~/.claude/projects/<dir>/<session_id>.jsonl` → `DELETE FROM project`

### 2.8 POST /continue/{project_id}

- 向指定项目发送 `Continue.`
- 逻辑: 获取 `session_id` → `claude --dangerously-skip-permissions -p --output-format json --resume <session_id> "Continue."`
- 更新 `claude_result`、`is_finished`

### 2.9 GET /sessions?limit=50

- 列出最近 50 条项目记录（兼容旧路由名）
- 等同于 `GET /projects?limit=50`

### 2.10 周期性 PID 健康检测（后台任务）

- **目的**：防止 `is_finished=0` 但 subprocess 已死（crash / OOM / 被外部 kill）导致 PID 残留在 DB 中
- **机制**：FastAPI 启动时启动一个 asyncio 后台任务，每 60 秒执行一次
- **逻辑**：
  1. 查询所有 `is_finished=0` 且 `subprocess_pid > 0` 的项目
  2. 对每个，调用 `os.kill(pid, 0)`（不真正杀死，只检测进程是否存在）
     - `ProcessLookupError` → 进程不存在
     - `PermissionError` → 进程存在（跨用户权限差异，Linux 特有）
  3. 如果进程已死：
     - `database.update_project(project_id, is_finished=1, status=5, subprocess_pid=0)`
     - `logger.warning(f"zombie_pid: user={user}, dir={dir}, pid={pid}")` → `log/server.log`
  4. 如果进程还活着：跳过，不做任何操作
- **启动方式**：
  ```python
  @app.on_event("startup")
  async def start_pid_monitor():
      asyncio.create_task(_periodic_pid_checker())
  ```
- **注意**：status=3（超时 kill）路径中，主流程已经 kill 并更新了 DB，周期性检测不会重复触发（`is_finished` 已被设为 1）

---

## 三、前端页面（Vue 3 + Vite，端口 3112）

### 3.1 整体布局

```
┌──────────────────────────────────────────────┐
│  ⬡ Claude Code Proxy                         │
├────────────────┬─────────────────────────────┤
│  左侧面板 (320px) │       右侧面板             │
├────────────────┬─────────────────────────────┤
│  发送任务表单    │  Claude 回复                │
│  - 对接人 ▼     │  [Avatar] 会话名称(可编辑)   │
│  - 项目目录 ▼   │  目录路径   status  🗑       │
│  - 消息 textarea│  ─── 原始消息 ───           │
│  - 发送 ▶       │  用户发的消息内容           │
│                 │  ─── 回复内容 ───           │
│  项目列表       │  Claude 回复的文本内容      │
│  [项目卡片1]    │  [重试 ▶] [🗑 删除]        │
│  [项目卡片2]    │                             │
└────────────────┴─────────────────────────────┘
```

### 3.2 左侧面板

#### 3.2.1 发送任务表单

- **对接人**: `v-model="form.user"`，下拉选择，必须填写
- **项目目录**: `v-model="form.dir"`，下拉选择或手动输入
- **消息**: `textarea`，`Ctrl+Enter` 快捷发送
- **发送按钮**: `发送 ▶` / `发送中...`（禁用状态）

#### 3.2.2 项目列表

- **标题**: `项目 ({{ filteredProjects.length }})`
- **过滤**: 按 `form.user` 过滤
- **列表项**: 文件夹名 + 用户消息前20字 + 状态标签
- **状态**: `is_finished=0` 活跃（绿）、`=1` 且 `status=0` 完成（绿）、`=1` 且 `status≥1` 失败（红）
- **点击**: 自动填 dir + 加载右侧面板

### 3.3 右侧面板

#### 会话卡片

```
┌────────────────────────────────────┐
│ [Avatar] 会话名称(可编辑) status 🗑│
│        目录路径                    │
├────────────────────────────────────┤
│ ─── 原始消息 ───                   │
│ 用户发送的消息内容                 │
├────────────────────────────────────┤
│ ─── 回复内容 ───                   │
│ Claude 回复的文本内容              │
├────────────────────────────────────┤
│ [重试 ▶]                           │
└────────────────────────────────────┘
```

- **会话名称**: `<input>` 可编辑，失焦自动保存（`PATCH /projects/{id}`）
- **删除**: `🗑` 按钮 → 确认 → `DELETE /projects/{id}` → 同时删 DB + JSONL
- **重试**: 仅 `status === failed` 时显示 → `POST /continue/{id}`

### 3.4 数据流

```
用户填写 form.user + form.dir
       │
       ▼
  watch 触发
       │
       ▼
  loadProjectForDir(user, dir)
       │
       ├── 找到 → 加载到右侧卡片
       └── 没找到 → 空面板
       │
       ▼
  用户发送 → api.sendChat(user, dir, message)
       │
       ▼
  更新 claude_result（完整 JSON）
       │
       ▼
  刷新列表 + 重绘头像
```

### 3.5 API 封装（api.js）

```js
const API = 'http://localhost:8112'

// 基础
getHealth()              → GET /health
getUsers()               → GET /users
getProjects(user_id?)    → GET /projects
getProject(id)           → GET /projects/{id}

// 操作
sendChat(user, dir, message)  → POST /chat
continueProject(id)           → POST /continue/{id}
updateProject(id, fields)     → PATCH /projects/{id}
deleteProject(id)             → DELETE /projects/{id}

// 兼容旧名
getSessions(limit)           → GET /sessions?limit=50
```

### 3.6 像素头像

- Canvas 绘制，40x40px
- 种子: `project.folder_path`
- `image-rendering: pixelated`

### 3.7 样式

- **主题**: 深色科技风
- **背景**: `#0a0a1a` / `#111128` / `#1a1a3e`
- **主色**: `#7c3aed` 紫色光效
- **状态**: 绿=`#22c55e`，红=`#ef4444`
- **字体**: 等宽字体
- **背景**: CSS grid 紫色透明线

---

## 四、实施计划

### 第一阶段：数据库重构

1. **重写 db.py** — 删除 session 表，project 表新增 `claude_result TEXT` 字段
2. **迁移旧数据** — 将现有 session 数据迁移到 project 表（`claude_result` 存完整 JSON）
3. **更新索引** — 新增 `idx_project_session`、`idx_project_updated`

### 第二阶段：后端 API 适配

4. **server.py** — 所有 session 相关路由改为 project 操作
5. **POST /chat** — 返回完整 `claude_result` JSON
6. **PATCH /projects/{id}** — 更新名称、头像
7. **DELETE /projects/{id}** — DB + JSONL 双删
8. **POST /continue/{id}** — resume 项目

### 第三阶段：前端适配

9. **api.js** — 路由重命名（session → project）
10. **App.vue** — 数据结构适配，`claude_result` 中抽取子字段
11. **头像绘制** — 统一用 folder_path 作为种子

### 第四阶段：验证

12. 测试发送消息 → 完整 JSON 存入 `claude_result`
13. 测试重命名/删除/重试
14. 测试 Claude JSONL 文件同步删除

---

## 五、claude_result JSON 提取参考

前端/后端常用子字段提取：

| 字段 | SQL 提取 | 说明 |
|---|---|---|
| session_id | `json_extract(claude_result, '$.session_id')` | Claude 会话 ID，用于 resume |
| uuid | `json_extract(claude_result, '$.uuid')` | 每次消息的 UUID |
| output | `json_extract(claude_result, '$.result')` | AI 回复文本 |
| status | 从 subtype/is_error 推导 | success/failed |
| cost | `json_extract(claude_result, '$.total_cost_usd')` | 花费（美元） |
| num_turns | `json_extract(claude_result, '$.num_turns')` | 工具调用轮次 |
| model | `json_extract(claude_result, '$.modelUsage')` | 使用模型信息 |
| usage | `json_extract(claude_result, '$.usage')` | token 用量统计 |
| errors | `json_extract(claude_result, '$.errors')` | 错误信息数组 |
| terminal_reason | `json_extract(claude_result, '$.terminal_reason')` | completed/max_turns |

---

## 六、关键变更总结

| 变更 | 旧方案 | 新方案 |
|---|---|---|
| 表数量 | 3 张（user + project + session） | **2 张（user + project）** |
| 回复存储 | `model_response TEXT` 仅预览 | `claude_result TEXT` 完整 JSON |
| session 独立表 | 有 | **无**，session 合并到 project |
| 每次交互 | 新建 session 记录 | 更新同一条 project 记录 |
| 字段提取 | 直接读列 | `json_extract()` 或后端抽取 |
| 删除逻辑 | DELETE session + JSONL | DELETE project + JSONL |
