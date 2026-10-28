"""check_icons 工具：核对图标名是否存在，并报告多色、动画等特性。"""

from collections.abc import Sequence
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from pyside_iconify_mcp.common import library
from pyside_iconify_mcp.common.errors import InputError
from pyside_iconify_mcp.common.iconify_api import (
    STATUS_NOT_FOUND,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    IconifyApi,
    Lookup,
    get_api,
)
from pyside_iconify_mcp.common.lookup import lookup_names
from pyside_iconify_mcp.common.tool_annotations import ONLINE_READ

NAME = "check_icons"
DESCRIPTION = (
    "Verify icon names before using them in code. For each name returns whether it exists "
    "(status 'ok', 'not_found', 'invalid_name' or 'unavailable'), and for existing icons "
    "whether they are monotone or multi-color (fixed_colors), whether they animate "
    "themselves, and notes about what that means for color and animation arguments. "
    "For missing icons returns similar real icons. 'unavailable' means the check failed "
    "(for example no network), not that the icon is missing."
)

MAX_NAMES = 50
STATUS_INVALID_NAME = "invalid_name"
INVALID_NAME_REASON = (
    "must look like 'prefix:name' with lowercase letters, digits and hyphens, e.g. 'mdi:home'"
)


def notes_for(info: library.IconInfo) -> list[str]:
    """把图标特性翻译成写代码时要注意的提示。

    Args:
        info: 图标特性。

    Returns:
        英文提示列表；没有需要注意的地方时为空。
    """
    notes: list[str] = []
    if info.fixed_colors and info.uses_current_color:
        notes.append(
            "Mixed colors: the currentColor parts follow `color`, the fixed colors "
            f"({', '.join(info.fixed_colors)}) do not. Recolor them with a {{original: new}} mapping."
        )
    elif info.fixed_colors:
        notes.append(
            f"Fixed colors ({', '.join(info.fixed_colors)}): a single `color` has no effect. "
            "Pass a {original: new} mapping to recolor."
        )
    if info.animated:
        notes.append(
            "Self-animating (SMIL): IconWidget plays it; get_icon, get_pixmap and set_icon "
            "show only the finished frame."
        )
    return notes


def _entry(lookup: Lookup) -> dict[str, object]:
    """把一条核对结果转成输出字典。"""
    if lookup.status == STATUS_OK and lookup.info is not None:
        return {
            "name": lookup.name,
            "status": STATUS_OK,
            "monotone": lookup.info.monotone,
            "fixed_colors": list(lookup.info.fixed_colors),
            "animated": lookup.info.animated,
            "notes": notes_for(lookup.info),
        }
    entry: dict[str, object] = {
        "name": lookup.name,
        "status": lookup.status,
        "reason": lookup.reason,
    }
    if lookup.status == STATUS_NOT_FOUND:
        entry["suggestions"] = list(lookup.suggestions)
    return entry


def run(names: Sequence[str], *, api: IconifyApi | None = None) -> dict[str, object]:
    """核对图标名是否存在，并报告多色、动画等特性。

    Args:
        names: 图标名列表，1 到 50 个。
        api: 客户端；None 时用共享实例。

    Returns:
        可直接序列化的结果字典。

    Raises:
        InputError: 入参不合法。
    """
    if not names:
        raise InputError("names must not be empty")
    if len(names) > MAX_NAMES:
        raise InputError(f"too many names (at most {MAX_NAMES} per call)")
    results: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for raw in names:
        if raw in seen:
            continue
        seen.add(raw)
        try:
            results.append((raw, library.canonical_name(raw)))
        except library.InvalidIconNameError:
            results.append((raw, None))
    valid = [canonical for _, canonical in results if canonical is not None]
    lookups = lookup_names(valid, api or get_api(), suggest=True) if valid else {}
    entries: list[dict[str, object]] = []
    emitted: set[str] = set()
    for raw, canonical in results:
        if canonical is None:
            entries.append(
                {"name": raw, "status": STATUS_INVALID_NAME, "reason": INVALID_NAME_REASON}
            )
        elif canonical not in emitted:
            emitted.add(canonical)
            entries.append(_entry(lookups[canonical]))
    summary = {STATUS_OK: 0, STATUS_NOT_FOUND: 0, STATUS_INVALID_NAME: 0, STATUS_UNAVAILABLE: 0}
    for entry in entries:
        summary[str(entry["status"])] += 1
    return {"results": entries, "summary": summary}


def register(mcp: FastMCP) -> None:
    """把本工具注册到服务上。

    Args:
        mcp: FastMCP 服务实例。
    """

    @mcp.tool(name=NAME, description=DESCRIPTION, annotations=ONLINE_READ)
    def check_icons(
        names: Annotated[
            list[str], Field(description="Icon names like 'mdi:home' (1-50 names per call).")
        ],
    ) -> dict[str, object]:
        """核对图标名是否存在，并报告多色、动画等特性。"""
        try:
            return run(names)
        except InputError as error:
            raise ToolError(str(error)) from error
