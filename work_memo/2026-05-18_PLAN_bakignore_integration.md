# PLAN — bakignore 规则接入引擎

> Last-Updated: 2026-05-18

## 目标

将 bakignore 规则（user_config + .kmmbakignore + 硬编码后缀）接入 `backup()` / `apply()` 引擎流程，使 `load_bakignore_rules` 从死代码变为活代码。

## 规则分层

| 层 | 来源 | 粒度 | 用途 |
|----|------|------|------|
| 硬编码底线 | `_HARDCODED_BACKUP_SKIP_SUFFIX = ".kmmbackup"` | 目录名 | 引擎内部始终生效，防循环备份 |
| user_config | `user_config.bakignore`（list[str]） | 目录名后缀 | 用户自定义的额外忽略后缀 |
| .kmmbakignore | 各 contentid 源目录下的 `.kmmbakignore` 文件 | gitignore 模式 | 文件级灵活忽略 |

## 实现

### 1. `.kmmbakignore` 级联解析

拟合 git 行为：从文件所在目录往上走到 contentid 根目录，
每层 `.kmmbakignore` 都参与判定。子目录规则优先级高于父目录。
每文件只解析一次，结果缓存。

```python
_ignore_cache: dict[str, callable] = {}

def _should_ignore(file_abs: str, contentid_root: str, dir_suffixes: list[str]) -> bool:
    """判定 file_abs 是否应被忽略。

    1. 目录级检查：路径任意组件以 dir_suffixes 中任一后缀结尾 → 忽略
    2. gitignore 级联：从文件目录向上走到 contentid_root，
       每层 .kmmbakignore 用 gitignore-parser 解析并缓存。
       子目录规则覆盖父目录（git 语义：后匹配优先）。
    """
    # 目录级
    if _any_path_component_ends_with(file_abs, dir_suffixes):
        return True

    # gitignore 级联
    file_path = Path(file_abs)
    current = file_path.parent
    content_root_path = Path(contentid_root)
    matched = False
    while current != content_root_path.parent and current != current.parent:  # 到根为止
        ig = current / ".kmmbakignore"
        if ig.is_file():
            rules = _ignore_cache.get(str(ig))
            if rules is None:
                rules = _parse_gitignore_file(str(ig))
                _ignore_cache[str(ig)] = rules
            rel = str(file_path.relative_to(current))
            if rules(rel):
                matched = True
            elif rules(rel) is False:  # ! 否定
                matched = False
        current = current.parent

    return matched

def _parse_gitignore_file(path: str):
    """用 gitignore-parser 解析 .kmmbakignore，返回判定函数。"""
    import gitignore_parser
    return gitignore_parser.parse_gitignore_file(path)
```

### 2. `load_bakignore_rules` 重写

简化为只产出目录级后缀列表（硬编码 + user_config），文件级规则由级联函数实时判定：

```python
def load_dir_suffixes(user_config: dict) -> list[str]:
    """合并硬编码底线 + user_config.bakignore，去重。"""
    suffixes = [".kmmbackup"]
    config_ignore = user_config.get("bakignore")
    if isinstance(config_ignore, list):
        for item in config_ignore:
            if isinstance(item, str) and item.strip():
                s = item.strip()
                if not s.startswith("."):
                    s = "." + s
                if s not in suffixes:
                    suffixes.append(s)
    return suffixes
```

### 3. `backup()` 集成

在遍历 `backup_dirs` 的内部循环中：

```python
for backup_dir_str, files in backup_dirs.items():
    source_dir = _derive_source_dir(backup_dir_str)  # 从 backup_dir 反推源 contentid 根
    dir_suffixes = load_dir_suffixes(user_config)

    # 过滤 + 拷贝 .kmmbakignore
    filtered_files = []
    copied_ignores = set()
    for f in files:
        if _should_ignore(f, source_dir, dir_suffixes):
            continue
        filtered_files.append(f)
        # 拷贝沿途各级 .kmmbakignore 进 backup_dir（同一文件只拷一次）
        _copy_kmmbakignore_chain(f, source_dir, backup_dir_str, copied_ignores)

    run_differential_backup(backup_dir_str, filtered_files, ...)
```

`_copy_kmmbakignore_chain`：从文件所在目录往上走到 contentid 根，每层的 `.kmmbakignore` 都拷贝进 backup_dir 对应位置。

### 4. `apply()` 集成

apply 完成后，从 backup_dir 把各级 `.kmmbakignore` 覆盖回源目录：

```python
# 扫描 backup_dir 中所有 .kmmbakignore，反向拷贝
for ig_path in Path(backup_dir_str).rglob(".kmmbakignore"):
    rel = ig_path.relative_to(backup_dir_str)
    dest = Path(source_dir) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(ig_path), str(dest))
```

apply 不做 bakignore 过滤——只关心 final_mapping 中的文件。

## 涉及文件

| 文件 | 改动 |
|------|------|
| `orchestrator.py` | 新增 `_should_ignore`（git 级联 + 缓存）、`_parse_gitignore_file`、`_copy_kmmbakignore_chain`、`_any_path_component_ends_with`；`backup()` 加入过滤 + .kmmbakignore 链式拷贝；`apply()` 加入反向拷贝 |
| `backup_dir_builder.py` | `load_bakignore_rules` 重写为 `load_dir_suffixes`（仅产出后缀列表，供 `_should_ignore` 使用） |
| `DESIGN_BACKUP.md` §5 | 更新循环备份防护，描述三层规则 + git 级联 + 拷贝逻辑 |
| `backup_ops.py` | 无改动（硬编码后缀已正确） |
| `DESIGN_BACKUP.md` | 更新 §5 循环备份防护，描述三层规则 |
| `DESIGN_ORCHESTRATOR.md` | 更新 backup()/apply() 描述，提及 bakignore 集成 |

## 实施顺序

1. 施工文档（本文）
2. `DESIGN_BACKUP.md` §5 更新
3. `DESIGN_ORCHESTRATOR.md` 更新
4. `backup_dir_builder.py` — 重写 `load_bakignore_rules`
5. `orchestrator.py` — `backup()` 加过滤；`apply()` 加 .kmmbakignore 拷出
6. 验证导入 + 编译
7. 提交
