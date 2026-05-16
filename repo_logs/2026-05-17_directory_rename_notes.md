# 目录重命名注意事项

> 将项目目录从 `modmanager_cli` 重命名为 `modmanager` 后的操作清单。

## 必须执行

### 1. 重建 .venv

虚拟环境内大量绝对路径引用了旧目录名，重命名后 .venv 完全失效。

```bash
# 在重命名后的新目录中执行
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[web]"
```

### 2. 清理旧 egg-info

`src/modmanager_cli.egg-info/` 是旧包名的残留，应删除：

```bash
rm -rf src/modmanager_cli.egg-info
```

`src/modmanager.egg-info/` 是新的，保留即可（重建 venv 后 pip install -e 会重新生成）。

## 建议处理

### 3. 更新文本引用

以下文件中仍有 `modmanager_cli` 字样，属于描述性文本，不影响功能运行：

| 文件 | 位置 | 内容 |
|---|---|---|
| `tools/generate_fixture.py` | 第3行 docstring、第414行 description | `modmanager_cli 测试 Fixture 生成器` |
| `repo_spec/mapping_output.schema.json` | 第4行 description | `Schema for the dict returned by modmanager_cli.engine...` |

`repo_logs/2026-04-30.md` 中记录了历史上 `src/modmanager_cli/ → src/modmanager/` 的改名操作，属于归档日志，无需修改。

## 无需处理

| 组件 | 原因 |
|---|---|
| `fnm` / `.node-version` | `.node-version` 仅含版本号 `24`，与目录名无关 |
| `node_modules/` | 无任何对目录名的硬编码引用 |
| `frontend/package.json` | 项目名为 `modmanager-frontend`，与目录名无关 |
| Git | 无 remote，本地改名不影响远程 |
| `.vscode/` | 无硬编码路径 |
| `pyproject.toml` | `[project] name` 已为 `modmanager`，入口命令为 `modmanager-cli` |
