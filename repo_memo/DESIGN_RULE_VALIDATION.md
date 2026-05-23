# DESIGN_RULE_VALIDATION — 规则文件预检漏斗

> Status: proposed
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 规定规则文件在进入聚合器前的两层预检机制——JSON Schema 结构粗筛 + 语义字段精筛

创建：2026-05-23

---

## 一、问题背景

规则文件（`*.kmmrule.json`）来自多个作者，写法存在历史遗留差异。当前管线中文件直接进入聚合器，无前置校验。非法字段值（如 `"path"` 被写成 `from_type`）一路漏到引擎才暴露，且暴露形式是**静默跳过**——用户看到结果不对，但不知道原因。

需要一个漏斗，在规则文件进入聚合器之前拦截此类问题。

## 二、漏斗模型

```
                        Schema 粗筛              语义精筛
用户规则文件 ──────────▶ JSON Schema 校验 ──────▶ 字段值域校验 ──────▶ 聚合器
                            │                        │
                        不合格 → 拒绝报告          有歧义 → 警告报告
                        （终止该文件）             （可继续，标记）
```

### 2.1 第一层：Schema 粗筛

**职责**：验证 JSON 结构合法性（必填字段、类型匹配）。

**实现**：已有 `repo_spec/kmm_rule.schema.json` 作为 JSON Schema。在聚合器入口处对每个规则文件执行 `jsonschema.validate()`。

**不合格行为**：该文件被标记为 `rejected`，携带错误原因。其余文件正常进入精筛。

### 2.2 第二层：语义精筛

**职责**：验证字段值域（枚举值是否在允许集合中）、路径格式、逻辑一致性。

**检查项**：

| # | 检查 | 验证逻辑 | 不合格 | 级别 |
|---|------|---------|--------|------|
| C1 | `from_type` 值域 | `value in ("file", "dir")` | `E_INVALID_FROM_TYPE: {value}` | **拒绝** |
| C2 | `into_type` 值域 | `value in ("file", "dir")` | `E_INVALID_INTO_TYPE: {value}` | **拒绝** |
| C3 | `action` 值域 | `value in ("hold", "replace", "copy", "delete", "create")` | `E_INVALID_ACTION: {value}` | **拒绝** |
| C4 | `from` 路径安全 | 不含 `".."` 路径穿越 | `E_PATH_TRAVERSAL: from` | **拒绝** |
| C5 | `into` 路径安全 | 同 C4 | `E_PATH_TRAVERSAL: into` | **拒绝** |
| C6 | `from` 非空（需要时） | `action not in ("delete", "hold") → len(from) > 0` | `E_MISSING_FROM` | **拒绝** |
| C7 | `into` 非空（需要时） | `action != "hold" → len(into) > 0` | `E_MISSING_INTO` | **拒绝** |
| C8 | `mixed_id` 格式 | `"<appid>:<modid>"` | `W_MIXED_ID_FORMAT` | **警告** |
| C9 | `def_destin` 格式 | `"<appid>:<modid>"` 或 `"<appid>:0"` | `W_DESTIN_FORMAT` | **警告** |
| C10 | `sub[]` 格式 | 同 C8 | `W_SUB_FORMAT` | **警告** |

**检查级别定义**：

| 级别 | 行为 |
|------|------|
| **拒绝** | 文件不可聚合。错误记录到 `rejected`。 |
| **警告** | 文件可聚合但标记为有歧义。记录到 `warnings`。 |

**类型术语**：`"file"` = 操作对象为单个或多个具名文件；`"dir"` = 操作对象为目录及其全部内容（递归展开）。`"path"` 不在允许值域中，参见下文设计决策。

**实现细节**：
- `"path"` 作为历史遗留值，在精筛阶段**被拒绝**（不自动归一化）——原因：`"path"` 的语义取决于规则的 DSL 版本，自动归一化会掩盖规则作者的意图。应让用户在规则文件中明确修正为 `"dir"` 或 `"file"`。
- 前端展示拒绝原因时，引用 `DESIGN_RULE_VALIDATION.md` 作为规范来源。

## 三、落点与接口

### 3.1 模块位置

**独立模块** `src/modmgr/rule_validator.py`。不与 `validation.py`（聚合后校验）合并——漏斗是聚合器的前置，职责独立，便于单独测试和维护。

```python
# src/modmgr/rule_validator.py

def validate_kmm_rule_files(
    rule_paths: list[str],
) -> tuple[list[str], list[dict], list[dict]]:
    """两阶段漏斗校验规则文件列表。

    Stage 1: JSON Schema 粗筛（kmm_rule.schema.json）
    Stage 2: 语义精筛（C1-C10）

    Returns:
        (passed_paths, rejected, warnings)
        - passed_paths: 通过校验的文件路径列表（可直接聚合）
        - rejected: 被拒绝的文件列表，每项 { path, errors: [str] }
        - warnings: 有歧义建议的文件列表，每项 { path, warnings: [str] }
    """
```

### 3.2 调用位置

`src/modmgr/rule_aggregator.py` 的 `aggregate()` 函数入口——在加载文件内容之前先跑漏斗：

```python
def aggregate(kmm_rule_paths, *, action_orders=None, sidecar_refs=None):
    passed, rejected, warnings = validate_kmm_rule_files(kmm_rule_paths)
    if rejected:
        all_warnings.extend(
            f"W_RULE_REJECTED: {r['path']}: {'; '.join(r['errors'])}"
            for r in rejected
        )
    # 仅对 passed 文件执行后续加载和聚合
    ...
```

### 3.3 Web 路由适配

`POST /api/rules/aggregate`（workspace 端点）接收 `rejected` 和 `warnings`，原样返回给前端。前端在规则概览页展示"N 条规则通过，M 条被拒绝"以及详细原因。

## 四、Schema 文件

已有的 `repo_spec/kmm_rule.schema.json` 在结构校验时引用。若当前 schema 未覆盖所有约束（如 `from_type` 的 enum 仅有 `["file", "dir"]`），需同步更新。

## 五、与现有校验的关系

| 函数 | 模块 | 阶段 | 职责 |
|------|------|------|------|
| `validate_kmm_rule_files()` ← **新增** | `rule_validator.py` | 聚合前 | 两阶段漏斗，过滤不合法文件 |
| `validate_aggregated_rule_set()`（已有） | `validation.py` | 聚合后 | 验证聚合结果结构完整性 |
| `validate_database()`（已有） | `validation.py` | 引擎前 | 验证数据库结构 |

三者不冲突——漏斗在聚合前拦截，`validate_aggregated_rule_set` 在聚合后二次确认，`validate_database` 在引擎入口再确认。

## 六、实现映射

| C# | 代码落点 |
|----|---------|
| C1-C3 值域检查 | `rule_validator.py::_validate_field_enum()` |
| C4-C5 路径安全 | `rule_validator.py::_validate_path_safety()` |
| C6-C7 必填性 | `rule_validator.py::_validate_required_fields()` |
| C8-C10 格式 | `rule_validator.py::_validate_id_format()` |
| Schema 粗筛 | `rule_validator.py::_schema_check()` |
| 漏斗入口 | `rule_validator.py::validate_kmm_rule_files()` |
| 聚合器调用 | `rule_aggregator.py::aggregate()` 入口 |

## 七、测试断言

详见 `repo_test/rule_validation.md`。
