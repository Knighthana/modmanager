# Bootstrap 模块设计 — 待决策问题

状态：待用户确认
创建：2026-04-30

---

## 模块定位

`src/modmanager_cli/bootstrap.py` — 在现有 M1、聚合器、备份模块之上，提供一个编排层：

```
user_config 发现 → Steam 扫描 → 聚合规则 → 计算映射 → 可视化/应用
```

---

## Q1: "软件本体所在目录"的定义

当前约定：user_config 按 `~/.config/kmm/` → 软件本体目录 → PWD 三级搜索。

但"软件本体目录"在两种场景下含义不同：

| 场景 | 软件本体目录 |
|------|-------------|
| 开发模式（`python -m` 或 `PYTHONPATH=src`） | repo 根目录 |
| pip install 后的生产环境 | `site-packages/modmanager_cli/` |

选择方案：
- A) bootstrap 检测运行模式：检查 `sys.prefix` 或 `__file__` 位置，自动区分
- B) bootstrap 只支持一个固定约定（比如"包含 pyproject.toml 的目录向上找"）
- C) 接受外部参数显式指定，不自行推断

---

## Q2: user_config 搜索链的启动时刻

当前约定：bootstrap 负责生成默认 user_config（如果三级搜索都找不到，按 `.example` 样式在软件本体目录生成）。

但"启动"指的是什么时刻？
- A) bootstrap 模块被导入时
- B) 显式调用某个 `bootstrap.init()` 函数时
- C) 第一次需要 user_config 时才惰性加载

---

## Q3: Steam 数据库的生成策略

bootstrap 需要为 M1 引擎准备 `database.json`。有两种路径：

| 路径 | 说明 |
|------|------|
| 自动发现 | 调用 `steam_scanner` 从常见 Steam 路径自动扫描多库 |
| 手动指定 | 用户提供 Steam 库路径列表 |

选择方案：
- A) 先尝试自动发现，失败时 fallback 到手动指定
- B) 始终要求手动指定（符合"永远允许手动指定"的约束）
- C) 两者都支持，通过参数控制

另外：数据库是否应该缓存？
- A) 每次重新扫描
- B) 缓存到文件，bootstrap 检查文件修改时间决定是否重新扫描
- C) 缓存 + 支持 `--force-rescan` 强制刷新

---

## Q4: kmm_rule 文件的发现

聚合器要求显式传入 kmm_rule 文件列表（不负责发现）。bootstrap 需要提供这个列表。来源是：
- A) 从约定目录扫描（如 `~/.config/kmm/rules/` + 软件本体目录 `rules/`）
- B) 从 `user_config.json` 中的一个 `rule_directories` 字段读取
- C) 由外部调用者显式传入（bootstrap 不负责发现 kmm_rule）

如果是 A 或 B，目录扫描是否递归？是否只扫描 `*_Replace.json` 之类有特定命名模式的文件？

---

## Q5: bootstrap 的接口粒度

一个大函数还是多个独立步骤？

**方案 A — 单步**：
```python
def run_pipeline(config) -> PipelineResult:
    # scan → aggregate → compute → return forest + final_mapping
```

**方案 B — 分步**：
```python
def init_user_config() -> dict
def generate_database(...) -> dict
def load_rules(...) -> list[str]
def aggregate_rules(...) -> dict
def compute(...) -> dict
```

方案 B 的优点：GUI 可以在每步之间插入交互（展示扫描进度、让用户勾选规则、展示森林后再决定是否应用）。方案 A 更简洁但不够灵活。

---

## Q6: 与现有 CLI 的关系

当前 `src/modmanager_cli/cli.py` 提供子命令：`steamlib`、`liveupdate`、`regen`、`backup`、`apply`、`restore`、`visualize`。

以及 `cli-hmi/run.py` 做了部分编排工作（加载文件 → 聚合 → 计算映射）。

bootstrap 模块应该：
- A) **替代** CLI 的编排部分，CLI 改为调用 bootstrap
- B) **独立于** CLI，两者平行存在（CLI 给高级用户，bootstrap 给 GUI）
- C) **融入** CLI（bootstrap 是 CLI 的一个子命令）

---

## Q7: 错误处理与进度反馈

扫描 Steam 库可能很慢（遍历大量文件）。bootstrap 如何反馈进度？
- A) 打印到 stdout/stderr（简单）
- B) 通过回调函数（如 `on_progress(step, percent)`）
- C) 通过 Python logging 模块

对于错误：如果某个步骤失败（如 Steam 扫描找不到任何库），是终止全流程还是跳过该步骤继续？

---

## Q8: 会话持久化的范围

`session.py`（状态持久化模块）需要保存什么？

| 数据 | 说明 | 必须？ |
|------|------|--------|
| 激活的 kmm_rule 文件列表 | 用户勾选了哪些规则 | ✅ |
| 最近使用的数据库路径 | 避免每次重扫 | ✅ |
| 分支裁决历史 | `branch_decisions` 的选择 | 可选 |
| 备份目录列表 | 方便恢复 | 可选 |
| 窗口布局/偏好 | GUI 特有 | 暂不需要 |

会话存储格式：JSON 文件？放在哪里（`~/.config/kmm/session.json`）？

---

## 决策优先级

| Q# | 阻塞程度 | 说明 |
|-----|---------|------|
| Q1 | 高 | 软件目录定义影响 user_config 搜索 |
| Q3 | 高 | Steam 数据库是后续所有步骤的前提 |
| Q4 | 高 | 规则发现是聚合器的输入 |
| Q5 | 高 | 接口粒度影响 bootstrap 与 GUI 的对接方式 |
| Q2 | 中 | 惰性加载 vs 显式初始化 |
| Q6 | 中 | 与现有代码的关系 |
| Q7 | 低 | 可后续增强 |
| Q8 | 低 | 先做最小集 |
