"""common/lookup.py：批量核对与相近图标建议（check_icons、check_code 共用）。"""

from __future__ import annotations

from pyside_iconify_mcp.common import lookup
from pyside_iconify_mcp.common.iconify_api import ApiError, IconifyApi
from tests.fakes import FakeIconify


def test_suggests_similar_icons_by_shortening_the_name(api: IconifyApi, fake: FakeIconify) -> None:
    """完整名字搜不到就去掉末尾的词再搜（官方搜索要求所有词同时匹配）。"""
    found = lookup.lookup_names(["mdi:home-filled"], api, suggest=True)
    assert found["mdi:home-filled"].suggestions == ("mdi:home", "mdi:home-outline")
    assert any("query=home+filled" in url for url in fake.urls)
    assert any("query=home&" in url for url in fake.urls)


def test_suggestions_never_include_the_missing_name_itself(api: IconifyApi) -> None:
    """建议里不会出现被核对的名字本身。"""
    found = lookup.lookup_names(["mdi:home-nope"], api, suggest=True)
    assert "mdi:home-nope" not in found["mdi:home-nope"].suggestions


def test_missing_icon_set_searches_all_sets(api: IconifyApi, fake: FakeIconify) -> None:
    """图标集不存在时，建议不限定图标集。"""
    lookup.lookup_names(["nosuchset:home"], api, suggest=True)
    search_urls = [url for url in fake.urls if "/search" in url]
    assert search_urls and all("prefix=" not in url for url in search_urls)


def test_suggestion_budget_is_bounded(api: IconifyApi, fake: FakeIconify) -> None:
    """对官方搜索接口的请求数有上限，不会随不存在的名字线性增长。"""
    names = [f"mdi:missing-thing-{index}" for index in range(10)]
    lookup.lookup_names(names, api, suggest=True)
    searches = [url for url in fake.urls if "/search" in url]
    assert 0 < len(searches) <= lookup.SUGGESTION_LOOKUPS * lookup.SUGGESTION_ATTEMPTS


def test_no_suggestions_when_not_asked(api: IconifyApi, fake: FakeIconify) -> None:
    """suggest=False 时不发搜索请求。"""
    found = lookup.lookup_names(["mdi:nope"], api, suggest=False)
    assert found["mdi:nope"].suggestions == ()
    assert not [url for url in fake.urls if "/search" in url]


def test_search_failure_while_suggesting_is_harmless(fake: FakeIconify) -> None:
    """找建议时搜索失败：不抛错，只是没有建议；核对结果本身不受影响。"""

    def fetch(url: str) -> object:
        if "/search" in url:
            raise ApiError("network", "cannot reach the Iconify API: boom")
        return fake(url)

    found = lookup.lookup_names(["mdi:nope"], IconifyApi(fetch=fetch), suggest=True)
    assert found["mdi:nope"].status == "not_found"
    assert found["mdi:nope"].suggestions == ()


def test_duplicates_are_looked_up_once(api: IconifyApi, fake: FakeIconify) -> None:
    """重复的名字只请求一次。"""
    lookup.lookup_names(["mdi:home", "mdi:home"], api, suggest=False)
    assert len(fake.urls) == 1
