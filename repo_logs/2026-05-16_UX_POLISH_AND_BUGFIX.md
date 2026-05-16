# 2026-05-16 前端联调 — UX 打磨与 bug 修复

> 继工作区模型落地后的前端实机测试与改进

---

## 一、关键 Bug 修复

| Bug | 根因 | 修复 |
|------|------|------|
| 白屏 | `useAppStore().init()` 在 Pinia 安装前调用 | 改为直接调 `migrateOldWorkspace()` |
| database 列表为空 | `API_ENDPOINTS` 含 `API_BASE` → apiPost 双重前缀 `/api/api/...` | 端点常量改为相对路径，文档固化规则 |
| GET 端点 405 | `apiPost` 永远发 POST | 新增 `apiGet()`；3 处调用修正 |
| ElMessageBox 无样式 | 命令式组件 CSS 不被 `unplugin-vue-components` 加载 | `main.ts` 显式导入 CSS |
| 规则聚合 422 | `RulesAggregateRequest` 前向引用未顶层 import | 顶层 import，去掉字符串引用 |
| 聚合错误提示不显示 | FastAPI 422 返回 `detail` 而非 `errors` | 同时读取 `detail` 数组 |
| 森林可视小地图消失 | `watch` 缺 `{immediate: true}` | 加 immediate |
| 库表复选框刷新后不反映 decisions | `recalcLibraryState` 在 decisions 加载前执行 | 补调于 decisions 恢复后 |
| 查看结果按钮刷新后灰色 | 仅依赖 Pinia 内存不检查后端 | 页面加载时 GET `/forest/mapping` |

---

## 二、UX 规范落地

### 导航栏
- 无工作区时：工作区相关菜单项灰显（短文案），点击 `el-popover` 气泡提示
- 不再跳转——用户停留原地

### 工作区列表
- 创建后**不自动跳转**，新卡片上弹出一次性 popover 提示
- 按钮语义色：`新建`(蓝) → `进入`(绿) → `删除`(红)

### 计算准备
- `开始计算`：执行后保持在当前页
- `查看结果`：橙色，页面加载时检查后端；无结果→灰色 disabled
- 复选框：加载期间全部未选，decisions 恢复后按规则勾选 → 库表重算三态

### 规则概览
- 聚合错误：中文描述 + 原始错误码，持续 8 秒
- 跳转链接：`.subtle-link` 样式（无边框/浅蓝文字/悬浮光晕）

### 删除确认
- `confirmButtonType='danger'`（语义红，夜间模式自动适配）
- 按钮加 emoji

---

## 三、功能实现

| 项 | 内容 |
|------|------|
| TODO-69 | `inputs_hash` 指纹计算：`compute_ws` 写入 `fingerprints.json`（kmmrule + database SHA256 + timestamp） |
| Transport 收敛 | 14 个文件 import 从 `api/client`、`api/sse` → `api/transport` |
| 存储门禁 | useAppStore 封装 persistence.ts，组件不直接 import persistence |
| 审计清结 | audit_todo_future 三项全部完成 |

---

## 四、新增设计文档

- `DESIGN_EXT_RESOURCE.md` — 外部资源服务模型（preview/readme 端点、白名单机制、`ext_resource` 独立包）

## 五、文档更新

- `DESIGN_GUI.md` — 页面流拓扑、RulesOverviewPage、ComputePrepPage 行为规范
- `DESIGN_WORKSPACE_MODEL.md` — UX 规范增补（按钮语义、导航提示、创建流程）
- `DESIGN_FRONTEND_LAYER_INDEPENDENCE.md` — API 调用规则固化、两层架构
