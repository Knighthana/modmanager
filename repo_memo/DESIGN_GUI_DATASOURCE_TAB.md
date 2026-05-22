# DESIGN_P6_DATASOURCE_TAB — 数据源独立选项卡

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 规定数据源独立选项卡的目标、问题域与设计方向，指导后续 GUI 数据源改造
> 来源：2026-05-07 用户讨论（数据源独立 + 去重 + 展示 + 暂存）  
> 依赖：P0-P5 全部已完成（338 Python + 42 前端 tests）  
> 更新：2026-05-09 — 重写 §3.3 重复 ID 决策（managed 字段 + 进来不管出去合法 + 批量提交）；补充库归属匹配规则（basepath/modpath 前缀匹配）+ MOD 排列顺序（appid+modid 数值序）+ TODO-19 视觉提示规定
> 更新：2026-05-13 — 重写 §3.3：managed 决策从 DataSourcePage 完全移除。重复条目纯展示，不做裁决。预选移至计算准备页（checkbox + managed_entries 作为 compute 参数）

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
│  选择的数据库: [default ▼]                                         │
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

### 3.3 重复条目——纯展示，不做裁决

**原则**：DataSourcePage 仅展示扫描结果。对重复 appid/mixed_id 条目不提供 radio、不提供"确认"按钮、不做任何用户决策。

**行为**：
- database.json 中所有重复条目**全部展示**在表格中
- 重复条目不额外高亮、不标记——DataPage 是客观数据展示，不引入"待决策"语义
- 重复条目的取舍在**计算准备页**完成（通过 checkbox 可选预选，见 `DESIGN_COMPUTE_PREP_PAGE.md`）
- 若用户不做任何预选，engine 自行处理重复条目（产生 branching 由 ConflictsPage 裁决）

**库归属匹配**（不变）：
- Game 条目的"所属库"通过 `basepath` 前缀匹配 `steamlib[].path` 确定
- Mod 条目的"所属库"通过 `path` 前缀匹配 game 的 `modpath` 确定
- 匹配失败时回退到 `libraryIndex = 0`
- **禁止**仅凭 `appid` 或 `mixed_id` 做库归属推断

**MOD 排列顺序**（不变）：
- MOD 表条目按 `(appid数值, modid数值, modid字符串)` 三级排序

---

## 3.4 自动读取 database

DataSourcePage **不再是纯扫描页**——用户选择 database 后应能立即查看其内容，无需先点"扫描"。

**触发时机**：
1. 页面挂载（`onMounted`）——读取 `DatabaseSelector` 默认值对应的 database
2. 用户切换 `DatabaseSelector` 下拉选项（`watch`）——自动读取新选中的 database

**数据流**：
```
DatabaseSelector 变化
  → POST /api/database/read { database_name }
  → 后端返回 database JSON（含 steamlib / game / mod）
  → 前端调用 _populateFromDatabase(db) 渲染三张表格
  → 可见性 toggle 重置为全部可见
```

**与"扫描"按钮的关系**：
- 扫描 (= `POST /api/database/generate`) 仍然是**重新生成** database 的唯一方式
- 自动读取只展示当前 database 的**已有内容**，不触发扫描
- 扫描完成后，扫描结果自动覆盖当前展示

### 3.5 steam.exe 手动指定（Windows）

当前手动模式仅支持输入 `steamapps/` 目录路径（文本输入）。Windows 用户更倾向于"选 `steam.exe`"的交互。

**前端**：新增文件选择器 `<input type="file" accept=".exe">`（仅 Windows 平台显示）。用户选择 `steam.exe` → 前端将路径传入 API。

**后端**：`GenerateDatabaseRequest` 新增 `steam_exe_path: str | None` 字段。当此字段非空时，后端按 `DESIGN_BOOTSTRAP.md` §2.1 推导 SteamRoot → 定位 `libraryfolders.vdf` → 展开库列表。

**UI 交互**：
- 手动路径表保留（Linux/macOS 用户继续使用文本输入）
- Windows 下额外显示文件选择器按钮：`[📁 选择 steam.exe]`
- 选中的 steam.exe 路径展示在选择器下方，可清空
- 与现有"全部/仅自动/仅手动"模式选择器正交——steam.exe 仅在手动路径生效时参与

> 实现文件选择器无需额外依赖——`<input type="file">` 是浏览器标准 API。

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
| F4 | 新建 `pages/DataSourcePage.vue` — 扫描面板 + 三表 + 警告 | 前端新文件 |
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
| 自动读取 database | 页面挂载时自动加载选中 database；切换 database 下拉自动刷新表格 |
| steam.exe 选择 | Windows 下显示文件选择器，选中后路径传入 API 请求 |

---

## 7. 决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | 持久化方案 | 自写抽象层 `persistence.ts`，当前 localStorage，预留 Tauri |
| D2 | 重复 ID 处理 | 重复条目 DataSourcePage 纯展示，裁决移入 ComputePrepPage |
| D3 | 表格布局 | 统一大表（库→游戏→MOD，依次纵向排列），库摘要在最顶 |
| D4 | 库标识 | 序号 "库#1" / "库#2" |
| D5 | 跳转 | `scrollintotabitem()` 封装，当前 `scrollIntoView` |
| D6 | 定长表格 | `.horizontal-cell-scroll` CSS 类 |
| D7 | 可见性 | `displayForLibrary AND displayForGame` 决定 MOD 显示 |
| D8 | ForestPage database | 自动传入（store），可解锁手动编辑 |
| D9 | 自动读取 database | 页面挂载 + database 切换时自动调 `/database/read`，无需先扫描 |
| D10 | steam.exe 路径 | Windows 下用 `<input type="file">` 选择，后端按 `DESIGN_BOOTSTRAP.md` §2.1 推导 |
