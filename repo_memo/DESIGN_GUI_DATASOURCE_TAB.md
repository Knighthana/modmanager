# DESIGN_P6_DATASOURCE_TAB — 数据源独立选项卡

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 规定数据源独立选项卡的目标、问题域与设计方向，指导后续 GUI 数据源改造
> 来源：2026-05-07 用户讨论（数据源独立 + 去重 + 展示 + 暂存）  
> 依赖：P0-P5 全部已完成（338 Python + 42 前端 tests）  
> 更新：2026-05-09 — 重写 §3.3 重复 ID 决策（managed 字段 + 进来不管出去合法 + 批量提交）；补充库归属匹配规则（basepath/modpath 前缀匹配）

---

## 1. 涉及的问题

| 来源 | 问题 | 修复方向 |
|------|------|---------|
| BUG-1 | `manual` 模式仍跑 auto-discovery，用户无法做"仅手动" | 修复 `discover_with_fallback` |
| BUG-2 | 同 appid 跨库静默覆盖，无警告 | `_scan_from_libraries` 检测重复并写 warning |
| 当前讨论 | 缺少"全部/仅自动/仅手动"三选一 | 前端 mode 选择器 |
| 当前讨论 | 探测后无明细，用户无法审查结果 | 统一展示表格（库→游戏→MOD） |
| 当前讨论 | 重复 appid/modid 无法交互式选择 | radio group 决策 |
| TODO-1 | 数据源需独立选项卡 + 跨 tab 暂存 | 新页面 + persistence 模块 |

---

## 2. 架构变更

### 2.1 页面拆分

```
旧:     新:
/forest  /data-source  ← DataSourcePage（新建，数据源发现+审查）
         /forest       ← ForestPage（移除数据源面板）
/conflicts
/rules
/backup
```

### 2.2 后端修复范围

| 函数 | 改动 |
|------|------|
| `discover_with_fallback()` | 新增 `manual_only: bool=False` 参数；为 True 时跳过 auto 扫描 |
| `_scan_from_libraries()` | 返回 dict 新增 `warnings` 键；检测重复 appid 追加 warning |
| `regen_database()` | 传播 `warnings` 到返回值 |
| `generate_database()` | `mode='manual'` 时传 `manual_only=True`；`mode='auto'` + `paths` 非空时传 `manual_only=False`（即全部模式） |

### 2.3 `generate_database` 行为矩阵

| 前端选择 | `mode` | `paths` | `manual_only` | 行为 |
|---------|--------|---------|---------------|------|
| 仅自动 | `"auto"` | `null` | —（不适用） | 仅 auto discover |
| 仅手动 | `"manual"` | `["/tmp/..."]` | `True` | 仅 manual paths |
| 全部 | `"auto"` | `["/tmp/..."]` | `False` | auto + manual 合并 |
| 全部（无手动路径）| `"auto"` | `null` | — | 仅 auto discover（同仅自动） |

---

## 3. DataSourcePage 设计

### 3.1 布局概览

```
┌─ 数据源 ────────────────────────────────────────────────────────┐
│                                                                    │
│  ○ 全部   ○ 仅自动   ○ 仅手动                                    │
│                                                                    │
│  Working: [auto ▼]  Greedy: [○]  Cache: [/tmp/...]              │
│  ┌─ 手动路径（"仅手动"/"全部"时显示）───────────────────────┐    │
│  │ /tmp/fixture/steamapps                                     │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                    │
│  [🔍 扫描 Steam 库]                                               │
│                                                                    │
│  ═════════════ 扫描结果 ═════════════                             │
│                                                                    │
│  ▶ 📊 库摘要表                                                    │
│  ┌────┬───────────────────┬──────┬──────┬──────────────────────┐ │
│  │ 序 │ 👁           │ 游戏 │ MOD  │ 路径                   │ │
│  │ 号 │     │ 库名    │      │      │                        │ │
│  ├────┼──────┼─────────┼──────┼──────┼──────────────────────┤ │
│  │ 1  │ ✅❌  │ 库#1    │  35  │  12  │ /mnt/c/.../steamapps │ │
│  │ 2  │ ✅❌  │ 库#2    │  42  │  58  │ /mnt/d/.../steamapps │ │
│  │ 3  │ ✅❌  │ 库#3    │  13  │   4  │ /mnt/e/.../steamapps │ │
│  │ 4  │ ✅❌  │ 库#4    │   1  │  74  │ /tmp/fixture/steamapps │ │
│  └────┴──────┴─────────┴──────┴──────┴──────────────────────┘ │
│                                                                    │
│  ▶ 📋 游戏表                                                      │
│  ┌────┬────┬───────┬──────────┬────────────────┬──────┬────────┐ │
│  │ 序 │ [选]│ appid │ 名称      │ 路径           │ MOD  │ 所属库  │ │
│  │ 号 │     │       │           │                │ 数   │        │ │
│  ├────┼────┼───────┼──────────┼────────────────┼──────┼────────┤ │
│  │ 1  │  ○ │270150 │RWR        │/mnt/d/.../comm │  74  │ 库#2   │ │
│  │ 2  │    │107410 │Arma3      │/mnt/d/.../comm │  12  │ 库#2   │ │
│ ...                                                                 │
│  │ 35 │  ○ │270150 │RWR        │/tmp/fixture/co │  74  │ 库#4   │ │←重复!│
│ ...                                                                 │
│  └────┴────┴───────┴──────────┴────────────────┴──────┴────────┘ │
│                                                                    │
│  ⚠️ appid "270150" 在 库#2 和 库#4 中重复出现。勾选其一作为操作目标。│
│                                                                    │
│  ▶ 📦 MOD 表                                                      │
│  ┌────┬────┬──────────┬──────────┬────────┬────────┬────────────┐ │
│  │ 序 │ [选]│ MODID    │ 名称      │ 所属   │ 所属库  │ 路径       │ │
│  │    │     │          │           │ APPID  │        │            │ │
│  ├────┼────┼──────────┼──────────┼────────┼────────┼────────────┤ │
│  │ 1  │    │2606099273│GFL_Castl │270150  │ 库#2   │ /mnt/d/... │ │
│ ...                                                                 │
│  └────┴────┴──────────┴──────────┴────────┴────────┴────────────┘ │
│                                                                    │
│  [应用此数据源 → 前往 Forest]                                       │
└────────────────────────────────────────────────────────────────────┘
```

### 3.2 可见性筛选

| 控制 | 位置 | 效果 |
|------|------|------|
| 库行 ✅/❌ | 库摘要表每行 | 隐藏/显示此库的游戏 + 由此库游戏决定的 MOD |
| 游戏行 ✅/❌ | 游戏表每行 | 隐藏/显示此游戏决定的 MOD |
| MOD 可见性 | 计算 | `displayForLibrary(库) AND displayForGame(库.游戏)` |
| 默认 | — | 全部 ✅ |

偏好存入 persistence（跨 tab 暂存，与 TODO-1 生命周期一致）。

### 3.3 重复 ID 决策（managed + radio）

**原则**：进来不管，出去必须合法。

**数据模型**：
- 每个 `game` 条目有 `managed: boolean` 字段
- 每个 `mod` 条目有 `managed: boolean` 字段
- 同 `appid` 的 game 条目中，最多一个 `managed: true`
- 同 `mixed_id` 的 mod 条目中，最多一个 `managed: true`

**库归属匹配**：
- Game 条目的"所属库"通过 `basepath` 前缀匹配 `steamlib[].path` 确定：game 的 basepath 必然以所属 steamlib 的 path 开头
- Mod 条目的"所属库"通过 `path` 前缀匹配 game 的 `modpath` 确定：mod 的 path 必然以所属 game 的 modpath 开头
- 匹配失败时回退到 `libraryIndex = 0`
- **禁止**仅凭 `appid` 或 `mixed_id` 做库归属推断——同 ID 可跨库出现，必须用路径前缀匹配

**加载时（读入）**：
- 从 `database.json` 读取 `managed` 字段，直接反映到 radio 状态
- 不做合法性校验——允许多个同名的 `managed: true` 并存（前端如实展示）
- radio 仅展示状态，不做即时写入

**编辑时**：
- 用户点击 radio 切换 `managed` 状态，仅改变前端本地状态
- Game 表的 radio 和 Mod 表的 radio **各自独立**，不共用 v-model
- `managed: false` 的条目仍正常显示，只是 radio 为 unchecked
- 重复组中任一 radio 被选中时，同组其他 radio 自动变为 unchecked（前端本地互斥）

**离开时（写出）**：
- 点击"确认并进入规则概览"按钮
- 收集当前所有条目的 `managed` 状态
- 调用 `POST /api/database/save`，后端校验：
  - 同 appid 最多一个 `managed: true`
  - 同 mixed_id 最多一个 `managed: true`
- 校验通过 → 写入 `database.json` → 导航到规则概览页
- 校验失败 → 返回具体错误列表，**逐条平铺展示**（不计数），用户修正后重试

**错误展示**：
- 错误和警告**逐条平铺**，不显示计数
- 每条错误/警告包含完整描述，用户可直接定位问题

### 3.4 跳转与导航

- 底部按钮：**"确认并进入规则概览"**——触发 §3.3 的批量保存流程
- 保存成功 → 导航到 `/rules-overview`
- 点击游戏表的"MOD 数" → `scrollintotabitem(element)` 跳转到该游戏的第一个 MOD
- 点击 MOD 表的"所属库" → 跳转到库摘要行

### 3.5 表格定长

```css
.horizontal-cell-scroll {
  white-space: nowrap;
  overflow-x: auto;
  scrollbar-width: none;
}
```

应用于路径列。名称列截断 + hover tooltip（Element Plus `el-table-column` 默认行为）。

---

## 4. Persistence 模块

### 4.1 接口抽象

```typescript
// frontend/src/utils/persistence.ts

interface PersistenceAdapter {
  save(key: string, value: unknown): void;
  load<T>(key: string): T | null;
  clear(key: string): void;
}

// 浏览器实现
class LocalStorageAdapter implements PersistenceAdapter { ... }

// 预留 Tauri 接口
// class TauriStoreAdapter implements PersistenceAdapter { ... }

// 工厂
export function createPersistence(): PersistenceAdapter {
  // 当前: localStorage
  return new LocalStorageAdapter();
}
```

### 4.2 Store 使用

```typescript
// useDataSourceStore
import { createPersistence } from '@/utils/persistence';

const pers = createPersistence();
pers.save('datasource', { discoveryMode, manualPath, visibility, resolutions });
const saved = pers.load<DataSourceState>('datasource');
```

---

## 5. 任务分解

### 后端修复（3 tasks）

| # | 任务 | 模块 |
|---|------|------|
| B1 | `discover_with_fallback()` 新增 `manual_only: bool=False` 参数 | `database_ops.py` |
| B2 | `_scan_from_libraries()` 检测重复 appid + 返回 warnings；`regen_database` 传播 warnings | `database_ops.py` |
| B3 | `generate_database()` 按矩阵传递 `manual_only` | `bootstrap.py` |

### 前端重构（8 tasks）

| # | 任务 | 模块 |
|---|------|------|
| F1 | 新建 `utils/persistence.ts` — 抽象存储层（接口 + localStorage + 预留 Tauri） | 前端新文件 |
| F2 | 新建 `utils/scroll.ts` — `scrollintotabitem()` 封装 | 前端新文件 |
| F3 | 新建 `stores/datasource.ts` — `useDataSourceStore`（状态 + 持久化 + 筛选逻辑） | 前端新文件 |
| F4 | 新建 `pages/DataSourcePage.vue` — 扫描面板 + 三表 + 警告 + 跳转 | 前端新文件 |
| F5 | ForestPage 移除数据源面板，database 路径改为可解锁编辑 | `pages/ForestPage.vue` |
| F6 | 路由新增 `/data-source`，导航栏加"数据源"选项 | `router/` + `App.vue` |
| F7 | DataSourceStore → ForestStore 跨 store 传递 database 数据 | 前端 stores |
| F8 | `types/` 扩展数据源相关类型 | `types/index.ts` |

### 测试（3 tasks）

| # | 任务 | 模块 |
|---|------|------|
| T1 | 后端：`test_web_api.py` 扩展（manual_only + 重复 warning） | `tests/` |
| T2 | 后端：`test_database_ops.py` 扩展（重复检测） | `tests/` |
| T3 | 前端：DataSourcePage + store + persistence 单元测试 | `frontend/src/__tests__/` |

### 总计：14 tasks

---

## 6. 验收标准

| 验收项 | 条件 |
|-------|------|
| Python 全量 | 338+ 新增后端测试全部通过 |
| 前端 Vitest | 42+ 新增前端测试全部通过 |
| 前端构建 | `npm run build` 成功 |
| "仅手动"模式 | `/tmp/fixture/steamapps` → 仅 1 个库，无 auto 干扰 |
| 重复 appid 警告 | 同 appid 跨库 → warnings 字段中存在，前端 radio 可选 |
| 跨 tab 暂存 | 切换到 Forest 再切回 DataSource → 状态不丢失 |
| 可见性筛选 | 隐藏某库 → 其游戏+MOD 消失（AND 逻辑） |

---

## 7. 决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | 持久化方案 | 自写抽象层 `persistence.ts`，当前 localStorage，预留 Tauri |
| D2 | 重复 ID 处理 | 交互式 radio group，同一 ID 的多行共享 |
| D3 | 表格布局 | 统一大表（库→游戏→MOD，依次纵向排列），库摘要在最顶 |
| D4 | 库标识 | 序号 "库#1" / "库#2" |
| D5 | 跳转 | `scrollintotabitem()` 封装，当前 `scrollIntoView` |
| D6 | 定长表格 | `.horizontal-cell-scroll` CSS 类 |
| D7 | 可见性 | `displayForLibrary AND displayForGame` 决定 MOD 显示 |
| D8 | ForestPage database | 自动传入（store），可解锁手动编辑 |
