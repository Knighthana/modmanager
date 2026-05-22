# DESIGN_PATH_CASE — 路径大小写归一化规范

> Status: proposed
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义所有路径进入系统时的统一归一化规则，消除跨平台、跨来源路径比较中的大小写不一致问题

创建：2026-05-23

---

## 零、问题诊断

### 0.1 根因

当前系统从多个来源接收路径——

| 来源 | 示例 | 大小写特征 |
|------|------|-----------|
| Steam VDF | `D:\Games\Steam\steamapps\` | Windows 默认大写盘符 |
| 用户手动输入 | `/mnt/d/games/steamapps/` | 随意 |
| 文件系统扫描 | `/home/user/.steam/steam/` | Linux 保真，Windows 不敏感 |
| kmm_rule 文件 | `from: ["materials/"]` | 规则作者手写，任意 |
| WSL 桥接 | `/mnt/c/Program Files (x86)/Steam/` | Linux 侧保真，Windows 侧不敏感 |

这些路径经过 **仅归一化分隔符** 的 `normalize_posix()` 后，带着不同的大小写进入数据库、参与比较。后续 40+ 处比较点全以字符串相等/前缀匹配进行——**大小写差异不归零**。

### 0.2 为什么不能全局 `.lower()`

Linux 文件系统是大小写敏感的：`/home/User/` 和 `/home/user/` 是不同的目录。全局小写会破坏 Linux 语义。

### 0.3 为什么也不能逐比较点加 `.lower()`

已在树节点查找试过——三处加了，但 40+ 处没加。逐点修补不可维护，且每处都要判断"这两个路径来自同一平台吗？"——判断逻辑本身也容易出错。

---

## 一、核心原则

> **路径在进入系统存储层时归一化。归一化后的路径在任何比较点均可直接使用原生字符串运算，无需额外大小写处理。**

即：**入口归一化，出口不操心。**

### 1.1 归一化包含两层

| 层 | 内容 | 说明 |
|----|------|------|
| **L1 — 风格归一化** | `\` → `/`，`C:\` ↔ `/mnt/c/` 互转 | 现有 `normalize_posix()` 已做 |
| **L2 — 大小写归一化** | 根据来源文件系统类型决定 | **本文档新增** |

### 1.2 大小写归一化规则

| 来源文件系统 | 规则 | 理由 |
|-------------|------|------|
| **Windows（含 WSL `/mnt/` 挂载）** | 全路径转为**小写** | Windows 文件系统大小写不敏感；小写消除所有变体 |
| **Linux（原生文件系统）** | **保持原样** | Linux 大小写敏感，`/home/User/` ≠ `/home/user/` |
| **macOS（HFS+/APFS 默认）** | **保持原样**（同 Linux 规则） | macOS 默认大小写不敏感但保留原样；与 Linux 规则一致以避免 `normalize_posix` 争议 |
| **用户手写路径**（kmm_rule 中的 `from`/`into`） | **保持原样** | 手写路径应精确匹配规则作者的意图；大小写差异由规则作者负责 |

### 1.3 归一化时机

路径在以下**入口点**完成 L1+L2 归一化后，方可进入后续处理：

| 入口 | 对应模块 | 归一化位置 |
|------|---------|-----------|
| Steam VDF 解析 | `vdf_parser.py` | `parse_libraryfolders_vdf()` 返回值中 |
| 文件系统扫描 | `steam_scanner.py` | `discover_steam_libraries()` → `_scan_from_libraries()` |
| 用户手动输入 | `bootstrap.py` | `generate_database(mode="manual")` |
| 用户手写规则 | `rule_aggregator.py` | 加载 `kmm_rule.json` 时 |
| `user_config` 中的路径 | `bootstrap.py` | `discover_user_config()` 时 |

### 1.4 归一化函数签名

```python
def normalize_path(path: str, *, source_platform: str | None = None) -> str:
    """Normalize a path for storage and comparison.

    L1: Convert to POSIX style (normalize_posix).
    L2: Normalize case based on source platform.

    Args:
        path: Raw path string from any source.
        source_platform: "windows" | "linux" | "darwin" | "wsl".
            If None, auto-detected from path content and sys.platform.

    Returns:
        POSIX-style path with case normalized per platform rules.

    Platform rules:
        windows / wsl → lowercase entire path
        linux / darwin → preserve case
    """
```

---

## 二、各模块归一化落点

### 2.1 `paths.py` — 新增 `normalize_path()`

当前 `normalize_posix()` 只做 L1。新增 `normalize_path()` 做 L1+L2。

| 平台检测 | 实现 |
|----------|------|
| Windows | `sys.platform == "win32"` |
| WSL | `path.startswith("/mnt/")` 且 `sys.platform != "win32"` |
| macOS | `sys.platform == "darwin"` |
| Linux | 其他 |

### 2.2 `steam_scanner.py` — 扫描结果归一化

`discover_steam_libraries()` 返回的 `SteamLibraryInfo.path` 须经 `normalize_path()` 处理。

`_scan_from_libraries()` 中 `game["basepath"]`、`game["modpath"]`、`mod["path"]` 须经 `normalize_path()` 处理。

### 2.3 `bootstrap.py` — 手动输入归一化

`generate_database(mode="manual")` 中用户提供的路径须经 `normalize_path()` 处理后再传入 `discover_with_fallback()`。

### 2.4 `database_ops.py` — CRUD 操作

`add_manual_steamlib()`、`remove_manual_steamlib()`、`update_manual_steamlib()` 中的路径比较——在归一化已做完的前提下，保持原生 `==` / `.startswith()` 即可。无需额外改动。

### 2.5 `backup_dir_builder.py` — 目标匹配

`target.startswith(ge["basepath"])` —— 由于 `target`（来自 engine）和 `ge["basepath"]`（来自 database）均在入口归一化，保持原生 `.startswith()` 即可。

### 2.6 `ignore_rules.py` — 忽略规则匹配

忽略模式（gitignore 语法）的匹配保持大小写敏感——gitignore 规范本身就是大小写敏感的。路径在传入 `should_ignore()` 前已由上游归一化。

### 2.7 树节点查找

`_find_tree_node()` / `_tree_node_is_backuped()` / `_update_tree_node()` —— 由于 backupinfo.tree 中的节点名来自源目录文件的实际名称（文件系统扫描时记录），而传入的 `rel_path` 也来自同一源目录的归一化路径，理论上已一致。但为了防御 Windows 文件系统扫描时的意外差异，**保留**现有的 `.lower()` 比较作为 safety net。

### 2.8 `removeprefix()` 相对路径派生

`backup_ops.py` 和 `restore_ops.py` 中的 `normalize_posix(target).removeprefix(normalize_posix(content_root))` —— 由于 `target` 和 `content_root` 均经归一化，`removeprefix` 不再有大小写失配风险。将 `normalize_posix` 调用统一替换为 `normalize_path`。

---

## 三、不变式（Invariants）

以下不变式在归一化落地后必须成立：

| # | 不变式 | 验证方式 |
|---|--------|---------|
| I1 | 数据库 `steamlib[].path`、`game[].basepath`、`game[].modpath`、`mod[].path` 中所有路径均已经过 `normalize_path()` | 扫描/手动输入后检查 |
| I2 | 同一物理位置的路径，无论通过扫描、手动输入还是 VDF 解析进入系统，归一化后字符串**完全相等** | 跨来源对比测试 |
| I3 | 来自 Windows/WSL 的路径全为小写；来自 Linux 的路径保留原始大小写 | 平台检测测试 |
| I4 | `normalize_path()` 是**幂等**的——对已归一化的路径再次调用不产生变化 | 单元测试 |

---

## 四、回退兼容

归一化规则变更后，已存在的 `database.json` 和 `backupinfo.json` 中存储的路径可能未归一化。

**策略**：不自动迁移旧数据。新旧路径的差异由以下机制消化：
- 数据库：用户重新扫描即可获得归一化后的路径
- backupinfo：树节点查找已有 `.lower()` safety net，不受影响
- 手动路径：用户下次手动输入时自动归一化

---

## 五、与现存 WSL 处理的关系

`pathstyle.py` 的 `_win_to_linux()` 已有 `drive.lower()` 逻辑。新增的 `normalize_path()` 在 WSL 场景下将整个路径小写——这比仅小写盘符更彻底，且与 `_win_to_linux()` 的盘符小写一致。

`steam_scanner.py:170` 注释警告"WSL 路径不应被 auto-detect 为 Linux"——此逻辑保留。`normalize_path()` 中 WSL 检测依赖 `/mnt/` 前缀，不依赖 `detect_pathstyle()`。

---

## 六、测试断言

### 6.1 `normalize_path()` 单元测试

- Windows 平台：`normalize_path("D:\\Games\\Steam\\steamapps\\")` → `"/mnt/d/games/steam/steamapps/"`
- WSL 检测：`normalize_path("/mnt/c/Program Files (x86)/Steam/")` → `"/mnt/c/program files (x86)/steam/"`
- Linux 平台：`normalize_path("/home/User/.steam/steam/")` → `"/home/User/.steam/steam/"`（保持原样）
- macOS 平台：`normalize_path("/Users/Name/Library/")` → `"/Users/Name/Library/"`（保持原样）
- 幂等：对已归一化的路径再次调用 `normalize_path()` 结果不变

### 6.2 跨来源一致性

- 同一 Steam 库通过 VDF 解析和手动输入分别进入系统 → 归一化后相等
- WSL 下扫描 `/mnt/d/Games/steamapps/` 与用户手动输入 `/mnt/d/games/steamapps/` → 归一化后相等

### 6.3 数据库 CRUD

- `add_manual_steamlib()` 在归一化已做完的前提下，`==` 比较正确识别重复
- `remove_manual_steamlib()` 的 `.startswith()` 匹配正确

---

## 七、实施顺序

| 优先级 | 步骤 | 涉及模块 |
|--------|------|---------|
| **P0** | `paths.py` 新增 `normalize_path()` | `paths.py` |
| **P1** | 入口归一化：扫描器 + 手动输入 + VDF 解析 | `steam_scanner.py`、`bootstrap.py`、`vdf_parser.py` |
| **P2** | 比较点替换：`normalize_posix()` → `normalize_path()`（backup_ops / restore_ops / backup_dir_builder 中的前缀剥除） | `backup_ops.py`、`restore_ops.py`、`backup_dir_builder.py` |
| **P3** | 验证不变式 I1-I4 | 测试套件 |
