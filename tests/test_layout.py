"""目录结构规则：把“一个工具一个同名文件、通用代码放 common、只有 library.py 碰主库”写成检查。

新增工具时如果漏了一步（没加进 TOOLS、文件名与工具名不一致、工具之间互相导入……），
这里会失败并告诉你是哪一步。
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pyside_iconify_mcp
from fastmcp import Client

from pyside_iconify_mcp import tools
from pyside_iconify_mcp.server import mcp

PACKAGE_DIR = Path(pyside_iconify_mcp.__file__).parent
TOOLS_DIR = PACKAGE_DIR / "tools"
COMMON_DIR = PACKAGE_DIR / "common"


def _tool_files() -> list[Path]:
    """tools/ 下的工具文件（不含 __init__.py）；同名的包目录也算一个工具。"""
    files = [p for p in TOOLS_DIR.glob("*.py") if p.name != "__init__.py"]
    packages = [p / "__init__.py" for p in TOOLS_DIR.iterdir() if p.is_dir() and (p / "__init__.py").exists()]
    return sorted([*files, *packages])


def _tool_name(path: Path) -> str:
    return path.parent.name if path.name == "__init__.py" else path.stem


def _imports(path: Path) -> set[str]:
    """文件里导入的全部模块名（绝对路径）。"""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_every_tool_file_is_registered_in_tools() -> None:
    """tools/ 里每个工具文件都在 TOOLS 里，TOOLS 里每个工具都有对应文件。"""
    on_disk = {_tool_name(path) for path in _tool_files()}
    listed = {module.__name__.rsplit(".", 1)[1] for module in tools.TOOLS}
    assert on_disk == listed


def test_each_tool_module_has_the_four_parts() -> None:
    """每个工具模块都有 NAME、DESCRIPTION、run、register，且 NAME 与文件名一致。"""
    for module in tools.TOOLS:
        stem = module.__name__.rsplit(".", 1)[1]
        assert module.NAME == stem, f"{stem}: NAME is {module.NAME!r}"
        assert module.DESCRIPTION.strip(), stem
        assert callable(module.run), stem
        assert callable(module.register), stem


def test_registered_tool_names_match_the_files() -> None:
    """服务上注册出去的工具名，正好就是各工具文件的名字，不多不少。"""

    async def names() -> set[str]:
        async with Client(mcp) as client:
            return {tool.name for tool in await client.list_tools()}

    assert asyncio.run(names()) == {module.NAME for module in tools.TOOLS}


def test_tools_do_not_import_each_other() -> None:
    """工具之间互不导入；要共用的代码放进 common/。"""
    for path in _tool_files():
        imported = {name for name in _imports(path) if name.startswith("pyside_iconify_mcp.tools")}
        assert not imported, f"{path.name} imports other tools: {sorted(imported)}"


def test_common_does_not_import_tools_or_server() -> None:
    """common/ 是底层，不能反过来依赖 tools/ 或 server。"""
    for path in COMMON_DIR.glob("*.py"):
        bad = {
            name
            for name in _imports(path)
            if name.startswith(("pyside_iconify_mcp.tools", "pyside_iconify_mcp.server"))
        }
        assert not bad, f"{path.name} imports {sorted(bad)}"


def test_only_library_py_imports_pyside_iconify() -> None:
    """只有 common/library.py 可以导入主库，其余文件一律通过它。"""
    for path in PACKAGE_DIR.rglob("*.py"):
        if path == COMMON_DIR / "library.py":
            continue
        direct = {name for name in _imports(path) if name == "pyside_iconify" or name.startswith("pyside_iconify.")}
        assert not direct, f"{path.relative_to(PACKAGE_DIR)} imports pyside-iconify directly: {sorted(direct)}"


def test_no_catch_all_modules() -> None:
    """不设 utils / helpers / misc 这类杂物间：每个通用文件都要有明确的名字和职责。"""
    banned = {"utils", "util", "helpers", "helper", "misc", "common_utils", "tools_utils"}
    for path in PACKAGE_DIR.rglob("*.py"):
        assert path.stem not in banned, f"{path.relative_to(PACKAGE_DIR)}: use a name that says what it does"
    for path in PACKAGE_DIR.rglob("*"):
        if path.is_dir():
            assert path.name not in banned, path.relative_to(PACKAGE_DIR)


def test_server_py_has_no_tool_logic() -> None:
    """server.py 只负责创建服务和注册，不定义任何工具。"""
    tree = ast.parse((PACKAGE_DIR / "server.py").read_text(encoding="utf-8"))
    decorated = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.decorator_list
    ]
    assert not decorated, f"tools must be defined in tools/, found: {decorated}"
