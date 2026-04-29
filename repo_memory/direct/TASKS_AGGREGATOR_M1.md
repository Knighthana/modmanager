# Aggregator & M1 Engine Update — Implementation Tasks

基于 `repo_memory/RULE_AGGREGATION_DESIGN.md`（最终版）
创建时间：2026-04-30

---

## 前置阅读（必读）

实现前必须阅读以下文档：
- `repo_memory/RULE_AGGREGATION_DESIGN.md`（聚合器设计全文）
- `repo_memory/TERMINOLOGY.md`（术语定义）
- `repo_memory/aggregated_rule_set.json.example`（输出 schema 示例）

---

## Task 1: 更新 validation.py

**文件**: `src/modmanager_cli/validation.py`

**改动清单**：

1. `"mod"` → `"operation"`：
   - L34: `if "mod" not in aggregated_rule_set:` → `if "operation" not in aggregated_rule_set:`
   - L35: 错误消息中的 `'mod'` → `'operation'`
   - L37–39: `aggregated_rule_set["mod"]` → `aggregated_rule_set["operation"]`
   - L45–47: 错误消息中的 `mod[{idx}]` → 可保持为 `operation[{idx}]`（语义更新）
   - 对应变量名 `mods` → `operations`，`mod_obj` → `op_obj`

2. `action` 和 `destin` 变为必填字段：
   - 在 actionlist 条目的校验中，增加检查：非 hold 且非 delete 的 action 必须显式包含 `action` 字段（不再允许缺省继承）
   - `destin` 必须显式包含（不为空）；`"none"` 是有效值但不触发缺失错误

3. 移除对 `def_destin` / `def_action` 的引用（任何校验逻辑中不应再检查这两个字段是否存在）

4. 更新 `__all__` 和 docstring 中的描述

---

## Task 2: 更新 engine.py（M1 引擎）

**文件**: `src/modmanager_cli/engine.py`

**改动清单**：

### 2.1 变量重命名
- L363: `aggregated_rule_set.get("mod", [])` → `aggregated_rule_set.get("operation", [])`
- L363 变量名 `mods` → `operations`
- L364: `mod_index` → `op_index`，遍历变量 `mod_obj` → `op_obj`（全文搜索替换，确保一致）

### 2.2 移除 `def_destin` / `def_action` 继承（L392–397）
删除以下两行及其上下文依赖：
```python
def_destin = mod_obj.get("def_destin", "")
def_action = mod_obj.get("def_action", "hold")
```
以及：
```python
action = str(item.get("action", def_action))
destin = str(item.get("destin", def_destin))
```
改为直接读取（不再 fallback）：
```python
action = str(item.get("action", ""))
destin = str(item.get("destin", ""))
```
如果 `action` 或 `destin` 为空字符串，在后续处理中会被校验拦截（validation 已保证它们存在）。

### 2.3 移除 `sub` 权限检查（L408–412）
删除以下代码块：
```python
if destin in mod_index and destin != actor_id:
    target_sub = mod_index[destin].get("sub", [])
    if actor_id not in target_sub:
        warnings.append(f"W_SUB_NOT_RECOGNIZED: {actor_id} -> {destin}")
        continue
```
鉴权已完全由聚合器承担。

### 2.4 移除 `validate_forest_roots`（L291–340 + L569）
- 删除 `validate_forest_roots` 函数定义（L291–340）
- 删除 L569: `warnings.extend(validate_forest_roots(forest, mod_index))`
- 从 `__all__` 中移除 `"validate_forest_roots"`

### 2.5 更新 docstring 和注释
- `compute_mapping` 的 docstring 中更新输入描述（`operation` 替代 `mod`）
- 移除任何提及 `def_destin`、`def_action`、`sub` 检查的注释

---

## Task 3: 创建 rule_aggregator.py（新文件）

**文件**: `src/modmanager_cli/rule_aggregator.py`（新建）

**核心函数签名**：
```python
def aggregate(
    kmm_rule_paths: list[str],
    user_config_path: str,
    *,
    action_orders: dict[str, int] | None = None,
    sidecar_refs: dict[str, dict[str, dict[int, str]]] | None = None,
    output_path: str | None = None,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
```

### 3.1 实现流程（参考 §6.3）

```
Step 1: 加载 user_config.json（验证基本 schema）
Step 2: 加载全部 kmm_rule 文件（逐个验证根结构，dict 且含 "mod" key）
Step 3: 第一遍扫描 — 构建权限映射
    - game_permissions: {appid: set(modid)}  （union across all files）
    - sub_permissions:  {dom_mixed_id: set(actor_mixed_id)}  （union）
Step 4: 第二遍 — 逐文件逐 mod 处理（文件内具体化 + 注入）
    对每个 kmm_rule 文件的每个 mod：
        - 对每个 action：
            a. 继承：若 action.destin 缺失，填入 mod.def_destin
                    若 action.action 缺失，填入 mod.def_action
            b. 若 action=="hold" → 跳过（不进入后续）
            c. 若 destin=="none" → W_DESTIN_NONE_SKIPPED，跳过
            d. 注入 provenance_ref = <当前文件的绝对路径>
            e. 注入 action_order = action_orders.get(mixed_id, 0)
            f. 注入 sidecar_ref = 从 sidecar_refs 查找，无则 "404"
            g. 保留该 action（加入该 mod 的 processed_actions 列表）
Step 5: 第三遍 — 跨文件合并
    - 以 mixed_id 为键，合并各文件的 processed_actions（按文件顺序拼接）
    - preview/readme: extend + 去重
    - nickname: 后入者若非空则覆盖
Step 6: 第四遍 — 鉴权过滤
    - 每个 action 检查权限（§5.2）：
        - destin modid==0 → 检查 game_permissions[appid] 是否包含 actor modid
        - destin modid!=0 → 检查 sub_permissions[destin] 是否包含 actor
        - 不通过 → E_PERMISSION_DENIED_BASE / E_PERMISSION_DENIED_SUB，移除
Step 7: 校验输出 — 调用 validate_aggregated_rule_set
Step 8: 可选写文件到 output_path
Step 9: 返回 (result, errors, warnings)
```

### 3.2 输出结构
```python
{
    "schema_namespace": "KMM_RuleSet",
    "schema_version": "knighthana@0.1.0",
    "operation": [
        {
            "mixed_id": "...",
            "nickname": "...",
            "preview": [...],
            "readme": [...],
            "actionlist": [
                {
                    "action": "...",
                    "destin": "...",
                    "from": [...],
                    "from_type": "...",
                    "into": [...],
                    "into_type": "...",
                    "action_order": int,
                    "provenance_ref": "...",
                    "sidecar_ref": "..."
                }
            ]
        }
    ]
}
```

### 3.3 错误码
参见设计文档 §10。实现时需要产出的错误码：
- `E_KMM_RULE_LOAD_FAILED`
- `E_KMM_RULE_INVALID`
- `E_PERMISSION_DENIED_BASE`
- `E_PERMISSION_DENIED_SUB`
- `E_USER_CONFIG_LOAD_FAILED`

告警码：
- `W_DESTIN_NONE_SKIPPED`
- `W_ACTION_ORDER_DEFAULTED`
- `W_NICKNAME_CONFLICT`
- `W_EMPTY_ACTIONLIST_AFTER_FILTER`
- `W_SIDECAR_REF_DEFAULTED`

### 3.4 实现备注
- 路径相关：聚合器不做路径规范化（M1 引擎的 `pathstyle.py` 已处理），保持 kmm_rule 中的路径原样
- KISS：不要在这个文件里引用 engine.py 的任何函数（保持逻辑独立）
- 可以引用 `iojson.load_json_file` 和 `validation.validate_aggregated_rule_set`
- 函数应该是纯逻辑，不依赖全局状态

---

## Task 4: 更新测试

### 4.1 更新现有测试（适配 M1 改动）

**文件**: `tests/test_validation.py`
- 更新引用 `aggregated_rule_set["mod"]` 的测试夹具 → `["operation"]`
- 确保所有测试夹具中的 action 包含显式 `action` 和 `destin` 字段
- 移除依赖 `def_destin` / `def_action` 继承的测试用例

**文件**: `tests/test_engine.py`
- 更新引用 `"mod"` 的测试夹具 → `"operation"`
- 移除测试 `validate_forest_roots` 的用例
- 移除测试 `W_SUB_NOT_RECOGNIZED` 行为（action 不再因 sub 被拒绝而跳过）的用例

**文件**: `tests/test_integration_fixtures.py`
- 更新所有 `aggregated_rule_set` 夹具：`"mod"` → `"operation"`，补全 action 的 `action`/`destin`
- 移除依赖 sub 鉴权的集成测试

**文件**: `tests/test_contract.py`
- 更新输出合同测试的夹具

**文件**: `tests/test_cli_database_ops.py`
- 检查是否有引用 `"mod"` 的地方（如果有的话更新）

### 4.2 新增聚合器测试

**新文件**: `tests/test_rule_aggregator.py`
- 单文件聚合成功（基本路径）
- 多文件聚合 — 同 mixed_id actionlist 拼接
- 多文件聚合 — preview/readme/nickname 合并
- 权限检查 — game 鉴权（可写 base 的 action 通过、不可写的拒绝）
- 权限检查 — sub 鉴权（sub 内的 action 通过、非 sub 的拒绝）
- hold action 过滤
- destin=none action 过滤
- provenance_ref 正确注入（绝对路径）
- action_order 注入
- sidecar_ref 注入
- 无效 kmm_rule 文件处理
- user_config 不存在处理
- 空输入（无 action 通过过滤）

---

## 执行顺序

```
Task 1 (validation.py)  ← 先改，因为 Task 3 调用它
Task 2 (engine.py)      ← 并行，与 Task 1 无依赖
Task 3 (aggregator.py)  ← 依赖 Task 1
Task 4 (tests)          ← 依赖 Task 1/2/3 全部完成
```

---

## 验收标准

1. `python -m unittest discover tests -v` 全量通过
2. 聚合器对单文件 kmm_rule 可产出合法 `aggregated_rule_set`
3. 聚合器 + M1 引擎端到端可用（`aggregate()` 的输出可直接传给 `compute_mapping()`）
4. 权限鉴权功能正确（无效 action 被移除 + 正确告警）
