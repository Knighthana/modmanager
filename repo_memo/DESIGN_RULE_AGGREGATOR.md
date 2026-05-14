# Rule Aggregation Design

> Status: stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义多份 kmm_rule 聚合为 aggregated_rule_set 的规则、边界与输入输出契约

更新时间：2026-04-30 | 2026-05-13 — 命名约定从 `kmm_rule_*.json` 改为 `*.kmmrule.json`
实现状态：已落地并持续生效

---

## 1. 定位

聚合器是一个与 M1 引擎**逻辑独立**的模块，负责将多份 `*.kmmrule.json` 文件合并为单份 `aggregated_rule_set.json`，供 M1 引擎消费。

- **输入**：多份 kmm_rule JSON 文件 + 可选的 `action_order` 映射 + 可选的 `sidecar_ref` 注入映射
- **输出**：`aggregated_rule_set`（内存对象，可选写文件）
- **核心职责**：字段归一化 + 权限鉴权 + `def_destin`/`def_action` 具体化 + 多源合并

---

## 2. 输入规范

### 2.1 kmm_rule 文件

kmm_rule 文件的顶层结构：

```json
{
  "schema_namespace": "KMM_Rule",
  "schema_version": "knighthana@0.1.0",
  "file_example_URL": "https://...",
  "rule_meta_tag": { ... },
  "game": [
    {
      "appid": "270150",
      "modid": ["2606099273", "3425312546", "..."]
    }
  ],
  "mod": [
    {
      "mixed_id": "270150:2606099273",
      "nickname": "GFL_Castling",
      "preview": ["path/to/preview.jpg"],
      "readme": ["path/to/readme.md"],
      "sub": ["270150:3425312546"],
      "def_destin": "270150:0",
      "def_action": "replace",
      "actionlist": [ ... ]
    }
  ]
}
```

### 2.2 user_config.json

user_config 的字段定义与搜索策略见 `DESIGN_STORAGE.md` §3。
聚合器不消费 user_config。调用方需要的是 `kmm_rule_paths` 列表和可选的 `output_path`——这些由上层（orchestrator）传入。

### 2.3 action_order 映射（可选）

由外部（未来 GUI）传入，格式：

```json
{
  "<mixed_id>": <int>
}
```

聚合器将此值注入该 `mixed_id` 对应 operation 的所有 action 的 `action_order` 字段。未传入的 operation 的 action 默认 `action_order=0`。

### 2.4 sidecar_ref 注入映射（可选）

聚合器提供一个外部注入接口，允许将 `sidecar_ref` 注入到指定 action。注入发生在**文件内处理阶段**（与 concretization 同步），使用原始 kmm_rule 文件中的 action 序号：

```json
{
  "<source_file_abs_path>": {
    "<mixed_id>": {
      "<original_action_index>": "<sidecar_ref_value>"
    }
  }
}
```

- `original_action_index` 是 kmm_rule 源文件中该 action 在 `actionlist` 中的 0-based 序号（未处理前的原始位置）
- 若某 action 在 concretization 后被移除（hold / destin=none），其对应的注入项无害地被忽略
- 若无注入则 action 的 `sidecar_ref` 字段为 `"404"`

聚合器本身不实现填充逻辑——它只接受映射并填入。

---

## 3. 输出规范

聚合器输出的 `aggregated_rule_set` 结构。注意：
- 顶层 key 使用 `operation` 而非 `mod`（`mod` 在移除 `game` 后已无区别性）
- 每个 action 的 `action` 和 `destin` 均为显式必填（聚合器已具体化完毕）
- 不存在 `def_destin` 和 `def_action`（聚合器已完全解析）

```json
{
  "schema_namespace": "KMM_RuleSet",
  "schema_version": "knighthana@0.1.0",
  "operation": [
    {
      "mixed_id": "270150:2606099273",
      "nickname": "GFL_Castling",
      "preview": ["path/to/preview.jpg"],
      "readme": ["path/to/readme.md"],
      "actionlist": [
        {
          "from": ["weaponpics/1.6/*.png"],
          "from_type": "file",
          "into": ["media/packages/GFL_Castling/textures/"],
          "into_type": "path",
          "action": "replace",
          "destin": "270150:2606099273",
          "action_order": 0,
          "provenance_ref": "/abs/path/to/some_kmm_rule.json",
          "sidecar_ref": "404"
        }
      ]
    }
  ]
}
```

---

## 4. 字段映射：输入 → 输出

### 4.1 顶层字段

| 输入 (kmm_rule) | 输出 (rule_set) | 处理 |
|-----------------|-----------------|------|
| `schema_namespace` | `schema_namespace` | 固定为 `"KMM_RuleSet"`（不从输入继承） |
| `schema_version` | `schema_version` | 固定为 `"knighthana@0.1.0"` |
| `file_example_URL` | 移除 | — |
| `rule_meta_tag` | 移除 | 溯源通过 `provenance_ref` 回到源文件读取 |
| `game` | 移除 | 仅内部鉴权用（见 §5） |
| `mod` | `operation` | 合并并归一化（见下文），key 名变更 |

### 4.2 operation[] 条目字段

| 输入字段 | 输出字段 | 处理 |
|---------|---------|------|
| `mixed_id` | `mixed_id` | 保留，合并键 |
| `nickname` | `nickname` | 保留；多文件同 mixed_id 时，后入者若非空则覆盖 |
| `preview` | `preview` | 保留；多文件同 mixed_id 时 extend + 去重 |
| `readme` | `readme` | 保留；多文件同 mixed_id 时 extend + 去重 |
| `sub` | **移除** | 仅内部鉴权用（见 §5） |
| `def_destin` | **移除** | 聚合器已解析到每个 action 中（见 §4.4） |
| `def_action` | **移除** | 聚合器已解析到每个 action 中（见 §4.4） |
| `actionlist` | `actionlist` | 归一化后保留（见 §4.3） |
| `comment` | **移除** | 仅供人类阅读 |

### 4.3 actionlist[] 条目字段

| 输入字段 | 输出字段 | 处理 |
|---------|---------|------|
| `from` | `from` | 保留，保持 `list[string]` |
| `from_type` | `from_type` | 保留 |
| `into` | `into` | 保留，保持 `list[string]` |
| `into_type` | `into_type` | 保留 |
| `action` | `action` | **必填**，聚合器已从 `def_action` 或显式值填入 |
| `destin` | `destin` | **必填**，聚合器已从 `def_destin` 或显式值填入 |
| `nwname` | — | rename_then_replace 专用字段（历史） |
| `action_order` | `action_order` | **聚合器注入**，默认 `0` |
| `provenance_ref` | `provenance_ref` | **聚合器注入**，永远为 kmm_rule 文件的绝对路径 |
| `sidecar_ref` | `sidecar_ref` | 外部注入，无注入时默认 `"404"` |
| `sidecar` | **移除** | kmm_rule 中若存在 `sidecar: {}` 对象，丢弃 |
| `comment` | **移除** | 仅供人类阅读 |

### 4.4 继承具体化（聚合器独家职责）

每个 action 的 `action` 和 `destin` 在聚合器内部完成具体化，优先级：

1. action 条目自身显式声明的值
2. 若未声明，继承所属 operation 的 `def_action` / `def_destin`

**具体化结果直接写入每个 action 的输出字段**。输出中不存在 `def_destin` 和 `def_action`——M1 引擎永远不会见到这两个字段，也无需实现继承逻辑。

`hold` action 的处理：
- 具体化后 `action=="hold"` 的 action → 不进入输出
- `def_action=hold` 只影响**未显式声明 `action`** 的子条目，不覆盖显式非 `hold` action

`destin=none` 的处理：
- 聚合器将其标记为 `W_DESTIN_NONE_SKIPPED`，不进入输出

### 4.5 多规则合并策略

**Step 1 — 文件内具体化**（每份 kmm_rule 独立执行）：
对每个 mod 条目的每个 action，将 `def_destin` 和 `def_action` 解析填入各自的 `destin` 和 `action` 字段。

**Step 2 — 跨文件合并**：
- `game`：已在 Step 3 以 union 构建权限映射，此处不再重复合并
- `sub`：已在 Step 3 以 union 构建权限映射，此处不再重复合并
- `operation`：以 `mixed_id` 为合并键
  - `actionlist`：直接拼接（跨文件按文件传入顺序）
  - `preview`：extend + 去重（无文件提供时默认 `[]`）
  - `readme`：extend + 去重（无文件提供时默认 `[]`）
  - `nickname`：后入者若非空则覆盖（无文件提供时默认 `""`）
  - （注：`def_destin` / `def_action` 在 Step 1 已全部具体化完毕，此阶段不再存在，无需合并规则）

**Step 3 — 鉴权过滤**：
对每个具体化后的 action 执行 §5 的鉴权检查，不通过的 action 移除。

---

## 5. 权限鉴权（聚合器独家职责）

聚合器接管所有权限检查，M1 引擎不再进行任何鉴权。

### 5.1 权限数据源

聚合器从所有输入 kmm_rule 文件中提取两份权限映射（仅内部使用，不输出）：

**game 权限映射**（按 appid 聚合）：
```
game_permissions[appid] = {modid1, modid2, ...}   // union across all input files
```

**sub 权限映射**（按 dom 聚合）：
```
sub_permissions[dom_mixed_id] = {actor_mixed_id1, actor_mixed_id2, ...}  // union
```

### 5.2 鉴权规则

```
对于每个 action（destin 已具体化）：
    actor = 所属 operation 的 mixed_id
    target = action 的 destin

    如果 target 是 base（modid=0）：
        从 actor 提取 appid 和 modid
        检查：modid ∈ game_permissions[appid]
        不通过 → E_PERMISSION_DENIED_BASE，移除该 action

    如果 target 是其他 mod（modid ≠ 0 且 target ≠ "none"）：
        检查：actor ∈ sub_permissions[target]
        不通过 → E_PERMISSION_DENIED_SUB，移除该 action

    如果 target 是 "none"：
        W_DESTIN_NONE_SKIPPED，移除该 action
```

鉴权限定在 action 粒度：一个 action 无效**不影响**同 operation 下的其他 action。

### 5.3 鉴权的"死板性"

鉴权只检查直接权限关系，不做传递推断：
- "A 能写 B" 且 "B 能写 base" ≠ "A 能写 base"
- 每条 action 只检查其 actor 是否对该 action 的 target 有直接权限

---

## 6. 聚合器模块接口

### 6.1 模块位置

`src/modmanager/rule_aggregator.py`

与 M1 引擎共处一个包内，可共享基础设施（`iojson`、`validation`），但逻辑上不耦合 M1 的执行流程。

### 6.2 核心函数签名

```python
def aggregate(
    kmm_rule_paths: list[str],
    *,
    action_orders: dict[str, int] | None = None,
    sidecar_refs: dict[str, dict[str, dict[int, str]]] | None = None,
    output_path: str | None = None,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """聚合多份 kmm_rule 文件为 aggregated_rule_set。

    Args:
        kmm_rule_paths: kmm_rule JSON 文件的绝对路径列表
        action_orders: mixed_id -> action_order 的映射（可选，由 GUI 注入）
        sidecar_refs: file_abs_path -> mixed_id -> {action_index: sidecar_ref} 的映射（可选）
        output_path: 若提供，将结果写入此路径

    Returns:
        (aggregated_rule_set_or_none, errors, warnings)
        - 若 errors 非空，第一项为 None
        - output_path 参数只影响是否写文件，不影响返回值
    """
```

### 6.3 聚合流程

```
1. 加载全部 kmm_rule 文件（逐个验证根结构）
2. 第一遍：构建 game_permissions 和 sub_permissions（跨文件 union）
3. 第二遍：逐文件、逐 mod 进行文件内处理
   3a. 对每个 action 执行 def_destin / def_action 继承解析（具体化）
   3b. 注入 provenance_ref（kmm_rule 文件绝对路径）
   3c. 注入 action_order
   3d. 注入 sidecar_ref（按外部映射的原始 action 序号匹配）
   3e. 过滤 hold action
   3f. 过滤 destin=none action
4. 第三遍：跨文件合并
   4a. 合并同 mixed_id 的 operation（actionlist 拼接, preview/readme extend+去重, nickname 后入覆盖）
5. 第四遍：鉴权过滤
   5a. 检查 game / sub 权限
   5b. 不通过的 action 移除
6. 调用 validate_aggregated_rule_set 校验输出
7. 可选写文件
8. 返回 (result, errors, warnings)
```

---

## 7. M1 引擎的配套改动

由于聚合器接管了继承和鉴权职责，需要对 M1 引擎做以下最小改动。

### 7.1 `engine.py` 改动

| 位置 | 内容 | 改动 |
|------|------|------|
| L363 | `mods = [m for m in aggregated_rule_set.get("mod", [])` | 改为 `aggregated_rule_set.get("operation", [])` |
| L364 | `mod_index = {m.get("mixed_id", ""): m for m in mods` | `mods` → `operations` 变量更名 |
| L367 | `continue` 跳过不含 `:` 的 mixed_id | 不变 |
| L382 | `for actor_id, mod_obj in mod_index.items():` | 变量更名 |
| L392–397 | 继承逻辑（`action = item.get("action", def_action)` 等） | **移除**。`action` 和 `destin` 改为直接读取，不做 fallback |
| L408–412 | `sub` 权限检查 | **移除**。鉴权已由聚合器完成 |
| L569 | `warnings.extend(validate_forest_roots(forest, mod_index))` | **移除** |
| L291–340 | `validate_forest_roots` 函数定义 | **移除** |
| `__all__` | 含 `validate_forest_roots` | **移除**该项 |

### 7.2 `validation.py` 改动

| 位置 | 内容 | 改动 |
|------|------|------|
| L34 | `if "mod" not in aggregated_rule_set:` | 改为 `"operation"` |
| L37 | `mods = aggregated_rule_set["mod"]` | 改为 `aggregated_rule_set["operation"]` |
| 校验逻辑 | action 条目的 `action` / `destin` | 改为**必填**字段检查（不再允许缺省继承） |
| 校验逻辑 | 移除对 `def_destin` / `def_action` 的引用 | 这些字段不再出现在输入中 |

### 7.3 测试改动

移除或更新涉及以下内容的测试用例：
- `validate_forest_roots` 和 `W_SUB_AS_ROOT` / `W_GAMEBASE_NOT_ROOT`
- `W_SUB_NOT_RECOGNIZED`
- `aggregated_rule_set["mod"]` → `aggregated_rule_set["operation"]`
- 依赖 `def_destin` / `def_action` 继承的测试夹具

---

## 8. 示例文件同步

`description/aggregated_rule_set.json.example` 需要同步更新：
- 顶层 key：`"mod"` → `"operation"`
- 每个 action 显式包含 `action` 和 `destin`
- 移除所有 `def_destin` 和 `def_action` 字段
- 移除所有 `game` 和 `sub` 字段
- 移除所有 `comment` 字段（或保留为人类可读标注但语义上不参与消费）
- 添加 `sidecar_ref` 字段

---

## 9. 与现有 Demo 聚合器的关系

`cli-hmi/rule_aggregator.py` 是为演示目的临时构建的单文件直通转换器。其设计逻辑（处理 `provenance_ref`、`sidecar_ref`、路径规范化的方式，以及输出中是否保留 `def_destin` / `def_action`）**与本设计文档不一致**。

正式聚合器 `src/modmanager/rule_aggregator.py` 应**完全按本文档设计实现**，不参考 Demo 实现。

---

## 10. 错误码与告警汇总

### 聚合器专属

| 错误码 | 含义 |
|--------|------|
| `E_KMM_RULE_LOAD_FAILED` | 无法加载 kmm_rule 文件 |
| `E_KMM_RULE_INVALID` | kmm_rule 文件结构不合法 |
| `E_PERMISSION_DENIED_BASE` | action 目标为 base，但 actor 不在 `game[].modid` 中 |
| `E_PERMISSION_DENIED_SUB` | action 目标为其他 mod，但 actor 不在目标 mod 的 `sub` 中 |
| `E_AGGREGATION_FAILED` | 聚合过程致命错误 |

### 告警

| 警告码 | 含义 |
|--------|------|
| `W_DESTIN_NONE_SKIPPED` | action 的 destin 为 "none"，已跳过 |
| `W_ACTION_ORDER_DEFAULTED` | action_order 未指定，已使用默认值 0 |
| `W_NICKNAME_CONFLICT` | 同 mixed_id 跨文件 nickname 冲突，以后入者覆盖 |
| `W_EMPTY_ACTIONLIST_AFTER_FILTER` | operation 的所有 action 因鉴权或 hold 被过滤，条目仍保留（actionlist 为空） |
| `W_SIDECAR_REF_DEFAULTED` | sidecar_ref 未注入，已使用默认值 "404" |
| `W_PATH_TRAILING_SLASH_FIXED` | 目录路径缺少末尾 `/`，已由聚合器自动补全 |

---

## 11. 聚合器不应做的事

- 不负责发现 kmm_rule 文件（文件列表由上层传入）
- 不负责搜索、拼接或生成 `user_config.json`
- 不执行任何文件 I/O 操作（替换、备份等）
- 不修改 M1 引擎的映射计算逻辑
- 不尝试"修复"非法规则（fail-fast）
- 不自行填充 `sidecar_ref`（仅接收外部注入）
