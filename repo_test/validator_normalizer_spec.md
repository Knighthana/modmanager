# validator_normalizer_placement — validator / normalizer 调用点归位

> Status: active
> Authority: normative
> Read-Tier: task-scoped
> Purpose: 裁定 5 的测试断言 — 验证 `validate_kmm_rule_files()` 和 `normalize_rule_actions()` 的调用位置
> 依据: `DESIGN_RULE_VALIDATION.md`、`DESIGN_RULE_AGGREGATOR.md`、`DESIGN_BOOTSTRAP.md`、`work_memo/2026-06-01_TASK_arch_drift_review.md` 裁定 5

---

## 一、适用范围

| 模块 | 调用方 | 调用时机 | 职责 |
|------|--------|---------|------|
| `rule_validator.validate_kmm_rule_files()` | bootstrap → verifier | kmm_rule 文件加载后、送入 aggregator 前 | schema 校验 + C1-C10 语义检查 |
| `path_normalizer.normalize_rule_actions()` | aggregator 入口 | `aggregate()` 内部，每个 kmm_rule 文件加载后 | 路径归一化 |

---

## 二、黑箱测试断言

### 2.1 validator 调用位置

| # | 断言 | 级别 |
|---|------|:---:|
| T-VN-01 | `validate_kmm_rule_files()` **不由** `rule_aggregator.aggregate()` 内部直接调用 | MUST |
| T-VN-02 | `validate_kmm_rule_files()` 的调用发生在 aggregator 被调之前（通过 bootstrap → verifier 路径） | MUST |
| T-VN-03 | 传入 `aggregate()` 的 `kmm_rule_paths` 均为已通过校验的文件（无不合格文件混入） | MUST |
| T-VN-04 | `validate_kmm_rule_files()` 拒绝的文件不出现在 aggregator 输入中 | MUST |

### 2.2 normalizer 调用位置

| # | 断言 | 级别 |
|---|------|:---:|
| T-VN-05 | `normalize_rule_actions()` 在 `aggregate()` 入口处被调用（文件加载后、权限映射构建前） | MUST |
| T-VN-06 | 路径归一化后 `"path"` 类型被拒绝或归一化为合法值 | MUST |
| T-VN-07 | 路径归一化后尾 `/` 按要求补全 | MUST |
| T-VN-08 | 路径归一化后 `".."` 路径穿越被拒绝 | MUST |

### 2.3 文档一致性

| # | 断言 | 级别 |
|---|------|:---:|
| T-VN-09 | `DESIGN_RULE_VALIDATION.md` 中 validator 调用方描述为 bootstrap → verifier | MUST |
| T-VN-10 | `DESIGN_RULE_AGGREGATOR.md` §6.3 聚合流程中包含 `normalize_rule_actions` 步骤 | MUST |
| T-VN-11 | `DESIGN_BOOTSTRAP.md` 中补充了 verifier 的 kmm_rule 验证职责 | MUST |

---

## 三、验收标准

- [ ] 全部 T-VN-01 ~ T-VN-11 通过
- [ ] 现有聚合器测试不受影响
- [ ] 非法 kmm_rule 文件在 aggregator 被调用前即被拦截
- [ ] 路径归一化结果符合 `DESIGN_ENGINE_INVARIANTS.md` 路径约定
