"""所有工具。每个工具一个同名文件，文件名就是工具名。

新增工具的步骤：
1. 在本目录新建 ``<工具名>.py``，写 ``NAME``、``DESCRIPTION``、``run``、``register`` 四样；
2. 在下面的 ``TOOLS`` 里加上它。

tests/test_server.py 会检查：目录里每个工具文件都在 ``TOOLS`` 里，
每个模块的 ``NAME`` 与文件名一致，且注册出去的工具名与 ``NAME`` 一致。
只有一个工具用的代码写在它自己的文件里；多个工具共用的放 ``common/``。
单个工具文件长到难读时，可以把它升级成同名的包（``<工具名>/__init__.py``），导入路径不变。
"""

from types import ModuleType

from fastmcp import FastMCP

from pyside_iconify_mcp.tools import check_code, check_icons, get_reference, search_icons

TOOLS: tuple[ModuleType, ...] = (get_reference, search_icons, check_icons, check_code)


def register_all(mcp: FastMCP) -> None:
    """把全部工具注册到服务上。

    Args:
        mcp: FastMCP 服务实例。
    """
    for tool in TOOLS:
        tool.register(mcp)
