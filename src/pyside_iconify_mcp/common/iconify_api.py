"""Iconify 公共 API 客户端：只读、带内存缓存、不依赖 Qt。

主库自带的 IconifyClient 基于 Qt 网络模块，这里不能用，所以用标准库 urllib 自己请求。
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar

from pyside_iconify_mcp import __version__
from pyside_iconify_mcp.common import library

_T = TypeVar("_T")

API_ROOT = "https://api.iconify.design"
USER_AGENT = f"pyside-iconify-mcp/{__version__} (+https://github.com/LingChen-tsjmdlc/pyside-iconify-mcp)"
TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
CACHE_TTL_SECONDS = 3600.0
CACHE_MAX_ENTRIES = 2048
BATCH_SIZE = 50
# 官方搜索接口要求 limit 在 32 到 999 之间
MIN_SEARCH_LIMIT = 32

STATUS_OK = "ok"
STATUS_NOT_FOUND = "not_found"
STATUS_UNAVAILABLE = "unavailable"

Fetcher = Callable[[str], object]


class ApiError(Exception):
    """访问 Iconify API 失败。

    Attributes:
        kind: network、rate_limit、server、bad_request 或 invalid_response。
    """

    def __init__(self, kind: str, message: str) -> None:
        """创建错误。

        Args:
            kind: 错误类别。
            message: 面向使用者的说明（英文）。
        """
        super().__init__(message)
        self.kind = kind

    def describe(self) -> str:
        """返回 ``类别: 说明`` 形式的文本。"""
        return f"{self.kind}: {self}"


def http_get_json(url: str) -> object:
    """GET 一个地址并解析 JSON。

    HTTP 404 返回整数 404（与官方对不存在的图标集返回正文 ``404`` 的行为统一）。

    Args:
        url: 完整地址。

    Returns:
        解析后的 JSON 值。

    Raises:
        ApiError: 网络失败、限流、服务器错误或响应不是合法 JSON。
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return 404
        if error.code == 429:
            raise ApiError("rate_limit", "rate limited by the Iconify API") from error
        if error.code in (400, 403):
            raise ApiError("bad_request", f"the Iconify API rejected the request (HTTP {error.code})") from error
        raise ApiError("server", f"Iconify API error (HTTP {error.code})") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ApiError("network", f"cannot reach the Iconify API: {error}") from error
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ApiError("invalid_response", "response from the Iconify API is too large")
    try:
        return json.loads(payload)
    except ValueError as error:
        raise ApiError("invalid_response", "response from the Iconify API is not valid JSON") from error


@dataclass(frozen=True, slots=True)
class CollectionInfo:
    """图标集的概况。

    Attributes:
        name: 图标集名称。
        license: 许可证名称；未提供为 None。
        total: 图标总数；未提供为 None。
    """

    name: str
    license: str | None
    total: int | None


@dataclass(frozen=True, slots=True)
class SearchResult:
    """一次搜索的结果。

    Attributes:
        icons: ``prefix:name`` 列表。
        collections: 结果涉及的图标集概况。
    """

    icons: tuple[str, ...]
    collections: Mapping[str, CollectionInfo]


@dataclass(frozen=True, slots=True)
class Lookup:
    """一个图标名的核对结果。

    Attributes:
        name: 标准化的图标名。
        status: ok、not_found 或 unavailable（没查成，不代表不存在）。
        info: status 为 ok 时的图标特性。
        reason: 非 ok 时的说明。
        set_missing: 不存在的原因是整个图标集不存在。
        suggestions: 相近图标（由上层按需填充）。
    """

    name: str
    status: str
    info: library.IconInfo | None = None
    reason: str | None = None
    set_missing: bool = False
    suggestions: tuple[str, ...] = ()


class IconifyApi:
    """带缓存的 Iconify API 客户端；线程安全。"""

    def __init__(
        self,
        fetch: Fetcher = http_get_json,
        *,
        ttl: float = CACHE_TTL_SECONDS,
        max_entries: int = CACHE_MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """创建客户端。

        Args:
            fetch: 取 JSON 的函数；测试时可换成假实现。
            ttl: 缓存有效期（秒）。
            max_entries: 每类缓存的最大条目数。
            clock: 计时函数；测试时可换成假时钟。
        """
        self._fetch = fetch
        self._ttl = ttl
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._searches: dict[str, tuple[float, SearchResult]] = {}
        self._lookups: dict[str, tuple[float, Lookup]] = {}

    def search(self, query: str, *, prefix: str | None, limit: int) -> SearchResult:
        """搜索图标。

        Args:
            query: 关键词；多个词需要同时匹配。
            prefix: 只在某个图标集里找；None 表示全部。
            limit: 最多返回几个。

        Returns:
            搜索结果，图标数不超过 limit。

        Raises:
            ApiError: 请求失败或响应不合法。
        """
        params = {"query": query, "limit": str(max(MIN_SEARCH_LIMIT, limit))}
        if prefix:
            params["prefix"] = prefix
        url = f"{API_ROOT}/search?{urllib.parse.urlencode(params)}"
        cached = self._get(self._searches, url)
        if cached is None:
            cached = _parse_search(self._fetch(url))
            self._put(self._searches, url, cached)
        icons = cached.icons[:limit]
        used = {icon.partition(":")[0] for icon in icons}
        collections = {key: value for key, value in cached.collections.items() if key in used}
        return SearchResult(icons=icons, collections=collections)

    def lookup(self, names: Sequence[str]) -> dict[str, Lookup]:
        """核对一批图标名，按图标集分组批量请求。

        Args:
            names: 已标准化且格式合法的图标名，不含重复。

        Returns:
            每个传入名字对应一条结果；请求失败的名字状态为 unavailable。
        """
        results: dict[str, Lookup] = {}
        pending: dict[str, list[str]] = {}
        for full in names:
            cached = self._get(self._lookups, full)
            if cached is not None:
                results[full] = cached
                continue
            prefix, name = library.split_icon_name(full)
            pending.setdefault(prefix, []).append(name)
        for prefix, local_names in pending.items():
            for start in range(0, len(local_names), BATCH_SIZE):
                results.update(self._lookup_batch(prefix, local_names[start : start + BATCH_SIZE]))
        return results

    def _lookup_batch(self, prefix: str, names: list[str]) -> dict[str, Lookup]:
        """请求同一图标集的一批图标，并写入缓存。"""
        url = f"{API_ROOT}/{prefix}.json?icons={','.join(names)}"
        try:
            found = _interpret(prefix, names, self._fetch(url))
        except ApiError as error:
            return {
                f"{prefix}:{name}": Lookup(
                    f"{prefix}:{name}", STATUS_UNAVAILABLE, reason=error.describe()
                )
                for name in names
            }
        for full, lookup in found.items():
            if lookup.status != STATUS_UNAVAILABLE:
                self._put(self._lookups, full, lookup)
        return found

    def _get(self, store: dict[str, tuple[float, _T]], key: str) -> _T | None:
        """读缓存；过期的条目当作未命中并删除。"""
        with self._lock:
            entry = store.get(key)
            if entry is None:
                return None
            if entry[0] <= self._clock():
                del store[key]
                return None
            return entry[1]

    def _put(self, store: dict[str, tuple[float, _T]], key: str, value: _T) -> None:
        """写缓存；超过上限时丢弃最早写入的条目。"""
        with self._lock:
            store[key] = (self._clock() + self._ttl, value)
            overflow = len(store) - self._max_entries
            if overflow > 0:
                for old in list(store)[:overflow]:
                    del store[old]


def _parse_search(document: object) -> SearchResult:
    """把搜索接口的响应解析成 SearchResult。

    Raises:
        ApiError: 响应结构不对，或搜索接口被关闭（HTTP 404）。
    """
    if document == 404:
        raise ApiError("server", "the Iconify search endpoint is not available")
    if not isinstance(document, dict) or not isinstance(document.get("icons"), list):
        raise ApiError("invalid_response", "unexpected search response from the Iconify API")
    icons = tuple(icon for icon in document["icons"] if isinstance(icon, str))
    collections: dict[str, CollectionInfo] = {}
    raw_collections = document.get("collections")
    if isinstance(raw_collections, dict):
        for prefix, raw in raw_collections.items():
            if not isinstance(prefix, str) or not isinstance(raw, dict):
                continue
            name = raw.get("name")
            licence = raw.get("license")
            total = raw.get("total")
            title = licence.get("title") if isinstance(licence, dict) else None
            collections[prefix] = CollectionInfo(
                name=name if isinstance(name, str) else prefix,
                license=title if isinstance(title, str) else None,
                total=total if isinstance(total, int) and not isinstance(total, bool) else None,
            )
    return SearchResult(icons=icons, collections=collections)


def _number(value: object) -> float | None:
    """把 JSON 数值转为 float；布尔值和其他类型返回 None。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _resolvable_aliases(
    aliases: Mapping[str, dict[str, object]], icons: Mapping[str, dict[str, object]]
) -> dict[str, dict[str, object]]:
    """只保留能一路追溯到真实图标的别名（与主库客户端的做法一致，但支持别名链）。"""
    kept: dict[str, dict[str, object]] = {}
    changed = True
    while changed:
        changed = False
        for name, alias in aliases.items():
            parent = alias.get("parent")
            if name not in kept and isinstance(parent, str) and (parent in icons or parent in kept):
                kept[name] = alias
                changed = True
    return kept


def _subset(
    base: Mapping[str, object],
    icons: Mapping[str, dict[str, object]],
    aliases: Mapping[str, dict[str, object]],
    name: str,
) -> dict[str, object]:
    """取出单个图标（含它的别名链）组成的小集合，用于定位是哪个图标的数据有问题。"""
    chain_icons: dict[str, dict[str, object]] = {}
    chain_aliases: dict[str, dict[str, object]] = {}
    current: str | None = name
    while current is not None and current not in chain_aliases and current not in chain_icons:
        if current in icons:
            chain_icons[current] = icons[current]
            break
        alias = aliases.get(current)
        if alias is None:
            break
        chain_aliases[current] = alias
        parent = alias.get("parent")
        current = parent if isinstance(parent, str) else None
    subset = {key: base[key] for key in ("prefix", "width", "height") if key in base}
    subset["icons"] = chain_icons
    subset["aliases"] = chain_aliases
    return subset


def _analyze(
    base: dict[str, object],
    icons: Mapping[str, dict[str, object]],
    aliases: Mapping[str, dict[str, object]],
) -> tuple[dict[str, library.IconInfo], dict[str, str]]:
    """分析整份集合；整体失败时逐个分析，找出是哪些图标有问题。

    Returns:
        (解析成功的图标特性, 解析失败的图标名到原因)。
    """
    try:
        return library.analyze_collection(base), {}
    except library.IconifyError:
        pass
    infos: dict[str, library.IconInfo] = {}
    failures: dict[str, str] = {}
    for name in [*icons, *aliases]:
        try:
            infos[name] = library.analyze_collection(_subset(base, icons, aliases, name))[name]
        except library.IconifyError as error:
            failures[name] = str(error)
    return infos, failures


def _interpret(prefix: str, names: Sequence[str], document: object) -> dict[str, Lookup]:
    """把批量取图标接口的响应翻译成每个名字的核对结果。

    Args:
        prefix: 图标集前缀。
        names: 本次请求的图标名（不含前缀）。
        document: 接口返回的 JSON。

    Returns:
        完整图标名到结果的映射。

    Raises:
        ApiError: 响应结构不合法。
    """
    if not isinstance(document, dict):
        if document == 404:
            reason = f"icon set '{prefix}' does not exist"
            return {
                f"{prefix}:{name}": Lookup(
                    f"{prefix}:{name}", STATUS_NOT_FOUND, reason=reason, set_missing=True
                )
                for name in names
            }
        raise ApiError("invalid_response", "response must be a JSON object")
    if document.get("prefix", prefix) != prefix:
        raise ApiError("invalid_response", "response prefix does not match the request")
    icons_raw = document.get("icons") or {}
    aliases_raw = document.get("aliases") or {}
    if not isinstance(icons_raw, dict) or not isinstance(aliases_raw, dict):
        raise ApiError("invalid_response", "icons and aliases must be objects")
    icons = {k: v for k, v in icons_raw.items() if isinstance(k, str) and isinstance(v, dict)}
    all_aliases = {k: v for k, v in aliases_raw.items() if isinstance(k, str) and isinstance(v, dict)}
    aliases = _resolvable_aliases(all_aliases, icons)
    base: dict[str, object] = {"prefix": prefix, "icons": icons, "aliases": aliases}
    for key in ("width", "height"):
        number = _number(document.get(key))
        if number is not None:
            base[key] = number
    infos, failures = _analyze(base, icons, aliases)
    results: dict[str, Lookup] = {}
    for name in names:
        full = f"{prefix}:{name}"
        if name in infos:
            results[full] = Lookup(full, STATUS_OK, info=infos[name])
        elif name in failures:
            results[full] = Lookup(
                full, STATUS_UNAVAILABLE, reason=f"icon data could not be parsed: {failures[name]}"
            )
        elif name in all_aliases:
            results[full] = Lookup(
                full, STATUS_UNAVAILABLE, reason="alias target is missing from the API response"
            )
        else:
            results[full] = Lookup(
                full,
                STATUS_NOT_FOUND,
                reason=f"icon '{full}' does not exist",
            )
    return results


_default_api: IconifyApi | None = None
_default_lock = threading.Lock()


def get_api() -> IconifyApi:
    """返回进程级共享的客户端（首次调用时创建）。

    Returns:
        共享的 IconifyApi。
    """
    global _default_api
    with _default_lock:
        if _default_api is None:
            _default_api = IconifyApi()
        return _default_api
