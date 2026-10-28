"""FastMCP 服务：创建服务实例并注册 tools/ 下的全部工具，本文件不含工具逻辑。"""

from fastmcp import FastMCP

from pyside_iconify_mcp import __version__
from pyside_iconify_mcp.tools import register_all

INSTRUCTIONS = (
    "Use this server whenever you write Python code that uses pyside-iconify (QIcon icons from "
    "Iconify by name, e.g. 'mdi:home'). Before writing: call get_reference (start with topic "
    "'overview'). Never invent icon names: find them with search_icons and verify every name "
    "with check_icons. After writing: pass the finished code to check_code and fix every error "
    "it reports. Not affiliated with the Iconify project."
)

mcp = FastMCP("pyside-iconify", instructions=INSTRUCTIONS, version=__version__)
register_all(mcp)


def main() -> None:
    """以 stdio 传输启动服务；AI 客户端通过配置的命令拉起本进程。"""
    mcp.run()


if __name__ == "__main__":
    main()
