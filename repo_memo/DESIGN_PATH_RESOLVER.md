# DESIGN_PATH_RESOLVER — 通用路径解析模块

> Status: stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 路径规范化模块设计；所有路径猜测集中于此，下游只做合规性校验

> 来源：2026-05-07 用户讨论 — DataSource 手动路径、Database JSON、User config 等多处需要路径猜测  
> 原则：所有"猜测"集中于此模块；产出后的路径为规范值，下游只做合规性校验
> 更新：2026-05-14 — 【§十二补充裁定】补充 `expand_path` 函数文档、`~`/`$HOME` 展开规则、存储时保留原始输入、目录末尾 `/` 补齐职责边界

---

## 1. 动机

用户输入路径时写法不规范：

- 目录路径可能忘写 `/`，也可能多写了 `steamapps` 层级
- 文件路径可能写的是文件本身、也可能写的是所在目录
- 如果每个调用方各自猜测，逻辑分散且容易不一致

所有"猜测用户意图"的代码集中到一个模块。模块产出即为规范格式，下游不再猜测。

---

## 2. 接口

```python
# src/modmanager/path_resolver.py

def resolve_directory_path(input_str: str, dirname: str) -> str:
    """解析用户输入的目录路径，返回规范化绝对路径（以 / 结尾）。

    Args:
        input_str: 用户输入的原始字符串
        dirname: 期望的子目录名称，例如 'steamapps'、'workshop'

    Returns:
        以 / 结尾的规范化路径

    Raises:
        FileNotFoundError: 所有试探完毕后无结果
    """

def resolve_file_path(input_str: str, filename: str) -> str:
    """解析用户输入的文件路径，返回规范化绝对路径（不以 / 结尾）。

    Args:
        input_str: 用户输入的原始字符串
        filename: 期望的文件名，例如 'database.json'、'user_config.json'

    Returns:
        不以 / 结尾的规范化文件路径

    Raises:
        FileNotFoundError: 所有试探完毕后无结果
        IsADirectoryError: 目标存在但是目录而非文件
    """
```

### 2.1 `expand_path` 展开函数

```python
def expand_path(path: str) -> str:
    """展开路径中的 ~、$HOME（Linux）和 %APPDATA%（Windows）等环境变量。
    
    内部使用 os.path.expanduser（展开 ~）和 os.path.expandvars（展开 $VAR / %VAR%）。
    返回展开后的绝对路径，不修改持久化存储。

    Args:
        path: 用户输入的原始路径（可能含 ~、$HOME、%APPDATA% 等）

    Returns:
        展开后的绝对路径字符串

    Note:
        存储时保留用户原始输入（含 ~），计算时通过 expand_path 展开。
        path_resolver 只读不写用户设置。
    """
```

调用方示例：

```python
# DataSource 手动路径
steamapps_path = resolve_directory_path(user_input, 'steamapps')

# Database 路径
db_path = resolve_file_path(user_input, 'database.json')

# User config 路径
config_path = resolve_file_path(user_input, 'user_config.json')
```

---

## 3. 解析算法

### 3.1 `resolve_directory_path(input_str, dirname)`

`input_str` 先规范化（`normalize_posix` + `rstrip('/')`）。

所有路径在解析前先调用 `_expand_path()` 展开 `~`、`$HOME`（Linux）和 `%appdata%` 等环境变量（Windows）。

| input_str 规范化后 | 试探顺序 |
|-------------------|---------|
| `/path/to/<dirname>` | ① `/path/to/<dirname>/` 是否存在 → 存在则返回<br>② `/path/to/<dirname>/<dirname>/` 是否存在 → 存在则返回<br>③ 报错 |
| `/path/to/<dirname>/` | 同①→② |
| `/path/to` | ① `/path/to/<dirname>/` 是否存在 → 存在则返回<br>② 报错 |

**`<dirname>` 不含尾部 `/`**。规范化后末尾不带 `/` 的路径统一 append 一次 `/` 再做存在性检查。

### 3.2 `resolve_file_path(input_str, filename)`

| input_str 特征 | 试探顺序 |
|---------------|---------|
| 以 `/` 结尾 | ① 该目录下 `<filename>` 是否存在 → 存在则返回<br>② 报错 |
| 不以 `/` 结尾 | ① 该路径是否为存在的文件 → 是则返回<br>② 该路径是否为存在的目录 → 是则在目录下找 `<filename>` → 存在则返回<br>③ 报错 |

---

## 4. 下游门禁约定

`path_resolver` 产出后，下游路径必须遵守：

| 路径类型 | 规则 | 校验位置 |
|---------|------|---------|
| 目录路径 | **必须以 `/` 结尾** | engine、backup_ops 等核心模块入口 |
| 文件路径 | **不得以 `/` 结尾** | engine、backup_ops 等核心模块入口 |

如果下游收到不符合规范的路径，**直接报错**（断言式），明确指出违规位置，方便溯源。

任何模块（engine、backup_ops、bootstrap、scanner 等）都**禁止**再做路径"猜测"或"补全"。只做合规性断言。

---

## 5. 验收

- Python 全量测试不破坏
- 新增 `tests/test_path_resolver.py`，覆盖：
  - `resolve_directory_path` 三路径格式 × 成功/失败
  - `resolve_file_path` 文件/目录/末尾带 `/` × 成功/失败
  - 不存在路径报错
  - 规范化（`..` 支持、冗余 `/` 去除等）

---

## 6. 路径展开与持久化规则（§十二补充裁定）

### 6.1 `expand_path` 展开的变量枚举

| 符号 | 展开方式 | 示例（Linux） | 示例（Windows） |
|------|---------|--------------|----------------|
| `~` | `os.path.expanduser` | `~/.config/kmm` → `/home/user/.config/kmm` | `~\AppData\Roaming` → `C:\Users\user\AppData\Roaming` |
| `$HOME` | `os.path.expandvars` | `$HOME/.config/kmm` → `/home/user/.config/kmm` | 不适用（Windows 用 `%USERPROFILE%`） |
| `%APPDATA%` | `os.path.expandvars` | 不适用 | `%APPDATA%/kmm` → `C:\Users\user\AppData\Roaming\kmm` |

### 6.2 使用规则

1. **凡是来自用户直接输入的路径，必须经过 `path_resolver` 模块处理**。各端点统一用 `from modmanager.path_resolver import expand_path`。
2. **存储时保留用户原始输入（含 `~`），计算时通过 `expand_path` 展开。** path_resolver 只读不写用户设置。
3. **目录末尾 `/` 的补齐发生在 `_normalize_rule_sources`（保存时），不在 path_resolver；** path_resolver 永远不修改持久化存储。

### 6.3 职责边界

| 行为 | 归属模块 | 说明 |
|------|---------|------|
| `~`、`$HOME`、`%APPDATA%` 展开 | `path_resolver.expand_path` | 纯计算，不写存储 |
| 路径存在性校验 | `path_resolver.resolve_directory_path` / `resolve_file_path` | 读类入口使用 |
| 目录末尾 `/` 补齐 | `_normalize_rule_sources`（路由层保存时） | 修改持久化存储（user_config.rule_sources） |
| 路径存储 | 调用方（路由/bootstrap） | 存原始用户输入，不调 path_resolver 修改 |

## 7. 决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | 模块位置 | `src/modmanager/path_resolver.py`，核心模块，独立于 Web/CLI |
| D2 | 接口参数化 | 调用方传入 `dirname`/`filename`，模块不与业务含义耦合 |
| D3 | 下游门禁 | 目录路径必须以 `/` 结尾；文件路径不得以 `/` 结尾；违规即报错 |
| D4 | 猜测集中 | 所有路径"推测"逻辑仅在 `path_resolver`；其他模块禁止补全/猜测 |
