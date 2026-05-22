# Claude Code JSONL 理解文档

## 1. 文件系统组织结构

```
~/.claude/projects/
├── {project_name}/                    # 按工作目录名划分的项目目录
│   ├── {session-uuid}.jsonl           # 主 session 对话历史
│   └── {parent-uuid}/subagents/       # 子 Agent 会话（仅主 session 下）
│       └── agent-{agent-uuid}.jsonl   # 子 Agent 的独立对话
```

**规则**：
- 文件名中的 UUID stem 以 8 位十六进制开头（`int(uuid[:8], 16)`），用于标识合法 session
- `history.jsonl` 是 Claude Code 内部文件，**代理不处理**
- `subagents/*.jsonl` 是 Claude Agent 内部文件，**代理不扫描**（`d.glob('*.jsonl')` 不递归）

## 2. JSONL 条目类型

每个 `.jsonl` 文件是一系列 JSON 对象的逐行文本。按功能分为四类：

### 2.1 对话条目（代理关心）

| 类型 | `type` | 说明 | 关键内容 |
|------|--------|------|----------|
| **用户** | `user` | 用户输入或工具返回结果 | `message.content` — 字符串或 `tool_result` 列表 |
| **助手** | `assistant` | Claude 回复 | `message.content` — 文本块 + `tool_use` 块 |

**用户条目类型**（3 种）：

**类型 A — 纯文本输入**（`message.content` 为字符串）：
```json
{
  "parentUuid": null,
  "isSidechain": false,
  "promptId": "d6976792-...",
  "type": "user",
  "message": { "role": "user", "content": "列出当前目录下所有.py文件" },
  "uuid": "d6624b29-...",
  "timestamp": "2026-05-15T05:56:25Z"
}
```

**类型 B — 工具返回结果**（`message.content` 为列表，含 `tool_result`）：
```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "tool_use_id": "call_abc123",
        "type": "tool_result",
        "content": "  2 /path/to/a.py\n  1 /path/to/b.py",
        "is_error": false
      }
    ]
  },
  "uuid": "bbc34a69-..."
}
```
`tool_result` 字段：`type` | `tool_use_id` | `content` | `is_error`

**类型 C — 工具调用失败**（`is_error: true`）：
```json
{
  "type": "user",
  "message": {
    "content": [
      {
        "tool_use_id": "call_f8c4fa...",
        "type": "tool_result",
        "content": "<tool_use_error>Directory does not exist: /data/openclaw/claude-manager/test-dir...",
        "is_error": true
      }
    ]
  }
}
```

**助手条目类型**（2 种，`message.content` 始终为列表）：

**类型 A — 纯文本回复**（`stop_reason: "end_turn"`，本轮结束）：
```json
{
  "parentUuid": "e91182ea-...",
  "type": "assistant",
  "message": {
    "role": "assistant",
    "content": [
      { "type": "text", "text": "当前目录下共有 **9** 个 `.py` 文件，统计如下：..." }
    ],
    "stop_reason": "end_turn"
  }
}
```

**类型 B — 工具调用**（`stop_reason: "tool_use"`，等待工具返回）：
```json
{
  "parentUuid": "d6624b29-...",
  "type": "assistant",
  "message": {
    "role": "assistant",
    "content": [
      { "type": "tool_use", "name": "Glob", "input": { "pattern": "*.py" } }
    ],
    "stop_reason": "tool_use"
  }
}
```

**对话轮次完整周期**：
```
user (文本输入) → assistant (tool_use) → user (tool_result) → assistant (tool_use) → user (tool_result) → assistant (end_turn)
```

### 2.2 系统条目（代理需要跳过）

**`api_error`** — Claude 后端 500 错误（重试链中的单条）：
```json
{
  "parentUuid": "e0ffa6b8-...",
  "type": "system",
  "subtype": "api_error",
  "level": "error",
  "error": { "status": 500, "server": "uvicorn" },
  "retryInMs": 516, "retryAttempt": 1, "maxRetries": 10
}
```

**`turn_duration`** — 轮次耗时统计（`end_turn` 后插入）：
```json
{
  "parentUuid": "2f530bb0-...",
  "type": "system",
  "subtype": "turn_duration",
  "durationMs": 37129, "messageCount": 26
}
```

**`api_error_chain_end`** — API 重试耗尽后的最终返回（`type="assistant"`）：
```json
{
  "parentUuid": "b4c3f2cb-...",
  "type": "assistant",
  "message": {
    "content": [{ "type": "text", "text": "API Error: 500 Internal Server Error..." }],
    "stop_reason": "stop_sequence"
  },
  "error": "server_error",
  "isApiErrorMessage": true,
  "apiErrorStatus": 500
}
```

**`compact_boundary`** — 上下文压缩边界标记：
```json
{
  "type": "system",
  "subtype": "compact_boundary",
  "content": "Conversation compacted",
  "compactMetadata": { "trigger": "auto", "preTokens": 167247, "postTokens": 8418 },
  "level": "info"
}
```

**`informational`** — Claude Code 内部通知：
```json
{
  "type": "system",
  "subtype": "informational",
  "content": "Unknown command: /8552f0af...",
  "level": "warning"
}
```

### 2.3 元数据条目（代理不处理）

**`permission-mode`** — 权限模式配置：
```json
{ "type": "permission-mode", "permissionMode": "bypassPermissions", "sessionId": "..." }
```

**`ai-title`** — Claude 自动生成的会话标题：
```json
{ "type": "ai-title", "aiTitle": "Understand file content architecture", "sessionId": "..." }
```

**`last-prompt`** — 当前会话最后 prompt 信息：
```json
{
  "type": "last-prompt",
  "lastPrompt": "记住我叫张三",
  "leafUuid": "8843f05f-..."
}
```

**`queue-operation`** — 内部队列操作：
```json
{ "type": "queue-operation", "operation": "enqueue", "content": "记住我叫张三" }
```

**`attachment`** — 附加信息（如 skill listing）：
```json
{
  "type": "attachment",
  "attachment": { "type": "skill_listing", "skillCount": 27, "isInitial": true },
  "uuid": "2c011306-..."
}
```

**`file-history-snapshot`** — 文件历史快照：
```json
{
  "type": "file-history-snapshot",
  "messageId": "ce38aa84-...",
  "snapshot": { "messageId": "ce38aa84-...", "trackedFileBackups": {} }
}
```

### 2.4 常见工具名称（assistant → tool_use.name）

| 工具 | 说明 |
|------|------|
| `Bash` | 执行 shell 命令 |
| `Read` | 读取文件内容 |
| `Write` | 写入文件内容 |
| `Edit` | 编辑文件指定文本 |
| `Glob` | 文件模式匹配搜索 |
| `Agent` | 调用子 Agent |

## 3. 代理的 JSONL 监管机制

### 3.1 Session 查找

```
run_claude() 调用入口
├── 有 session_id → find_session_jsonl(session_uuid)
│   └── 遍历 ~/.claude/projects/*/ → 查找 {session_uuid}.jsonl
├── 只有 project_dir → find_project_jsonl(project_dir)
│   └── 遍历所有项目 → 扫描前 20 行匹配 cwd 字段
└── 都没有 → 使用 -c 创建新 session
```

**关键过滤**：
1. `int(uuid[:8], 16)` — 验证文件名是合法 UUID
2. 排除 `history.jsonl`
3. 排除 `subagents/*.jsonl`（`glob('*.jsonl')` 不递归）

### 3.2 错误检测（两层管道）

**如何保证读取的是最新内容？**

JSONL 是**追加写入**的。Claude Code 每次对话产生新条目时，直接 `jsonl.write(line + '\n')`。所以文件尾部始终对应最新的对话轮次。

`detect_errors_in_jsonl` 使用 `lines[-last_n:]`（默认 50 行），天然取的是最新内容。无需特殊标记。

> **关于 `last-prompt`**：它是一个元数据条目，`leafUuid` 指向当前对话树中的"叶子节点"（最后一条未回复的 user/system/attachment 消息），**不是**最后一条 assistant 消息。它本身不参与错误检测，仅用于 Claude Code 内部标记会话进度。

```
┌─────────────────────────────────────────────────────────────┐
│ 管道 1: subprocess 输出                                      │
│  ├─ stdout → _parse_claude_json() → 提取 result/session_id  │
│  └─ stderr → detect_errors_in_output() → 正则匹配           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 管道 2: 目标 JSONL 文件尾部 50 行                            │
│  ├─ 跳过 type=system（内部消息，不构成错误）                  │
│  ├─ 跳过 type=assistant（自然语言回复中的关键词不匹配）       │
│  ├─ 跳过 type=assistant with error（API 重试耗尽的最终返回，isApiErrorMessage=true）   │
│  └─ 仅检测 type=user 列表中的 tool_result.content → <tool_use_error> 字符串      │
└─────────────────────────────────────────────────────────────┘
                          ↓
              分类: ignorable / high / medium
```

**错误正则**：

| 错误类型 | 正则 | 严重级 | 处理 |
|----------|------|--------|------|
| `context_too_long` | `context length|token limit|max tokens|...` | high | 自动切新 session 重试 |
| `api_error` | `api[ _]?error|rate[ _]?limit|quota|5\d{2}` | high | 等待后重试 |
| `read_timeout` | `read[ _]?timeout|file[ _]?too[ _]?large` | high | 等待后重试 |
| `tool_error` | `<tool_use_error>` | medium | 报告但不重试 |
| `cwd_missing` | `Directory does not exist` | ignorable | 直接忽略 |

### 3.3 错误检测的排除规则

**为什么跳过 assistant 消息？**
- Claude 的回复是自然语言，可能讨论错误但不代表实际发生了错误
- 例如 assistant 回复"API 错误可能导致重试"，正则仍会匹配到 `api_error`/`500`
- 这会造成**误报**，导致调用者以为发生了 API 错误

**为什么跳过 system 消息？**
- `system api_error` 是 Claude Code **内部重试链**，不是代理需要处理的
- 每个 system 条目带 `retryAttempt`/`maxRetries`，是 Claude 自身在管理重试
- 代理不应干预 Claude 内部的重试机制
- 而且 system 条目链式引用（`parentUuid` 指向前一个），会膨胀 JSONL

**关于 `api_error_chain_end`：**
- API 重试 10 次耗尽后，Claude Code 以 `type="assistant"` 返回最终结果
- 带 `error: "server_error"`、`stop_reason: "stop_sequence"`、`content` 为错误文本
- `isApiErrorMessage: true` 标记可识别
- 代理应跳过此类条目，因为这是 Claude Code 处理完毕的最终结果，不是待处理的错误

## 4. 常见报错及阻断策略

### 4.1 高严重错误（自动重试）

```
错误 → 检测到 → retry → 策略
─────────────────────────────────────
context_too_long → 生成新 session UUID → --session-id 继续
api_error        → 指数延迟 (3s, 5s) → 同上
read_timeout     → 指数延迟 (3s, 5s) → 同上
```

**重试上限**：`max_retries + 1`（默认 2 次），超过后返回失败。

### 4.2 中等严重错误（报告不重试）

```
tool_error → 出现在 tool_result 中 → error_details 中列出 → success=True
cwd_missing → 出现在 stdout/stderr → IGNORABLE 列表 → 完全忽略
```

### 4.3 超时阻断

```
subprocess.Popen → communicate(timeout=300s)
  ↓ TimeoutExpired
  proc.kill() → proc.communicate()  ← 确保子进程被清理
  ↓ 重试逻辑
  max_retries 耗尽 → 返回失败
```

### 4.4 文件损坏保护

```
JSONL 读取 → OSError/UnicodeDecodeError → 返回空列表 []
JSONL 裁剪 → tempfile.mkstemp + os.replace → 原子写入，崩溃不丢数据
```

## 5. JSONL 文件大小管理

| 阈值 | 行为 |
|------|------|
| > 1MB | 触发 `trim_jsonl()` |
| 裁剪后保留 | 第 1 行 + 最后 500 行 |
| 写入方式 | 临时文件 → `os.replace()` 原子替换 |

## 6. 并发控制

| 场景 | 锁状态 |
|------|--------|
| `-c` + 无已有 session | 需要锁（`acquire_lock`） |
| 有 `session_id` | 不需锁（已关联 session） |
| 有 `new_session_uuid`（context_too_long 恢复） | 不需锁 |
| 有 `target_jsonl`（通过 project_dir 找到） | 不需锁（已有 session） |

锁机制：`fcntl.flock` + 指数退避（0.05s → 1.0s 上限）+ 30s 超时
