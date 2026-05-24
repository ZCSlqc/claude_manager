# claude CLI 命令完整入参 — 实测记录

> 测试工具：`claude-2.1.138.4ba`
> 测试目录：`/data/openclaw/test/111`
> 测试模型：`qwen3.6-35b-a3b`
> 所有测试均加 `--dangerously-skip-permissions` 跳过权限、`-p --output-format json` 输出 JSON
> 实测中 stderr 警告会混入 stdout，需 `2>/dev/null` 纯捕获 stdout

---

## 一、会话核心参数

### 1.1 新建会话（无需参数）

```bash
cd /data/openclaw/test/111
claude --dangerously-skip-permissions -p --output-format json --max-turns 1 "测试" 2>/dev/null > result.json
```

**行为**：
- 无需 `-c`、`--session-id`、`--resume` 任何 session 参数
- 自动在 `~/.claude/projects/<dir>/` 下生成 `{session_id}.jsonl`
- JSONL 文件名 = `session_id`，不是 `uuid`
- 返回 JSON 包含 `session_id` 和 `uuid`，两者不同
- 每个请求返回的 `uuid` 都不同（代表当次推理的 UUID），`session_id` 保持不变

**实测返回**（`session_id: 9aec9b53-...`）：
```json
{
  "type":"result","subtype":"success","is_error":false,
  "num_turns":2,
  "session_id":"9aec9b53-d980-459f-884a-52d492c78237",
  "uuid":"fd240d35-3e97-4e50-b23b-f835d3118278",
  "result":"...","total_cost_usd":0.134885
}
```

**JSONL 内容**：
- 文件名：`~/.claude/projects/-data-openclaw-test-111/9aec9b53-d980-459f-884a-52d492c78237.jsonl`
- 格式：每行一个 JSON 对象（JSONL）
- 类型：`queue-operation`（入队/出队）、`user`（用户消息）、`assistant`（AI 回复）、`last-prompt`（最后消息）
- resume 后 JSONL 会追加新记录

### 1.2 Resume 会话

```bash
claude --dangerously-skip-permissions -p --output-format json --resume <session_id> "继续" 2>/dev/null > result.json
```

**实测**：
- `--resume <session_id>` ✅ 可以 resume
- `--resume <uuid>` ❌ 不行，uuid 会报 "No conversation found"
- resume 后返回的 JSON 中 `session_id` 不变，`uuid` 变（每次消息的 UUID）
- JSONL 文件追加新行（从 11 行 → 更多行）
- 上下文自动加载（知道之前聊过什么）

### 1.3 Fork 会话（分叉）

```bash
claude --dangerously-skip-permissions -p --output-format json --fork-session --resume <session_id> "分叉" 2>/dev/null > result.json
```

**实测**：
- `--fork-session` 必须配合 `--resume`
- 生成**新的** `session_id`，旧的不影响
- 上下文继承（从分叉前的会话状态开始）
- 旧 JSONL 不追加，新 `session_id` 生成新 JSONL 文件

### 1.4 新开会话（/new）

```bash
claude --dangerously-skip-permissions -p --output-format json --resume <session_id> "/new" 2>/dev/null > result.json
```

**实测**：
- 在同目录创建新 session，`session_id` 变为新值
- `result` 为空字符串，`num_turns=0`
- 新 JSONL 文件生成，内容含 `<command-name>/clear</command-name>`
- 相当于在旧会话基础上"清空上下文"

### 1.5 Continue 最近会话

```bash
claude -c --dangerously-skip-permissions -p --output-format json "你好" 2>/dev/null > result.json
```

- `-c, --continue`：在当前目录继续最近一次会话
- 不需要指定 `--resume`

---

## 二、控制参数

### 2.1 --max-turns（隐藏参数，不在 --help 中）

```bash
claude --dangerously-skip-permissions -p --output-format json --max-turns 1 "杭州今天天气怎么样" 2>/dev/null
```

**实测**：
- `--max-turns 1`：限制工具调用轮次为 1
- 返回 `is_error: true, subtype: "error_max_turns", terminal_reason: "max_turns"`
- `num_turns: 2`（1 轮用户 + 1 轮 AI 回复）
- 有 `errors` 字段：`["Reached maximum number of turns (1)"]`
- `--max-turns 10`：正常使用，`num_turns` 可达 6，`terminal_reason: "completed"`

**注意**：不在 `--help` 输出中，是隐藏参数。

### 2.2 --effort

```bash
claude --dangerously-skip-permissions -p --output-format json --effort low "1+1" 2>/dev/null
```

**可选值**：`low`, `medium`, `high`, `xhigh`, `max`

**实测**（`--effort low`）：
- 简单问题快速返回，`1+1=2`
- `num_turns: 1`（1 轮即完成）
- effort 越高，AI 思考越深入、token 消耗越大

### 2.3 --max-budget-usd

```bash
claude --dangerously-skip-permissions -p --output-format json --max-budget-usd 1 "你好" 2>/dev/null
```

- 限制本次 API 调用总花费（美元）
- 超过则中断

### 2.4 --model

```bash
claude --dangerously-skip-permissions -p --output-format json --model sonnet "你好" 2>/dev/null
```

- 指定模型，如 `sonnet`、`opus`、`claude-sonnet-4-6`
- 不指定则用默认模型

### 2.5 --tools / --allowedTools / --disallowedTools

```bash
claude --dangerously-skip-permissions -p --output-format json --tools Bash,Edit,Read "你好" 2>/dev/null
```

**实测**：
- `--tools ""`（禁用所有工具）❌ **报错**：`Input must be provided either through stdin or as a prompt argument when using --print`
- `--tools default` ❌ 同样报错
- `--tools Bash`（只允许 Bash）❌ 同样报错
- `--tools Read,Bash` ❌ 同样报错

> **结论**：当前版本（`2.1.138.4ba`）`--tools` 参数有 bug，会吞掉 prompt。不要使用。

```bash
claude --dangerously-skip-permissions -p --output-format json --allowedTools Read "你是谁" 2>/dev/null
```

**实测**：❌ 同样报错 `Input must be provided either through stdin or as a prompt argument`

```bash
claude --dangerously-skip-permissions -p --output-format json --permission-mode bypassPermissions "1+1" 2>/dev/null
```

**实测**：✅ 可用 — `--permission-mode bypassPermissions` 替代 `--dangerously-skip-permissions`
- 可选值：`default`、`acceptEdits`、`auto`、`bypassPermissions`、`dontAsk`、`plan`

**工具名称语法**（官方文档，待后续版本验证）：
```
Read                    # 所有文件读取
Edit                    # 文件编辑（已存在文件）
Write                   # 文件创建（新建文件）
Bash                    # 所有 shell 命令
Bash(git *)             # 仅 git 命令
Bash(npm run lint:*)    # 通配符匹配
WebSearch               # 网页搜索
WebFetch                # 网页抓取
mcp__<server>__<tool>   # 特定 MCP 工具
```

### 2.6 --system-prompt

```bash
claude --dangerously-skip-permissions -p --output-format json --system-prompt "你是一个助手" "你好" 2>/dev/null
```

- 自定义系统提示

### 2.7 --no-session-persistence

```bash
claude --dangerously-skip-permissions -p --output-format json --no-session-persistence "你好" 2>/dev/null
```

- 不持久化到 JSONL，用完即丢弃
- 不能 resume

### 2.8 --bare（最小模式）

```bash
claude --dangerously-skip-permissions --bare -p --output-format json "你是谁" 2>/dev/null
```

**实测**：✅ 可用
- 跳过 hooks、LSP、plugin sync、attribution、auto-memory、background prefetches、keychain、CLAUDE.md
- 设置 `CLAUDE_CODE_SIMPLE=1`
- 启动速度更快
- OAuth 和 keychain 不读取（API key 用户：用 `ANTHROPIC_API_KEY` 或 `--settings`）
- Skills 仍可通过 `/skill-name` 调用
- 如需上下文：手动传 `--system-prompt[-file]`、`--add-dir`、`--mcp-config`、`--agents`、`--plugin-dir`

### 2.9 --fallback-model

```bash
claude --dangerously-skip-permissions -p --output-format json --fallback-model haiku "1+1" 2>/dev/null
```

**实测**：✅ 可用
- 默认模型过载时自动 fallback 到指定模型
- 仅 `--print` 模式有效
- 实测花费 `$0.13`（与正常模式相同模型）

### 2.10 --name

```bash
claude --dangerously-skip-permissions --name "test-name-01" -p --output-format json "1+1" 2>/dev/null
```

**实测**：✅ 可用
- 设置会话显示名称（显示在 prompt box、`/resume` 选择器、终端标题中）
- 不影响功能，仅展示用途

### 2.11 --no-chrome

```bash
claude --dangerously-skip-permissions --no-chrome -p --output-format json "1+1" 2>/dev/null
```

**实测**：✅ 可用
- 禁用 Chrome 浏览器集成

### 2.12 --agent

```bash
claude --dangerously-skip-permissions -p --output-format json --agent sonnet "你好" 2>/dev/null
```

- 指定当前会话使用的 agent（覆盖 `agent` 设置）

### 2.13 --worktree

```bash
claude --dangerously-skip-permissions -p --output-format json --worktree my-branch "1+1" 2>/dev/null
```

**实测**：✅ 可用（需在 git 仓库中）
- 在临时 git worktree 中运行，不影响当前分支
- 非 git 目录会报错

### 2.14 --verbose

```bash
claude --dangerously-skip-permissions -p --output-format json --verbose "1+1" 2>/dev/null
```

**实测**：✅ 可用
- 返回 JSON 数组而非单个对象
- 首个元素含 system/init 信息，最后一个元素是最终结果

### 2.15 --output-format stream-json

```bash
claude --dangerously-skip-permissions -p --output-format stream-json "1+1" 2>/dev/null
```

**实测**：❌ 单独使用报错，需配合 `--verbose`

---

## 三、Session 管理

### 3.1 删除 JSONL（关闭 session）

CLI 无 `--close`、`--kill`、`--end` 参数。

```bash
rm ~/.claude/projects/<dir>/<session_id>.jsonl
```

删除后该 session_id 被废弃，后续 resume 会报错。

### 3.2 批量清理

```bash
claude project purge /data/openclaw/test/111 --yes    # 清理特定项目
claude project purge --all --yes                      # 清理所有项目
claude project purge --dry-run                        # 预览（不删除）
```

会删除 transcript、tasks、file history、config entry。

### 3.3 Session 字段对照

| 字段 | 含义 | 用途 |
|---|---|---|
| `session_id` | 会话唯一 ID | **resume 必须用此字段** |
| `uuid` | 每次消息的 UUID | 每次请求不同，不用于 resume |
| `num_turns` | 工具调用轮次 | `--max-turns` 限制此值 |
| `terminal_reason` | 终止原因 | `"completed"` / `"max_turns"` |
| `is_error` | 是否出错 | `true` 表示异常终止 |

---

## 四、完整命令模板

### 新建 + resume + fork 完整流程

```bash
# Step 1: 新建会话
cd /data/openclaw/test/111
claude --dangerously-skip-permissions -p --output-format json --max-turns 1 "你好" 2>/dev/null > /tmp/t1.json
# → 提取 session_id: eg. 9aec9b53-d980-459f-884a-52d492c78237

# Step 2: Resume 继续对话
claude --dangerously-skip-permissions -p --output-format json --resume 9aec9b53-d980-459f-884a-52d492c78237 "继续" 2>/dev/null > /tmp/t2.json
# → session_id 不变，uuid 变化，JSONL 追加

# Step 3: Fork 创建新分支
claude --dangerously-skip-permissions -p --output-format json --fork-session --resume 9aec9b53-d980-459f-884a-52d492c78237 "新话题" 2>/dev/null > /tmp/t3.json
# → 生成新 session_id，旧的不影响

# Step 4: 清除上下文（/new）
claude --dangerously-skip-permissions -p --output-format json --resume 9aec9b53-d980-459f-884a-52d492c78237 "/new" 2>/dev/null > /tmp/t4.json
# → 新 session_id，空 result，num_turns=0
```

### 推荐的服务调用模板

```bash
# 新建会话
claude --dangerously-skip-permissions -p --output-format json --max-turns 10 "消息内容" 2>/dev/null

# Resume（用 session_id，不是 uuid）
claude --dangerously-skip-permissions -p --output-format json --resume <session_id> "继续" 2>/dev/null

# Fork（分叉出新会话，保留旧的）
claude --dangerously-skip-permissions -p --output-format json --fork-session --resume <session_id> "新话题" 2>/dev/null

# /new（清除上下文）
claude --dangerously-skip-permissions -p --output-format json --resume <session_id> "/new" 2>/dev/null
```

---

## 五、JSONL 文件结构

```
~/.claude/projects/<project_dir>/<session_id>.jsonl
```

每行格式：
```json
{
  "type": "queue-operation|user|assistant|system|last-prompt",
  "sessionId": "...",           // session_id
  "uuid": "...",               // 当次推理 UUID
  "timestamp": "2026-05-17T...",
  "cwd": "/data/openclaw/test/111",
  "version": "2.1.138.4ba",
  "gitBranch": "HEAD",
  ...
}
```

- `type: queue-operation` — 入队/出队操作
- `type: user` — 用户消息
- `type: assistant` — AI 回复（含 `role: "assistant"`, `content`）
- `type: system` — 系统消息
- `type: last-prompt` — 标记最后一条消息（`leafUuid`）

---

## 六、斜杠命令（Slash Commands）

在 claude 交互界面中直接输入 `/xxx` 回车触发。通过 `消息内容` 传 `/xxx`。

### 6.1 会话管理

| 命令 | 命令示例 | 实测结果 | 说明 |
|---|---|---|---|
| `/new` | `"/new"` | ✅ 可用 | 同 `--resume <id> /new`，创建新 session，`num_turns=0`，空 result |
| `/clear` | `"/clear"` | ✅ 可用 | 清空当前会话上下文，不生成新 session，空 result，`num_turns=0` |
| `/compact` | `"/compact"` | ✅ 可用 | 压缩上下文，减少 token，避免超限。空 result，`num_turns=0` |
| `/branch` | `"/branch"` | ❌ 不可用 | 当前环境不支持 |
| `/resume` | `"/resume"` | ❌ 不可用 | 当前环境不支持 |
| `/rewind` | `"/rewind"` | ❌ 不可用 | 当前环境不支持 |

### 6.2 模型 / 显示

| 命令 | 命令示例 | 实测结果 | 说明 |
|---|---|---|---|
| `/model` | `"/model"` | ❌ 不可用 | 当前环境不支持（CLI 用 `--model` 参数） |
| `/context` | `"/context"` | ✅ 可用 | 显示当前 token 用量 / 剩余空间，返回详细用量报告 |

**`/context` 实测返回示例**：
```
## Context Usage
**Model:** qwen3.6-35b-a3b
**Tokens:** 27.6k / 200k (14%)

### Estimated usage by category
| Category | Tokens | Percentage |
|----------|--------|------------|
| System prompt | 6.1k | 3.1% |
| System tools | 17.9k | 9.0% |
| Custom agents | 1.8k | 0.9% |
| Memory files | 94 | 0.0% |
| Skills | 1.7k | 0.8% |
| Messages | 59 | 0.0% |
| Free space | 139.4k | 69.7% |
| Autocompact buffer | 33k | 16.5% |
```

### 6.3 信息 / 统计

| 命令 | 命令示例 | 实测结果 | 说明 |
|---|---|---|---|
| `/status` | `"/status"` | ❌ 不可用 | 当前环境不支持 |
| `/usage` | `"/usage"` | ✅ 可用 | 返回本次花费、token 统计（与 `/cost`、`/stats` 相同输出） |
| `/cost` | `"/cost"` | ✅ 可用 | 返回本次花费、token 统计 |
| `/stats` | `"/stats"` | ✅ 可用 | 同 `/cost`、`/usage` |

**`/cost` / `/usage` / `/stats` 实测返回**：
```
Total cost:            $0.0000
Total duration (API):  0s
Total duration (wall): 0s
Total code changes:    0 lines added, 0 lines removed
Usage:                 0 input, 0 output, 0 cache read, 0 cache write
```

> `/cost`、`/usage`、`/stats` 三者输出完全相同。

### 6.4 项目 / 记忆

| 命令 | 命令示例 | 实测结果 | 说明 |
|---|---|---|---|
| `/init` | `"/init"` | ✅ 可用 | 生成 CLAUDE.md 项目级记忆文件，消耗 5 turns，~$0.7 |
| `/memory` | `"/memory"` | ❌ 不可用 | 当前环境不支持 |

**`/init` 实测**：
- `num_turns=5`，耗时 ~9s，花费 `$0.71`
- 在项目中创建 `CLAUDE.md` 文件
- 空项目会生成最小化模板，说明当前项目状态

### 6.5 工具类

| 命令 | 命令示例 | 实测结果 | 说明 |
|---|---|---|---|
| `/diff` | `"/diff"` | ❌ 不可用 | 当前环境不支持（无 git 仓库） |
| `/terminal-setup` | `"/terminal-setup"` | ❌ 不可用 | 当前环境不支持 |

### 6.6 其他不可用命令汇总

以下命令在当前环境（`claude-2.1.138.4ba`，无 GUI）中均返回 `<name> isn't available in this environment`：

| 命令 | 命令 | 命令 |
|---|---|---|
| `/status` | `/help` | `/model` |
| `/memory` | `/branch` | `/resume` |
| `/rewind` | `/diff` | `/terminal-setup` |

> **结论**：当前环境仅支持 `/new`、`/clear`、`/compact`、`/context`、`/cost`、`/usage`、`/stats`、`/init` 共 8 个斜杠命令。
> 其余命令需要交互式 GUI 环境（Claude Desktop 等）才可用。

---

## 七、CLI 子命令

### 7.1 认证管理

```bash
claude auth login                   # 登录（浏览器 OAuth for Pro/Max，或设置 ANTHROPIC_API_KEY）
claude auth login --console         # API key 计费
claude auth login --sso             # Enterprise SSO
claude auth status                  # 登录状态（JSON 输出）
claude auth status --text           # 登录状态（人类可读）
claude setup-token                  # 设置长期认证 token（需订阅）
```

### 7.2 服务器管理

```bash
claude mcp add <name> -- <cmd>      # 添加 MCP 服务器
claude mcp list                     # 列出已配置 MCP 服务器
claude mcp remove <name>            # 移除 MCP 服务器

claude agents                       # 列出已配置 agents
claude plugin                       # 管理插件
```

### 7.3 项目 / 健康

```bash
claude doctor                       # 检查自动更新器和安装健康
claude update                       # 检查并安装更新
claude upgrade                      # 同上
claude install [target]             # 安装原生构建（stable/latest/指定版本）
claude auto-mode                    # 检查 auto mode 分类器配置
```

### 7.4 项目清理

```bash
claude project purge /path --yes    # 清理特定项目（删除 transcript、tasks、file history、config）
claude project purge --all --yes    # 清理所有项目
claude project purge --dry-run      # 预览（不删除）
```

### 7.5 远程控制

```bash
claude remote-control [name]        # 启动远程控制会话（通过 claude.ai 或 mobile app 控制）
```

### 7.6 PR 审核

```bash
claude ultrareview --branch feature  # 云托管多 agent 代码审核
```

### 7.7 子命令对照表

| 子命令 | 用途 | 实测验证 |
|---|---|---|
| `auth login` | 登录认证 | 需浏览器 |
| `auth status` | 查看登录状态 | JSON 输出 |
| `mcp add/list/remove` | MCP 服务器管理 | 见下方 |
| `agents` | 列出 agents | — |
| `doctor` | 健康检查 | — |
| `update/upgrade` | 更新 | — |
| `install` | 安装原生构建 | — |
| `project purge` | 清理项目状态 | 已实测 |
| `remote-control` | 远程控制 | — |
| `ultrareview` | 多 agent 代码审核 | — |
| `auto-mode` | 检查 auto mode | — |
| `plugin` | 管理插件 | — |
| `setup-token` | 设置长期 token | — |

---

## 八、关键发现总结

1. **`--max-turns` 存在但不在 `--help` 中** — 隐藏参数
2. **Resume 必须用 `session_id`** — `uuid`（每次消息的 UUID）不能 resume
3. **每次返回的 `uuid` 都不同** — 每次消息的 UUID，不是 session 级别
4. **JSONL 文件名 = `session_id`** — 不是 `uuid`
5. **`-c` 等于 `--continue`** — 继续当前目录最近会话
6. **`/new` 可以清除上下文** — 在同目录下创建新 session
7. **`--fork-session` 可以分叉** — 保留旧 session 不影响
8. **无关闭/终止 session 的 CLI 参数** — 只能删 JSONL 文件
9. **JSONL 追加写入** — resume 后追加新行
10. **`effort` 影响 AI 深度** — `low` 快速简单，`max` 深入分析
11. **斜杠命令部分可用** — 当前环境仅 8 个可用（`/new`、`/clear`、`/compact`、`/context`、`/cost`、`/usage`、`/stats`、`/init`），其余需 GUI 环境
12. **`--tools` / `--allowedTools` 在当前版本有 bug** — 会吞掉 prompt，报 "Input must be provided"，不可用（`2.1.138.4ba`）
13. **`--bare` 可用** — 最小模式，跳过 hooks/plugins/MCP/CLAUDE.md，启动更快
14. **`--fallback-model` 可用** — 默认模型过载时自动 fallback
15. **`--name` 可用** — 设置会话显示名称
16. **`--verbose` 返回 JSON 数组** — 非单个 JSON 对象，首个元素含 system/init 信息
17. **`stream-json` 需要 `--verbose`** — 单独用 `--output-format stream-json` 会报错
18. **`--permission-mode bypassPermissions`** — 可替代 `--dangerously-skip-permissions`
19. **`--worktree` 需在 git 仓库中** — 非 git 目录会报错
20. **`--add-dir` 在当前版本有 bug** — 同 `--tools`，会吞掉 prompt
