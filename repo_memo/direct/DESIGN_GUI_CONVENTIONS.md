# DESIGN_GUI_CONVENTIONS — GUI 行为约定

> 状态：DRAFT  
> 来源：2026-05-07 夜间 GUI 迭代讨论  
> 覆盖：ForestPage 交互行为、通知系统、路径显示规范、品牌元素

---

## 1. ForestPage — Database 路径行

### 1.1 布局

```
[el-form-item label="Database 路径"]
  [el-input (flex:1)]   [ℹ️ popover]   [按钮]

输入框内 #suffix 槽：
  锁定: "🔒"（仅锁 emoji）
  解锁: 无

按钮文字：
  锁定: "手动填写"
  解锁: "使用自动"
```

### 1.2 锁定 / 解锁语义

| 状态 | 输入框 | 按钮 | 点击效果 |
|------|--------|------|---------|
| 锁定 | disabled，灰色 | "手动填写" | 解锁 → 可写，文字全选 |
| 解锁 | editable，白色 | "使用自动" | 锁定 → 恢复自动值 |

### 1.3 内容来源

```typescript
const dbPathDisplay = computed({
    get(): string {
        // 锁定: 带 "(从数据源页面自动传入)" 后缀
        // 解锁: 纯路径
    },
    set(value: string) { store.pipelineForm.databasePath = value }
})
```

### 1.4 自动传入标识

当 `storedDatabase` 存在（从 DataSource 页面应用）：
- 显示 `Frontend Storage (从数据源页面自动传入)`
- 否则显示 `{path} (从数据源页面自动传入)`

### 1.5 自动重新锁定

DataSourcesPage 的"应用此数据源 → 前往 Forest"操作会：
- 设置 `forestStore.dbManualOverride = false`
- 设置 `forestStore.storedDatabase = lastResult`

---

## 2. prepareParams 数据库优先级

```typescript
// 优先级 1: Database JSON 非空
if (databaseJson.trim()) → JSON.parse(databaseJson)

// 优先级 2: 自动模式 + storedDatabase 存在
else if (!dbManualOverride && storedDatabase) → storedDatabase（dict）

// 优先级 3: 手动模式 + databasePath 非空
else if (dbManualOverride && databasePath) → databasePath（str，后端 resolve + load）

// 优先级 4: 无数据
else → {}
```

前端在手动模式下直接发路径字符串给后端——不绕路先 load 再发 dict。

---

## 3. 错误 / 警告提示系统

### 3.1 模块架构

```
notify.ts        — 平台解耦的弹出通知（当前:浏览器 DOM popup，预留: Tauri）
errorCodes.ts    — 错误/警告代码 → 人类可读说明的映射
                 — extractCode(msg) / getDescription(msg)
```

### 3.2 交互

- 错误/警告条目可点击
- 点击 → `extractCode(msg)` → 查映射 → `showPopup(description, element)` → 气泡出现在条目右侧
- 气泡可关闭（× 按钮 / 点击外部）

### 3.3 ℹ️ 信息气泡

ForestPage Database 路径行的 ℹ️ 图标同样调用 `showPopup()`，不使用 Element Plus `el-popover`。

---

## 4. 路径显示规范

- 所有 GUI 表格中目录路径显示必须以 `/` 结尾
- 使用 `ensureTrailingSlash(path)` 工具函数（`utils/paths.ts`）
- 输入框 placeholder 提示路径以 `/` 结尾

---

## 5. 侧边栏品牌

- 侧边栏顶部显示项目名称
- 格式：`🔧 Knighthana's Mod Manager`
- 样式：粗体 800，14px，允许换行，底部有分割线

---

## 6. ForestStore reset() 边界

`reset()` 仅清空**输出字段**（trees、errors、warnings、finalMapping 等），保留**输入字段**（storedDatabase、pipelineForm、dbManualOverride、userConfig）。

---

## 7. 决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | Database 输入形式 | pipeline 端点同时接受 dict 和路径字符串，后端自行 resolve + load |
| D2 | 通知系统 | `notify.ts` 平台解耦抽象层，当前浏览器 DOM popup 实现 |
| D3 | 错误说明 | 点击条目弹出，不再使用静态"关于警告"块 |
| D4 | 路径显示 | 目录路径统一以 `/` 结尾 |
| D5 | reset() 范围 | 只清输出不清输入 |
| D6 | prepareParams 优先级 | JSON > storedDatabase dict > path string > {} |
