# 前端框架独立性设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义前端代码的分层结构，确保 Vue 组件与传输层解耦，支持从 HTTP 迁移到 Tauri 等不同宿主环境时的零代码改动

创建：2026-05-14

---

## 0. 分层总览

前端代码按职责分为 3 层，自下而上分别为：

```
┌──────────────────────────────────────┐
│ 第 3 层：Components（业务组件）       │  框架迁移时零改动
│ src/pages/*.vue / src/components/     │  ↓
├──────────────────────────────────────┤
│ 第 2 层：State Management（状态管理）  │  框架迁移时零改动
│ src/stores/*.ts (Pinia)               │  ↓
├──────────────────────────────────────┤
│ 第 1 层：Transport Abstraction（传输） │  框架迁移时唯一改动点
│ src/api/transport.ts / client.ts / sse.ts │  ↓
└──────────────────────────────────────┘
```

---

## 1. 第 1 层：Transport Abstraction（传输适配层）

### 职责
定义前后端通讯的接口规范，隐藏底层传输实现细节。

### 当前实现
- `src/api/config.ts` — API 基础配置
  - 导出：`API_BASE` 常量
  
- `src/api/transport.ts` — 接口定义（TypeScript interface）
  - 定义：`PostFn<T>` — 发送 JSON 请求的通用签名
  - 定义：`ProgressCallbacks` — SSE 进度回调的标准接口
  
- `src/api/client.ts` — HTTP 实现（当前）
  - 实现：`apiPost<T>(path, body)` 符合 `PostFn<T>` 接口
  - 传输：HTTP POST 到 `/api/*`
  
- `src/api/sse.ts` — SSE 实现（当前）
  - 实现：`streamSse(path, body, callbacks)` 符合 `ProgressCallbacks`
  - 传输：HTTP POST + Server-Sent Events

### 接口定义（TypeScript）

```typescript
// src/api/transport.ts — 统一导出入口
export { apiPost, apiGet, invoke } from './client'
export { streamSse } from './sse'
```

**调用规则**：
- `apiPost(path, body)` — POST 请求。`path` 为**相对路径**（如 `/workspace/create`），不含 `/api` 前缀——`apiPost` 内部拼接 `API_BASE + path`
- `apiGet(path)` — GET 请求。同样传相对路径
- `streamSse(path, body, callbacks)` — SSE 流式请求。同样传相对路径
- `API_ENDPOINTS` 常量中的值**不含** `API_BASE`，全部为相对路径
- 违反此规则的后果：双重 `/api` 前缀 → 404 或 405

```typescript
// src/api/config.ts
// API_BASE 仅由 apiPost/apiGet/streamSse 内部使用
export const API_BASE = getApiBase()   // '/api'

// API_ENDPOINTS 中的值是相对路径，不含 API_BASE
export const API_ENDPOINTS = {
  WORKSPACE_LIST: '/workspace/list',       // ✓
  // WORKSPACE_LIST: `${API_BASE}/workspace/list`  // ✗ 双重前缀
} as const
```
  warnings: string[]
}
```

### Tauri 迁移时的改动

```typescript
// Tauri 版本: src/api/transport-tauri.ts

import { invoke } from '@tauri-apps/api/tauri'
import { listen } from '@tauri-apps/api/event'

export async function apiPost<T>(path: string, body: unknown): Promise<ApiResponse<T>> {
  // 调用 Rust 后端的 invoke 命令，替代 HTTP POST
  return invoke('api_invoke', { path, body })
}

export async function streamSse(
  path: string,
  body: unknown,
  callbacks: ProgressCallbacks,
): Promise<void> {
  // 替代 SSE，用 Tauri event 系统
  const unlisten = await listen(`progress_${path}`, (event) => {
    callbacks.onProgress?.(event.payload)
  })
  // ... 逻辑
  unlisten()
}
```

**关键特点**：
- 仅改 `src/api/` 目录的几个文件
- 所有其他 `src/pages/` 和 `src/stores/` 的代码零改动
- 接口签名完全相同，组件代码无感知

### Tauri 迁移步骤
1. 新建 `src/api/transport-tauri.ts`，实现同样的接口
2. 通过 `import.meta.env.VITE_PLATFORM` 或其他机制选择加载 client.ts 或 transport-tauri.ts
3. 所有 store 和 component 的代码保持不变
4. 前后端通讯完全改变，UI 逻辑零改动

---

## 2. 第 2 层：State Management（状态管理）

### 职责
管理前端的业务状态，与传输方式无关。所有组件通过 Pinia store 访问数据和执行操作。

### 包含的 Stores

#### 2.1 浏览器存储层（两层架构）

##### 底层：persistence.ts

**职责**：浏览器存储的唯一底层。所有 localStorage/sessionStorage 读写通过其导出函数进行。不与组件直接对话。

**导出函数**
- `loadPersistent<T>(key)` — sessionStorage 优先 → localStorage 回退
- `savePersistent(key, value)` — 同时写 sessionStorage + localStorage
- `clearPersistent(key)` — 清除两处
- `loadUiState(scope)` / `saveUiState(scope, state)` — 按 scope 分键读写 UI 状态
- `loadCurrentWorkspaceId()` / `saveCurrentWorkspaceId(id)` — Tab 级工作区导航状态
- `loadSidebarCollapsed()` / `saveSidebarCollapsed(collapsed)` — 侧栏折叠偏好

##### 上层：useAppStore（Pinia）

**职责**：组件的唯一持久化入口。封装 persistence.ts 为 reactive action。**组件不允许 import persistence.ts**——只通过 useAppStore 读写浏览器存储。Tauri 迁移时仅替换 persistence.ts 内部的存储适配器，useAppStore 和组件零改动。

**设计决策**：
- 命名：`useAppStore`（非旧 audit 中的 `useWorkspaceStore`——workspace 现已改义为后端工作区目录，app store 管的是 app 级 UI 状态）
- 审计 `audit_todo_future.md` 中 `useWorkspaceStore` 唯一写者 → 此处落地为 `useAppStore`

#### 2.2 useDataSourceStore
**职责**：DataSourcePage 的扫描会话数据与 UI 状态

**特点**：
- 扫描结果（libraries, games, mods）仅在 Pinia 内存中，刷新后通过 `POST /api/database/read` 重新加载
- 可见性偏好（libraryVisibility, gameVisibility）持久化到 `sessionStorage['modmanager:uiState:datasource']`（主读）+ `localStorage`（留档）

**状态**
```typescript
{
  discoveryMode: 'auto' | 'manual' | 'all'
  libraries: LibraryRow[]
  games: GameRow[]
  mods: ModRow[]
  libraryVisibility: Record<number, boolean>  // UI 状态
  gameVisibility: Record<number, boolean>     // UI 状态
  warnings: string[]
  errors: string[]
}
```

**生命周期**：
- DataSourcePage 初始化时创建
- 调用 `POST /api/database/generate` 填充数据
- 可见性偏好改动时同步写入 sessionStorage + localStorage
- 刷新后：database 数据通过 API 重新加载；可见性从 sessionStorage 恢复

#### 2.3 useComputeStore
**职责**：当前工作区的计算会话状态（Pinia 内存，刷新后从后端工作区目录恢复）

**状态**
```typescript
{
  trees: TreeNode[]
  finalMapping: MappingEntry[]
  aggregatedRuleSet: RuleSet  // 内存持有，从工作区 aggregated_rule.json 加载
  errors: string[]
  warnings: string[]
  progress: SseProgress
}
```

**生命周期**：
- ComputePrepPage 调用 `POST /api/workspace/{id}/pipeline/compute` → 结果写入工作区目录
- ForestPage 通过 `GET /api/workspace/{id}/forest/mapping` 从后端恢复
- 刷新后：从工作区目录重新加载，无需重新 compute

### 特点

**与传输无关**
- 完全不依赖 `src/api/` 目录
- 即使改成 Tauri invoke，store 代码零改动
- 只需 `import { apiPost } from '@/api'` 这一条 import，当 api 的实现改变时自动适应

**单一数据源**
- `useAppStore` 是组件读写浏览器存储的**唯一入口**（组件不 import persistence.ts）
- `persistence.ts` 是浏览器存储的**唯一底层**（存储介质适配在此层完成）
- 业务数据（decisions, mapping, SVG）以后端工作区目录为权威
- Tauri 迁移路径：仅替换 persistence.ts 内部的 LocalStorageAdapter → TauriStoreAdapter

---

## 3. 第 3 层：Components（业务组件）

### 职责
展示 UI，响应用户交互，调用 store 方法。

### 组织结构

```
src/pages/                           # 页面级组件（6 个主页面）
  ├── DataSourcePage.vue             # 扫描库和游戏
  ├── RulesOverviewPage.vue          # 选规则、聚合
  ├── ComputePrepPage.vue            # 准备计算（managed 筛选）
  ├── ForestPage.vue                 # 可视化树（结果展示）
  ├── ConflictsPage.vue              # 冲突裁决（branch 选择）
  └── OperationsPage.vue             # 备份/应用/恢复

src/components/                      # 复用组件（UI 片段）
  ├── LayoutShell.vue                # 布局壳（侧栏、导航）
  ├── DatabaseSelector.vue           # 数据库下拉选择器
  ├── ForestViewer.vue               # SVG 可视化
  └── SseStatusBar.vue               # SSE 进度条
```

### 代码特点

**依赖关系**（单向）
```
Component → Pinia store → API client
              ↓
         localStorage (via store)
```

**严格约束**
- 组件不直接调用 `apiPost()` / `streamSse()`
- 所有 API 调用都通过 store 的 action
- 组件只访问 store 的 computed/state，不知道后端细节
- 组件不直接读写 localStorage

**示例：ComputePrepPage**
```typescript
// ❌ 禁止
const { data } = await apiPost('/api/workspace/{id}/pipeline/compute', {...})

// ✅ 正确
const store = useComputeStore()
await store.compute(database_name, ...)  // store 内部调 apiPost
```

### 框架迁移时的不变性

Tauri 迁移时，组件代码完全不动：
- 底层从 HTTP 改成 Tauri invoke
- Store 中的 API 调用自动用新的 apiPost 实现
- 组件对此无感知，因为依赖注入已隔离

---

## 4. 分层验证清单

### 传输层（第 1 层）
- [ ] 所有网络调用都通过 `src/api/` 中的函数
- [ ] 不存在 `fetch()` 或其他网络调用直接出现在 component/store
- [ ] `client.ts` 和 `sse.ts` 的函数签名符合 `PostFn` 和 `ProgressCallbacks`
- [ ] `API_BASE` 从 config.ts 导入，不硬编码

### 状态层（第 2 层）
- [ ] 所有 reactive 状态都在 Pinia store
- [ ] Component 不直接操作 localStorage/sessionStorage，仅通过 useAppStore
- [ ] Component 不 import persistence.ts（门禁由 useAppStore 承担）
- [ ] `useAppStore` 是组件读写浏览器存储的唯一入口（替代旧 audit 中的 useWorkspaceStore 唯一写者）
- [ ] 每个 store 的职责清晰（workspace / datasource / compute 不混)

### 组件层（第 3 层）
- [ ] Component 中没有 `apiPost()` 或 `fetch()` 直接调用
- [ ] Component 中没有 `localStorage.getItem()` 或 `setItem()` 直接调用
- [ ] Component 只依赖 Pinia store 和自身的局部状态
- [ ] 页面间通讯都通过 store（不通过全局变量或 window）

---

## 5. Tauri 迁移路径

### 短期（当前 + 3 个月）
- 保持 HTTP 实现不变
- 提前做好分层约束，防止代码耦合加深

### 中期（未来 6-12 个月）
- 准备 Rust 后端（使用 DESIGN_PYTHON_LAYERS.md 的规则）
- 新建 `src/api/transport-tauri.ts` 实现 Tauri 版本的 apiPost/streamSse

### 长期（迁移启动）
1. Rust 后端完成并测试通过
2. 将 `import` 指向改为 `transport-tauri.ts`
3. `npm run build` 确保没有编译错误
4. 测试前端 → Rust 的通讯
5. 所有 component/store 代码零改动

---

## 6. 禁止事项

**以下代码模式在前端严格禁止**：

1. **Component 中直接调 API**
   ```typescript
   // ❌ 禁止
   const Component = () => {
     const onClick = async () => {
       const res = await apiPost('/api/pipeline/compute', {...})
     }
   }
   ```

2. **Store 中硬编码 HTTP 细节**
   ```typescript
   // ❌ 禁止
   action: async () => {
     const res = await fetch('http://localhost:8000/api/...')
   }
   ```

3. **Component 中直接操作 localStorage**
   ```typescript
   // ❌ 禁止
   onMounted(() => {
     const data = JSON.parse(localStorage.getItem('modmanager:workspace'))
   })
   ```

4. **跨 store 直接读取状态**
   ```typescript
   // ❌ 禁止（虽然 Pinia 技术上允许）
   const computeStore = useComputeStore()
   const workspaceData = useWorkspaceStore().perDatabase  // 违反职责边界
   ```

---

## 7. 文档链接

- 存储设计：`repo_memo/DESIGN_STORAGE.md`
- REST API 约束：`repo_memo/DESIGN_REST_API.md`
- 工程模式：`repo_memo/PATTERNS_ENGINEERING.md`
