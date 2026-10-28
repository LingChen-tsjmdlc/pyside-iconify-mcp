"""服务层：工具已注册、参数模式正确、能经客户端调用。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import TypeVar

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from pyside_iconify_mcp import __version__
from pyside_iconify_mcp.common.iconify_api import IconifyApi
from pyside_iconify_mcp.server import INSTRUCTIONS, main, mcp
from pyside_iconify_mcp.tools import get_reference

T = TypeVar("T")

TOOL_NAMES = {"search_icons", "check_icons", "get_reference", "check_code"}


def run(action: Callable[[Client], Awaitable[T]]) -> T:
    """在内存传输的客户端里执行一个异步操作。"""

    async def inner() -> T:
        async with Client(mcp) as client:
            return await action(client)

    return asyncio.run(inner())


def list_tools() -> list[object]:
    """列出服务端注册的工具。"""

    async def action(client: Client) -> list[object]:
        return list(await client.list_tools())

    return run(action)


def payload(result: object) -> dict[str, object]:
    """取出工具返回的结构化结果。"""
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        inner = structured.get("result")
        return inner if set(structured) == {"result"} and isinstance(inner, dict) else structured
    return json.loads(result.content[0].text)  # type: ignore[attr-defined]


def test_server_identity() -> None:
    """服务名、版本号、使用说明。"""
    assert mcp.name == "pyside-iconify"
    assert mcp.version == __version__
    assert "check_code" in INSTRUCTIONS and "check_icons" in INSTRUCTIONS


def test_exactly_the_four_tools_are_registered() -> None:
    """只注册设计里的四个工具，且都是只读的、带说明。"""
    tools = list_tools()
    assert {tool.name for tool in tools} == TOOL_NAMES  # type: ignore[attr-defined]
    for tool in tools:
        assert tool.description  # type: ignore[attr-defined]
        assert tool.annotations is not None  # type: ignore[attr-defined]
        assert tool.annotations.read_only_hint is True  # type: ignore[attr-defined]


def test_get_reference_topics_match_the_schema() -> None:
    """get_reference 的 topic 枚举与参考文档的主题一致。"""
    tool = next(t for t in list_tools() if t.name == "get_reference")  # type: ignore[attr-defined]
    schema = json.dumps(tool.input_schema)  # type: ignore[attr-defined]
    for key in get_reference.TOPIC_KEYS:
        assert f'"{key}"' in schema


def test_parameters_have_descriptions() -> None:
    """每个工具的每个参数都有说明，AI 才知道怎么填。"""
    for tool in list_tools():
        for name, prop in tool.input_schema["properties"].items():  # type: ignore[attr-defined]
            assert prop.get("description"), f"{tool.name}.{name}"  # type: ignore[attr-defined]


def test_get_reference_through_the_client() -> None:
    """经客户端读取参考文档。"""

    async def action(client: Client) -> object:
        return await client.call_tool("get_reference", {"topic": "pitfalls"})

    text = run(action).content[0].text  # type: ignore[attr-defined]
    assert "Common mistakes" in text


def test_check_code_through_the_client() -> None:
    """经客户端检查代码（离线）。"""
    code = 'from pyside_iconify import get_icon\nget_icon("mdi:home", hover_color="red")\n'

    async def action(client: Client) -> object:
        return await client.call_tool("check_code", {"code": code, "verify_icon_names": False})

    data = payload(run(action))
    assert data["ok"] is False
    assert data["issues"][0]["code"] == "unknown_parameter"  # type: ignore[index]


def test_online_tools_through_the_client(default_api: IconifyApi) -> None:
    """走服务层的联网工具，使用假的 Iconify 服务。"""

    async def action(client: Client) -> tuple[object, object]:
        found = await client.call_tool("search_icons", {"query": "home", "prefix": "mdi"})
        checked = await client.call_tool("check_icons", {"names": ["mdi:home", "mdi:nope"]})
        return found, checked

    found, checked = run(action)
    assert payload(found)["icons"] == ["mdi:home", "mdi:home-outline"]
    assert payload(checked)["summary"] == {"ok": 1, "not_found": 1, "invalid_name": 0, "unavailable": 0}


@pytest.mark.parametrize(
    ("tool", "arguments", "text"),
    [
        ("search_icons", {"query": "  "}, "empty"),
        ("search_icons", {"query": "home", "prefix": "MDI"}, "prefix"),
        ("check_icons", {"names": []}, "empty"),
        ("check_code", {"code": "  "}, "empty"),
    ],
)
def test_input_errors_become_tool_errors(
    default_api: IconifyApi, tool: str, arguments: dict[str, object], text: str
) -> None:
    """调用方的入参错误以工具错误返回，信息写明原因。"""

    async def action(client: Client) -> object:
        return await client.call_tool(tool, arguments)

    with pytest.raises(ToolError, match=text):
        run(action)


def test_entry_point_is_callable() -> None:
    """脚本入口可调用。"""
    assert callable(main)
