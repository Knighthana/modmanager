# 规则文件校验 — 测试断言

> 依据：`DESIGN_RULE_VALIDATION.md`
> Schema 权威：`repo_spec/kmm_rule.schema.json`

---

## 一、Schema 粗筛（Stage 1）

| # | 场景 | 输入 | 期望 |
|---|------|------|------|
| S1 | 合法文件 | 完整 kmm_rule JSON | `passed`，无 `rejected` |
| S2 | `from_type: "path"` | `actionlist[0].from_type = "path"` | `rejected`，包含 `E_INVALID_FROM_TYPE: "path"`（schema enum 不含 `"path"`） |
| S3 | `into_type: "path"` | 同上 | `rejected`，同原因 |
| S4 | 缺少 `mixed_id` | mod 条目无 `mixed_id` | `rejected`（schema `required`） |
| S5 | 非 JSON | 文件内容为纯文本 | `rejected`（JSON parse 失败） |
| S6 | 空文件 | 0 字节 | `rejected` |

## 二、语义精筛（Stage 2）

| # | 场景 | 期望 |
|---|------|------|
| S7 | `from` 含 `../` | `rejected`，`E_PATH_TRAVERSAL` |
| S8 | `into` 含 `../` | `rejected`，`E_PATH_TRAVERSAL` |
| S9 | `from` 含 `//`（冗余分隔符） | `passed`（非安全问题，不拒绝；可 belated warning） |
| S10 | `from` 以 `/` 起始（绝对路径） | `passed`（规则 DSL 不禁止，但引擎可能警告） |
| S11 | `action: "unknown_action"` | `rejected`，`E_INVALID_ACTION` |
| S12 | `replace` 无 `from` | `rejected`，`E_MISSING_FROM` |
| S13 | `delete` 有 `from` | `passed`（虽多余但无害） |
| S14 | `hold` 有 `from` + `into` | `passed`（虽多余但无害） |
| S15 | `from` 空列表 + action = `replace` | `rejected`，`E_MISSING_FROM` |
| S16 | `into` 空列表 + action = `replace` | `rejected`，`E_MISSING_INTO` |
| S17 | `mixed_id` 缺少冒号 | `warning`，`W_MIXED_ID_FORMAT` |
| S18 | `mixed_id: "::"` | `warning`（格式虽合法但无意义） |
| S19 | `def_destin` 非标准格式 | `warning`，`W_DESTIN_FORMAT` |
| S20 | `sub[]` 中某条缺冒号 | `warning`，`W_SUB_FORMAT` |

## 三、集成

| # | 场景 | 期望 |
|---|------|------|
| I1 | 全部合法 | `passed` 长度 = 输入文件数；`rejected` 空；聚合正常 |
| I2 | 混合（2 合法 + 1 不合法） | `passed` = 2，`rejected` = 1；聚合仅处理 2 个 |
| I3 | 全部不合法 | `passed` 空，`rejected` = 3；聚合器收到警告无崩溃 |
| I4 | rejected 文件的错误详情 | 每项含 `path` 和 `errors: [str]` |
| I5 | 聚合器调用 | `aggregate()` 入口跑 `validate_kmm_rule_files()`；rejected 不影响合法文件结果 |

## 四、SPEC 引用

- Stage 1 依赖 `kmm_rule.schema.json` 的 `enum`、`required`、`type` 约束
- Stage 2 C1-C10 见 `DESIGN_RULE_VALIDATION.md` §二
- `"path"` 拒绝决策见 `DESIGN_RULE_VALIDATION.md` §2.2
