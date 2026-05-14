# DESIGN_MOCK_INFRA — 前端 Mock 基础设施

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义前端 MSW（Mock Service Worker）mock 基础设施的架构、目录结构、切换机制与开发流程。支撑 SettingsPage / OperationsPage / RulesOverviewPage 的 mock-first 开发。
> 创建：2026-05-13

---

## 一、定位

- **Mock 是 API 层拦截**，而非页面级 mock。UI 代码是真实运行的 Vue 组件，只是 fetch 请求被 MSW 拦截并返回假数据。
- **Mock 的数据结构与真实 REST API 完全一致**。REST API 是唯一权威接口，mock 必须模拟同一套契约。
- **Mock 仅用于开发阶段**。生产构建不包含 MSW。
- **已有页面不 mock**。ForestPage / DataSourcePage / ConflictsPage 已有真实实现，不参与 mock。

---

## 二、技术选型：MSW v2

| 维度 | 说明 |
|------|------|
| 拦截层级 | Service Worker（浏览器网络层）——不修改应用代码 |
| 匹配方式 | URL pattern + method + body |
| SSE 模拟 | 返回 `ReadableStream` 或简化为一发即完的 one-shot 响应 |
| 生产剔除 | `import.meta.env.DEV` 条件判断 |

---

## 三、目录结构

```
frontend/src/mocks/
├── browser.ts              # MSW browser worker 初始化（条件加载）
├── handlers/
│   ├── index.ts            # 汇总所有 handler
│   ├── database.ts         # /api/database/* 的 mock handler
│   ├── pipeline.ts         # /api/pipeline/* 的 mock handler
│   ├── config.ts           # /api/config/* 的 mock handler
│   ├── rules.ts            # /api/rules/* 的 mock handler
│   ├── backups.ts          # /api/backups/* 的 mock handler
│   └── workspace.ts        # /api/workspace/* 的 mock handler
└── data/
    ├── database.json       # mock 用的假 database
    ├── config.json         # mock 用的假 user_config
    ├── pipeline-result.json # mock 用的假 pipeline compute 结果
    ├── rules-list.json     # mock 用的假 rule 文件列表
    └── backups-list.json   # mock 用的假 backup 目录列表
```

---

## 四、Handler 设计模式

### 4.1 Handler 文件格式

```typescript
// frontend/src/mocks/handlers/database.ts
import { http, HttpResponse } from 'msw'
import dbData from '../data/database.json'

export const databaseHandlers = [
  // 模拟 POST /api/database/generate
  http.post('/api/database/generate', async () => {
    return HttpResponse.json({
      ok: true,
      data: dbData,
      warnings: [],
      errors: [],
    })
  }),

  // 模拟 POST /api/database/load
  http.post('/api/database/load', async ({ request }) => {
    // 可读取 request body 做条件响应
    return HttpResponse.json({
      ok: true,
      data: dbData,
    })
  }),
]
```

### 4.2 汇总入口

```typescript
// frontend/src/mocks/handlers/index.ts
import { databaseHandlers } from './database'
import { pipelineHandlers } from './pipeline'
import { configHandlers } from './config'
import { rulesHandlers } from './rules'
import { backupsHandlers } from './backups'
import { workspaceHandlers } from './workspace'

export const handlers = [
  ...databaseHandlers,
  ...pipelineHandlers,
  ...configHandlers,
  ...rulesHandlers,
  ...backupsHandlers,
  ...workspaceHandlers,
]
```

### 4.3 SSE mock 简化策略

真实 pipeline 端点返回 `text/event-stream` 流式数据。mock 阶段做**简化处理**：

```typescript
// 模拟 POST /api/pipeline/compute (SSE → 简化为一发即完)
http.post('/api/pipeline/compute', async () => {
  // 方案 A：模拟 SSE 流（返回多个 chunk）
  const encoder = new TextEncoder()
  const events = [
    `data: ${JSON.stringify({ step: 'compute', finished: 1, total: 3, message: 'computing...' })}\n\n`,
    `data: ${JSON.stringify({ ok: true, data: pipelineResult })}\n\n`,
  ]
  
  const stream = new ReadableStream({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(event))
      }
      controller.close()
    },
  })
  
  return new HttpResponse(stream, {
    headers: { 'Content-Type': 'text/event-stream' },
  })
})
```

如果 SSE mock 实现复杂，可先**降至 one-shot 响应**（直接返回最终 result），后续再补流式模拟。进度条在 mock 模式下不会动——这不影响界面布局验证。

---

## 五、切换机制

### 5.1 npm scripts

```json
{
  "scripts": {
    "dev": "vite",
    "dev:mock": "VITE_ENABLE_MOCK=true vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

### 5.2 条件加载

```typescript
// frontend/src/main.ts
import { createApp } from 'vue'
import App from './App.vue'

async function bootstrap() {
  // 仅开发环境 + mock 模式下加载 MSW
  if (import.meta.env.DEV && import.meta.env.VITE_ENABLE_MOCK === 'true') {
    const { worker } = await import('./mocks/browser')
    await worker.start({ onUnhandledRequest: 'bypass' })
    console.log('[MSW] Mock Service Worker started')
  }

  const app = createApp(App)
  // ... router, pinia, mount
}

bootstrap()
```

### 5.3 水印

在 `dev:mock` 模式下，`App.vue` 左上角显示半透明浮动水印：

```vue
<!-- 条件渲染 -->
<div v-if="isMockMode" class="mock-watermark">[MOCK MODE]</div>

<style scoped>
.mock-watermark {
  position: fixed;
  top: 4px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  background: rgba(255, 165, 0, 0.85);
  color: #fff;
  padding: 2px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
  pointer-events: none;
}
</style>
```

### 5.4 使用方式

```bash
# 仅开发 UI（不启动后端）
npm run dev:mock

# 全功能开发（需启动后端）
npm run dev
```

---

## 六、Mock 数据约定

### 6.1 数据文件格式

所有 `data/*.json` 必须与对应 REST API 的响应格式**结构一致**。允许字段值造假（如路径全用 `/tmp/fixture/...`），但类型必须正确。

### 6.2 数据维护

- Mock 数据随页面开发逐步丰富。初期只需满足 SettingsPage / OperationsPage / RulesOverviewPage 的布局需求。
- 修改真实 API 响应格式时，**同步更新**对应的 mock data。
- Mock data 不参与 Vitest 单元测试（Vitest 测试接口实现，不测 mock 数据）。

### 6.3 首批需要 mock 的数据

| 数据文件 | 服务页面 | 对应 API |
|---------|---------|---------|
| `database.json` | SettingsPage（Database JSON 编辑） | `POST /api/database/load` |
| `config.json` | SettingsPage（user_config 编辑） | `POST /api/config/discover` |
| `pipeline-result.json` | OperationsPage（结果概览） | 从 localStorage（`results:{name}`）读取 |
| `rules-list.json` | RulesOverviewPage（规则列表） | `POST /api/rules/scan` |

---

## 七、执行步骤（Phase 3.1）

| 步骤 | 任务 | 产出 |
|------|------|------|
| 1 | 安装 MSW 依赖 | `npm install --save-dev msw` |
| 2 | 初始化 Service Worker | `npx msw init public/` |
| 3 | 创建目录结构 | `frontend/src/mocks/` 及子目录 |
| 4 | 编写 handler 文件 | 6 个 handler 模块 |
| 5 | 编写 mock data 文件 | 4 个 JSON fixture |
| 6 | 修改 `main.ts` 条件加载 | `VITE_ENABLE_MOCK` 环境变量 |
| 7 | 修改 `package.json` scripts | 新增 `dev:mock` |
| 8 | 添加水印组件 | App.vue 条件渲染 |
| 9 | 验证 | `npm run dev:mock` → 打开浏览器 → 看到 [MOCK MODE] 水印 → DevTools Network 显示 MSW 拦截 |

---

## 八、决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | Mock 技术栈 | MSW v2 |
| D2 | SSE mock 策略 | 简化——初始阶段使用 one-shot 响应；后续可选补流式 |
| D3 | Mock 页面范围 | 仅 SettingsPage / OperationsPage / RulesOverviewPage |
| D4 | Mock data 与测试关系 | 不共用——Vitest 直接测接口实现 |
| D5 | 切换方式 | 环境变量 `VITE_ENABLE_MOCK` + `npm run dev:mock` |
| D6 | 生产构建 | MSW 不打包进生产构建（`import.meta.env.DEV` 守卫） |
