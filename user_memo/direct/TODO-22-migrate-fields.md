# TODO-22: Forest 页字段迁移 + 规则概览页重构

> 状态: 设计完成，待实现
> 关联: `work_memo/states.md` TODO-22
> 涉及: 4 个后端文件 + 5 个前端文件

---

## 一、三项迁移概览

| # | 字段 | 迁出 | 迁入 | 当前状态 |
|---|------|------|------|---------|
| ① | Database JSON 栏 | ForestPage PipelineForm | **SettingsPage**（已有 Database JSON 高级区，作为唯一权威入口） | Settings 已有，Forest 需删除 |
| ② | Rule paths | ForestPage PipelineForm | **RulesOverviewPage**（全新设计，支持路径列表 + 目录两种来源） | 均需实现 |
| ③ | User config 路径 | ForestPage PipelineForm | **SettingsPage**（新增独立栏） | 均需实现 |

---

## 二、后端改动

### 2.1 扩展 `/api/rules/scan`

**文件**: `src/modmanager_web/schemas.py` + `src/modmanager_web/routes/rules.py`

**Schema 改动**:
```python
class RulesScanRequest(BaseModel):
    dir: str | None = None          # 保留兼容旧调用
    paths: list[str] | None = None  # 新增：每个元素可为文件路径或目录路径
```

**路由逻辑改动**（`routes/rules.py`）:
```python
@router.post("/scan")
async def rules_scan(req: RulesScanRequest):
    all_files: list[dict] = []
    seen: set[str] = set()
    
    candidates: list[str] = []
    if req.paths:
        candidates.extend(req.paths)
    if req.dir:
        candidates.append(req.dir)
    
    for raw in candidates:
        p = Path(raw)
        if p.is_file() and p.suffix == '.json':
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                all_files.append({"name": p.name, "path": str(p), "size": p.stat().st_size})
        elif p.is_dir():
            for entry in sorted(p.iterdir()):
                if entry.is_file() and entry.suffix == '.json':
                    key = str(entry.resolve())
                    if key not in seen:
                        seen.add(key)
                        all_files.append({"name": entry.name, "path": str(entry), "size": entry.stat().st_size})
    
    return adapt_dict_result({"files": all_files})
```

> **向后兼容**：保留 `dir` 字段，旧调用方不受影响。

### 2.2 新增 `/api/rules/parse`

**文件**: `src/modmanager_web/schemas.py` + `src/modmanager_web/routes/rules.py` + 可能需要 `src/modmanager/` 下新增模块

**Schema**:
```python
class RulesParseRequest(BaseModel):
    paths: list[str]                         # 要解析的 rule 文件路径列表
    database_path: str | None = None         # database 文件路径（不传则用默认）
    offset: int = 0
    limit: int = 50

class ParsedModEntry(TypedDict):
    mixed_id: str
    nickname: str
    preview: list[str]
    readme: list[str]
    def_action: str
    def_destin: str
    actionlist_count: int
    game: dict | None         # 从 database 反查的 game 信息

class RulesParseResponse(TypedDict):
    files: list[dict]         # [{ path, name, rulename, mods: [ParsedModEntry] }]
    total: int
    offset: int
    limit: int
```

**路由**:
```python
@router.post("/parse")
async def rules_parse(req: RulesParseRequest):
    # 1. 加载 database（用于反查 game）
    db_path = req.database_path or _default_database_path()
    database = load_json_file(db_path) if Path(db_path).exists() else {}
    game_index = build_game_index(database)
    
    # 2. 解析 rule 文件（复用 _load_kmm_rules 能力）
    raw_rules = _load_and_parse_rules(req.paths)  # 新函数，只提取元数据
    
    # 3. 组装瘦 schema + game 反查
    result_files = []
    total_mods = 0
    for rule in raw_rules:
        mods = []
        for mod_entry in rule.get("mod", []):
            mid = mod_entry.get("mixed_id", "")
            appid = mid.split(":")[0] if ":" in mid else ""
            game = game_index.get(appid)
            mods.append({
                "mixed_id": mid,
                "nickname": mod_entry.get("nickname", ""),
                "preview": mod_entry.get("preview", [])[:],
                "readme": mod_entry.get("readme", [])[:],
                "def_action": mod_entry.get("def_action", ""),
                "def_destin": mod_entry.get("def_destin", ""),
                "actionlist_count": len(mod_entry.get("actionlist", [])),
                "game": {
                    "appid": game.get("appid", appid),
                    "name": game.get("name", ""),
                    "basepath": game.get("basepath", ""),
                    "modpath": game.get("modpath", ""),
                    "managed": game.get("managed", False),
                } if game else None,
            })
            total_mods += 1
        result_files.append({
            "path": rule.get("_source_path", ""),
            "name": Path(rule.get("_source_path", "")).name,
            "rulename": rule.get("rule_meta_tag", {}).get("rulename", ""),
            "mods": mods,
        })
    
    # 4. 分页
    paginated = result_files[req.offset : req.offset + req.limit]
    
    return adapt_dict_result({
        "files": paginated,
        "total": total_mods,
        "offset": req.offset,
        "limit": req.limit,
    })
```

**新增 `_load_and_parse_rules()` 函数**（可放在 `rule_aggregator.py` 或新文件 `rule_parser.py`）:

```python
def load_and_parse_rules(paths: list[str]) -> list[dict]:
    """加载并做基础校验，不执行完整聚合。返回包含元数据的 rule 列表。"""
    rules = []
    for p in paths:
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "mod" not in data:
                continue
            data["_source_path"] = str(p)
            rules.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return rules
```

---

## 三、前端改动

### 3.1 ForestPage — 删除 PipelineForm

**文件**: `frontend/src/pages/ForestPage.vue`

删除整个 `<el-card>` PipelineForm 区域（第 6-54 行），仅保留：

```html
<template>
  <div>
    <h2>{{ STR.forestPage.title }}</h2>

    <!-- 计算映射按钮 -->
    <el-button type="primary" :loading="store.isRunning" :disabled="store.isRunning"
               @click="onCompute" style="margin-bottom: 16px;">
      {{ store.isRunning ? STR.forestPage.computeBtnRunning : STR.forestPage.computeBtn }}
    </el-button>

    <!-- ResultSummary → 不变 -->
    <!-- 错误/警告面板 → 不变 -->
    <!-- 展示模式切换 → 不变 -->
    <!-- ForestViewer → 不变 -->
  </div>
</template>
```

**`prepareParams()` 简化**：不再从 `pipelineForm` 读 databaseJson / rulesPaths / userConfigPath，改为从 store 的 `storedDatabase` + RulesOverviewStore 的 selectedPaths 读取。

**`<script setup>` 删除项**:
- `generateBackupDir` import（backup dir 由 TODO-24 处理）
- `pipelineForm.databaseJson` / `rulesPaths` / `userConfigPath` / `backupDir` / `dryRun` 引用
- `showBranchingOnly` 及相关 computed（保留，仍需）

### 3.2 SettingsPage — 新增 User Config 栏

**文件**: `frontend/src/pages/SettingsPage.vue`

在现有"基本设置"表单中，聚合规则集输出路径之后，保存按钮之前，插入 User Config 行：

```html
<el-form-item label="用户配置文件路径">
  <el-input v-model="form.userConfigPath"
            placeholder="~/.local/share/kmm/user_config.json" />
</el-form-item>
```

form 新增字段 `userConfigPath: ''`，保存时一并写入 user_config。

### 3.3 RulesOverviewPage — 全新设计

**文件**: `frontend/src/pages/RulesOverviewPage.vue`（完全重写）
**新增**: `frontend/src/stores/rulesOverview.ts`（Pinia store）

#### 3.3.1 页面布局

```
┌──────────────────────────────────────────────┐
│ 规则概览                                       │
├──────────────────────────────────────────────┤
│ 📁 规则来源                                    │
│ ┌──────────────────────────────────────────┐ │
│ │ 文件路径列表（JSON数组，每行一个文件）       │ │
│ │ ┌──────────────────────────────────────┐ │ │
│ │ │ ["/path/to/rule_a.json",             │ │ │
│ │ │  "/path/to/rule_b.json"]             │ │ │
│ │ └──────────────────────────────────────┘ │ │
│ ├──────────────────────────────────────────┤ │
│ │ 搜索目录（以 / 结尾）                      │ │
│ │ [                      ] [🔍 扫描]       │ │
│ └──────────────────────────────────────────┘ │
│ [扫描全部来源 → 调用 /rules/scan + /rules/parse]│
├──────────────────────────────────────────────┤
│ 📋 规则覆盖清单 (N 个 mod)                     │
│ ┌──────────────────────────────────────────┐ │
│ │ ☑ mixed_id    │ nickname    │ game   │预览│ │
│ │ ☑ 253230:2414 │ Castears... │ Raven..│ 👁 │ │
│ │ ☐ 253230:100  │ (无昵称)    │ Raven..│ 👁 │ │
│ │ ...                                       │ │
│ └──────────────────────────────────────────┘ │
│ 已勾选 N 个，来源：M 个 rule 文件               │
│ [确认选择 → 写入 store，供 Forest 页读取]       │
└──────────────────────────────────────────────┘
```

#### 3.3.2 交互流程

1. **输入规则来源**：用户在路径列表 textarea 填 JSON 数组 + 搜索目录 input 填目录路径
2. **扫描全部来源**：前端组装所有路径 → `POST /rules/scan { paths: [...] }` → 获取文件列表
3. **解析规则**：`POST /rules/parse { paths: files[].path, database_path: "..." }` → 获取结构化 mod 列表 + game 反查 + nickname/preview/readme
4. **展示表格**：
   - ☑ 勾选框，默认全选
   - mixed_id 列（可复制）
   - nickname 列（优先 nickname，无则显示 mixed_id 的 modid 部分）
   - game 列（appid + name）
   - 操作列：👁 展开 preview/readme 弹窗
   - 分页控件
5. **确认选择**：收集勾选的 mixed_id → 写入 `rulesOverviewStore.selectedMixedIds` + 对应的 rule 文件路径 → Forest 页读取

#### 3.3.3 Store: `rulesOverview.ts`

```typescript
export const useRulesOverviewStore = defineStore('rulesOverview', () => {
  // 输入
  const pathsInput = ref('[]')           // JSON 数组字符串
  const searchDir = ref('')              // 目录路径
  
  // 结果
  const discoveredFiles = ref<RuleFile[]>([])
  const parsedMods = ref<ParsedMod[]>([])
  
  // 选中状态（持久化）
  const selectedMixedIds = ref<Set<string>>(new Set())
  const selectedRulePaths = ref<string[]>([])
  
  // 分页
  const page = ref(0)
  const pageSize = 50
  
  // 操作
  async function scanAndParse() { ... }
  function toggleMod(mixedId: string) { ... }
  function confirmSelection() { ... }
  
  // 持久化
  const pers = createPersistence()
  function saveToCache() { ... }
  function loadFromCache() { ... }
})
```

#### 3.3.4 勾选状态持久化

- `selectedMixedIds` 写入 localStorage（key: `rulesOverview-selection`）
- 页面加载时恢复
- 确认选择时同步到 `forestStore`（供 pipeline 使用）

---

## 四、孤儿接口/存储排查

### 4.1 删除 ForestPage PipelineForm 后

| 项目 | 状态 | 处理 |
|------|------|------|
| `pipelineForm.databaseJson` | ForestStore 字段 | **不删除**——Settings 页的 Database JSON 保存后更新 `storedDatabase`，Forest 页的 pipelineForm.databaseJson 改为从 storedDatabase 重建（或废弃该字段） |
| `pipelineForm.rulesPaths` | ForestStore 字段 | **保留但不再从 Forest 页写入**——由 RulesOverview 页更新 |
| `pipelineForm.userConfigPath` | ForestStore 字段 | **保留但不再从 Forest 页写入**——由 Settings 页更新 |
| `/pipeline/compute` 的 database 参数 | 当前前端传 dict | **不改**（记入 TODO-27） |
| `backupDir` / `dryRun` 字段 | ForestStore 字段 | **不处理**（属于 TODO-24 / TODO-25） |

### 4.2 localStorage 键

| 键 | 归属 | 处理 |
|----|------|------|
| `modmanager:forest-store` | ForestStore 持久化 | pipelineForm 中移出的字段不再从 Forest 页写入，但保留键结构（向后兼容） |
| `modmanager:rulesOverview` | **新增** | RulesOverviewStore 持久化 |

---

## 五、Forest 页 compute 数据流（迁移后）

```
RulesOverview 页               Settings 页
  │                               │
  │ selectedMixedIds              │ userConfigPath
  │ selectedRulePaths             │ database (via save)
  │                               │
  ▼                               ▼
      ForestStore (Pinia, localStorage)
              │
              ▼
      Forest 页 onCompute()
        prepareParams():
          database  = store.storedDatabase
          kmm_rules = store.selectedRulePaths (from RulesOverview)
          user_conf = store.userConfigPath   (from Settings)
        POST /api/pipeline/compute
```

---

## 六、实现顺序

1. 后端：扩展 `/rules/scan` → 新增 `/rules/parse` + `load_and_parse_rules()`
2. 前端：新增 `rulesOverview.ts` store
3. 前端：重写 `RulesOverviewPage.vue`
4. 前端：修改 `SettingsPage.vue`（新增 User Config 栏）
5. 前端：精简 `ForestPage.vue`（删除 PipelineForm）
6. 前端：更新 `zh-CN.ts` 字符串
7. 排查孤儿接口/存储，清理

## 七、不改动范围

- Pipeline compute 数据流（TODO-27）
- backupDir / dryRun（TODO-24 / TODO-25）
- ForestViewer.vue / forest_visual.py（可视化零改动）
- DataSourcePage
