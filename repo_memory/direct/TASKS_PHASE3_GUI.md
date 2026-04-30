# Phase 3: 前端 GUI — 实现任务

创建：2026-04-30
状态：待实现
前置设计：`repo_memory/direct/DESIGN_PHASE3_GUI.md`（必读）
前置决策：`repo_memory/direct/QUESTIONS_PHASE3.md`（13 个决策全部确认 ✅）

---

## 前置阅读（必读）

1. `repo_memory/direct/DESIGN_PHASE3_GUI.md` — 完整设计（架构、组件树、路由、Store、交互模型）
2. `repo_memory/direct/QUESTIONS_PHASE3.md` — 13 个决策记录
3. Phase 2 产物：
   - `src/modmanager_web/app.py` — 需要修改（加 StaticFiles + SPA fallback）
   - `src/modmanager_web/routes/pipeline.py` — 参考 SSE 响应格式

---

## 执行顺序

```
Task 15: frontend/ 脚手架          ← npm + Vite + Vue 3 + TS + Element Plus + Pinia + Router
Task 16: M3 前置：forest_visual.py ← SVG 节点嵌入交互属性（data-* / title / desc）
Task 17: api/ 层                   ← fetch 封装 + SSE 流解析
Task 18: stores/forest.ts          ← Pinia store
Task 19: router + LayoutShell      ← Vue Router 配置 + 全局布局
Task 20: ForestPage + ForestViewer ← Forest 可视化嵌入（表单 + SVG + zoom/pan + SSE 进度）
Task 21: ConflictsPage             ← 冲突裁决 UI
Task 22: RulesPage                 ← 规则浏览器（MVP）
Task 23: BackupPage                ← 备份/恢复控制台（MVP）
Task 24: app.py 更新               ← 静态文件 mount + SPA fallback
Task 25: 测试                      ← 前端 Vitest + Python 全量回归
```

---

## Task 15: frontend/ 脚手架

**目标**：在项目根目录下创建可构建的 Vue 3 + TypeScript 项目。

### 15.1 npm init

在项目根目录执行：
```bash
cd frontend
npm init -y
npm install vue@3
npm install -D vite @vitejs/plugin-vue typescript vue-tsc vue-router@4 pinia element-plus
```

或等效的手动创建 `package.json`。

### 15.2 创建的文件

| 文件 | 说明 |
|------|------|
| `frontend/package.json` | 依赖声明（vue, vue-router, pinia, element-plus） |
| `frontend/tsconfig.json` | TypeScript 配置（strict, paths 别名 `@/` → `src/`） |
| `frontend/vite.config.ts` | Vite 配置：`outDir: '../src/modmanager_web/static'`，dev proxy `/api` → `http://127.0.0.1:8000` |
| `frontend/index.html` | SPA 入口 `<div id="app">` + `<script type="module" src="/src/main.ts">` |
| `frontend/src/main.ts` | `createApp(App).use(router).use(createPinia()).mount('#app')` |
| `frontend/src/App.vue` | `<LayoutShell><router-view /></LayoutShell>` |
| `frontend/src/env.d.ts` | `/// <reference types="vite/client" />` + Vue 模块声明 |

### 15.3 验证

```bash
cd frontend && npm run build
```
构建成功，产物落入 `src/modmanager_web/static/`（含 `index.html` + `assets/`）。

### 15.4 tsconfig.json 关键配置

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "noEmit": true,
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src/**/*.ts", "src/**/*.vue", "src/env.d.ts"]
}
```

### 15.5 vite.config.ts

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  build: {
    outDir: '../src/modmanager_web/static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
```

---

## Task 16: M3 前置 — forest_visual.py SVG 升级

**文件**：`src/modmanager_cli/forest_visual.py`（修改）

### 16.1 需要改动的内容

在现有 SVG renderer 中，每个森林节点 `<g>` 元素需追加以下属性：

| 属性 | 值 | 说明 |
|------|-----|------|
| `data-forest-node` | `node["path"]` | 目标路径，前端事件委托用 |
| `data-conflict` | `"true"` 或无 | 仅冲突节点携带，标识可点击 |
| `<title>` 子元素 | `f"target: {node['path']}"`  | 悬停提示 |
| `<desc>` 子元素 | `f"destin: {node.get('destin_mixed_id', '')}\ncandidates: {', '.join(node.get('candidates', []))}"` | 冲突节点携带候选列表 |

### 16.2 实现要点

- **仅修改 SVG renderer**（`_render_svg_*` 相关函数），不改 ASCII / DOT renderer
- 冲突节点的判断条件：`node.get("warning") == "W_FOREST_BRANCHING"` 且 `"candidates" in node`
- `data-conflict` 属性仅在冲突节点上输出（普通节点不输出该属性）
- `<desc>` 仅在冲突节点上输出（减少 SVG 体积）
- `<title>` 在所有节点上输出

### 16.3 测试验证

- 现有 `tests/test_forest_visual.py` 测试保持通过
- 新增检查：SVG 输出包含 `data-forest-node=` 属性和 `<title>` 标签
- 冲突节点的 SVG 包含 `data-conflict="true"` 和 `<desc>` 标签

---

## Task 17: api/ 层

**目录**：`frontend/src/api/`

### 17.1 `client.ts` — fetch 封装

```typescript
// api/client.ts
const BASE = '/api'

export interface ApiResponse<T = unknown> {
  ok: boolean
  data: T | null
  errors: string[]
  warnings: string[]
}

export async function apiPost<T>(path: string, body: unknown): Promise<ApiResponse<T>> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}
```

### 17.2 `sse.ts` — SSE 流式解析

```typescript
// api/sse.ts
export interface SseProgress {
  step: string
  finished: number
  total: number
  message: string
}

export interface SseCallbacks {
  onProgress?: (p: SseProgress) => void
  onResult?: (data: unknown) => void
  onError?: (message: string) => void
}

export async function streamSse(
  path: string,
  body: unknown,
  callbacks: SseCallbacks,
): Promise<void> {
  const response = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    callbacks.onError?.(`HTTP ${response.status}`)
    return
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    let eventType = ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const jsonStr = line.slice(6)
        try {
          const data = JSON.parse(jsonStr)
          if (eventType === 'progress') callbacks.onProgress?.(data)
          else if (eventType === 'result') callbacks.onResult?.(data)
          else if (eventType === 'error') callbacks.onError?.(data.errors?.[0] ?? 'Unknown error')
        } catch {
          // skip malformed JSON
        }
      }
    }
  }
}
```

### 17.3 SSE 解析注意事项

- `streamSse` 使用 `ReadableStream` API（浏览器原生支持，无需额外依赖）
- SSE 格式严格遵循 Phase 2 定义：`event: <type>\ndata: <json>\n\n`
- 缓冲区处理：`split('\n')` 的最后一个元素可能不完整，保留到下次循环
- JSON 解析失败时静默跳过（不崩溃）

---

## Task 18: stores/forest.ts — Pinia Store

**文件**：`frontend/src/stores/forest.ts`

按照设计文档 §4.1 实现 `useForestStore`，包含：

| 项目 | 说明 |
|------|------|
| **state** | `forest`, `finalMapping`, `conflictList`, `branchDecisions`, `errors`, `warnings`, `svgContent`, `isRunning`, `progress` |
| **getters** | `unresolvedCount`, `isClean` |
| **actions** | `runPipeline(params)`, `setDecision(target, source)`, `clearDecisions()`, `reset()` |

### 18.1 `runPipeline` 核心逻辑

```typescript
async function runPipeline(params: PipelineParams) {
  isRunning.value = true
  reset()

  await streamSse('/pipeline/run', params, {
    onProgress(p) { progress.value = p },
    onResult(data: any) {
      // Parse and populate store from result
      const result = data as { ok: boolean, data: { forest: any[], final_mapping: any[] }, errors: string[], warnings: string[] }
      errors.value = result.errors || []
      warnings.value = result.warnings || []
      if (result.data) {
        forest.value = extractForest(result.data.forest)
        finalMapping.value = extractFinalMapping(result.data.final_mapping)
        conflictList.value = extractConflicts(result.data.forest)
      }
    },
    onError(msg) { errors.value.push(msg) }
  })

  isRunning.value = false
}
```

### 18.2 辅助函数（store 内部或独立 utils）

```typescript
function extractConflicts(forest: any[]): ConflictItem[] {
  return forest
    .filter(n => n.warning === 'W_FOREST_BRANCHING')
    .map(n => ({
      target: n.path,
      destin_mixed_id: n.destin_mixed_id || '',
      candidates: n.candidates || [],
    }))
}
```

---

## Task 19: router + LayoutShell

### 19.1 `router/index.ts`

按照设计文档 §3 实现：
- 4 个路由：`/forest`, `/conflicts`, `/rules`, `/backup`
- `/` redirect → `/forest`
- `createWebHistory()`（history mode）

### 19.2 `LayoutShell.vue`

```vue
<template>
  <el-container style="height: 100vh">
    <el-aside width="200px">
      <el-menu :default-active="currentRoute" router>
        <el-menu-item index="/forest">
          <span>📊 Forest 可视化</span>
        </el-menu-item>
        <el-menu-item index="/conflicts">
          <span>⚔️ 冲突裁决</span>
          <el-badge v-if="store.unresolvedCount > 0" :value="store.unresolvedCount" />
        </el-menu-item>
        <el-menu-item index="/rules">
          <span>📋 规则管理</span>
        </el-menu-item>
        <el-menu-item index="/backup">
          <span>🗄️ 备份恢复</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-main>
        <router-view />
      </el-main>
      <SseStatusBar v-if="store.isRunning" />
    </el-container>
  </el-container>
</template>
```

### 19.3 `SseStatusBar.vue`

底部固定进度条，显示 `store.progress.step` + `store.progress.message` + 进度百分比。

使用 Element Plus 的 `el-progress` 或 `el-alert` 组件。

---

## Task 20: ForestPage + ForestViewer

### 20.1 `ForestPage.vue`

页面结构：
```
┌────────────────────────────────────────────┐
│ PipelineForm（参数表单）                      │
│  [database path] [rules paths] [backup dir] │
│  [dry run toggle]         [▶ 运行] 按钮      │
├────────────────────────────────────────────┤
│ ResultSummary（统计卡片，运行后显示）           │
│  backed_up: 42  applied: 42  errors: 0      │
├────────────────────────────────────────────┤
│ ForestViewer（SVG 渲染区）                    │
│  zoom/pan 交互                               │
│  ← 冲突节点可点击（触发跳转）                    │
└────────────────────────────────────────────┘
```

### 20.2 PipelineForm

- 三个 `el-input`：database 路径、kmm_rule 路径（逗号分隔）、backup 目录
- 一个 `el-switch`：dry run
- 一个 `el-button`：运行（type="primary"，loading 时禁用）

"运行"按钮触发 `store.runPipeline({...})`。

### 20.3 ForestViewer

核心交互（设计文档 §5.2）：

- **zoom/pan**：CSS `transform: scale() translate()`，鼠标滚轮缩放 + 鼠标拖拽平移
- **点击交互**：事件委托 `@click` → 找最近 `[data-forest-node]` → 若含 `[data-conflict]` → 跳 `/conflicts?target=...`
- **加载中**：`v-loading="store.isRunning"`（Element Plus 指令）

### 20.4 最小交互要求

- ✅ 滚轮缩放（scale 0.1x ~ 5x）
- ✅ 鼠标拖拽平移
- ✅ 冲突节点可点击（跳转到冲突页面）
- ✅ 加载状态 indicator
- ❌ M4 特性（hover 高亮、整链联动）→ 不在本阶段

---

## Task 21: ConflictsPage

### 21.1 ConflictsPage.vue

页面结构：
```
┌────────────────────────────────────────────┐
│ 冲突列表 (el-table)                          │
│ ┌──────┬──────────┬──────────────────────┐ │
│ │ 目标路径  │ destin   │ 候选 (el-radio-group) │ │
│ ├──────┼──────────┼──────────────────────┤ │
│ │ /a.png  │ mod:B    │ ○ /m1/a.png         │ │
│ │         │          │ ○ /m2/a.png         │ │
│ └──────┴──────────┴──────────────────────┘ │
├────────────────────────────────────────────┤
│ [重置决策]           [重新计算]               │
└────────────────────────────────────────────┘
```

### 21.2 核心逻辑

- `el-table` 数据源：`store.conflictList`
- `el-radio-group` 绑定：`store.branchDecisions[item.target]`
- "重新计算"：`store.runPipeline({...params, branch_decisions: store.branchDecisions})`
- "重置决策"：`store.clearDecisions()`
- 若 URL query 含 `?target=xxx`，页面加载后自动滚动到该行并高亮

### 21.3 最小交互要求

- ✅ 表格展示冲突列表（target / destin / candidates）
- ✅ 候选 radio 选择
- ✅ 重新计算 + 重置按钮
- ✅ 空状态：无冲突时显示 "暂无冲突，Forest 已为确定映射"
- ❌ 可视化森林中直接选枝 → 不在本阶段

---

## Task 22: RulesPage（MVP）

### 22.1 MVP 范围

- 展示 kmm_rule 文件列表（硬编码或简单配置）
- 点击文件查看 JSON 内容（`el-dialog` 弹窗 + 格式化 JSON）
- 本阶段不做编辑功能

### 22.2 组件

```vue
<template>
  <div>
    <h2>规则文件</h2>
    <el-table :data="ruleFiles" @row-click="showContent">
      <el-table-column prop="name" label="文件名" />
      <el-table-column prop="path" label="路径" />
    </el-table>
    <el-dialog v-model="dialogVisible" :title="selectedFile?.name">
      <pre>{{ fileContent }}</pre>
    </el-dialog>
  </div>
</template>
```

---

## Task 23: BackupPage（MVP）

### 23.1 MVP 范围

- 展示备份目录列表（通过 API 查询或本地路径扫描）
- 恢复操作按钮

### 23.2 组件

```vue
<template>
  <div>
    <h2>备份管理</h2>
    <el-table :data="backupDirs">
      <el-table-column prop="path" label="备份目录" />
      <el-table-column prop="fileCount" label="文件数" />
      <el-table-column label="操作">
        <template #default="{ row }">
          <el-button size="small" @click="restore(row.path)">恢复</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
```

> **注意**：备份目录列表的获取需要新增一个 API 端点或客户端本地扫描。MVP 可用简单的输入框让用户指定备份目录路径来查看和恢复。

---

## Task 24: app.py 更新

**文件**：`src/modmanager_web/app.py`（修改）

### 24.1 新增静态文件挂载（设计文档 §2）

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

# 在 create_app() 中，所有 api 路由注册完毕后：

static_dir = Path(__file__).parent / "static"
if static_dir.exists() and (static_dir / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        return FileResponse(str(static_dir / "index.html"))
```

### 24.2 注意事项

- SPA fallback 路由必须在 `app.get("/api/health")` 等 api 路由**之后**注册（FastAPI 路由匹配优先精确路径）
- 构建产物存在性检查：若 `static/index.html` 不存在，不应注册 fallback（避免开发时覆盖 API 路由）
- CORS 和 SSE 端点不受影响

---

## Task 25: 测试

### 25.1 前端测试（Vitest）

安装：`npm install -D vitest @vue/test-utils happy-dom`

新建 `frontend/src/__tests__/`：

| 测试文件 | 覆盖 |
|----------|------|
| `stores/forest.test.ts` | `useForestStore` 的 reset / setDecision / clearDecisions / unresolvedCount |
| `api/sse.test.ts` | SSE 解析器（buffer 拼接、JSON 解析、事件分流） |
| `components/ForestViewer.test.ts` | v-html 渲染 SVG、zoom/pan 计算、事件委托 |

**运行**：`cd frontend && npx vitest run`

### 25.2 Python 全量回归

```bash
python3 -m pytest tests/ -v
```

**必须保持 276 tests 通过**。主要验证 forest_visual.py 改动不破坏已有测试。

### 25.3 验证前端构建集成

```bash
cd frontend && npm run build
ls src/modmanager_web/static/index.html  # 必须存在
cd ../.. && python3 -m modmanager_web    # 启动后浏览器打开应看到 Forest 页面
```

---

## 验收标准（复述设计文档 §10）

1. `cd frontend && npm run build` 构建成功，产物写入 `src/modmanager_web/static/`
2. `modmanger-web` 启动后 `http://127.0.0.1:8000` 展示 Forest 页面
3. Forest 页面：填写参数 → 运行 → SSE 进度 → SVG 展示 → zoom/pan
4. 冲突裁决页面：展示冲突 → 选候选 → 重新计算 → Forest 更新
5. 四个页面路由切换正常（`/forest`, `/conflicts`, `/rules`, `/backup`）
6. Python 端 276 tests 保持通过
7. `node_modules/` 和 `frontend/dist/` 被 `.gitignore` 排除
