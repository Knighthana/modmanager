# 审计后可延后事项

> 来源：`work_memo/2026-05-14_ask_to_audit.md` + `work_memo/2026-05-14_audit_answers.md`
> 说明：以下 3 项审计要求经答复确认"可延后"，不阻塞当前迭代
> 最后一次更新于: 2026-05-15 04:59:00 UTC+8

---

## 1. `useWorkspaceStore` —— localStorage 唯一写者

### 审计要求
> Pinia 中的 `useWorkspaceStore` 是 localStorage 的唯一写者，所有页面通过 store action 修改决策，由 store 负责 flush

### 当前状态
各页面直接 `pers.save('workspace', ...)` 和 `pers.load('workspace')`。无独立 workspace store。

### 答复
> 方向正确，建议收敛为唯一写者。余地：现在做还是下一迭代做。persistence 作为底层工具保留，workspace store 调用它，不是替代关系；useComputeStore 可作为后续收敛项，不必和 workspace store 强绑定同一批次上线。

### 待执行
- [x] 创建 `src/stores/app.ts`——所有浏览器存储读写的唯一入口（2026-05-16 实施，命名变更：`useWorkspaceStore` → `useAppStore`，因 workspace 已改义为后端工作区目录）
- [x] `persistence.ts` 保留为底层工具，useAppStore 内部调用
- [x] 各页面改为通过 useAppStore action 读写，移除直接 import persistence.ts 的调用
- [ ] （可选）创建 `useComputeStore` 用于 aggregatedRuleSet 内存传递

---

## 2. `uiState` 并入 workspace

### 审计要求
```json
{
  "uiState": {
    "sidebarCollapsed": false,
    "activeTab": "datasource",
    "libraryVisibility": {},
    "gameVisibility": {}
  }
}
```

### 当前状态
UI 状态分散在多个 persistence key（`datasource-libraryVisibility`、`datasource-gameVisibility` 等）。

### 答复
> 可以并入，方向合理。按高价值字段先迁移，并加写入节流（例如 200ms 级）避免频繁刷 localStorage。

### 待执行
- [x] 将 `libraryVisibility`、`gameVisibility` 迁移进 `workspace.uiState` (2026-05-14 实施)
- [x] DataSourcePage + ComputePrepPage 可见性状态持久化
- [x] `activeTab`、`sidebarCollapsed` 迁入（2026-05-16 实施，通过 useAppStore 独立 key 实现，非嵌套 uiState 对象）

---

## 3. 前端 Transport Abstraction

### 审计要求
> `src/api/transport.ts` — 接口定义（`invoke<T>(path, payload)`, `onProgress` callback）。Tauri 时仅改此层的实现，组件零改动。

### 当前状态
没有 `transport.ts`。所有组件直接 `import { apiPost } from '../api/client'` / `import { streamSse } from '../api/sse'`。

### 答复
> 不是当前阻塞项，但建议尽早做薄封装，降低后续迁移成本。余地：现在做（P1）还是 Tauri 前做。先抽象 apiPost 与 streamSse 的统一入口，组件层不再直接绑定传输细节。

### 待执行
- [x] 创建 `src/api/transport.ts`——`apiPost` + `streamSse` + 类型 统一导出入口（2026-05-16 实施）
- [x] 将 `apiPost` 和 `streamSse` 收敛到 transport 接口之后（14 个文件 import 路径统一）
- [x] 组件层不再直接 import `apiPost` / `streamSse`（通过 transport.ts 间接引用）
