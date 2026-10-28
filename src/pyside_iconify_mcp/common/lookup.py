"""核对一批图标名：check_icons 与 check_code 共用。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from pyside_iconify_mcp.common import library
from pyside_iconify_mcp.common.iconify_api import STATUS_NOT_FOUND, ApiError, IconifyApi, Lookup

# 每次最多为几个不存在的名字找相近图标，避免对官方 API 发太多请求
SUGGESTION_LOOKUPS = 3
SUGGESTION_COUNT = 5
SUGGESTION_ATTEMPTS = 3


def lookup_names(names: Sequence[str], api: IconifyApi, *, suggest: bool) -> dict[str, Lookup]:
    """核对一批已标准化的图标名；可选地为不存在的名字补充相近图标。

    Args:
        names: 已标准化且格式合法的图标名，可含重复。
        api: 客户端。
        suggest: 是否为不存在的名字查找相近图标。

    Returns:
        每个名字对应一条结果。
    """
    unique = list(dict.fromkeys(names))
    found = api.lookup(unique)
    if suggest:
        missing = [name for name in unique if found[name].status == STATUS_NOT_FOUND]
        for name in missing[:SUGGESTION_LOOKUPS]:
            found[name] = replace(
                found[name], suggestions=_suggest(name, found[name].set_missing, api)
            )
    return found


def _suggest(name: str, set_missing: bool, api: IconifyApi) -> tuple[str, ...]:
    """为不存在的图标名找相近的真实图标。

    搜索要求所有词都匹配，所以从完整名字开始，逐步去掉末尾的词再搜。

    Args:
        name: 不存在的图标名。
        set_missing: 整个图标集都不存在；此时不限定图标集。
        api: 客户端。

    Returns:
        相近图标名；找不到或网络失败时为空。
    """
    prefix, local = library.split_icon_name(name)
    words = [word for word in local.split("-") if word]
    scope = None if set_missing else prefix
    for count in range(len(words), max(0, len(words) - SUGGESTION_ATTEMPTS), -1):
        try:
            result = api.search(" ".join(words[:count]), prefix=scope, limit=SUGGESTION_COUNT + 1)
        except ApiError:
            return ()
        icons = tuple(icon for icon in result.icons if icon != name)[:SUGGESTION_COUNT]
        if icons:
            return icons
    return ()
