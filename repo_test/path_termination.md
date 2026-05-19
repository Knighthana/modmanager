# 路径结尾方式规定

> Status: normative
> Authority: non-negotiable
> Purpose: 规定文件路径与目录路径的结尾方式，作为测试强制断言依据
> Based on: `repo_memo/DESIGN_ENGINE_INVARIANTS.md` §1

---

## 一、硬性规定

| 路径类型 | 结尾方式 | 违规行为 |
|---------|---------|---------|
| 目录路径 | **必须以 `/` 结尾** | 拒绝处理（`ValueError`） |
| 文件路径 | **不得以 `/` 结尾** | 拒绝处理（`ValueError`） |

此规定适用于 `engine.py`、`backup_ops.py`、`backup_dir_builder.py` 等所有核心模块的输入输出。

## 二、测试要求

### 2.1 目录目标测试

当 `into_type == "dir"` 时，`final_mapping` 中的 `path` 字段**必须以 `/` 结尾**：

```python
targets = {entry["path"] for entry in result["final_mapping"]}
# 目录目标必须尾 /
assert any(path.endswith("/maps/src1/") for path in targets)
```

### 2.2 文件目标测试

当 `into_type == "file"` 或 `from_type == "file"` 时，最终 `path` **不得以 `/` 结尾**：

```python
# 文件目标不得尾 /
assert any(path.endswith("/dest/root.txt") and not path.endswith("/dest/root.txt/") 
           for path in targets)
```

### 2.3 门禁测试

核心模块入口应对违规路径抛出 `ValueError`：

```python
# 非法：目录路径不带 /
with pytest.raises(ValueError):
    some_function("/path/to/dir_without_slash")

# 非法：文件路径带 /
with pytest.raises(ValueError):
    some_function("/path/to/file.txt/")
```

## 三、已知漏洞

`Path()` 拼接会吞尾 `/`。所有使用 `Path()` / `str(Path())` 拼接目标路径的地方，必须在拼接后从原始 `into_expr` 恢复尾 `/`。测试必须覆盖此类场景。
