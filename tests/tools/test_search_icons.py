"""search_icons：入参校验、输出结构、联网失败的处理。"""

from __future__ import annotations

import pytest

from pyside_iconify_mcp.common.errors import InputError
from pyside_iconify_mcp.common.iconify_api import ApiError, IconifyApi
from pyside_iconify_mcp.tools import search_icons
from tests.fakes import FakeIconify


def test_search_returns_icons_and_collections(api: IconifyApi) -> None:
    """搜索结果含图标名和图标集概况。"""
    result = search_icons.run("home", api=api)
    assert result["status"] == "ok"
    assert result["icons"] == ["mdi:home", "mdi:home-outline", "lucide:home"]
    assert result["count"] == 3
    collections = result["collections"]
    assert isinstance(collections, dict) and set(collections) == {"mdi", "lucide"}
    assert "hint" not in result


def test_search_with_prefix_and_limit(api: IconifyApi) -> None:
    """限定图标集并限制数量；刚好达到数量上限时提示可能被截断。"""
    result = search_icons.run("home", "mdi", 2, api=api)
    assert result["icons"] == ["mdi:home", "mdi:home-outline"]
    assert result["prefix"] == "mdi"
    assert "truncated" in str(result["hint"])


def test_search_without_matches_hints(api: IconifyApi) -> None:
    """没搜到：status 仍是 ok，并给出提示。"""
    result = search_icons.run("zzzz", api=api)
    assert result["status"] == "ok"
    assert result["icons"] == []
    assert "No matches" in str(result["hint"])


def test_search_failure_is_unavailable(api: IconifyApi, fake: FakeIconify) -> None:
    """联网失败是 unavailable，不返回 icons。"""
    fake.fail = ApiError("network", "cannot reach the Iconify API: boom")
    result = search_icons.run("home", api=api)
    assert result["status"] == "unavailable"
    assert "icons" not in result
    assert "network" in str(result["reason"])


def test_search_collapses_whitespace(api: IconifyApi, fake: FakeIconify) -> None:
    """多余空白被合并。"""
    search_icons.run("  home   outline ", api=api)
    assert "query=home+outline" in fake.urls[0]


@pytest.mark.parametrize(
    ("kwargs", "text"),
    [
        ({"query": "   "}, "empty"),
        ({"query": "x" * 101}, "too long"),
        ({"query": "home", "prefix": "MDI"}, "invalid icon set prefix"),
        ({"query": "home", "limit": 0}, "limit"),
        ({"query": "home", "limit": 101}, "limit"),
    ],
)
def test_search_rejects_bad_input(api: IconifyApi, kwargs: dict[str, object], text: str) -> None:
    """不合法的入参抛 InputError，不发请求。"""
    with pytest.raises(InputError, match=text):
        search_icons.run(api=api, **kwargs)  # type: ignore[arg-type]


def test_empty_prefix_means_all_sets(api: IconifyApi, fake: FakeIconify) -> None:
    """空字符串的 prefix 等同于不限定。"""
    search_icons.run("home", "", api=api)
    assert "prefix" not in fake.urls[0]
