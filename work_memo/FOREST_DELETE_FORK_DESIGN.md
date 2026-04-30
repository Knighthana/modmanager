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

## 7. 讨论演进：从"刨根移栽"到"独立根 + 引用"

### 旧模型的问题（§1-§6）

移植刨根导致 delete 语义污染、原根位置空洞、用户无否决权。

### 新模型：独立根 + 引用

```
Forest（每棵树独立）:
  Tree 1: /modA/file.png ──[delete]           ← 独立根，不被移植
                                  ↑ 引用（非占有）
  Tree 2: /game/target.png ──────┘            ← 声明依赖，不刨根

每棵树的根是自己路径上的操作。树之间通过引用表达依赖关系，不通过移植根来减少树的数量。
```

### Glob 与警告

`glob` 展开以磁盘当前状态为准。same actionlist 内：
- `delete → create`：不应产生 `W_CREATE_TARGET_EXISTS_OVERWRITE`（前序 delete 已清空）
- `replace → delete`：不应产生冲突（作者意图是先替换后删源）

这两个是 same actionlist 的内部语义，与跨树分岔无关。

### 关键权衡

| | 刨根移栽（旧） | 独立根 + 引用（新） |
|---|---|---|
| delete 语义 | 随迁移污染 | 留在原地，不变 |
| 原根位置 | 空洞 | 独立存在，可决策 |
| 用户否决权 | 需额外机制 | 天然支持 |
| delay-delete | 需要 | 不需要 |
| 树的数量 | 少但错误 | 多但正确 |

---

## 8. 特例 trick 枚举

无论是在旧模型还是新模型中，都需要处理的"特殊情况"：

| # | 特例 | 旧模型是否需要 | 新模型是否需要 |
|---|------|:---:|:---:|
| T1 | same actionlist: `delete X → create/replace X` | ✅ | ✅ |
| T2 | same actionlist: `replace X→T → delete X` | ✅ | ✅ |
| T3 | 跨树依赖：Tree A 引用 Tree B 的根作为源 | ✅（裂变） | ✅（引用解析） |
| T4 | 多棵树引用同一棵树的根 | ✅ | ✅ |
| T5 | delete 是目录，源是目录内文件 | ✅ | ✅ |
| T6 | `rename_then_replace` 后 delete 原始路径 | ✅ | ✅ |
| T7 | `clear_then_copy` 目录 + 依赖该目录内文件的操作 | ❓ | ❓ |
| T8 | 用户在引用树上做分支决策 → 影响被引用树的状态 | ✅ | ✅ |
| T9 | `apply` 执行顺序：依赖树的执行早于/晚于被依赖树 | ✅ | ✅ |
| T10 | Forest 可视化中引用关系的展示方式 | ✅ | ✅ |
| T11 | glob `*/` 在"文件已被 delete"的上下文中展开 | ✅ | 不展开（以磁盘为准） |

**计数**：旧模型 ~10 个，新模型 ~9 个。数量接近。

但如果按**"这个 trick 是否引入新的语义模糊"**来衡量：

| 模型 | 语义清晰的 trick | 语义模糊的 trick |
|------|:---:|:---:|
| 旧（刨根） | T1, T2, T5, T6 | T3, T4, T8, T9 |
| 新（引用） | T1-T6, T9-T11 | T8 |

新模型减少了一半模糊点。**T8 成了唯一的语义模糊点**：用户在 Tree A 上做了分支决策后，这个决策怎么传递给 Tree B？是通过"源可用/不可用"的布尔信号，还是需要更复杂的传递？

---

## 9. 当前判断

T1-T6 是两种模型共有的、逻辑上无法避免的边界情况处理。数量可控。

T8 是新模型的核心未解决问题。需要你的判断：

> 分支决策的传递粒度：是"文件存在/不存在"的布尔值，还是"用户选择保留此文件 → 所有依赖者都可以用它"的全局许可？