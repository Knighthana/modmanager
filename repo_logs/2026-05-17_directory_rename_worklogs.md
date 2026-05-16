# 2026-05-17 工作日志 — 目录迁移对齐

> 项目目录 `modmanager_cli` → `modmanager` 重命名后的对齐工作

## 必须执行

- 删除旧 egg-info `src/modmanager_cli.egg-info/`
- 重建 `.venv`：删除旧虚拟环境，重新创建并安装 `.[web]` 全套依赖
  - 因系统缺少 `python3.12-venv`（`ensurepip` 不可用），采用 `--without-pip` + 系统 pip3 `--target` 引导 PyPI 原版 pip

## 文本引用清理

- `tools/generate_fixture.py`：docstring 与 description 中 `modmanager_cli` → `modmanager`（2 处）
- `repo_spec/mapping_output.schema.json`：description 中 `modmanager_cli.engine` → `modmanager.engine`
- `description/user_config.json.example`：3 处路径 `modmanager_cli/` → `modmanager/`（笔记中遗漏，本次补充）
