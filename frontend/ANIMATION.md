# Claude Code Proxy — 前端卡片动画方案

## 概述

前端项目 `claude_manager/frontend/` 实现了项目卡片的 FLIP 动画效果。用户发送消息后，卡片会平滑移动到新位置，其他卡片依次后移。

---

## 技术方案

### 1. 乐观更新 (Optimistic Update)

用户点击"发送"后，**不等后端响应**，立即在 `projects` 数组头部插入一个 loading 占位卡片：

```js
// src/App.vue — send() 函数
const optimisticId = 'optimistic-' + Date.now()
const optimisticCard = {
  project_id: optimisticId,       // 唯一 key
  folder_name: form.value.dir,
  is_finished: 0,
  _loading: true,                 // 标记为 loading
}
projects.value = [optimisticCard, ...projects.value]
```

- 占位卡片显示"发送中..." + 脉冲辉光动画
- 如果发送失败，移除占位卡片并提示错误
- 如果发送成功，调用 `refreshProjects()` 从后端拉全量数据

**为什么这样做？**
- Vue 3 的 `key` diff 机制：后端返回的真实数据与占位卡片 `project_id` 相同
- Vue 自动识别这是"同一个 item 的更新"而非删除+新增
- 触发 FLIP 动画，卡片从顶部平滑过渡到正确位置

### 2. TransitionGroup + FLIP 动画

用 Vue 内置的 `<TransitionGroup>` 包裹卡片列表：

```html
<TransitionGroup name="card-list" tag="div" class="project-grid">
  <div v-for="p in sortedProjects" :key="p.project_id" class="project-thumb">
    ...
  </div>
</TransitionGroup>
```

**CSS 动画规则**（`src/App.vue`）：

| 类名 | 作用 | 时长 | 效果 |
|---|---|---|---|
| `.card-list-move` | 元素位置变化 | 350ms | 平滑移动 (cubic-bezier) |
| `.card-list-enter-active` | 进入动画 | 300ms | 淡入 + 缩放放大 + 向上滑入 |
| `.card-list-leave-active` | 离开动画 | 250ms | 淡出 + 缩小 + 向下滑出 |
| `.card-list-enter-from` | 进入初始态 | — | opacity:0, scale:0.85, translateY(-10px) |
| `.card-list-leave-to` | 离开终态 | — | opacity:0, scale:0.85, translateY(10px) |
| `.loading-pulse` | loading 脉冲 | 1.5s 循环 | box-shadow 紫色辉光呼吸 |

### 3. 网格布局

```css
.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 10px;
}
```

- 卡片最小宽度 130px，`auto-fill` 自动适应列数
- 列数随容器宽度变化：1366 屏 ~5 列，1920 屏 ~11 列
- FLIP 动画让 Grid 中元素的位置变化有过渡效果

---

## 用户操作流程

```
1. 用户点击"发送 ▶"
2. 立即看到新卡片出现在最上面（loading 脉冲动画）
3. 后端 Claude 执行中...
4. 后端返回真实数据 → refreshProjects()
5. loading 卡片被真实卡片替换（key 相同）
6. 动画：卡片从顶部"滑"到按 updated_at 排序的正确位置
7. 其他卡片依次后移，位置变化有过渡
8. 自动选中并弹出 Modal 显示详情
```

---

## 文件清单

| 文件 | 改动 |
|---|---|
| `frontend/src/App.vue` | 模板：`TransitionGroup` 包裹卡片 + loading 占位 |
| `frontend/src/App.vue` | script：`send()` 函数加入乐观更新逻辑 |
| `frontend/src/App.vue` | style：`.card-list-*` 过渡动画 + `.loading-pulse` 脉冲 |

---

## 未来扩展方向

1. **WebSocket 实时推送**：后端支持 WebSocket，前端收到单条消息只更新对应卡片，不动其他。省去全量拉取 + FLIP 的需求。
2. **卡片拖拽排序**：用 `vue-draggable-next` 实现用户手动排序，拖拽过渡动画由库内置。
3. **批量动画**：多个卡片同时变化时，使用 `stagger` 延迟让动画依次触发。

---

## 三个更新点（Heartbeat 机制）

### 数据流

```
用户发消息瞬间
  → 前端: 本地项目移到头部 + 标记 loading + updated_at=now
  → 前端: 调用 POST /heartbeat/{id}  ← 立刻更新数据库 updated_at + is_finished=0
  → 后端: Claude subprocess 开始执行（blocking，还在跑...）
  → 前端: 用户看到卡片已经在头部（loading 状态），动画已完成
  ↓
Claude 跑完瞬间
  → 后端: POST /chat 返回完整结果，DB 更新 claude_result + is_finished=1 + status
  → 前端: refreshProjects() 拿到真实数据，loading → 真实内容，动画完成
```

### Heartbeat 端点

| 方法 | 路径 | 作用 | 更新字段 |
|---|---|---|---|
| POST | `/heartbeat/{project_id}` | 发消息/重试时调用 | `updated_at` + `is_finished=0` |
| POST | `/chat` | 执行 Claude 并返回结果 | `claude_result` + `is_finished=1` + `status` |
| POST | `/continue/{id}` | 重试失败项目 | `claude_result` + `is_finished=1` + `status` |
| async | PID 检测器 | 发现进程异常死亡 | `status=5` + `is_finished=1` |

**三个时间点**：
1. **发消息瞬间** → heartbeat → DB 标记活跃中，前端立刻看到卡片跳到顶部
2. **Claude 跑完** → /chat 返回 → DB 写入结果，前端 loading → 真实数据
3. **PID 关掉** → 后台检测 → DB 标记异常，前端 status=5

### 前端实现

`send()` 函数中：
```js
// 1. 本地乐观更新: 移到头部 + loading
project._loading = true
project.updated_at = Date.now()
projects.value = [project, ...rest]

// 2. 心跳: 立刻通知后端
api.heartbeat(project.project_id).catch(() => {})
// 此时 /chat 还在 blocking，但 DB 已经 updated_at = now

// 3. 等 /chat 返回
const result = await api.sendChat(...)
await refreshProjects()
// DB 数据更新，loading → 真实，动画完成
```
