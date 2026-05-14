# 审计日志治理规范

> Status: active
> Authority: authoritative
> Read-Tier: meta
> Purpose: 定义 user_memo/audit_logs/ 的生命周期管理、元数据格式、冻结条件和检索方法，防止讨论知识散失和重复循环

创建：2026-05-14

---

## 0. 审计日志的定位

**不是：**
- 日常工作记录（那是 work_memo/）
- 历史实现日志（那是 repo_logs/）
- 设计权威（那是 repo_memo/）

**是：**
- 讨论到设计文档的**转换过程**记录
- 多工作组协作时的**知识同步点**
- 未来追溯**某个决定为什么这样**的**冷备份**

---

## 1. 审计日志的生命周期

```
讨论开始
    ↓
audit_logs/{date}_{topic}.md (ACTIVE)
  ├─ 记录讨论过程、论证、多方案比较
  ├─ 列出临时结论（待转换为设计文档）
  └─ Frontmatter: status = ACTIVE
    ↓
[讨论结束，进行集中决策]
    ↓
结论 → 转换为 repo_memo/ 的设计文档
  ├─ 新增：DESIGN_*.md
  ├─ 更新：TERMS_*.md, PATTERNS_*.md
  └─ 清理：删除旧术语和过时说法
    ↓
audit_logs 中该条目标记为 FINALIZED，Frontmatter 更新
  ├─ status = FINALIZED
  ├─ fixated_into = [转换后的文档列表]
  └─ 内容不再修改，作为冷备份存档
    ↓
新工作组上车
  ├─ 读 repo_memo/ 的 Tier 0/1 文档（权威）
  ├─ 不主动读 audit_logs/（除非被明确问到）
  └─ 所有决定来源于 repo_memo/，不需要追溯
```

---

## 2. 审计日志的 Frontmatter 格式

**所有审计文档必须在文件顶部使用 YAML frontmatter**：

```yaml
---
date: YYYY-MM-DD                  # 讨论日期
topic: Brief Title                # 讨论主题
status: ACTIVE | FINALIZED        # 状态
scope: Area1, Area2, ...          # 涉及的范围（用逗号分隔）
fixated_into:                     # [仅 FINALIZED 时填写] 决定转换后的文档
  - repo_memo/DESIGN_XXX.md (§ section name)
  - repo_memo/TERMS_YYY.md (add fields: ...)
cleanup_actions:                  # 删除/更新的文档操作
  - DOCUMENT_NAME: action description
  - ...
related_discussions:              # 相关的其他审计文档或讨论
  - 2026-05-13_Topic.md
  - 2026-05-12_Another-Topic.md
open_items:                       # 未来跟进事项（可选）
  - TODO-N: 描述 (status: blocked|backlog|delegated)
  - ...
---
```

**示例（ACTIVE）**：
```yaml
---
date: 2026-05-14
topic: Storage Architecture Deep Dive
status: ACTIVE
scope: Storage, Frontend, Backend
fixated_into: []
cleanup_actions: []
related_discussions:
  - 2026-05-14_REST-API-and-GUI-Analysis.md
open_items:
  - Decide: aggregatedRuleSet in localStorage or not
  - Validate: frontend storage structure
---
```

**示例（FINALIZED）**：
```yaml
---
date: 2026-05-14
topic: Architecture Design Finalization
status: FINALIZED
scope: Storage, Python Layers, Frontend Independence, API Stability
fixated_into:
  - repo_memo/DESIGN_PYTHON_LAYERS.md (complete file)
  - repo_memo/DESIGN_FRONTEND_LAYER_INDEPENDENCE.md (complete file)
  - repo_memo/DESIGN_REST_API.md (§1.6-1.7 冻结部分)
  - repo_memo/TERMS_FIELD_FREEZE.md (§新增冻结字段)
  - repo_memo/PATTERNS_ENGINEERING.md (§新增工程模式)
cleanup_actions:
  - TERMS_FIELD_FREEZE.md: delete "已废弃字段" section
  - DESIGN_REST_API.md: delete "forest → trees" migration notes
  - DESIGN_STORAGE.md: delete "workspace.json migration" history
  - DESIGN_FOREST_MODEL.md: verify no old terminology
---
```

---

## 3. ACTIVE 和 FINALIZED 的区别

| 属性 | ACTIVE | FINALIZED |
|------|--------|-----------|
| **修改权**| 讨论过程中可编辑 | 冻结，不再修改（除非标记为已过期） |
| **fixated_into** | 空列表 | 列出转换后的所有文档 |
| **阅读频率** | 讨论参与者频繁阅读 | 仅在明确查询时阅读 |
| **前置条件** | 无 | 所有决定已转换为 repo_memo/ 文档 |
| **何时标记** | 创建时立即设置 | 讨论结束，所有转换完成后 |

---

## 4. FINALIZED 的转换检查清单

标记为 FINALIZED 前，必须完成以下验证：

- [ ] 所有讨论的结论都已转换为 repo_memo/ 的文档
- [ ] 新增文档（如 DESIGN_PYTHON_LAYERS.md）都已创建
- [ ] 现有文档的更新（删除旧术语、加新冻结字段）都已完成
- [ ] `cleanup_actions` 中列出的删除/更新都已执行
- [ ] 检查 repo_memo/ 中的引用是否指向正确的文件和章节
- [ ] 所有旧术语从设计文档中消失（仅在本审计文档中记录）
- [ ] 测试：新来的团队成员只读 repo_memo/，能否完全理解当前架构

---

## 5. 检索规则

### 用户问：为什么存储要分成三层？

**流程**：
1. 新成员首先读：`repo_memo/DOCUMENT_GOVERNANCE.md`（已冻结的决定列表）
2. 找到"存储三层"的引用 → `repo_memo/DESIGN_STORAGE.md`
3. 从 DESIGN_STORAGE.md 的 frontmatter 或内容了解当前定义
4. **不需要查看 audit_logs/**

### 用户问：存储三层决定的详细讨论过程是什么？

**流程**：
1. 搜索 `user_memo/audit_logs/` 中的 FINALIZED 文档
2. 找到 `2026-05-14_Architecture-Design-Freeze-and-Cleanup.md`
3. 查看其 frontmatter 的 `fixated_into` 确认这是该决定的记录
4. 通过文档正文了解论证和多方案比较
5. **仅当被明确问到历史细节时才读取**

### 用户问：某个字段为什么改名了？

**流程**：
1. 读 `repo_memo/TERMS_FIELD_FREEZE.md`，看冻结列表
2. 如果想了解改名历史，搜索 audit_logs/ 中的 FINALIZED 文档
3. 找到相关审计记录，看 `related_discussions` 和正文
4. **不会问这个问题，因为旧名称已从设计文档消失**

---

## 6. Frontmatter 索引建立（可选工具）

为了防止日期命名失效，建议在 `user_memo/audit_logs/README.md` 中维护一个索引：

```markdown
# 审计日志索引

| 日期 | 主题 | Status | fixated_into |
|------|------|--------|--------------|
| 2026-05-14 | Architecture Design Finalization | FINALIZED | DESIGN_PYTHON_LAYERS, DESIGN_FRONTEND_LAYER_INDEPENDENCE, ... |
| 2026-05-13 | REST API and GUI Tar Pit Analysis | FINALIZED | DESIGN_REST_API (partially), ... |
| 2026-05-09 | Storage Architecture Deep Dive | FINALIZED | DESIGN_STORAGE, ... |
```

但这个索引**不是必须**，因为每个文档自己的 frontmatter 已经包含足够的元数据。

---

## 7. 禁止事项

**在审计日志中**：

1. **不要试图成为权威**
   ```markdown
   ❌ "字段冻结列表（当前）："
   ✅ "讨论的结论：以下字段冻结（已转换至 TERMS_FIELD_FREEZE.md）"
   ```

2. **不要重复 repo_memo/ 的内容**
   ```markdown
   ❌ "完整的存储三层定义如下：... [大段 copy/paste]"
   ✅ "决定：采用三层存储模型（详见 DESIGN_STORAGE.md）"
   ```

3. **不要在 FINALIZED 后继续修改**
   ```
   ❌ 发现有改进的地方，直接改审计文档
   ✅ 如需更新，在 repo_memo/ 中改设计文档，新增审计记录如"2026-05-15_Storage-Refinement.md"
   ```

4. **不要让审计日志成为设计参考**
   ```
   ❌ Plan 指令："按 audit_logs 的 Design_STORAGE_IMPLEMENTATION.md 改"
   ✅ Plan 指令："按 repo_memo/DESIGN_STORAGE_IMPLEMENTATION.md 改"
   ```

---

## 8. 文档生命周期示例

### 例 1：通常情况（决定 → 设计文档 → FINALIZED）

时间线：
- **2026-05-14 09:00** — 讨论开始，创建 `audit_logs/2026-05-14_Storage-XX.md`，status=ACTIVE
- **2026-05-14 11:00** — 讨论结束，决定已明确，开始转换为设计文档
- **2026-05-14 12:30** — 创建 DESIGN_PYTHON_LAYERS.md, DESIGN_FRONTEND_LAYER_INDEPENDENCE.md
- **2026-05-14 13:00** — 更新 TERMS_FIELD_FREEZE.md, PATTERNS_ENGINEERING.md 等
- **2026-05-14 13:30** — 审计文档改为 status=FINALIZED，加 fixated_into 列表
- **2026-05-14 14:00** — Plan 验收：新成员只读 repo_memo/，能否理解新架构？✅
- **2026-05-15+** — audit_logs 文档不再被读取（除非某日被问"为什么当初这样决定"）

### 例 2：需要回滚的情况（决定变更）

假设 6 个月后，发现存储三层模型需要调整：

- **2026-11-14** — 新讨论开始，创建 `audit_logs/2026-11-14_Storage-Refinement.md`
- 在新审计文档中说明：旧决定来自 `2026-05-14_...`（reference，不复述）
- 新决定转换为新的 DESIGN_STORAGE_v2.md（或直接改旧的并标记更新日期）
- 旧的 2026-05-14 审计文档保持 FINALIZED 状态不变（作为历史记录）

**结果**：新工作组读最新的 DESIGN_STORAGE.md，看到当前状态；追溯时可看到两份审计记录的对比。

---

## 9. 与 repo_logs/ 的区别

| | audit_logs/ | repo_logs/ |
|---|---|---|
| **内容** | 讨论 → 设计的转换过程 | 实现工作的日期记录 |
| **权威性** | 讨论论证，非权威 | 纯日志，无权威 |
| **生命周期** | ACTIVE → FINALIZED | append only |
| **阅读策略** | 结论转换后不读；追溯时按需读 | 禁止主动阅读，仅明确指令时读 |
| **粒度** | 架构级决定 | 日级别工作现场 |

---

## 10. 文档链接

- 文档治理：`repo_memo/DOCUMENT_GOVERNANCE.md`
- 工作现场：`work_memo/states.md`
- 所有审计日志：`user_memo/audit_logs/`
