"""提交文件本地校验脚本。

功能概述：检查 `team_controller.py` 是否满足基础接口和明显禁用能力要求。
输入输出：输入待提交 Python 文件路径，输出校验结果和进程退出码。
处理流程：解析 AST 检查导入和敏感名字，加载模块，用 mock 图像调用 `control()`。
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
from pathlib import Path

import numpy as np

BANNED_MODULES = {
    "os",
    "sys",
    "socket",
    "subprocess",
    "multiprocessing",
    "threading",
    "time",
    "datetime",
    "io",
    "builtins",
    "ctypes",
    "shutil",
    "tempfile",
    "requests",
    "urllib",
    "http",
    "ftplib",
    "smtplib",
    "signal",
    "gc",
    "inspect",
    "importlib",
    "pickle",
    "glob",
    "fnmatch",
}
BANNED_NAMES = {
    "open",
    "eval",
    "exec",
    "compile",
    "globals",
    "locals",
    "input",
    "breakpoint",
    "__import__",
    "vars",
}


def check_ast(source, path):
    """检查源码中的禁止导入和禁止名字。

    功能：提前拦住平台明显不允许的能力。
    参数：`source` 是源码文本，`path` 是文件路径。
    返回：错误字符串列表。
    逻辑：用 AST 遍历导入语句和名字引用，避免简单字符串扫描造成大量误报。
    """

    errors = []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"语法错误: {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                if root_name in BANNED_MODULES:
                    errors.append(f"禁止导入模块: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root_name = (node.module or "").split(".")[0]
            if root_name in BANNED_MODULES:
                errors.append(f"禁止从模块导入: {node.module}")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            errors.append(f"禁止使用名字: {node.id}")
    return errors


def load_submission(path):
    """加载待提交模块。

    功能：像平台一样导入单个 Python 文件。
    参数：`path` 是待校验文件路径。
    返回：已加载模块对象。
    逻辑：通过 `importlib` 按路径加载，避免要求文件位于 Python 包内。
    """

    spec = importlib.util.spec_from_file_location("team_controller_candidate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载文件: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_runtime(module):
    """用 mock 图像检查 `control()` 运行结果。

    功能：确认入口存在、可调用，并返回合法范围内的两个数。
    参数：`module` 是待提交模块。
    返回：错误字符串列表。
    逻辑：构造左右 480x640 BGR 图像，调用一次 `control()` 并检查类型和范围。
    """

    if not hasattr(module, "control") or not callable(module.control):
        return ["缺少可调用的 control(left_img, right_img, timestamp)"]

    left_img = np.zeros((480, 640, 3), dtype=np.uint8)
    right_img = np.zeros((480, 640, 3), dtype=np.uint8)
    result = module.control(left_img, right_img, 0.0)

    if not isinstance(result, tuple) or len(result) != 2:
        return ["control() 必须返回二元组"]

    steering, speed = result
    errors = []
    if not isinstance(steering, (int, float, np.floating)):
        errors.append("steering 必须是数值")
    elif not -1.0 <= float(steering) <= 1.0:
        errors.append(f"steering 越界: {steering}")

    if not isinstance(speed, (int, float, np.floating)):
        errors.append("speed 必须是数值")
    elif not 0.0 <= float(speed) <= 1.0:
        errors.append(f"speed 越界: {speed}")

    return errors


def parse_args():
    """解析命令行参数。

    功能：读取待校验文件路径。
    参数：无。
    返回：`argparse.Namespace`。
    逻辑：只接受一个位置参数，保持用法简单。
    """

    parser = argparse.ArgumentParser(description="Validate an AI Racer team_controller.py file.")
    parser.add_argument("path", type=Path)
    return parser.parse_args()


def main():
    """脚本入口。

    功能：执行静态和运行时两类校验。
    参数：来自命令行。
    返回：成功为 0，失败为 1。
    逻辑：先检查文件和 AST，再加载模块做 mock 调用，最后输出摘要。
    """

    args = parse_args()
    path = args.path.resolve()
    if not path.exists():
        print(f"文件不存在: {path}")
        return 1

    source = path.read_text(encoding="utf-8")
    errors = check_ast(source, path)
    if not errors:
        try:
            errors.extend(check_runtime(load_submission(path)))
        except Exception as exc:
            errors.append(f"运行时错误: {exc}")

    if errors:
        print("校验失败:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"校验通过: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
