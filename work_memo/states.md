# 工作状态

## 进行中：前端持久化入口收束 — `useAppStore`

> Pinia store 包装 persistence.ts，所有浏览器存储读写统一入口。
> 命名：`useAppStore`（旧 audit 的 `useWorkspaceStore` 已不适用，workspace 现指后端工作区目录）

- [x] TODO-A1: 新建 `src/stores/app.ts`（useAppStore，封装 persistence.ts 所有导出函数为 reactive action）
- [x] TODO-A2: 改造各页面/组件：`import from '../utils/persistence'` → `import from '../stores/app'`
- [x] TODO-A3: 更新 `DESIGN_FRONTEND_LAYER_INDEPENDENCE.md`（§2.1 改为两层架构，§4 检查清单更新）
- [x] TODO-A4: 更新 `DESIGN_WORKSPACE_MODEL.md`（可延后项引用更新为 useAppStore）
- [x] TODO-A5: vue-tsc + vitest 验证

---

## 存量待办

- [ ] （挂起）TODO-10: 前端空输入校验
- [ ] （待讨论）TODO-51: 统一界面视觉
- [ ] （待讨论）TODO-52: 主题切换
- [ ] （待讨论）TODO-53: 日志文件整洁
- [ ] TODO-66: 规则概览 — preview 图片加载（外部资源，需白名单机制）
- [ ] TODO-67: 规则概览 — README 文件内容查看（外部资源，需白名单机制）
- [ ] TODO-68: 规则概览 — author 字段的键含义与展示方式待讨论
- [ ] TODO-69: `inputs_hash` 实现不完整
- [ ] TODO-70: 森林图展示打磨（小地图比例/滚动条/放缩）— 独立任务

### 可延后（来自 audit_todo_future.md）
- [x] ~~`useWorkspaceStore` 唯一写者~~ → 已落地为 `useAppStore`
- [x] `activeTab` / `sidebarCollapsed` 迁入 uiState → 已通过 useAppStore 实现（独立 key，非嵌套对象）
- [ ] 前端 Transport Abstraction（`src/api/transport.ts`）
