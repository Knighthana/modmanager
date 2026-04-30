# 森林模型补丁：delete 结点裂变 + holdasoriginal

创建：2026-04-30
状态：设计草案（待质疑与完善）

---

## 1. 问题陈述

### 当前行为（有缺陷）

```
Author A: replace /modA/file.png → /game/target.png
Author B: delete  /modA/file.png

引擎处理：
  mapping[/game/target.png]  源 = /modA/file.png
  mapping[/modA/file.png]    操作 = delete

  _resolve_effective_leaf_request(/game/target.png):
    → 递归到 /modA/file.png
    → 得到 delete
    → 级联：/game/target.png 也被删除  ← BUG
```

**缺陷**：delete 的语义在递归中从"删除源文件"变成了"删除目标文件"。源文件的 delete 是 Author B 在 `/modA/file.png` 上挂的操作，不应影响 `/game/target.png` 的命运。

### 期望行为

当 `/modA/file.png` 作为源被挂到 `/game/target.png` 下方时，它的 delete 子结点应**当场裂变**为两个分岔：

```
/game/target.png
    └── /modA/file.png  ← 分岔结点（因为它是另一个操作的 target）
            ├── filenotexist     ← 分支 A：文件不存在（delete 先执行）
            └── holdasoriginal   ← 分支 B：保持原样（delete 暂缓）
```

用户选择：
- **选 A**：拒绝依赖此文件的所有操作（replace 无源，失败）
- **选 B**：先执行依赖操作（replace），后执行 delete

---

## 2. 三条推论

| # | 推论 | 说明 |
|---|------|------|
| 1 | delete 结点跟随迁移时**当场裂变** | 两个分支代表两种用户意图 |
| 2 | apply 时争议删除在**最后阶段**执行 | "延迟删除队列"：所有被 hold 的 delete 在 apply 末尾统一执行 |
| 3 | `hold` 语义需要重新审视 | 当前 hold = "跳过不执行"。可能需要新增 "postpone" 语义："暂时不删，但最终必须删" |

---

## 3. 分岔结点的判断条件

一个源路径 X 在森林中自动成为分岔结点，当：
1. X 在 mapping 中有 changerequest（即 X 是某个操作的 target）
2. 且 X 被另一个 target Y 的 changerequest 引用为源（即 X 是另一个映射的源）

满足这两个条件时，生成分岔：
- **分支 A**：X 的原始 changerequest（如 delete）
- **分支 B**：holdasoriginal（X 保持当前状态，允许以 X 为源的映射正常执行）

---

## 4. `filenotexist` vs `holdasoriginal` 的语义

| 结点类型 | 含义 | 对依赖者的影响 |
|----------|------|---------------|
| `filenotexist` | 文件在执行时不存在 | 以该文件为源的操作失败 |
| `holdasoriginal` | 文件暂保持当前状态，但最终必须删除 | 以该文件为源的操作可执行，执行完成后文件被删除 |

---

## 5. apply 执行顺序

```
Phase 1: 执行所有非争议操作（replace / create / rename / clear_then_copy）
Phase 2: 执行依赖 holdasoriginal 的操作（源文件此时还存在）
Phase 3: 执行"延迟删除队列"（所有被 hold 的 delete）
```

---

## 6. 自我质疑

### Q1: 多层级联时，裂变在哪里发生？

```
Author A: replace /modA/a.png → /game/x.png
Author B: replace /modB/b.png → /modA/a.png
Author C: delete  /modB/b.png

链：x.png ← a.png ← b.png (deleted)
```

b.png 被 delete 且被 a.png 引用为源 → b.png 裂变。
a.png 的源裂变后，a.png 自身也应该裂变——因为它的命运取决于 b.png 的分岔选择。

**问题**：裂变是只发生一次（b.png），还是逐层向上传导（b.png → a.png → x.png）？

**直觉**：应该逐层向上传导。层数 = 依赖链深度。每一层都是一个分岔。

→ 这会导致分岔数量指数爆炸吗？n 层依赖 = 2^n 个分支？

### Q2: "最终必须删除" 是否绑架了用户？

Author B 写了 `delete /modA/file.png`。但用户可能根本不同意 Author B——他想保留这个文件。

当前设计中 holdasoriginal **不是"不删"**，而是"先留着，最后删"。

**问题**：用户有没有权利说"我就是不删这个文件"？

**可能的答案**：如果用户选择了 holdasoriginal → 文件最后被删，那用户等于接受了 Author B 的规则，只是推迟了执行。如果用户真的想完全拒绝 Author B 的规则，他需要什么机制？

### Q3: 多条规则同时操作同一个源

```
Author A: replace /modA/file.png → /game/target.png
Author B: delete  /modA/file.png       ← 同一个源的两个命运
Author C: replace /modA/file.png → /game/target2.png  ← 又一个依赖者
```

这里 /modA/file.png 的分岔是二选一还是三选一？

- 分支 A: filenotexist（delete 先执行，A 和 C 都失败）
- 分支 B: holdasoriginal（delete 暂缓，A 和 C 都用它）

但如果用户希望 A 成功而 C 失败呢？分岔粒度是按"文件"分的，不是按"依赖者"分的。这意味着用户无法为同一个源的不同依赖者做不同决定。

→ 这是否是一个问题？

### Q4: delete 的是目录而非文件

```
Author A: replace /modA/maps/lobby/ → /game/maps/lobby/
Author B: delete  /modA/maps/
```

`/modA/maps/lobby/` 是 `/modA/maps/` 的子目录。delete 目录时，目录内的文件全部消失。

**问题**：裂变应该出现在 `/modA/maps/` 层（目录被删，子目录全灭）还是 `/modA/maps/lobby/` 层？如何检测这种父子目录关系？

### Q5: apply 的延迟删除队列是否安全？

Phase 1: 执行 replace / create  
Phase 2: 执行依赖 holdasoriginal 的操作  
Phase 3: 执行延迟删除

**问题**：Phase 2 的操作可能实际上**创建了新文件**到被 delete 的目录中。Phase 3 的 delete 会把 Phase 2 创建的文件也删掉吗？

例如：`delete /modA/maps/` 被 hold，Phase 2 中 `replace /modA/maps/new.png → /game/new.png`，Phase 3 执行 `delete /modA/maps/` → 这个 delete 要删除整个 `/modA/maps/` 目录，包含 Phase 1/2 创建的新文件吗？

**结论**：延迟删除应该只删除**原本要删的目标**（原始 delete 的目标路径），不能把 Phase 1/2 的产出物也删了。但这在实际操作中很难做到——`delete /modA/maps/` 是删整个目录，进去之后分不清哪些是原有的、哪些是新创建的。

### Q6: holdasoriginal 与 "later wins" 规则的冲突

同一 actionlist 内，如果先写 `replace x → t, delete x`，deleted 是 actionlist 的最后一个操作，按 later-wins 规则它赢。但如果 x 恰好也是另一个 target 的源，按裂变逻辑它会裂变。

**问题**：later-wins 是 actionlist 内部规则，裂变是跨 actionlist 的规则。同一个 actionlist 的 later-wins 结果是否应该进入跨 actionlist 的分岔？还是分岔只考虑跨 actionlist 的冲突？

### Q7: 文件被 delete 后又作为了别人的 rename_then_replace 源

如果源文件在被 delete 之前已经被 rename 走了（`rename_then_replace` 的第一步是 mv），那 delete 操作的是新名字还是旧名字？如果旧名字的文件已经不存在（被 rename 了），delete 应该静默成功（目标不存在）还是报警告？

---

## 7. 初步判断：哪些是真正的漏洞，哪些可以接受

| Q# | 判断 |
|-----|------|
| Q1 (多层裂变) | 需要解决。预计实现复杂度与依赖深度成正比，不是指数爆炸（裂变在同一层发生，不同层之间的分岔是独立的） |
| Q2 (用户能否拒绝 delete) | 需要给用户第三个选项："reject delete"（完全拒绝 Author B 的规则）。holdasoriginal ≠ 拒绝删除 |
| Q3 (多依赖者粒度) | 当前设计所有依赖者共享同一个分岔选择。这是否可接受取决于用户场景——通常情况下"这个文件是否存在"是二元状态，理应影响所有依赖者 |
| Q4 (目录 delete) | 需要特殊处理。目录 delete 的裂变应该在目录层，子路径的裂变继承父目录的分岔选择 |
| Q5 (delete 误删 Phase 2 产出) | 真正的安全问题。延迟 delete 必须做路径过滤——只删原始目标，不删 Phase 1/2 产出 |
| Q6 (later-wins 与裂变的关系) | 同一 actionlist 内 later-wins 的结果是"这个 actionlist 对这个文件的最终操作"。这个最终操作再参与跨 actionlist 的分岔 |
| Q7 (rename 后 delete) | 边缘情况。但引擎已处理：rename_then_replace 的源是 nwname，delete 的目标是原始路径。如果 delete 执行时文件已 rename → 目标不存在 → 静默成功或 warning
