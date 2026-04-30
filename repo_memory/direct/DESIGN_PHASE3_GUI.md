# Phase 3: 前端 GUI — 设计文档

创建：2026-04-30
状态：设计完成 ✅，待实现
前置完成：Phase 1 ✅ + Phase 2 ✅
决策记录：`repo_memory/direct/QUESTIONS_PHASE3.md`（13 个决策全部确认 ✅）

---

## 0. 决策汇总

| Q# | 决策 |
|-----|------|
| Q1 | **Vue 3** |
| Q2 | **M3 先独立完成**（静态 HTML 可视化），Phase 3 再交互 GUI |
| Q3 | **方案 A** — 前端构建产物嵌入 FastAPI 静态文件 |
| Q4 | Forest 可视化 → 冲突裁决 → 规则浏览器 → 备份控制台 |
| Q5 | **先最小集**（表格 + 按钮 + SVG zoom/pan），逐步完整 |
| Q6 | **REST + SSE** |
| Q7 | **仅 localhost** |
| Q8 | **npm + Vite + TypeScript** |
| Q9 | **`frontend/`**（项目根目录） |
| Q10 | **后端渲染 SVG** → API 返回 → `v-html` + 事件委托交互 |
| Q11 | **Element Plus** |
| Q12 | **SPA + Vue Router** |
| Q13 | **Pinia** — `useForestStore` 集中管理 pipeline 结果 |

---

## 1. 架构总览

```
                        ┌──────────────────────────────────┐
                        │          frontend/                │
                        │   Vue 3 + Vite + TypeScript       │
                        │   Element Plus + Pinia            │
                        │   ┌──────────┐  ┌─────────────┐  │
    浏览器 ──(HTTP)──────→│  │ Vue      │  │  SSE Client │  │
                        │  │  Router   │  │  (fetch+流)  │  │
                        │  └────┬─────┘  └─────────────┘  │
                        │       │                          │
                        │  ┌────▼──────────────────────┐   │
                        │  │         Pinia Store         │   │
                        │  │  useForestStore             │   │
                        │  │  usePipelineStore           │   │
                        │  └────────────────────────────┘   │
                        └────────────────┬─────────────────┘
                                         │ Vite build
                        ┌────────────────▼─────────────────┐
                        │  src/modmanager_web/static/       │
                        │  (构建产物 → FastAPI StaticFiles) │
                        └────────────────┬─────────────────┘
                                         │
                        ┌────────────────▼─────────────────┐
                        │       modmanager_web (FastAPI)    │
                        │  GET  /api/*    (REST endpoints)  │
                        │  POST /api/*    (SSE endpoints)   │
                        │  GET  /*        (SPA fallback)    │
                        └────────────────┬─────────────────┘
                                         │ import
                        ┌────────────────▼─────────────────┐
                        │       modmanager_cli              │
                        │  orchestrator / engine / ...      │
                        └──────────────────────────────────┘
```

---

## 2. 目录结构

```
frontend/                         ← 项目根目录下，与后端解耦
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html                   ← SPA 入口
├── src/
│   ├── main.ts                  ← Vue 应用启动
│   ├── App.vue                  ← 根组件（layout + router-view）
│   ├── router/
│   │   └── index.ts             ← Vue Router 配置
│   ├── stores/
│   │   └── forest.ts            ← useForestStore (Pinia)
│   ├── pages/
│   │   ├── ForestPage.vue       ← Forest 可视化嵌入
│   │   ├── ConflictsPage.vue    ← 冲突裁决 UI
│   │   ├── RulesPage.vue        ← 规则浏览器
│   │   └── BackupPage.vue       ← 备份/恢复控制台
│   ├── components/
│   │   ├── LayoutShell.vue       ← 全局布局（侧栏 + 顶栏 + 内容区）
│   │   ├── ForestViewer.vue     ← SVG 渲染 + zoom/pan 交互
│   │   ├── ConflictPanel.vue    ← 冲突列表 + 候选选择
│   │   ├── SseStatusBar.vue     ← SSE 进度条（全局）
│   │   └── ...
│   ├── api/
│   │   ├── client.ts            ← fetch 封装（base URL、error handling）
│   │   └── sse.ts               ← SSE 流式读取 + ProgressCallback 桥接
│   └── types/
│       └── index.ts             ← TypeScript 类型定义
```

### 构建产物位置

Vite 默认输出到 `frontend/dist/`，通过 `vite.config.ts` 改为：

```typescript
// vite.config.ts
export default defineConfig({
  build: {
    outDir: '../src/modmanager_web/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',   // 开发时代理到 FastAPI
    }
  }
})
```

构建后：`src/modmanager_web/static/` 包含 `index.html` + `assets/*.js` + `assets/*.css`

### FastAPI 静态文件挂载

在 `src/modmanager_web/app.py` 中新增：

```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA fallback: 非 /api 路径返回 index.html"""
        # 让 Vue Router 处理客户端路由
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"ok": False, "errors": ["Frontend not built. Run: cd frontend && npm run build"]}
```

---

## 3. Vue Router 设计

四个页面，一个 layout shell。

```typescript
// router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import ForestPage from '../pages/ForestPage.vue'
import ConflictsPage from '../pages/ConflictsPage.vue'
import RulesPage from '../pages/RulesPage.vue'
import BackupPage from '../pages/BackupPage.vue'

const routes = [
  { path: '/',           redirect: '/forest' },
  { path: '/forest',     name: 'forest',     component: ForestPage },
  { path: '/conflicts',  name: 'conflicts',  component: ConflictsPage },
  { path: '/rules',      name: 'rules',      component: RulesPage },
  { path: '/backup',     name: 'backup',     component: BackupPage },
]

export const router = createRouter({
  history: createWebHistory(),   // history mode, requires FastAPI SPA fallback
  routes,
})
```

### 导航栏

LayoutShell 组件包含左侧竖排导航（Element Plus `el-menu`），四个入口：
- 📊 Forest 可视化
- ⚔️ 冲突裁决
- 📋 规则管理
- 🗄️ 备份恢复

---

## 4. Pinia Store 设计

### 4.1 `useForestStore`

```typescript
// stores/forest.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

interface ForestNode {
  path: string
  destin_mixed_id: string
  changerequest: Changerequest[]
  warning?: string
  candidates?: string[]
}

interface Changerequest {
  path: string
  action: string
  action_order: number
  provenance_ref: string
  sidecar_ref: string
  mixed_id: string
  hashtype: string
  hashvalue: string
}

interface MappingEntry {
  path: string
  request: Changerequest
}

interface ConflictItem {
  target: string
  destin_mixed_id: string
  candidates: string[]
}

interface PipelineParams {
  database: object
  kmm_rule_paths: string[]
  user_config_path: string
  backup_dir: string
  dry_run: boolean
}

export const useForestStore = defineStore('forest', () => {
  // ── state ──
  const forest = ref<ForestNode[]>([])
  const finalMapping = ref<MappingEntry[]>([])
  const conflictList = ref<ConflictItem[]>([])
  const branchDecisions = ref<Record<string, string>>({})    // target → chosen_source
  const errors = ref<string[]>([])
  const warnings = ref<string[]>([])
  const svgContent = ref<string>('')                          // 后端返回的 SVG 字符串
  const isRunning = ref(false)
  const progress = ref({ step: '', finished: 0, total: -1, message: '' })

  // ── getters ──
  const unresolvedCount = computed(() =>
    conflictList.value.filter(c => !branchDecisions.value[c.target]).length
  )
  const isClean = computed(() => errors.value.length === 0 && unresolvedCount.value === 0)

  // ── actions ──
  async function runPipeline(params: PipelineParams) { ... }  // SSE
  function setDecision(target: string, source: string) { ... }
  function clearDecisions() { ... }
  function reset() { ... }

  return {
    forest, finalMapping, conflictList, branchDecisions,
    errors, warnings, svgContent, isRunning, progress,
    unresolvedCount, isClean,
    runPipeline, setDecision, clearDecisions, reset,
  }
})
```

### 4.2 SSE 集成

```typescript
// api/sse.ts — SSE 流式读取桥接到 Pinia

async function streamPipeline(params: PipelineParams, store: ReturnType<typeof useForestStore>) {
  store.isRunning = true
  store.reset()

  const response = await fetch('/api/pipeline/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // 解析 SSE 事件
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        const eventType = line.slice(7).trim()
        // 下一行是 data: ...
        // ... 完整解析逻辑
      }
    }
  }
}
```

> **实现注意**：SSE 解析遵循 `event: <type>\ndata: <json>\n\n` 格式（Phase 2 定义）。`event: progress` 更新 `store.progress`；`event: result` 写入 `store.forest/conflictList/errors/warnings`。

---

## 5. 交互流程

### 5.1 核心工作流（Happy Path）

```
① ForestPage:
   用户填写参数表单 → 点击"运行"
   → store.runPipeline(params) → SSE 进度条显示
   → 完成后 SVG 渲染在 ForestViewer 中
   → 用户可以 zoom/pan

② 若有冲突（unresolvedCount > 0）→ 导航栏"冲突裁决"显红点
   → 用户切换到 ConflictsPage
   → 表格列出每个 ConflictItem（target / destin / candidates）
   → 用户逐一点击候选 → store.setDecision(target, source)
   → 全部决策后点击"重新计算"
   → store.runPipeline({...params, branch_decisions: store.branchDecisions})

③ 无冲突 → finalMapping 展示，用户可执行 apply
```

### 5.2 ForestViewer 交互模型

```vue
<!-- ForestViewer.vue -->
<template>
  <div class="forest-container" ref="containerRef">
    <div class="forest-svg" v-html="svgContent" @click="onNodeClick">
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useForestStore } from '../stores/forest'

const store = useForestStore()
const containerRef = ref<HTMLElement>()

// zoom/pan: CSS transform 方案
const scale = ref(1)
const offset = ref({ x: 0, y: 0 })
function onWheel(e: WheelEvent) {
  e.preventDefault()
  scale.value *= (e.deltaY > 0 ? 0.9 : 1.1)
}

// 点击交互：事件委托
function onNodeClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  const nodeEl = target.closest('[data-forest-node]')
  if (!nodeEl) return

  const nodePath = nodeEl.getAttribute('data-forest-node')!
  const isConflictNode = nodeEl.hasAttribute('data-conflict')

  if (isConflictNode) {
    // 跳转到冲突裁决页面，预选中该节点
    router.push({ name: 'conflicts', query: { target: nodePath } })
  }
}
</script>
```

### 5.3 后端 SVG 约定

后端 `forest_visual.py` 生成的 SVG 需遵循以下规范（供前端交互使用）：

```
<g data-forest-node="/path/to/file.png" data-conflict="true">   ← 冲突节点
  <title>target: /path/to/file.png</title>
  <desc>candidates: /mod1/file.png, /mod2/file.png</desc>
  <rect ... />
  <text ... />
</g>

<g data-forest-node="/path/to/other.png">                       ← 普通节点
  <rect ... />
</g>
```

> **M3 任务**：升级 `forest_visual.py` 的 SVG renderer，为每个节点添加 `data-forest-node` 属性，冲突节点额外添加 `data-conflict="true"`，内嵌 `<title>` 和 `<desc>` 携带元数据。

---

## 6. 组件树

```
App.vue
├── LayoutShell.vue               ← 全局 chrome
│   ├── SseStatusBar.vue          ← 底部进度条（isRunning 时显示）
│   ├── el-menu (左侧导航)
│   └── el-main
│       └── <router-view />
│
├── ForestPage.vue                ← /forest
│   ├── PipelineForm.vue          ← 参数表单（database path, rules paths, backup dir, dry run toggle）
│   ├── ForestViewer.vue          ← SVG 渲染 + zoom/pan
│   └── ResultSummary.vue         ← 统计卡片（backed_up/applied/skipped/errors）
│
├── ConflictsPage.vue             ← /conflicts
│   ├── ConflictPanel.vue         ← 冲突列表表格
│   │   └── CandidateSelector.vue ← 单选候选（el-radio-group）
│   └── DecisionActions.vue       ← "重新计算" + "重置决策" 按钮
│
├── RulesPage.vue                 ← /rules
│   └── （MVP: kmm_rule 文件列表 + 内容查看器）
│
└── BackupPage.vue                ← /backup
    ├── BackupList.vue            ← 备份目录列表
    └── RestorePanel.vue          ← 恢复操作面板
```

---

## 7. Element Plus 组件映射

| UI 元素 | Element Plus 组件 |
|----------|-------------------|
| 全局布局 | `el-container` + `el-aside` + `el-main` |
| 导航菜单 | `el-menu` (vertical, collapse) |
| 参数表单 | `el-form` + `el-input` + `el-switch` + `el-button` |
| 进度条 | `el-progress` / `el-alert` |
| 冲突列表 | `el-table` + `el-tag` |
| 候选选择 | `el-radio-group` |
| 统计卡片 | `el-card` + `el-statistic` |
| 文件列表 | `el-tree` / `el-table` |
| 按钮操作 | `el-button` (primary/danger) |
| 通知 | `ElNotification` / `ElMessage` |
| 加载 | `v-loading` directive |
| Badge | `el-badge`（冲突数量红点） |

---

## 8. 对现有代码的改动

### 8.1 M3 前置：`forest_visual.py`（后端改动）

升级 SVG renderer，为节点嵌入交互属性：

```python
# 现有 SVG 生成逻辑中加入：
'data-forest-node': target_path,
'data-conflict': 'true' if node.has_conflict else None,   # 不渲染 None
'title': f'target: {target_path}',
'desc': f'destin: {destin_mid}',
```

> 改动量预估：在 `_render_svg_node()` 函数中追加 3-4 个属性，约 10-15 行。不影响现有测试。

### 8.2 `app.py`（Web 层改动）

新增静态文件 mount + SPA fallback 路由（见 §2）。

### 8.3 `pyproject.toml`

无改动（前端不通过 pip 管理）。

### 8.4 `modmanager_cli/*`

**零改动**。

---

## 9. 实现顺序

```
Task 15: frontend/ 脚手架          ← npm init + Vite + Vue 3 + TypeScript + Element Plus + Pinia
Task 16: M3 前置：forest_visual.py ← SVG 节点嵌入 data-forest-node / data-conflict / title / desc
Task 17: api/ 层（client.ts + sse.ts）← fetch 封装 + SSE 流解析
Task 18: stores/forest.ts          ← Pinia store 实现
Task 19: router + LayoutShell      ← Vue Router + 全局布局组件
Task 20: ForestPage + ForestViewer ← Forest 可视化嵌入（SVG zoom/pan + SSE 进度）
Task 21: ConflictsPage             ← 冲突裁决 UI（表格 + 候选选择 + 重新计算）
Task 22: RulesPage                 ← 规则浏览器（kmm_rule 文件列表 + 查看）
Task 23: BackupPage                ← 备份/恢复控制台（备份列表 + 恢复操作）
Task 24: app.py 更新               ← 静态文件 mount + SPA fallback
Task 25: 测试                      ← 前端 Vitest 单元测试 + Python 全量回归
```

---

## 10. 验收标准

1. `cd frontend && npm run build` 构建成功，产物写入 `src/modmanager_web/static/`
2. `modmanger-web` 启动后 `http://127.0.0.1:8000` 展示 Forest 页面
3. Forest 页面：填写参数 → 点击运行 → SSE 进度条 → SVG 展示 → zoom/pan 可用
4. 冲突裁决页面：展示冲突列表 → 选择候选 → 重新计算 → Forest 更新
5. 四个页面可正常路由切换，URL 正确（`/forest`、`/conflicts`、`/rules`、`/backup`）
6. Python 端 276 tests 保持通过
7. `__pycache__` 和 `node_modules/` 均被 `.gitignore` 排除
