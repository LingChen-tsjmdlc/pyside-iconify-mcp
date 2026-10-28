"""主库适配层：与主库的耦合点。主库改了这些东西，这里的测试会先失败。"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pyside_iconify

from pyside_iconify_mcp.common import library


def test_imports_without_qt() -> None:
    """导入本项目和主库 core 不会带入任何 Qt 绑定。"""
    qt = {"PySide6", "PyQt6", "PyQt5", "PySide2"}
    assert not [name for name in sys.modules if name.split(".")[0] in qt]


def _library_source(relative: str) -> ast.Module:
    path = Path(pyside_iconify.__file__).parent / relative
    return ast.parse(path.read_text(encoding="utf-8"))


def _assigned(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            assert node.value is not None
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found")


def test_animation_constants_match_library() -> None:
    """动画名与能设置幅度的动画，和主库 motion.py 一致。"""
    tree = _library_source("rendering/motion.py")
    assert tuple(_assigned(tree, "ANIMATIONS")) == library.ANIMATIONS  # type: ignore[arg-type]
    depths = _assigned(tree, "DEFAULT_DEPTHS")
    assert isinstance(depths, dict)
    assert tuple(depths) == library.DEPTH_ANIMATIONS


def test_entry_points_and_register_functions_are_public() -> None:
    """入口函数和注册函数都在主库的公开导出里。"""
    exported = set(pyside_iconify.__all__)
    assert set(library.ENTRY_POINTS) <= exported
    assert set(library.REGISTER_FUNCTIONS) <= exported


def test_hover_options_belong_to_widget_not_get_icon() -> None:
    """hover 参数是 IconWidget 的参数、不是 get_icon 的；set_icon 额外接受它们。"""
    specs = library.entry_specs()
    hover = set(library.HOVER_OPTIONS)
    assert hover <= specs["IconWidget"].keywords
    assert not hover & specs["get_icon"].keywords
    assert hover <= specs["set_icon"].keywords


def test_entry_specs_shape() -> None:
    """四个入口的位置参数与关键字参数。"""
    specs = library.entry_specs()
    assert set(specs) == set(library.ENTRY_POINTS)
    assert specs["IconWidget"].positional == ("icon",)
    assert specs["get_icon"].required == ("icon",)
    assert specs["set_icon"].positional == ("target", "icon")
    assert specs["set_icon"].var_positional
    assert {"size", "color", "opacity", "rotate", "selected_color"} <= specs["get_icon"].keywords
    assert "animation" not in specs["get_icon"].keywords
    assert "animation" in specs["IconWidget"].keywords
    assert "selected_color" not in specs["IconWidget"].keywords


def test_signature_parsing_keeps_defaults_and_kinds() -> None:
    """IconWidget 构造函数的参数种类、默认值被正确读出。"""
    init = library.load_signatures().widget_init
    by_name = {p.name: p for p in init.params}
    assert by_name["icon"].kind == "positional"
    assert by_name["icon"].default is None
    assert by_name["size"].kind == "keyword"
    assert by_name["size"].default == "None"
    assert by_name["autoplay"].default == "True"
    assert [m.name for m in library.load_signatures().widget_methods][:2] == ["iconName", "setIcon"]


def test_public_names() -> None:
    """公开名字含延迟导入的名字和子模块，不含乱写的名字。"""
    names = library.public_names()
    assert {"IconWidget", "get_icon", "IconData", "core", "widgets", "__version__"} <= names
    assert "IconButton" not in names


def test_icon_names() -> None:
    """图标名的拆分、标准化与图标集前缀校验。"""
    assert library.split_icon_name("mdi:home") == ("mdi", "home")
    assert library.canonical_name("  mdi:home ") == "mdi:home"
    assert library.is_valid_prefix("line-md")
    assert not library.is_valid_prefix("MDI")
    assert not library.is_valid_prefix("a:b")
    assert not library.is_valid_prefix("")


def test_analyze_collection_features() -> None:
    """单色、多色、混合色、动画四种图标被正确区分。"""
    from tests.fakes import COLLECTIONS

    merged = {
        "prefix": "x",
        "icons": {
            **COLLECTIONS["mdi"]["icons"],  # type: ignore[dict-item]
            **COLLECTIONS["logos"]["icons"],  # type: ignore[dict-item]
            **COLLECTIONS["line-md"]["icons"],  # type: ignore[dict-item]
        },
        "aliases": COLLECTIONS["mdi"]["aliases"],
    }
    info = library.analyze_collection(merged)
    assert info["home"].monotone and not info["home"].fixed_colors and not info["home"].animated
    assert not info["google-icon"].monotone
    assert info["google-icon"].fixed_colors == ("#4285f4", "#ea4335")
    assert not info["google-icon"].uses_current_color
    assert info["mixed"].uses_current_color and info["mixed"].fixed_colors == ("#4285f4",)
    assert info["loading-loop"].animated
    assert info["gear"].monotone
