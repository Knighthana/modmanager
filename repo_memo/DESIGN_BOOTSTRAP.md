# DESIGN_BOOTSTRAP — Bootstrap 环境初始化

> 来源：DESIGN_BOOTSTRAP_ORCHESTRATOR.md（bootstrap 部分）+ QUESTIONS_BOOTSTRAP.md（合并）
> 状态：已完成 ✅

---

## 一、定位

Bootstrap 负责环境初始化：user_config 发现、Steam 库发现、数据库生成。这些是 prepare 阶段的职责。

```
                    ┌─────────────────────┐
       CLI / GUI →  │    orchestrator      │  统一调度入口
                    └──────────┬──────────┘
                               │ 需要初始数据时调用
                    ┌──────────▼──────────┐
                    │     bootstrap        │  环境初始化
                    │  (user_config 发现、 │
                    │   Steam DB 生成)      │
                    └──────────────────────┘
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
          aggregator        engine        backup_ops
         (规则聚合)       (映射计算)      (备份/替换/恢复)
```

- **bootstrap**：纯粹的环境初始化。可被 orchestrator 调用，也可被测试/外部独立调用。
- 现有底层模块不感知 bootstrap 的存在，保持独立可测试。

**文件**：`src/modmanager/bootstrap.py`

---

## 二、核心函数

### 1. `discover_user_config()`

**三级搜索链**（后者覆盖前者）：
1. `~/.config/kmm/user_config.json`（最低优先级）
2. `<软件本体目录>/user_config.json`（中优先级）
3. `$PWD/user_config.json`（最高优先级）

软件本体目录 = 包含 pyproject.toml 的最近父目录（开发模式）或 site-packages/modmanager/（pip 安装后）。自动检测：从 `__file__` 向上查找 pyproject.toml，未找到则 fallback 到 site-packages 路径。

```python
def discover_user_config(home_dir: str | None = None) -> dict:
    """搜索三级 user_config.json 并按层级合并。
    
    合并规则：后者覆盖前者（dict 级别 shallow merge）。
    
    Returns:
        合并后的 user_config 字典
    Raises:
        FileNotFoundError: 若三级搜索均未找到任何 user_config.json
    """
```

### 2. `generate_database()`

```python
def generate_database(
    mode: str,
    *,
    paths: list[str] | None = None,
    working_pathstyle: str = "linux",
    greedy_parsing: bool = False,
    on_progress: ProgressCallback | None = None,
    cache_path: str | None = None,
) -> dict:
    """生成或加载 Steam 数据库。
    
    Args:
        mode:
            "auto"  — 自动发现 Steam 库路径，调用 steam_scanner
            "manual" — 手动模式，paths 必须传入（vdf 文件路径或 steamapps 目录路径）
        paths: manual 模式下的路径列表
        working_pathstyle: "linux" | "windows"
        greedy_parsing: 是否放宽 mod 解析范围
        on_progress: 进度回调
        cache_path: 若提供，优先从此路径加载缓存；生成后写入此路径
    
    Returns:
        database 字典，格式兼容 engine.compute_mapping 的 database 输入
    """
```

**缓存策略**：只缓存生成成功的数据库（`mode="auto"` 扫描成功后写入 `cache_path`；下次调用时若 `cache_path` 存在且有效则直接加载）。

### 3. `_detect_software_dir()`

```python
def _detect_software_dir() -> str:
    """从 __file__ 向上查找 pyproject.toml。
    找到则返回该目录（开发模式），否则返回 site-packages/modmanager/。
    """
```

---

## 三、决策记录（QUESTIONS_BOOTSTRAP.md）

| Q# | 决策 | 说明 |
|-----|------|------|
| Q1 | **自动检测** | 从 `__file__` 向上查找 `pyproject.toml`，未找到则 fallback 到 site-packages |
| Q2 | 启动时按层级拼接三个 user_config 文件 | 后者覆盖前者 |
| Q3 | 多接口 | `mode="auto"` 自动发现，`mode="manual"` 传入路径；只缓存成功的 |
| Q4 | 以文件颗粒度外部传入 kmm_rule | 支持批量 |
| Q5 | 不需要分步等待 | 采用分模块细粒度 + `run()` 聚合入口 |
| Q6 | **方案 A** | orchestrator 为唯一调度入口，CLI 变为薄壳 |
| Q7 | 回调 `(step, finished, total, message)` | log + stderr/stdout 并行 |
| Q8 | 会话持久化当前仅存 `action_order` | — |
