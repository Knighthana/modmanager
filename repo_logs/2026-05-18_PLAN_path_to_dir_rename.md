# PLAN — from_type/into_type: "path" → "dir"

> Last-Updated: 2026-05-18

## 原则

`from_type` / `into_type` 中代表"目录"的值从 `"path"` 改为 `"dir"`。清理后代码库中**不残留任何** `"path"` 作为类型值的痕迹。`"path"` 仅保留为字段名（如 `entry["path"]`、`lib["path"]`）。

## 影响范围

### schema（2 文件，8 处）

| 文件 | 行 | 当前 | 改为 |
|------|----|------|------|
| `aggregated_rule_set.schema.json` | 89 | `"enum": ["file", "path"]` | `["file", "dir"]` |
| 同上 | 99 | 同上 | 同上 |
| 同上 | 139 | `"const": "path"` | `"const": "dir"` |
| 同上 | 154 | 同上 | 同上 |
| `kmm_rule.schema.json` | 144 | `"enum": ["file", "path"]` | `["file", "dir"]` |
| 同上 | 153 | 同上 | 同上 |
| 同上 | 200 | `"const": "path"` | `"const": "dir"` |
| 同上 | 215 | 同上 | 同上 |

### 代码（3 文件，12 处）

| 文件 | 行 | 当前 | 改为 |
|------|----|------|------|
| `engine.py` | 89 | `source_type == "path"` | `source_type == "dir"` |
| 同上 | 106 | `into_type: str = "path"` | `into_type: str = "dir"` |
| 同上 | 109-111 | `into_type == "path"` / `from_type == "path"` | `== "dir"` |
| 同上 | 329 | `item.get("into_type", "path")` | `item.get("into_type", "dir")` |
| 同上 | 357 | 同上 | 同上 |
| `validation.py` | 113 | `{"file", "path"}` | `{"file", "dir"}` |
| 同上 | 117 | 同上 | 同上 |
| 同上 | 133 | `from_type == "path"` | `from_type == "dir"` |
| 同上 | 137 | `into_type == "path"` | `into_type == "dir"` |
| 同上 | 144 | `{"file", "path"}` | `{"file", "dir"}` |
| 同上 | 148 | `into_type == "path"` | `into_type == "dir"` |
| `rule_aggregator.py` | 246 | comment `"path"` | `"dir"` |
| 同上 | 250 | `_from_type == "path"` | `_from_type == "dir"` |
| 同上 | 269 | `_into_type == "path"` | `_into_type == "dir"` |

### 文档（1 处）

| 文件 | 行 | 当前 | 改为 |
|------|----|------|------|
| `TERMS_TERMINOLOGY.md` | 63 | `"file"` 或 `"path"` | `"file"` 或 `"dir"` |

### 示例文件（1 文件，5 处）

| 文件 | 行 | 当前 | 改为 |
|------|----|------|------|
| `aggregated_rule_set.json.example` | 47,58,69,80,103 | `"into_type": "path"` | `"into_type": "dir"` |

### 测试（1 文件，3 处）

| 文件 | 行 | 当前 | 改为 |
|------|----|------|------|
| `test_integration_fixtures.py` | 67,102,134 | `"into_type": "path"` | `"into_type": "dir"` |

### kmm_rule JSON 文件（外部文件）

用户库中的 `kmm_rule*.json` 需同步更新 `"into_type"` / `"from_type"` 值。不在此仓库中，不作向后兼容处理。

## 实施顺序

1. 施工文档（本文）
2. schema（2 文件）
3. 代码（3 文件）+ 向后兼容
4. 文档（TERMS_TERMINOLOGY.md）
5. 示例（aggregated_rule_set.json.example）
6. 测试（test_integration_fixtures.py）
7. 全量测试验证
8. 提交
