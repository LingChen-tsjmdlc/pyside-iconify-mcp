"""search_icons 工具：按关键词搜索真实存在的图标。

每个工具文件都有同样的三块：常量（NAME、DESCRIPTION）、``run``（真正的逻辑，
测试直接调它）、``register``（把工具注册到 FastMCP 服务上）。
"""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from pyside_iconify_mcp.common import library
from pyside_iconify_mcp.common.errors import InputError
from pyside_iconify_mcp.common.iconify_api import (
    STATUS_OK,
    STATUS_UNAVAILABLE,
    ApiError,
    IconifyApi,
    get_api,
)
from pyside_iconify_mcp.common.tool_annotations import ONLINE_READ

NAME = "search_icons"
DESCRIPTION = (
    "Find real icons by keyword (use this instead of guessing an icon name). Returns "
    "'prefix:name' strings that exist in Iconify, plus the icon sets they belong to. A "
    "query with several words must match all of them; narrow with 'prefix' (e.g. 'mdi', "
    "'lucide'). status 'unavailable' means the lookup failed (for example no network), "
    "not that nothing exists."
)

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_QUERY_LENGTH = 100


def run(
    query: str,
    prefix: str | None = None,
    limit: int = DEFAULT_LIMIT,
    *,
    api: IconifyApi | None = None,
) -> dict[str, object]:
    """按关键词搜索真实存在的图标。

    Args:
        query: 关键词；多个词需要同时匹配。
        prefix: 只在某个图标集里找，如 ``mdi``；None 或空串表示全部。
        limit: 最多返回几个，1 到 100。
        api: 客户端；None 时用共享实例。

    Returns:
        可直接序列化的结果字典；网络失败时 status 为 unavailable。

    Raises:
        InputError: 入参不合法。
    """
    text = " ".join(query.split())
    if not text:
        raise InputError("query must not be empty")
    if len(text) > MAX_QUERY_LENGTH:
        raise InputError(f"query is too long (at most {MAX_QUERY_LENGTH} characters)")
    if not 1 <= limit <= MAX_LIMIT:
        raise InputError(f"limit must be between 1 and {MAX_LIMIT}")
    scope = prefix.strip() if prefix else None
    if scope and not library.is_valid_prefix(scope):
        raise InputError(
            f"invalid icon set prefix {prefix!r}: use lowercase letters, digits and hyphens, e.g. 'mdi'"
        )
    scope = scope or None
    try:
        result = (api or get_api()).search(text, prefix=scope, limit=limit)
    except ApiError as error:
        return {"status": STATUS_UNAVAILABLE, "query": text, "reason": error.describe()}
    payload: dict[str, object] = {
        "status": STATUS_OK,
        "query": text,
        "count": len(result.icons),
        "icons": list(result.icons),
        "collections": {
            key: {"name": info.name, "license": info.license, "total": info.total}
            for key, info in result.collections.items()
        },
    }
    if scope:
        payload["prefix"] = scope
    if not result.icons:
        payload["hint"] = (
            "No matches. A query with several words must match all of them; "
            "try fewer or shorter words."
        )
    elif len(result.icons) >= limit:
        payload["hint"] = "The list may be truncated; narrow it with 'prefix' or a more specific query."
    payload["next"] = "Use check_icons to see whether an icon is multi-color or animated."
    return payload


def register(mcp: FastMCP) -> None:
    """把本工具注册到服务上。

    Args:
        mcp: FastMCP 服务实例。
    """

    @mcp.tool(name=NAME, description=DESCRIPTION, annotations=ONLINE_READ)
    def search_icons(
        query: Annotated[str, Field(description="Keywords, e.g. 'arrow left'. At most 100 characters.")],
        prefix: Annotated[
            str | None,
            Field(description="Only search this icon set, e.g. 'mdi'. Omit to search all sets."),
        ] = None,
        limit: Annotated[
            int, Field(description="Maximum number of icons to return (1-100).")
        ] = DEFAULT_LIMIT,
    ) -> dict[str, object]:
        """按关键词搜索真实存在的图标。"""
        try:
            return run(query, prefix, limit)
        except InputError as error:
            raise ToolError(str(error)) from error
