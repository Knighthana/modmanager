# Phase 3: 前端 GUI — 不确定性问题

创建：2026-04-30
状态：全部已决策 ✅
前置完成：Phase 1（bootstrap + orchestrator）✅ + Phase 2（Web API）✅

---

## 背景：已知决策与约束

### TASKLIST 中的 Phase 3 定义
> 规则浏览器、Forest 可视化嵌入、冲突裁决 UI、备份/恢复控制台。

### 已固化的设计约束

| # | 约束 | 来源 |
|---|------|------|
| 1 | **Web 形态**：在 Web 上投射管理终端 | `description/gui_description.md` |
| 2 | **架构**：通过 `modmanager_web` REST API + SSE 通信 | `DESIGN_REST_API.md` |
| 3 | **调度**：orchestrator 是 GUI 唯一调度入口（与 CLI 共享内核） | `DESIGN_ORCHESTRATOR.md` |
| 4 | **CLI 与 GUI 独立对等**（方案 A，共享内核模式） | `DESIGN_REST_API.md` Q7 |
| 5 | **进度推送**：SSE 已就绪（`text/event-stream`） | Phase 2 `sse.py` |
| 6 | **CORS 已开放**：`allow_origins=["*"]` | Phase 2 `app.py` |
| 7 | **action_order 由 GUI 运行时注入** | `DESIGN_RULE_AGGREGATOR.md` |
| 8 | **hash 展示由 GUI 负责**（状态机：未计算/已计算） | `OPEN_CONFLICTS.md` |
| 9 | **database 预留 UI 字段**：`history.ui.locale`、`history.layout.games_panel_ratio` | `database.json.example` |
| 10 | **preview 格式为 list**：WebUI 做轮换展示 | `description/TODO.md` |
| 11 | **backup_dir 命名由调用方（GUI）决定** | `DESIGN_ORCHESTRATOR.md` |

### Forest 可视化演进路径（已定义）
```
近期（已完成）：ASCII + DOT + DOT→SVG                    ← 控制台
M3（未做）   ：HTML fragment + HTML standalone            ← 静态浏览器
               + Plot renderer + trace/meta 兼容验证
M4（未做）   ：hover 整链高亮 + 分叉超链接 + 用户选枝      ← 交互式 GUI
               + 插件运行链 + 老浏览器 fallback
```

### 现有交互原型（cli-hmi demo.py）
cli-hmi 的 `demo.py` Phase 5 实现了终端的交互式冲突裁决流程：
```
遍历冲突节点 → 展示候选列表 → 用户输入选择 → 保存决策 → 二次映射
```
这是 GUI 冲突裁决 UI 的直接原型。

---

## 不确定性问题

### Q1: 前端技术栈

这是最大的开放问题。历史线索中有两条路径：

**路径 A：零依赖静态 HTML + vanilla JS + inline CSS**
- 参考 `cli-hmi/repo_memo/20260423_html_viewer_mvp_plan.md` 的设计
- 优点：KISS，无需 npm，与 Python 项目同构（无额外构建工具）
- 缺点：交互复杂后代码维护困难，无组件化，不适合大规模 UI
- 适合场景：**MVP 快速验证，功能简单**

**路径 B：现代前端框架（React / Vue / Svelte）**
- 优点：组件化，生态丰富，适合 4 大模块的复杂交互
- 缺点：引入 npm/Node 构建链，增加项目复杂度
- 适合场景：**正式产品，功能复杂，长期迭代**

**路径 C：HTMX 混合方案**
- 优点：HTML 主导，少量 JS，不需要完整前端框架
- 缺点：复杂的可视化交互（Forest 图的 hover/zoom/pan）仍需要 JS
- 适合场景：**以页面为主、少量动态交互的场景**

→ 倾向于哪条路径？

---

### Q2: M3 与 Phase 3 的关系

M3（HTML standalone + Plot renderer）属于 Forest 可视化的中间里程碑，Phase 3 是 GUI 的完整交付。二者关系有两种理解：

**方案 A：Phase 3 包含 M3**
- M3 的 HTML standalone 作为 Phase 3 的 Forest 可视化嵌入模块的第一个交付物
- Plot renderer 作为 Forest 可视化的备选渲染方式并入

**方案 B：M3 在 Phase 3 之前独立完成**
- 先把静态 HTML 可视化做出来（纯后端生成，零前端交互）
- Phase 3 再做交互式 GUI（在前端框架中集成）

→ Phase 3 是否包含 M3？还是 M3 作为前置条件先做？

---

### Q3: 部署模式

**方案 A：嵌入 FastAPI**
- 前端静态文件（HTML/CSS/JS）由 FastAPI 直接 serve（`StaticFiles` mount）
- 同一端口、同一进程，零 CORS 问题（本就是同源）
- 部署简单：`pip install` + `modmanager-web` 一把启动
- 限制：无热更新（HMR），开发体验较差

**方案 B：独立前端开发服务器**
- 前端用 Vite/Next dev server（端口 5173）+ 代理 API 到 8000
- 开发体验好（HMR），但部署需要额外步骤
- 生产构建后，产物可放回 FastAPI 静态目录

→ 开发模式用 B，生产部署用 A（前端 build 产物嵌入 FastAPI）？还是有其他偏好？

---

### Q4: 四大模块的优先级与分批策略

Phase 3 定义了四个模块：
1. **规则浏览器** — 浏览、查看、编辑 kmm_rule 文件
2. **Forest 可视化嵌入** — 在浏览器中查看森林图（可交互）
3. **冲突裁决 UI** — 分支决策交互（参考 cli-hmi demo.py 原型）
4. **备份/恢复控制台** — 管理备份目录、执行恢复

是**一期全部实现**，还是**分批交付**？如分批，建议顺序是什么？

个人直觉的优先级（从依赖关系和用户价值角度）：
```
Forest 可视化 → 冲突裁决 → 规则浏览器 → 备份控制台
     (基础)      (核心流程)    (数据管理)    (工具类)
```
Forest 可视化和冲突裁决构成了核心工作流（"看到→选择→执行"），可先交付。

---

### Q5: 交互深度 — MVP 范围

参考 cli-hmi demo.py 的交互原型，冲突裁决的核心交互是：
```
① 展示冲突节点列表
② 显示每个节点的候选来源
③ 用户选择候选 → 保存决策
④ 一键重新计算并预览最终映射
```

对于 MVP 阶段，交互程度的边界在哪里？

- **最小集**（等同于终端原型）：
  - Forest：SVG 渲染 + zoom/pan，无 hover 高亮
  - 冲突裁决：表格形式列表 + 下拉选择 + 按钮提交
  - 规则浏览器：纯文本展示
  - 备份控制台：列表 + 按钮操作

- **完整集**（含 M4 特性）：
  - Forest：hover 整链高亮 + 分叉节点可点击 + 详情弹窗
  - 冲突裁决：可视化森林中直接选枝 + drag-drop
  - 规则浏览器：可视化编辑表单 + 语法高亮
  - 备份控制台：时间轴视图 + diff 预览

→ MVP 做到什么程度？

---

### Q6: 前后端通信协议

Phase 2 已提供 REST API + SSE。是否需要 WebSocket？

- **纯 REST + SSE**：当前已就绪，适合大多数场景（请求→响应 + 单向推送）
- **加入 WebSocket**：双向实时通信，适合需要服务端主动推送的场景（如后台任务完成通知）

当前 SSE 覆盖了 progress → result 的推送模式。除非有"用户在 GUI 操作时，服务端需要主动通知"的需求（例如另一个 CLI 实例修改了文件），否则 REST + SSE 已足够。

→ 需要 WebSocket 吗？还是 Phase 3 MVP 保持 REST + SSE？

---

### Q7: 访问范围与认证

Phase 2 的 Web API 设计为 `127.0.0.1` only，无认证。

- **仅 localhost**：最简单，无安全问题，但仅限本机浏览器
- **局域网访问**：可通过 `0.0.0.0` 监听，但需要至少简单的 token 认证
- **HTTPS**：是否有需求？

→ GUI 仅限本机使用，还是需要局域网内其他设备访问？

---

### Q8: 构建工具与包管理

如果选择路径 A（零依赖 HTML），不需要 npm。

如果选择路径 B 或 C（有 JS 构建），需要决定：
- 包管理器：npm / yarn / pnpm？
- 构建工具：Vite / Webpack / 直接用框架 CLI？
- TypeScript 还是 vanilla JS？
- 前端代码放在项目中的哪个位置？`frontend/`？`src/modmanager_web/static/`？

→ 取决于 Q1 的选择，再进一步细化。

---

## 其他可提前决策的事项（非阻塞）

### 国际化
database 中已有 `history.ui.locale: "zh_CN"` 预留。GUI 初期是否需要支持多语言？还是仅 zh_CN？

### 主题
是否需要深色/浅色主题切换？

### 响应式
是否需要适配移动端？还是仅桌面浏览器？

### 测试策略
- 前端单元测试（Jest / Vitest）
- E2E 测试（Playwright / Cypress）
- 是否需要保持 Python 端 276 tests 不受影响？（答案：是）

---

## 决策汇总

| Q# | 决策 |
|-----|------|
| Q1 | **Vue 3** — 手写 JS 不易维护，Vue.js 组件化 |
| Q2 | **分开做** — M3（HTML standalone）先独立完成，Phase 3 再做交互式 GUI |
| Q3 | **方案 A** — 前端静态文件嵌入 FastAPI（同一端口，零配置部署） |
| Q4 | **Forest 可视化 → 冲突裁决 → 规则浏览器 → 备份控制台** |
| Q5 | **先最小集排坑** — 表格 + 按钮 + SVG zoom/pan；逐步实现完整集 |
| Q6 | **REST + SSE**（Phase 2 已有，不引入 WebSocket） |
| Q7 | **仅 localhost**（无认证，与 Phase 2 一致） |
| Q8 | **npm + Vite + TypeScript** — 用 FNM 管理 Node 环境 |
| Q9 | **frontend/**（项目根目录，前端代码彻底与后端解耦） |
| Q10 | **方式 A** — 后端渲染 SVG → API 返回 → Vue `v-html` 嵌入 + 事件委托交互 |
| Q11 | **Element Plus** — Vue 3 生态最成熟的组件库 |
| Q12 | **SPA + Vue Router** — 单页应用，客户端路由 |
| Q13 | **Pinia** — `useForestStore` 存储 forest / conflictList / branchDecisions / finalMapping |

## 详细设计

见 `repo_memo/DESIGN_GUI.md`
