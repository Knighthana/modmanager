# SPEC_RULE_VALIDATION — 规则文件字段约束规范

> Status: proposed
> Authority: authoritative
> Read-Tier: implementation-scoped
> Purpose: 规定 `*.kmmrule.json` 每个字段的合法值域、格式、约束，供 `validate_kmm_rule_files()` 实现

创建：2026-05-23
依赖：`DESIGN_RULE_VALIDATION.md`

---

## 一、字段约束表

### 1.1 顶层结构

| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| `schema_namespace` | `str` | ✅ | 固定值 `"KMM_Rule"` |
| `schema_version` | `str` | ✅ | 版本字符串，不校验 |
| `rule_meta_tag` | `object` | ✅ | 含 `rulenamespace`、`rulename`、`author`、`description` |
| `game` | `list` | ✅ | 非空 |
| `mod` | `list` | ✅ | 非空 |

### 1.2 `game[]` 条目

| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| `appid` | `str` | ✅ | 纯数字字符串（如 `"270150"`），非空 |
| `modid` | `list[str]` | ✅ | 非空，每项为非空字符串 |

### 1.3 `mod[]` 条目

| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| `mixed_id` | `str` | ✅ | `"<appid>:<modid>"` 格式——冒号分隔，两端非空 |
| `nickname` | `str` | — | 无约束 |
| `sub` | `list[str]` | — | 每项为 `"<appid>:<modid>"` 格式；可为空列表 |
| `def_destin` | `str` | — | `"<appid>:<modid>"` 或 `"<appid>:0"`；缺省时聚合器内补为 `"<appid>:0"` |
| `def_action` | `str` | ✅ | enum: `"hold"`、`"replace"`、`"copy"`、`"delete"`、`"create"` |
| `actionlist` | `list` | ✅ | 可为空列表 |

### 1.4 `actionlist[]` 条目

| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| `action` | `str` | — | enum: `"hold"`、`"replace"`、`"copy"`、`"delete"`、`"create"`；缺省时取 `def_action` |
| `destin` | `str` | — | `"<appid>:<modid>"` 格式；缺省时取 `def_destin` |
| `from` | `list[str]` | 条件 | `delete` 和 `hold` 无 `from`；其余必须有，非空 |
| `from_type` | `str` | 条件 | enum: **`"file"`**、**`"dir"`**；仅当 `from` 存在时有意义 |
| `into` | `list[str]` | 条件 | `hold` 无 `into`；其余必须有，非空 |
| `into_type` | `str` | 条件 | enum: **`"file"`**、**`"dir"`**；仅当 `into` 存在时有意义 |

---

## 二、Checklist（实现 `validate_kmm_rule_files()` 的检查项）

### Stage 1: JSON Schema 校验

对每个文件执行 `jsonschema.validate(instance=rule_dict, schema=KMM_RULE_SCHEMA)`。

若 `VALIDATION_ERROR` → 加入 `rejected`，跳过 Stage 2。

### Stage 2: 语义校验

按以下顺序逐字段检查。首项不通过即标记 `rejected`，不再继续该文件的后续检查。

| # | 检查 | 验证逻辑 | 不合格 | 级别 |
|---|------|---------|--------|------|
| C1 | `from_type` 值域 | `value in ("file", "dir")` | `E_INVALID_FROM_TYPE: {value} not in ["file", "dir"]` | **拒绝** |
| C2 | `into_type` 值域 | `value in ("file", "dir")` | `E_INVALID_INTO_TYPE: {value} not in ["file", "dir"]` | **拒绝** |
| C3 | `action` 值域 | `value in ("hold", "replace", "copy", "delete", "create")` | `E_INVALID_ACTION: {value}` | **拒绝** |
| C4 | `from` 路径安全 | `"/../" not in path` 且不以 `"../"` 起始 | `E_PATH_TRAVERSAL: from` | **拒绝** |
| C5 | `into` 路径安全 | 同 C4 | `E_PATH_TRAVERSAL: into` | **拒绝** |
| C6 | `from` 非空（需要时） | `action not in ("delete", "hold") → len(from) > 0` | `E_MISSING_FROM: action={action}` | **拒绝** |
| C7 | `into` 非空（需要时） | `action != "hold" → len(into) > 0` | `E_MISSING_INTO: action={action}` | **拒绝** |
| C8 | `mixed_id` 格式 | `re.match(r"^\d+:.+$", value)` | `W_MIXED_ID_FORMAT: {value}` | **警告** |
| C9 | `def_destin` 格式 | `re.match(r"^\d+:(0|.+)$", value)` | `W_DESTIN_FORMAT: {value}` | **警告** |
| C10 | `sub[]` 格式 | 同 C8 | `W_SUB_FORMAT: {value}` | **警告** |

### 2.1 检查级别定义

| 级别 | 行为 |
|------|------|
| **拒绝** | 文件不可聚合。错误记录到 `rejected`，前端标红。 |
| **警告** | 文件可聚合但标记为有歧义。记录到 `warnings`，前端标黄。 |

### 2.2 类型术语

| 术语 | 定义 | 示例 |
|------|------|------|
| `file` | 操作对象为单个或多个具名文件。Glob 模式（`*.png`）在 `from` 中展开为文件列表 | `"weaponpics/1.6/*.png"` |
| `dir` | 操作对象为目录及其全部内容。递归展开 | `"no smoke/materials/"` |

> `"path"` 不在允许值域中——参见 `DESIGN_RULE_VALIDATION.md` §2.2 设计决策。规则作者应将 `"path"` 明确写为 `"file"` 或 `"dir"`。

---

## 三、Schema 文件同步

`repo_spec/kmm_rule.schema.json` 需同步更新以下约束：

1. `from_type` 和 `into_type` 的 `enum` 从当前值改为 `["file", "dir"]`
2. `action` 的 `enum` 确认为 `["hold", "replace", "copy", "delete", "create"]`

若当前 schema 中 `from_type` 的 `enum` 包含 `"path"`——将其移除。

---

## 四、兼容性

由于 `"path"` 被明确拒绝而非自动归一化，使用旧 DSL 语法的规则文件在通过漏斗时会被拦截。这对用户的影响：

- **现有规则作者**：需要将规则文件中的 `"path"` 替换为 `"dir"` 或 `"file"`
- **工具行为**：拒绝时不静默——返回明确的错误信息，指明文件路径和具体字段
- **迁移辅助**：可在错误信息中附带提示："若意图为复制目录及其全部内容，请将 'path' 改为 'dir'"

---

## 五、实现映射

| SPEC 条目 | 代码落点 |
|-----------|---------|
| C1-C3 值域检查 | `validation.py::_validate_actionlist_field_enum()` |
| C4-C5 路径安全 | `validation.py::_validate_path_no_traversal()` |
| C6-C7 必填性 | `validation.py::_validate_actionlist_required_fields()` |
| C8-C10 格式 | `validation.py::_validate_mixed_id_format()` |
| Schema 粗筛 | `validation.py::_schema_validate_rule_file()` |
| 漏斗入口 | `validation.py::validate_kmm_rule_files()` |
| 聚合器调用 | `rule_aggregator.py::aggregate()` 入口 |
