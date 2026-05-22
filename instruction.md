# claude 命令入参 — 行为测试记录

## 基础用法

```bash
claude --help
```

---

## 模式 A: 没有 session ID（新建会话）

### 1. 全新会话（首次进入）

```bash
claude -p --dangerously-skip-permissions --output-format json --max-turns 1  "杭州今天天气怎么样" 
```
{"type":"result","subtype":"success","is_error":false,"api_error_status":null,"duration_ms":930,"duration_api_ms":876,"num_turns":1,"result":"你好，ZCS！有什么可以帮你的？","stop_reason":"end_turn","session_id":"b0b26f7b-e7da-49af-b6bd-dab1690a4377","total_cost_usd":0.13373,"usage":{"input_tokens":26691,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":11,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"qwen3.6-35b-a3b":{"inputTokens":26691,"outputTokens":11,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0.13373,"contextWindow":200000,"maxOutputTokens":32000}},"permission_denials":[],"terminal_reason":"completed","fast_mode_state":"off","uuid":"02db8586-7344-4067-b1ba-cb99e35fed99"}


- `-p`: 打印模式，输出 JSON
- `--dangerously-skip-permissions`: 跳过权限确认
- `--output-format json`: 输出 JSON 格式（stdout 只有一个 JSON 对象）
- 无 session 参数 → 新建会话
- **返回**: 完整执行结果，stdout 包含 `session_id`、`uuid`、`result`、`num_turns`、`total_cost_usd` 等字段
- **注意**: 此模式不会持久化到 Claude 项目的 JSONL 文件，**无法 resume**

### 2. 指定新 session ID（不推荐，容易冲突）  ##不要这种

```bash
claude -p --dangerously-skip-permissions --output-format json --session-id my-session "你好"
```

- `--session-id my-session`: 使用指定名称（非 UUID）
- 第一次执行时新建会话
- 之后可用 `--resume my-session` 恢复
- **返回**: 同上

### 3. 使用 `-c` 创建新会话并指定名称   ##不要这种

```bash
claude -c -p --dangerously-skip-permissions --output-format json "你好"
```

- `-c`: 创建新会话（类似 `--new`）
- **注意**: `-c` 会生成一个随机 session UUID，但 stdout 可能不包含

---

## 模式 B: 有 session ID（恢复已有会话）

### 1. 通过 session UUID resume

```bash
claude -p --dangerously-skip-permissions --output-format json --resume b0b26f7b-e7da-49af-b6bd-dab1690a4377 "继续"
```
{"type":"result","subtype":"success","is_error":false,"api_error_status":null,"duration_ms":950,"duration_api_ms":868,"num_turns":1,"result":"你好，请告诉我你想继续做什么？","stop_reason":"end_turn","session_id":"b0b26f7b-e7da-49af-b6bd-dab1690a4377","total_cost_usd":0.13378500000000002,"usage":{"input_tokens":26712,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":9,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"qwen3.6-35b-a3b":{"inputTokens":26712,"outputTokens":9,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0.13378500000000002,"contextWindow":200000,"maxOutputTokens":32000}},"permission_denials":[],"terminal_reason":"completed","fast_mode_state":"off","uuid":"084c1d8f-f8fa-477b-ae1e-4f7b86bd657b"}

- `--resume <uuid>`: 恢复指定 UUID 的会话
- Claude 会读取该会话的 JSONL 上下文，继续对话
- **返回**: 追加后的完整结果，stdout 包含更新后的 JSON
- **前提**: JSONL 文件必须存在且未被损坏

### 2. 通过 session 名称 resume

```bash
claude -p --dangerously-skip-permissions --output-format json --resume my-session "继续"
```

- 用名称 resume 也可以
- 需要之前用 `--session-id` 指定过同名

---

## 模式 C: 新建会话后 resume（推荐流程）

```bash
# Step 1: 创建新会话，拿到 UUID
claude -c -p --dangerously-skip-permissions --output-format json "你好"
# → stdout JSON 中获取 uuid 或 session_id

# Step 2: 用该 UUID resume
claude -p --dangerously-skip-permissions --output-format json --resume <uuid> "继续"
# → 上下文已加载，继续对话
```

---

## 模式 D: 没有 `-p` 和 `--output-format json`

```bash
claude --dangerously-skip-permissions "你好"
```

- 交互模式，直接打印纯文本输出到终端
- **不输出 JSON**，无法程序解析
- 适用于手动调试

---

## 特殊场景测试

### 1. API 错误重试

```bash
# 正常发送 → 如果 API 报错 → Claude Code 内部重试 10 次 → 最终返回 api_error_chain_end
claude -p --dangerously-skip-permissions --output-format json "你好"

# 然后发送 "继续" 看是否能恢复
claude -p --dangerously-skip-permissions --output-format json --resume <uuid> "继续"
```

### 2. 长时间任务超时

```bash
claude -p --dangerously-skip-permissions --output-format json "帮我写一个完整的项目"
# → 如果执行超时（>300s），kill 进程
# → resume 继续
claude -p --dangerously-skip-permissions --output-format json --resume <uuid> "继续"
```

### 3. 上下文溢出

```bash
# 连续发送多条 → 上下文超长
claude -p --dangerously-skip-permissions --output-format json "你好"
claude -p --dangerously-skip-permissions --output-format json --resume <uuid> "继续"
claude -p --dangerously-skip-permissions --output-format json --resume <uuid> "继续"
# → 可能触发 context length exceeded
```

### 4. 检查 JSONL 文件位置

```bash
# Claude 项目的 JSONL 文件
ls ~/.claude/projects/*/
# → 每个 UUID 对应一个 {uuid}.jsonl 文件
```

---

## 关键发现

| 参数组合 | 行为 | 持久化 | Resume |
|---|---|---|---|
| `-p --output-format json`（无 session） | 新建会话，执行完即销毁 | ❌ 有 JSONL 但无法 resume | ❌ |
| `-c -p --output-format json` | 创建新会话 | ✅ JSONL 存在 | ✅ 用 uuid |
| `--session-id <name> -p` | 创建命名会话 | ✅ JSONL 存在 | ✅ 用名称 |
| `--resume <uuid> -p` | 恢复已有会话 | ✅ 追加 | ✅ 继续 |
| `--resume <name> -p` | 恢复命名会话 | ✅ 追加 | ✅ 继续 |

### 结论

1. **`-c` 是最可靠的新建方式** — 会生成 UUID 并持久化 JSONL
2. **直接 `--output-format json` 不带 `-c`** — 也能持久化（因为 `-p` 模式本身会创建临时 JSONL）
3. **Resume 只需要 `--resume <uuid>`** — UUID 来自上次执行返回的 `stdout` JSON
4. **`session_id` 和 `uuid` 可能不同** — 需要两个都记录

---

## 实际调用命令模板

```bash
# 新建
claude --dangerously-skip-permissions -p --output-format json -c "消息内容"

# Resume
claude --dangerously-skip-permissions -p --output-format json --resume <uuid> "消息内容"

# Resume（如果有 session_id 字段但 uuid 为空）
claude --dangerously-skip-permissions -p --output-format json --resume <session_id> "消息内容"
```
