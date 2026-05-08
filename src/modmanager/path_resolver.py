"""path_resolver.py — 用户输入路径的"猜测"统一入口。

所有对用户不规范路径输入的推测和补全集中于此模块。
模块产出后即为规范格式，下游只做合规性断言，禁止再猜测。

下游门禁约定：
- 目录路径：必须以 / 结尾。核心模块（engine、backup_ops 等）应断言此条件。
- 文件路径：不得以 / 结尾。
- 任何模块禁止再做路径"猜测"或"补全"。只做合规性断言。
"""

import os
from pathlib import Path

from .paths import normalize_posix


def _expand_path(input_str: str) -> str:
    """Expand ~ and $HOME/%appdata% to absolute paths."""
    expanded = os.path.expanduser(input_str)
    expanded = os.path.expandvars(expanded)
    return expanded


def _fully_normalize(path: str) -> str:
    """对 input_str 做完整规范化：风格转换 + 冗余分隔符 + . / .. 解析。

    顺序：
      1. normalize_posix — 转换为 POSIX 风格并折叠冗余 /
      2. os.path.normpath — 解析 . 和 .. 组件
    """
    return os.path.normpath(normalize_posix(path))


def resolve_directory_path(input_str: str, dirname: str) -> str:
    """解析用户输入的目录路径，返回规范化绝对路径（以 / 结尾）。

    Args:
        input_str: 用户输入的原始路径字符串
        dirname: 期望的子目录名称（不含尾部 /），如 'steamapps'

    Returns:
        以 / 结尾的规范化目录路径

    Raises:
        FileNotFoundError: 所有试探完成后无结果
        NotADirectoryError: 路径存在但不是目录
    """
    if not input_str:
        raise ValueError("input_str 不能为空字符串")

    input_str = _expand_path(input_str)
    normalized = _fully_normalize(input_str).rstrip('/')

    # 情况 1 & 2: input 以 dirname 结尾（含或不含 /）
    if normalized.endswith(f'/{dirname}'):
        # 试: /path/to/dirname/
        direct = normalized + '/'
        if Path(direct).is_dir():
            return direct
        # 试: /path/to/dirname/dirname/
        nested = normalized + f'/{dirname}/'
        if Path(nested).is_dir():
            return nested

        # 如果路径本身存在但不是目录，报告明确错误
        p = Path(normalized)
        if p.exists() and not p.is_dir():
            raise NotADirectoryError(
                f"路径存在但不是目录：'{normalized}'"
            )
        raise FileNotFoundError(
            f"目录解析失败：'{input_str}' → 尝试了 '{direct}' 和 '{nested}'，均不存在"
        )

    # 情况 3: input 是父目录
    candidate = normalized + f'/{dirname}/'
    if Path(candidate).is_dir():
        return candidate

    # 如果 input 本身存在但不是目录
    p = Path(normalized)
    if p.exists() and not p.is_dir():
        raise NotADirectoryError(
            f"路径存在但不是目录：'{normalized}'"
        )
    raise FileNotFoundError(
        f"目录解析失败：'{input_str}' → '{candidate}' 不存在"
    )


def resolve_file_path(input_str: str, filename: str) -> str:
    """解析用户输入的文件路径，返回规范化绝对路径（不以 / 结尾）。

    Args:
        input_str: 用户输入的原始路径字符串
        filename: 期望的文件名，如 'database.json'

    Returns:
        规范化文件路径（不以 / 结尾）

    Raises:
        FileNotFoundError: 所有试探完成后无结果
        IsADirectoryError: 目标存在但是目录而非文件
    """
    if not input_str:
        raise ValueError("input_str 不能为空字符串")

    input_str = _expand_path(input_str)
    normalized = _fully_normalize(input_str)

    # 以 / 结尾 → 一定是目录 → 在目录下找文件
    if normalized.endswith('/'):
        candidate = normalized + filename
        if Path(candidate).is_file():
            return candidate
        raise FileNotFoundError(
            f"文件解析失败：'{input_str}' 是目录，但其中没有 '{filename}'"
        )

    # 不以 / 结尾 → 可能是文件，也可能是目录
    p = Path(normalized)
    if p.is_file():
        return normalized
    if p.is_dir():
        candidate = normalized.rstrip('/') + f'/{filename}'
        if Path(candidate).is_file():
            return candidate
        raise FileNotFoundError(
            f"文件解析失败：'{input_str}' 是目录，但其中没有 '{filename}'"
        )

    raise FileNotFoundError(
        f"文件解析失败：'{input_str}' 不存在（不是文件，也不是目录）"
    )


# ── 下游门禁断言 ────────────────────────────────────────────────────────────
#
# 以下函数用于 engine / backup_ops 等下游模块入口处的合规性检查。
# 违规时直接 raise ValueError，不做静默修补。


def assert_directory_path(path: str, label: str = "path") -> None:
    """断言 *path* 是目录路径（以 ``/`` 结尾），否则 raise ValueError。

    Args:
        path: 待检查的路径字符串
        label: 出错时用于标识路径来源的描述标签

    Raises:
        ValueError: 当路径不以 ``/`` 结尾时
    """
    if not path.endswith('/'):
        raise ValueError(
            f"E_PATH_GATE_DIR: {label}={path!r} must end with '/' "
            f"(directory path convention violated)"
        )


def assert_file_path(path: str, label: str = "path") -> None:
    """断言 *path* 是文件路径（不以 ``/`` 结尾），否则 raise ValueError。

    Args:
        path: 待检查的路径字符串
        label: 出错时用于标识路径来源的描述标签

    Raises:
        ValueError: 当路径以 ``/`` 结尾时
    """
    if path.endswith('/'):
        raise ValueError(
            f"E_PATH_GATE_FILE: {label}={path!r} must NOT end with '/' "
            f"(file path convention violated)"
        )


__all__ = [
    "resolve_directory_path",
    "resolve_file_path",
    "assert_directory_path",
    "assert_file_path",
]
