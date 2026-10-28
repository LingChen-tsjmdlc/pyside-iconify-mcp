"""Iconify API 客户端：查询解析、缓存、失败处理。全部用假服务，不联网。"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import IO

import pytest

from pyside_iconify_mcp.common import iconify_api as api_module
from pyside_iconify_mcp.common.iconify_api import (
    STATUS_NOT_FOUND,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    ApiError,
    IconifyApi,
)
from tests.fakes import FakeIconify


def test_lookup_existing_missing_and_alias(api: IconifyApi) -> None:
    """存在、不存在、别名三种结果。"""
    found = api.lookup(["mdi:home", "mdi:home-filled", "mdi:gear"])
    assert found["mdi:home"].status == STATUS_OK
    assert found["mdi:home"].info is not None and found["mdi:home"].info.monotone
    assert found["mdi:home-filled"].status == STATUS_NOT_FOUND
    assert not found["mdi:home-filled"].set_missing
    assert found["mdi:gear"].status == STATUS_OK


def test_lookup_unknown_icon_set(api: IconifyApi) -> None:
    """整个图标集不存在（接口返回 404）。"""
    found = api.lookup(["nosuchset:abc"])
    assert found["nosuchset:abc"].status == STATUS_NOT_FOUND
    assert found["nosuchset:abc"].set_missing
    assert "nosuchset" in (found["nosuchset:abc"].reason or "")


def test_lookup_groups_by_prefix(api: IconifyApi, fake: FakeIconify) -> None:
    """同一图标集的名字只发一次请求。"""
    api.lookup(["mdi:home", "logos:google-icon", "mdi:cog"])
    assert len(fake.urls) == 2
    assert any("mdi.json?icons=home,cog" in url for url in fake.urls)


def test_lookup_is_cached(api: IconifyApi, fake: FakeIconify) -> None:
    """已查过的名字（包括不存在的）不再请求。"""
    api.lookup(["mdi:home", "mdi:nope"])
    api.lookup(["mdi:home", "mdi:nope"])
    assert len(fake.urls) == 1


def test_cache_expires(fake: FakeIconify) -> None:
    """缓存过期后重新请求。"""
    now = [0.0]
    client = IconifyApi(fetch=fake, ttl=10, clock=lambda: now[0])
    client.lookup(["mdi:home"])
    now[0] = 5
    client.lookup(["mdi:home"])
    assert len(fake.urls) == 1
    now[0] = 11
    client.lookup(["mdi:home"])
    assert len(fake.urls) == 2


def test_cache_is_bounded(fake: FakeIconify) -> None:
    """缓存条目数有上限。"""
    client = IconifyApi(fetch=fake, max_entries=1)
    client.lookup(["mdi:home", "mdi:cog"])
    client.lookup(["mdi:home"])
    assert len(fake.urls) == 2


def test_failures_are_unavailable_and_not_cached(api: IconifyApi, fake: FakeIconify) -> None:
    """网络失败是 unavailable，不当作不存在，也不进缓存。"""
    fake.fail = ApiError("network", "cannot reach the Iconify API: boom")
    found = api.lookup(["mdi:home"])
    assert found["mdi:home"].status == STATUS_UNAVAILABLE
    assert "network" in (found["mdi:home"].reason or "")
    fake.fail = None
    assert api.lookup(["mdi:home"])["mdi:home"].status == STATUS_OK


def test_invalid_response_is_unavailable() -> None:
    """响应结构不对时是 unavailable。"""
    client = IconifyApi(fetch=lambda url: ["not", "an", "object"])
    assert client.lookup(["mdi:home"])["mdi:home"].status == STATUS_UNAVAILABLE


def test_prefix_mismatch_is_unavailable() -> None:
    """响应里的前缀与请求不一致。"""
    client = IconifyApi(fetch=lambda url: {"prefix": "other", "icons": {}})
    assert client.lookup(["mdi:home"])["mdi:home"].status == STATUS_UNAVAILABLE


def test_one_bad_icon_does_not_poison_the_batch(api: IconifyApi) -> None:
    """集合里某个图标含脚本时，只有它 unavailable，同批其他图标照常。"""
    found = api.lookup(["evil:fine", "evil:script"])
    assert found["evil:fine"].status == STATUS_OK
    assert found["evil:script"].status == STATUS_UNAVAILABLE
    assert "parsed" in (found["evil:script"].reason or "")


def test_alias_chain_is_resolved() -> None:
    """别名的别名也能一路追溯到真实图标。"""
    document = {
        "prefix": "x",
        "icons": {"base": {"body": '<path fill="currentColor" d="M0 0h1v1z"/>'}},
        "aliases": {"a1": {"parent": "base"}, "a2": {"parent": "a1"}},
        "width": 24,
        "height": 24,
    }
    client = IconifyApi(fetch=lambda url: document)
    found = client.lookup(["x:a2"])
    assert found["x:a2"].status == STATUS_OK


def test_alias_with_missing_parent_is_unavailable() -> None:
    """别名的目标不在响应里，不能说它不存在。"""
    document = {"prefix": "x", "icons": {}, "aliases": {"a1": {"parent": "ghost"}}}
    client = IconifyApi(fetch=lambda url: document)
    found = client.lookup(["x:a1"])
    assert found["x:a1"].status == STATUS_UNAVAILABLE


def test_large_lookup_is_split_into_batches(fake: FakeIconify) -> None:
    """一批名字过多时分多次请求。"""
    client = IconifyApi(fetch=fake)
    names = [f"mdi:icon-{index}" for index in range(api_module.BATCH_SIZE + 5)]
    client.lookup(names)
    assert len(fake.urls) == 2


def test_search_truncates_and_uses_minimum_limit(api: IconifyApi, fake: FakeIconify) -> None:
    """向官方请求的 limit 不小于 32，返回给调用方时按 limit 截断。"""
    result = api.search("home", prefix=None, limit=2)
    assert len(result.icons) == 2
    assert "limit=32" in fake.urls[0]
    assert set(result.collections) == {icon.partition(":")[0] for icon in result.icons}


def test_search_with_prefix_and_cache(api: IconifyApi, fake: FakeIconify) -> None:
    """限定图标集；相同查询走缓存。"""
    first = api.search("home", prefix="mdi", limit=10)
    api.search("home", prefix="mdi", limit=10)
    assert all(icon.startswith("mdi:") for icon in first.icons)
    assert "prefix=mdi" in fake.urls[0]
    assert len(fake.urls) == 1


def test_search_errors() -> None:
    """搜索接口关闭或响应不合法时抛 ApiError。"""
    for document in (404, {"icons": "nope"}, []):
        client = IconifyApi(fetch=lambda url, d=document: d)
        with pytest.raises(ApiError):
            client.search("home", prefix=None, limit=5)


class _FakeResponse:
    """假的 HTTP 响应。"""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", code, "msg", {}, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("code", "kind"),
    [(429, "rate_limit"), (400, "bad_request"), (403, "bad_request"), (500, "server"), (503, "server")],
)
def test_http_errors_are_mapped(monkeypatch: pytest.MonkeyPatch, code: int, kind: str) -> None:
    """HTTP 错误码映射为带类别的 ApiError。"""

    def fail(request: urllib.request.Request, timeout: float) -> IO[bytes]:
        raise _http_error(code)

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(ApiError) as caught:
        api_module.http_get_json("https://x")
    assert caught.value.kind == kind


def test_http_404_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 404 与官方对未知图标集返回正文 404 的行为统一。"""

    def fail(request: urllib.request.Request, timeout: float) -> IO[bytes]:
        raise _http_error(404)

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    assert api_module.http_get_json("https://x") == 404


def test_network_failure_and_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """连不上是 network；返回的不是 JSON 是 invalid_response。"""

    def unreachable(request: urllib.request.Request, timeout: float) -> IO[bytes]:
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(urllib.request, "urlopen", unreachable)
    with pytest.raises(ApiError) as caught:
        api_module.http_get_json("https://x")
    assert caught.value.kind == "network"

    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: _FakeResponse(b"<html>"))
    with pytest.raises(ApiError) as caught:
        api_module.http_get_json("https://x")
    assert caught.value.kind == "invalid_response"


def test_oversized_response_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """响应超过大小上限。"""
    big = b"1" * (api_module.MAX_RESPONSE_BYTES + 1)
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: _FakeResponse(big))
    with pytest.raises(ApiError) as caught:
        api_module.http_get_json("https://x")
    assert caught.value.kind == "invalid_response"


def test_valid_json_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    """正常响应被解析。"""
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: _FakeResponse(b'{"a": 1}'))
    assert api_module.http_get_json("https://x") == {"a": 1}
