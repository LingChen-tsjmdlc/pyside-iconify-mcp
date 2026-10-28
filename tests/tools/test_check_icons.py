"""check_icons：状态分类、特性提示、去重与入参校验。"""

from __future__ import annotations

import pytest

from pyside_iconify_mcp.common.errors import InputError
from pyside_iconify_mcp.common.iconify_api import ApiError, IconifyApi
from pyside_iconify_mcp.tools import check_icons
from tests.fakes import FakeIconify


def _by_name(result: dict[str, object]) -> dict[str, dict[str, object]]:
    entries = result["results"]
    assert isinstance(entries, list)
    return {str(entry["name"]): entry for entry in entries}


def test_check_icons_statuses(api: IconifyApi) -> None:
    """四种状态各一个。"""
    result = check_icons.run(["mdi:home", "mdi:home-filled", "MDI:Home", "nosuchset:abc"], api=api)
    entries = _by_name(result)
    assert entries["mdi:home"]["status"] == "ok"
    assert entries["mdi:home-filled"]["status"] == "not_found"
    assert entries["MDI:Home"]["status"] == "invalid_name"
    assert entries["nosuchset:abc"]["status"] == "not_found"
    assert "does not exist" in str(entries["nosuchset:abc"]["reason"])
    assert result["summary"] == {"ok": 1, "not_found": 2, "invalid_name": 1, "unavailable": 0}


def test_check_icons_reports_features_and_notes(api: IconifyApi) -> None:
    """多色、混合色、动画图标带有对应提示。"""
    entries = _by_name(
        check_icons.run(
            ["mdi:home", "logos:google-icon", "logos:mixed", "line-md:loading-loop"], api=api
        )
    )
    assert entries["mdi:home"] == {
        "name": "mdi:home",
        "status": "ok",
        "monotone": True,
        "fixed_colors": [],
        "animated": False,
        "notes": [],
    }
    google = entries["logos:google-icon"]
    assert google["monotone"] is False
    assert google["fixed_colors"] == ["#4285f4", "#ea4335"]
    assert "no effect" in str(google["notes"])
    assert "currentColor parts follow" in str(entries["logos:mixed"]["notes"])
    loop = entries["line-md:loading-loop"]
    assert loop["animated"] is True
    assert "IconWidget plays it" in str(loop["notes"])


def test_missing_icons_come_with_suggestions(api: IconifyApi) -> None:
    """不存在的图标附带相近图标（找法的细节见 tests/common/test_lookup.py）。"""
    entries = _by_name(check_icons.run(["mdi:home-filled"], api=api))
    assert entries["mdi:home-filled"]["suggestions"] == ["mdi:home", "mdi:home-outline"]


def test_check_icons_unavailable(api: IconifyApi, fake: FakeIconify) -> None:
    """联网失败：unavailable，不当作不存在，也不找建议。"""
    fake.fail = ApiError("network", "cannot reach the Iconify API: boom")
    entries = _by_name(check_icons.run(["mdi:home"], api=api))
    assert entries["mdi:home"]["status"] == "unavailable"
    assert "suggestions" not in entries["mdi:home"]


def test_check_icons_dedupes_and_validates_size(api: IconifyApi) -> None:
    """重复的名字只出现一次；数量为空或过多报错。"""
    result = check_icons.run(["mdi:home", " mdi:home ", "mdi:home"], api=api)
    assert len(result["results"]) == 1  # type: ignore[arg-type]
    with pytest.raises(InputError):
        check_icons.run([], api=api)
    with pytest.raises(InputError):
        check_icons.run([f"mdi:a{i}" for i in range(check_icons.MAX_NAMES + 1)], api=api)


def test_check_icons_only_invalid_names_makes_no_request(
    api: IconifyApi, fake: FakeIconify
) -> None:
    """全是格式错误的名字时不联网。"""
    result = check_icons.run(["nope", "A:B"], api=api)
    assert result["summary"] == {"ok": 0, "not_found": 0, "invalid_name": 2, "unavailable": 0}
    assert fake.urls == []
