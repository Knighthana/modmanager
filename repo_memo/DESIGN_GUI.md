# DESIGN_GUI — 前端 GUI 设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 规定前端 GUI 的总体架构、页面流、交互边界与页面级设计原则
> 创建：2026-05-08
> 更新：2026-05-13 — 【重大改版】六页面流重定义；Forest 全屏 SVG 布局；DataSource 缩减为纯展示；新增计算准备页；managed_entries 改为可选预选 + compute 参数传入；移除前端业务数据持久化
> 来源：2026-05-13 讨论（mock-first 策略、localStorage 清退、managed 语义迁移、workspace 状态设计）

---

## 一、架构总览

```
┌────────────────────────────────────────────────┐
│                   frontend/                     │
│        Vue 3 + Vite + TypeScript               │
│        Element Plus + Pinia + MSW (dev mock)    │
│                                                │
│  ┌──────────┐  ┌─────────────┐                │
│  │ Vue      │  │  SSE Client │                │
│  │  Router   │  │  (fetch+流)  │                │
│  └────┬─────┘  └─────────────┘                │
│       │                                        │
│  ┌────▼────────────────────────┐              │
│  │       Pinia Store            │              │
│  │  useForestStore              │              │
│  │  useDataSourceStore          │              │
│  │  (仅内存状态，不做数据持久化)  │              │
│  └─────────────────────────────┘              │
└──────────────────┬─────────────────────────────┘
                   │ fetch / SSE (localhost)
┌──────────────────▼─────────────────────────────┐
│           modmanager_web (FastAPI)             │
│  GET/POST /api/*  (REST + SSE endpoints)       │
└──────────────────┬─────────────────────────────┘
                   │ import
┌──────────────────▼─────────────────────────────┐
│             modmanager 核心模块                  │
│  orchestrator / engine / database_ops / ...     │
└────────────────────────────────────────────────┘
```

---

## 二、页面流

```
 ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
 │DataSource│ → │  Rules   │ → │  计算准备  │ → │  Forest  │ → │Conflicts │ → │Operations│
 │          │    │ Overview │    │(ComputePrep)│   │          │    │          │    │          │
 │磁盘上有什么│    │用哪些规则  │    │预选+计算   │   │看图       │    │分支裁决   │    │执行操作   │
 └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### 页面职责矩阵

| 页面 | 路由 | 职责 | 写入操作 |
|------|------|------|---------|
| DataSourcePage | `/datasource` | 扫描 Steam 库 → 三张表纯展示（lib/game/mod）；可见性筛选 | `POST /api/database/generate`（后端写 database.json） |
| RulesOverviewPage | `/rules-overview` | 展示所有可用 rule 文件 + 详情；用户勾选 + [保存规则选择] → 后端聚合 | `POST /api/rules/aggregate`（后端写 aggregated_rule_set.json） |
| 计算准备 | `/compute-prep` | 展示受影响 game/mod；重复条目柔和高亮；可选预选（checkbox）；[▶ 开始计算] | `POST /api/pipeline/compute`；成功→ [查看结果] 亮起 |
| ForestPage | `/forest` | 全屏 SVG 可视化；摘要抽屉；警告面板；小地图；结果过期检测 | 无（纯消费计算结果） |
| ConflictsPage | `/conflicts` | 分支冲突表格 + radio 选择；[确认决策] → 写 branch_decisions 到 workspace | 写 `localStorage.modmanager:workspace.perDatabase[name].decisions.branch_decisions` |
| OperationsPage | `/operations` | 映射摘要 + backup/apply/restore 按钮 | `POST /api/pipeline/backup` / `apply` / `restore` |

### Vue Router

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 重定向 | → `/datasource` |
| `/datasource` | DataSourcePage | 数据源扫描 + 展示 |
| `/rules-overview` | RulesOverviewPage | 规则选择 + 聚合 |
| `/compute-prep` | 计算准备 | 可选预选 + 触发计算 |
| `/forest` | ForestPage | SVG 可视化 |
| `/conflicts` | ConflictsPage | 分支裁决 |
| `/operations` | OperationsPage | 备份/应用/恢复 |
| `/settings` | SettingsPage | user_config 表单编辑 |
| `/advanced` | AdvancedPage | 数据文件 JSON 监控 |

---

## 三、逐页面设计

### 3.1 DataSourcePage — 数据源

**职责**：扫描磁盘，展示客观结果。不承担用户决策。

```
┌ 数据源 ────────────────────────────────────────────────────┐
│                                                              │
│  目标数据库: [default ▼]                                      │
│  ○ 全部   ○ 仅自动   ○ 仅手动                                │
│                                                              │
│  [🔍 扫描 Steam 库]  [✅ 确认并进入规则概览]                    │
│                                                              │
│  ▶ 📊 库摘要表（可见性 👀/🙈 toggle）                          │
│  ▶ 📋 游戏表（appid / 名称 / MOD 数 / 所属库 / 路径）          │
│  ▶ 📦 MOD 表（MODID / 名称 / 所属APPID / 所属库 / 路径）       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**关键约束**：
- DataSourcePage 仅展示扫描结果。重复条目客观展示，不做裁决。裁决在计算准备页完成。
- 可见性筛选（库/游戏 toggle，👀可见 / 🙈隐藏）为 UI 状态，通过 persistence.ts 持久化
- "扫描 Steam 库"按钮 → `POST /api/database/generate` → 后端扫描并写入 database → 返回数据。**每次均重新扫描，不走缓存。**
- "确认并进入规则概览"按钮：扫描结果存在时彩色可点击，否则灰色不可点击。点击后保存 database 并跳转。
- ~~"保存当前选择"按钮已删除~~——扫描已顺带保存，无需独立保存按钮。
- **database 下拉组件**：用户选择要操作的目标 database。选项来自 `user_config.databases`。选中值仅作为组件本地状态——不改 localStorage、不改后端文件。操作时作为 `database_name?` 参数传入请求。**DataSourcePage 上不显示"有历史决策"标签。**
- 重复 appid/mixed_id 条目自然展示，无额外处理
- 游戏表列顺序：序号 → 可见性 → appid → 名称 → MOD数 → 所属库 → 路径
- 点击游戏表的"所属库"→ 滚到库表对应行；点击 MOD 表的"所属APPID"→ 滚到游戏表对应行；点击游戏表的 MOD 数→ 滚到该游戏第一个 MOD 处

---

### 3.2 RulesOverviewPage — 规则概览

**职责**：规则文件浏览、选择、聚合。**不管理规则来源路径**（路径在 Settings 页的 user_config.rule_sources 中管理）。

**kmmrule 文件结构**：
- 文件顶层仅 `rule_meta_tag`（rulenamespace, rulename, author, description）
- `nickname` / `preview` / `readme` 在 **mod 条目级别**，非文件级别

```
┌ 规则概览 ──────────────────────────────────────────────────────┐
│                                                               │
│  规则来源（来自 user_config）:                                  │
│    /home/user/kmm_rules/          [前往设置面板管理]              │
│                                                               │
│  发现的规则文件:                                                │
│  ☑ my_mods.kmmrule.json            [展开 ▾]                   │
│    └─ rule_meta_tag:                                          │
│       namespace: "kmm" | name: "我的规则集"                    │
│       author: knighthana                                      │
│       description: "RWR + Arma3 的 MOD 管理规则"               │
│    └─ 覆盖游戏: RWR (270150) ─ 3 MOD, Arma3 (107410) ─ 1 MOD │
│    └─ MOD 详情:                                                │
│       Castle (2606099273)                                      │
│         preview: preview.png, thumb.png                       │
│         readme: README.md                                      │
│       Grass (2890123456)                                       │
│         readme: grass_readme.txt                               │
│  ☑ extra.kmmrule.json               [展开 ▾]                  │
│  ☐ unused.kmmrule.json                                        │
│                                                               │
│  ──────────────────────────────────                          │
│  [💾 保存规则选择]  [✅ 进入计算准备]                             │
└───────────────────────────────────────────────────────────────┘
```

**行为**：
- 页面自动展示 `user_config.rule_sources` 中发现的所有规则文件（无需手动扫描）
- **预加载**：所有规则文件的详情在页面加载时并行获取（`/api/rules/read`），展开前即可显示 `rulename | filename`
- 规则文件行格式：**`rulename`**（加粗深色） + `|` + `filename`（浅色细体），div 可横向滚动
- `rule_meta_tag` 显示为 **"规则文件元信息"**
- author：每位独立按钮，点击弹出 popover 遍历展示所有字段（键含义和展示方式待后续规定）
- 游戏名从 `/api/database/read` 的 `game[].name` 获取（非硬编码映射）
- 文件夹图标可点击：调 `/api/rules/read` → 弹出对话框以 JSON 格式化展示源文件内容
- 每个 rule 可展开查看详情
- 用户通过 checkbox 勾选/取消 rule
- [💾 保存规则选择] → `POST /api/rules/aggregate { paths: [已选文件路径] }` → 结果存 localStorage workspace.aggregatedRuleSet + selectedRulePaths
- [✅ 进入计算准备]：聚合完成后亮起可点击（`savedCount !== null`），否则灰色不可点击
- **autoRestoreAggregated**：页面加载时比对当前规则文件路径与 workspace.selectedRulePaths——一致则自动恢复聚合结果，按钮亮起

**不展示**聚合后的冲突分析——留给计算准备页。
- preview 图片加载和 README 文件查看见 TODO-66/67（需新增后端端点）

---

### 3.3 计算准备 —— ComputePrep

**职责**：展示受影响的条目、可选预选、触发计算。

完整设计见 `DESIGN_COMPUTE_PREP_PAGE.md`。

**database 下拉组件**：选项来自 `user_config.databases`。选中值作为 `database_name?` 参数传入 compute 请求。

```
┌ 计算准备 ───────────────────────────────────────────────────────────────────┐
│                                                                              │
│  [▶️ 开始计算] [👁️ 查看结果]  [✅ 计算完成：42棵树，15个映射]                   │
│                                                                              │
│  覆盖 2 个库，5 个游戏 (2 个有多个入口)，12 个 MOD (3 个有多个入口)             │
│ ─────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│ ▶ 库                                                                          │
│ ┌────┬────┬──────┬──────┬──────┬──────────────────────────────────────────┐  │
│ │选中│序号│ 👀🙈│ 游戏 │ MOD  │ 路径                                       │  │
│ ├────┼────┼──────┼──────┼──────┼──────────────────────────────────────────┤  │
│ │ ☑  │ 1  │ 👀  │  1   │  15  │ /mnt/d/Games/steamapps/                   │  │
│ │ ◐  │ 2  │ 🙈  │  1   │  15  │ /tmp/fixture/steamapps/                    │  │
│ └────┴────┴──────┴──────┴──────┴──────────────────────────────────────────┘  │
│                                                                              │
│ ▶ 游戏                                                                        │
│ ┌──────┬────┬────────┬──────────┬──────────────────────────────────────────┐ │
│ │ 选中  │序号│ appid   │ 名称      │ 路径                                     │ │
│ ├──────┼────┼────────┼──────────┼──────────────────────────────────────────┤ │
│ │  ☑   │ 1  │ 270150 │ RWR      │ /mnt/d/.../common/RWR           ←重复   │ │
│ │  ☐   │ 2  │ 270150 │ RWR      │ /tmp/fixture/.../common/RWR              │ │
│ └──────┴────┴────────┴──────────┴──────────────────────────────────────────┘ │
│                                                                              │
│ ▶ MOD                                                                         │
│ ┌──────┬────┬──────────────────┬──────────┬───────────────────────────────┐  │
│ │ 选中  │序号│ mixed_id          │ 名称      │ 路径                           │  │
│ ├──────┼────┼──────────────────┼──────────┼───────────────────────────────┤  │
│ │  ☑   │ 1  │ 270150:260609... │ GFL_Castl│ /mnt/d/.../2606099273 ←重复   │  │
│ │  ☐   │ 2  │ 270150:260609... │ GFL_Castl│ /tmp/fixture/.../2606099273    │  │
│ └──────┴────┴──────────────────┴──────────┴───────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**checkbox 行为**：
- 默认：全部选中（不干预 = 全留给 engine）
- **重复高亮**：前端动态计算——统计当前勾选行中同一 appid/mixed_id 出现次数，>1 则高亮
- **取消 checkbox 自动消高亮**：取消勾选 → 该行不参与重复计数 → 高亮消失
- 仅被取消的条目纳入 managed_entries（列表格式）→ 作为 compute 参数传入

**库表可见性**：
- 👀 / 🙈 emoji 按钮切换每库的可见状态
- 同时影响游戏表和 MOD 表的显示
- 库表全选 checkbox 联动该库下所有 game + mod

**[▶️ 开始计算]**：
- 从 localStorage workspace 读 decisions
- 收集 checkbox 状态 → 构建 managed_entries
- `POST /api/pipeline/compute { database_name, aggregated_rule_set, managed_entries, branch_decisions }`
- 成功后 → 写 workspace → [👁️ 查看结果] 亮起
- 计算完成消息与按钮同行，不挤占表格空间

**MOD 名称**：从 aggregated_rule_set.operation[].nickname 获取（非 database 的 mod 条目）

**managed_entries 格式**：
```json
{
  "game": { "270150": ["/mnt/d/.../RWR"] },
  "mod": { "270150:2606099273": ["/mnt/d/.../mod"] }
}
```
值为列表——表达"仅保留这些路径"。不在其中的 appid/mixed_id → 全部保留。

---

### 3.4 ForestPage — 森林可视

**职责**：全屏 SVG 可视化 + 摘要查看。纯消费计算结果，不做计算触发。

**数据来源**：工作区目录 `mapping.json`（`GET /api/workspace/{id}/forest/mapping`）。刷新后从后端恢复，无需重新 compute。

#### 布局

```
┌──────────────────────────────────────────────────────────────────┐
│ 🔄 重置  📐 小地图  仅分岔/全部             📊 摘要              │  ← 顶栏面板
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│                        SVG 全屏视图区                              │
│               (随窗口大小自适应)                                   │
│               (wheel → svg-pan-zoom viewBox 操作)                 │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│ 📋 925  925 树 925 映射 0 警告 0 错误                            │  ← 底栏状态
└──────────────────────────────────────────────────────────────────┘
```

#### 顶栏面板

| 按钮 | 行为 |
|------|------|
| 🔄 重置视图 | svg-pan-zoom `fit()` + `center()` |
| 📐 小地图 | toggle 小地图显示/隐藏 |
| 仅分岔/全部 开关 | 切换是否只显示 pending 树 |
| 📊 摘要 | toggle 右侧 el-drawer，显示树/映射/警告/错误计数 |

#### 底栏状态

- 默认展开：`|📋{n}| 925 树 925 映射 0 警告 0 错误|`，点击 `📋` 收起右侧详情
- 收起状态：`|📋{n}|`，点击 `📋` 展开完整面板
- 位置：SVG 视图左下角，浮于 SVG 上方
- 仅在有结果时显示

#### 结果有效性

- Forest 加载时从工作区目录读取 mapping（`GET /api/workspace/{id}/forest/mapping`）
- 刷新后从后端恢复——工作区目录持久化，无需重新 compute

---

### 3.5 ConflictsPage — 冲突裁决

**职责**：处理 branch 冲突（不同 rule 对同一文件产生竞争 action）。

- 表格展示 pending 树：目标路径 | Destin | 候选来源
- 用户通过 radio 选择候选
- [确认决策] 按钮 → `POST /api/workspace/{id}/decisions/save` 写入工作区目录 `decisions.json`
- [重新计算] → 工作区已存最新 decisions → 触发 compute 端点
- 成功后显示提示 + [查看映射图 →] → 跳转 Forest

**不做** managed_entries 相关的裁决（那是计算准备的职责）。

---

### 3.6 OperationsPage — 文件操作

**职责**：展示映射摘要 + 执行文件操作。

```
┌ 文件操作 ────────────────────────────────────────────────────┐
│                                                              │
│  📊 本次映射摘要（从 localStorage.results 读取）                │
│  总文件数: 15    新增: 3    覆盖: 10    删除: 2               │
│  警告: 3    错误: 0                                          │
│                                                              │
│  ⚙️ 执行选项                                                 │
│  [x] dry run（仅预览，不实际写文件）                            │
│                                                              │
│  [备份]  [应用]  [恢复]                                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

- 仅消费 Forest 计算结果，不负责计算
- 按钮触发对应 `POST /api/pipeline/backup` / `apply` / `restore`
- dry run 开关在此页面管理

---

### 3.7 高级 —— 数据文件监控

**职责**：查看/编辑当前生效的数据文件（JSON raw view）。面向高级用户。

侧边栏与"设置"平级，不折叠。

```
┌ 高级 ────────────────────────────────────────────────────────┐
│                                                              │
│  [Database] [Aggregated Rules] [User Config]                  │  ← el-tabs
│                                                              │
│  ┌ Database JSON ──────────────────────────────────────────┐ │
│  │                                                          │ │
│  │  文件路径: /tmp/modmanager_database_generated.json        │ │
│  │  文件大小: 45.2 KB    最后修改: 2026-05-13 15:30          │ │
│  │                                                          │ │
│  │  ┌──────────────────────────────────────────────────┐   │ │
│  │  │ {                                                │   │ │
│  │  │   "steamlib": [...],                             │   │ │
│  │  │   "game": [...],                                 │   │ │
│  │  │   ...                                            │   │ │
│  │  │ }                                                │   │ │
│  │  └──────────────────────────────────────────────────┘   │ │
│  │                                                          │ │
│  │  [编辑] [保存] [刷新]                                     │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**四个 tab**：

| Tab | 数据来源 | 写入端点 |
|-----|---------|---------|
| Database | `POST /api/database/read` | `POST /api/database/save` |
| Aggregated Rules | `POST /api/rules/load-aggregated` | 不需要（聚合自动生成） |
| User Config | `POST /api/config/discover` | `POST /api/config/save` |
| LocalStorage | `window.localStorage (modmanager:*)` | 不支持编辑（只读 dump） |

**行为**：
- 默认只读。点击 [编辑] 解锁 → [保存] → REST API 写入
- [刷新] 从后端重新加载
- 标签切换时自动刷新当前标签（database / aggregated / userConfig / localStorage）
- Database JSON 编辑独立模块，可随时迁移

---

## 四、可编辑列表 UI 规范

### 适用场景

当页面需要管理**可变数量的字符串列表**（如 bakignore、rule_sources、手动路径），使用统一的 el-table 行内编辑模式。

### 样式

- 使用 `el-table` + `border` + `stripe` + `size="small"`，与页面内其他数据表格（库/游戏/MOD 表）视觉一致
- 外框、行分割线、背景色由 Element Plus 主题管理
- 路径类文本使用 `<code>` 标签（monospace 字体）

### 行内编辑

- 每行两种状态：**显示态**（文字 + 删除按钮）↔ **编辑态**（`el-input size="small"` + 确定/取消按钮）
- 同时只允许一行处于编辑态
- 高度固定不跳变
- Enter / 确定 → 保存值；Esc / 取消 → 恢复原值
- 删除需 `el-popconfirm` 确认

### 添加新项

- 底部 `#append` slot 放 "➕ 添加来源" 按钮
- 点击后 → 该按钮行变为输入框行（同上编辑态样式）

### 已应用此模式的组件

| 页面 | 列表 |
|------|------|
| SettingsPage | bakignore、rule_sources |
| DataSourcePage | manualPaths |

---

## 五、选项卡解耦原则

| 原则 | 说明 |
|------|------|
| **单向数据流** | 上游页面产出数据 → 下游消费。不做反向依赖 |
| **API 为唯一信使** | 页面间通过 REST API 传递状态，不通过 Pinia store 跨页面直接读写 |
| **各自可独立渲染** | 任一页面在缺少上游数据时显示明确空状态，不崩溃 |
| **禁止跨页面直接调用** | 若需共享状态 → 通过后端 API / 前端 localStorage（decisions/results）/ persistence.ts（仅 UI 状态） |

---

## 六、数据流规范

### 核心原则

> 后端是唯一权威数据源。前端不做业务数据持久化。Pinia store 仅暂存本次页面会话的内存状态。

### 前端数据持久化边界

| 数据 | 存储位置 |
|------|---------|
| 业务数据（database, pipeline 结果） | 后端 database / API |
| 用户决策（decisions, results） | 前端 localStorage（`modmanager:workspace.perDatabase[name]`） |
| UI 状态（tab 位置, sidebar 折叠, 可见性 toggle, 表单输入） | persistence.ts → localStorage（`modmanager:` 前缀） |

详见 `DESIGN_DATA_CLEANUP.md`。

### API 数据流

```
POST /api/database/generate  → 返回 database (无 managed/warnings/errors)
POST /api/rules/aggregate    → 返回 aggregated_rule_set
POST /api/workspace/{id}/pipeline/compute   → 直接从工作区读取聚合规则和决策，计算结果写入工作区目录
```

### DatabaseSelector 组件

database 下拉组件在 DataSourcePage 使用：

- 下拉选中值 = 组件本地状态。不改后端文件。
- 用户点操作按钮时，选中值作为参数传入请求
- 刷新恢复：无需恢复——DataSourcePage 为全局 database 管理页，每次进入默认展示列表即可

详见 `DESIGN_WORKSPACE_MODEL.md`。

---

## 七、Mock 策略

- MSW 拦截 fetch 层；`npm run dev:mock` / `npm run dev` 双命令切换
- 仅 SettingsPage / OperationsPage / RulesOverviewPage 从 mock 起步
- ForestPage / DataSourcePage / ConflictsPage 保持真实 API
- 详见 `DESIGN_MOCK_INFRA.md`

---

## 八、实现顺序

```
Phase 0: 设计文档定稿 ✅
Phase 1: 后端底层改造（workspace.py + database_ops 移除 managed + engine/orchestrator 适配）
Phase 2: 前端清退 localStorage + 接入 workspace API
Phase 3: MSW mock 基础设施 + 三页面重写
Phase 4: 存量适配 + 迁移收尾（三项迁移 / 解耦 / 小地图修复等）
```

详见 `DESIGN_EXECUTION_PLAN.md`。

---

## 九、决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | 页面流 | 六页面：DataSource → RulesOverview → 计算准备 → Forest → Conflicts → Operations |
| D2 | managed 归属 | 前端 localStorage（`modmanager:workspace.perDatabase[name].decisions.managed_entries`），compute 时作为参数传入 |
| D3 | managed 格式 | 路径列表——"仅保留这些" |
| D4 | Forest 布局 | 全屏 SVG + 顶栏按钮 + 浮层（小地图/底栏/抽屉），overflow:hidden |
| D5 | 计算触发位置 | 计算准备页 [▶ 开始计算]；Forest 纯展示 |
| D6 | 前端持久化 | 业务权威在后端；用户决策与结果摘要持久化在 `modmanager:workspace` |
| D7 | mock 范围 | 仅 SettingsPage / OperationsPage / RulesOverviewPage |
| D8 | branch_decisions 保存 | ConflictsPage [确认决策] 按钮 → 写 `localStorage.modmanager:workspace.perDatabase[name].decisions.branch_decisions` |
| D9 | 计算准备默认行为 | 默认全选（不干预），用户主动取消才产生 managed_entries |
| D10 | 可编辑列表 UI | el-table + border + stripe + 行内编辑（显示/编辑态切换）；路径用 code 字体 |
