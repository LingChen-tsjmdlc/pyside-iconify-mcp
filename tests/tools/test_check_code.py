"""check_code：静态检查的各种情形。核心原则是宁可漏报、绝不误报。"""

from __future__ import annotations

import pytest

from pyside_iconify_mcp.common.errors import InputError
from pyside_iconify_mcp.common.iconify_api import ApiError, IconifyApi
from pyside_iconify_mcp.tools import check_code
from tests.fakes import FakeIconify

HEADER = "from pyside_iconify import IconWidget, get_icon, get_pixmap, set_icon\n"


def run(code: str, *, api: IconifyApi | None = None, verify: bool = False) -> dict[str, object]:
    """检查代码；默认离线。"""
    return check_code.run(code, verify_icon_names=verify, api=api)


def codes(result: dict[str, object], severity: str | None = None) -> list[str]:
    """取出问题类别列表。"""
    issues = result["issues"]
    assert isinstance(issues, list)
    return [i["code"] for i in issues if severity is None or i["severity"] == severity]


def errors(result: dict[str, object]) -> list[str]:
    return codes(result, "error")


def skipped_text(result: dict[str, object]) -> str:
    return " | ".join(str(s["reason"]) for s in result["skipped"])  # type: ignore[attr-defined]


# -- 正确的写法不报错 -------------------------------------------------------


def test_correct_code_has_no_errors() -> None:
    """常见的正确写法没有任何问题。"""
    result = run(
        HEADER
        + 'w = IconWidget("mdi:home", size=24, color="red", opacity=0.5, rotate=90, h_flip=True)\n'
        'b = get_icon("mdi:cog", size="1.5em", color_light_theme="#000", color_dark_theme="white")\n'
        'set_icon(button, "mdi:cog", size=20, hover_color="red")\n'
        'set_icon(tabs, "mdi:home", 0)\n'
        'p = get_pixmap("mdi:home", size=(16, 24), color={"#4285f4": "red", "currentColor": "blue"})\n'
        'IconWidget("mdi:home", animation="pulse", animation_depth=0.5, animation_period=2)\n'
        'IconWidget("line-md:loading-loop", autoplay=False, speed=0.5, fallback="mdi:home", qss="a b")\n'
    )
    assert result["ok"] is True
    assert result["issues"] == []
    assert result["checked"] == {"calls": 7, "icon_names": 3}


def test_hex_and_functions_and_tuples_are_valid_colors() -> None:
    """各种合法的颜色写法。"""
    result = run(
        HEADER
        + 'get_icon("mdi:home", color="#f00")\n'
        'get_icon("mdi:home", color="#ff000080")\n'
        'get_icon("mdi:home", color="rgb(255, 0, 0)")\n'
        'get_icon("mdi:home", color="hsla(210, 50%, 40%, 0.5)")\n'
        'get_icon("mdi:home", color=(255, 0, 0))\n'
        'get_icon("mdi:home", color="transparent")\n'
        'get_icon("mdi:home", color=None)\n'
    )
    assert result["issues"] == []


# -- 参数名 -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("call", "wrong", "hint"),
    [
        ('IconWidget("mdi:home", light_color="red")', "light_color", "color_light_theme"),
        ('IconWidget("mdi:home", dark_color="red")', "dark_color", "color_dark_theme"),
        ('IconWidget("mdi:home", class_name="x")', "class_name", "qss"),
        ('get_icon("mdi:home", scale=2)', "scale", "size"),
        ('get_icon("mdi:home", rotation=90)', "rotation", "rotate"),
        ('get_icon("mdi:home", flip_h=True)', "flip_h", "h_flip"),
    ],
)
def test_invented_parameters_are_reported_with_the_right_name(call: str, wrong: str, hint: str) -> None:
    """AI 常编造的参数名被识别，并给出正确的名字。"""
    result = run(HEADER + call + "\n")
    assert errors(result) == ["unknown_parameter"]
    issue = result["issues"][0]  # type: ignore[index]
    assert wrong in issue["message"]
    assert hint in issue["suggestion"]


def test_name_keyword_points_to_positional_icon() -> None:
    """文档里常见的 name= 并不存在，真正的参数叫 icon。"""
    result = run(HEADER + 'get_icon(name="mdi:home")\n')
    assert set(errors(result)) == {"unknown_parameter", "missing_argument"}
    assert "first positional argument" in str(result["issues"])


def test_hover_color_on_get_icon_points_to_other_entries() -> None:
    """get_icon 没有 hover_color；提示该用 set_icon 或 IconWidget。"""
    result = run(HEADER + 'get_icon("mdi:home", hover_color="red")\n')
    assert errors(result) == ["unknown_parameter"]
    suggestion = result["issues"][0]["suggestion"]  # type: ignore[index]
    assert "IconWidget()" in suggestion and "set_icon()" in suggestion


def test_animation_on_get_icon_points_to_icon_widget() -> None:
    """QIcon 不能动，动画参数只在 IconWidget。"""
    result = run(HEADER + 'get_icon("mdi:home", animation="pulse")\n')
    assert errors(result) == ["unknown_parameter"]
    assert "cannot animate" in result["issues"][0]["suggestion"]  # type: ignore[index]


def test_set_icon_accepts_hover_but_not_animation() -> None:
    """set_icon 接受 hover 参数，不接受动画参数。"""
    assert run(HEADER + 'set_icon(b, "mdi:home", hover_color_dark_theme="red")\n')["issues"] == []
    assert errors(run(HEADER + 'set_icon(b, "mdi:home", animation="spin")\n')) == ["unknown_parameter"]


def test_get_pixmap_is_lenient_about_extra_options_but_not_nonsense() -> None:
    """get_pixmap 把多余关键字交给 make_options：它认的名字不报错，乱写的才报错。"""
    assert run(HEADER + 'get_pixmap("mdi:home", size=16, hover_color="red")\n')["issues"] == []
    assert errors(run(HEADER + 'get_pixmap("mdi:home", bogus=1)\n')) == ["unknown_parameter"]


def test_argument_count_errors() -> None:
    """缺必填参数、位置参数过多、重复传值。"""
    assert errors(run(HEADER + "IconWidget()\n")) == ["missing_argument"]
    assert errors(run(HEADER + "set_icon(button)\n")) == ["missing_argument"]
    assert errors(run(HEADER + 'IconWidget("mdi:home", "mdi:cog")\n')) == ["too_many_positional_args"]
    assert errors(run(HEADER + 'IconWidget("mdi:home", icon="mdi:cog")\n')) == ["multiple_values"]


# -- 取值 -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ('size="24"', "invalid_size"),
        ("size=0", "invalid_size"),
        ("size=True", "invalid_size"),
        ("size=(1, 2, 3)", "invalid_size"),
        ("width=-1", "invalid_size"),
        ("opacity=1.5", "invalid_opacity"),
        ("opacity=50", "invalid_opacity"),
        ('opacity="half"', "invalid_opacity"),
        ('rotate="90deg"', "invalid_rotation"),
        ("rotate=None", "invalid_rotation"),
        ('animation="shake"', "invalid_animation"),
        ("animation_period=0", "invalid_period"),
        ("spin_period=-1", "invalid_period"),
        ('animation="pulse", animation_depth=2', "invalid_depth"),
        ("speed=0", "invalid_speed"),
        ("speed=None", "invalid_speed"),
        ('color="#12"', "invalid_color"),
        ('color="rgb(255 0 0)"', "invalid_color"),
        ("color=(255, 0, 300)", "invalid_color"),
        ("color=5", "invalid_color"),
        ('color_dark_theme="#zzz"', "invalid_color"),
    ],
)
def test_invalid_literal_values(arguments: str, code: str) -> None:
    """明确非法的字面量值。"""
    result = run(HEADER + f'IconWidget("mdi:home", {arguments})\n')
    assert code in errors(result)


@pytest.mark.parametrize(
    "arguments",
    [
        "size=n",
        "size=QSize(24, 24)",
        "color=QColor('red')",
        "color=Qt.GlobalColor.red",
        "color=self.color",
        "opacity=compute()",
        "rotate=angle",
        "animation=name",
        "size=None",
        "opacity=None",
        "animation=None",
    ],
)
def test_non_literals_and_none_are_never_flagged(arguments: str) -> None:
    """变量、函数调用、Qt 对象一律不下结论；None 是合法值。"""
    result = run(HEADER + f'IconWidget("mdi:home", {arguments})\n')
    assert errors(result) == []


def test_non_literal_values_are_listed_as_skipped() -> None:
    """没检查的地方要明说。"""
    result = run(HEADER + 'IconWidget("mdi:home", size=n, color=c)\n')
    text = skipped_text(result)
    assert "size is not a literal" in text and "color is not a literal" in text


def test_color_names_are_checked_softly() -> None:
    """标准颜色名没问题；不认识的名字只给警告，不给错误。"""
    assert run(HEADER + 'get_icon("mdi:home", color="rebeccapurple")\n')["issues"] == []
    result = run(HEADER + 'get_icon("mdi:home", color="reddish")\n')
    assert result["ok"] is True
    assert codes(result, "warning") == ["unverified_color"]


def test_qt_only_hex_forms_are_not_errors() -> None:
    """Qt 接受的 9、12 位 HEX，主库纯 Python 解析不认；只给警告。"""
    result = run(HEADER + 'get_icon("mdi:home", color="#fffffffff")\n')
    assert result["ok"] is True
    assert codes(result, "warning") == ["unverified_color"]


def test_color_mapping_values_are_checked() -> None:
    """颜色映射表里的键和值逐个检查。"""
    result = run(HEADER + 'get_icon("mdi:home", color={"#12": "red", "#4285f4": "#99"})\n')
    assert errors(result) == ["invalid_color", "invalid_color"]


def test_light_dark_mapping_is_a_distinct_error() -> None:
    """color={"light":..., "dark":...} 是常见误解：映射表的键是被替换的原色。"""
    result = run(HEADER + 'IconWidget("mdi:home", color={"light": "#fff", "dark": "#000"})\n')
    assert errors(result) == ["invalid_color_mapping"]
    assert "color_light_theme" in result["issues"][0]["suggestion"]  # type: ignore[index]


def test_dict_unpacking_in_mapping_is_skipped() -> None:
    """含 **展开的映射表不检查。"""
    result = run(HEADER + 'IconWidget("mdi:home", color={**base, "light": 1})\n')
    assert errors(result) == []
    assert "dict unpacking" in skipped_text(result)


# -- 参数之间的冲突 ---------------------------------------------------------


def test_spin_conflicts_with_another_animation() -> None:
    """spin=True 与别的动画冲突；与 animation='spin' 一致则没问题。"""
    assert errors(run(HEADER + 'IconWidget("mdi:home", spin=True, animation="pulse")\n')) == ["conflicting_options"]
    assert errors(run(HEADER + 'IconWidget("mdi:home", spin=True, animation="spin")\n')) == []


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ('animation="spin", animation_depth=0.5', ["conflicting_options"]),
        ("animation=None, animation_depth=0.5", ["conflicting_options"]),
        ("animation_depth=0.5", ["conflicting_options"]),
        ('animation="bounce", animation_depth=0.5', []),
        ("animation_depth=None", []),
        ("animation=kind, animation_depth=0.5", []),
        ("animation_depth=depth", []),
        ("**options, animation_depth=0.5", []),
    ],
)
def test_animation_depth_rules(arguments: str, expected: list[str]) -> None:
    """animation_depth 只能配 pulse、breathe、ping、bounce；拿不准的不报。"""
    assert errors(run(HEADER + f'IconWidget("mdi:home", {arguments})\n')) == expected


# -- 导入与绑定 -------------------------------------------------------------


def test_unknown_imports_and_attributes() -> None:
    """导入不存在的名字或子模块；访问不存在的属性。"""
    result = run(
        "from pyside_iconify import IconButton, IconWidget, core\n"
        "import pyside_iconify as pi\n"
        "from pyside_iconify.nothing import x\n"
        "pi.GetIcon('mdi:home')\n"
        "print(pi.__version__, pi.__file__, pi.get_icon)\n"
    )
    assert errors(result) == ["unknown_import", "unknown_module", "unknown_attribute"]


def test_aliases_and_module_attribute_calls_are_recognized() -> None:
    """别名导入、模块属性调用都能识别。"""
    result = run(
        "import pyside_iconify as pi\n"
        "from pyside_iconify import get_icon as gi\n"
        "pi.get_icon('mdi:home', scale=1)\n"
        "gi('mdi:home', bogus=2)\n"
        "import pyside_iconify\n"
        "pyside_iconify.IconWidget('mdi:home', bogus=3)\n"
    )
    assert errors(result) == ["unknown_parameter"] * 3
    assert result["checked"]["calls"] == 3  # type: ignore[index]


def test_import_from_submodule_is_recognized() -> None:
    """从子模块导入入口也能识别。"""
    result = run("from pyside_iconify.widgets import IconWidget\nIconWidget('mdi:home', bogus=1)\n")
    assert errors(result) == ["unknown_parameter"]


def test_rebound_names_are_not_checked() -> None:
    """名字被自己重新定义后，不能再当作 pyside-iconify 的函数检查。"""
    result = run(
        "from pyside_iconify import get_icon\n"
        "def get_icon(x):\n    return x\n"
        "get_icon(foo=1)\n"
    )
    assert result["issues"] == []
    assert "rebound" in skipped_text(result)


def test_other_libraries_with_the_same_name_are_ignored() -> None:
    """别的库里同名的函数不会被误检查。"""
    result = run("from other import get_icon\nget_icon('x', hover_color=1)\n")
    assert result["issues"] == []
    assert "No calls" in skipped_text(result)


def test_unrelated_code_reports_no_calls_found() -> None:
    """没有任何 pyside-iconify 调用时明确说明，而不是悄悄返回 ok。"""
    result = run("x = 1\n")
    assert result["ok"] is True
    assert "No calls" in skipped_text(result)


def test_star_arguments_are_skipped_not_guessed() -> None:
    """*args、**kwargs 让参数不完整：不报缺参数，只提示。"""
    result = run(HEADER + "IconWidget(*args)\nIconWidget(**kw)\n")
    assert errors(result) == []
    assert "uses *args or **kwargs" in skipped_text(result)


def test_syntax_error_is_reported() -> None:
    """语法错误只报这一条。"""
    result = run("def (:\n")
    assert result["ok"] is False
    assert codes(result) == ["syntax_error"]


def test_input_limits() -> None:
    """空代码和过长的代码被拒绝。"""
    with pytest.raises(InputError):
        run("   \n")
    with pytest.raises(InputError):
        run("x" * (check_code.MAX_CODE_LENGTH + 1))


# -- 图标名 -----------------------------------------------------------------


def test_malformed_icon_names_offline() -> None:
    """格式错误的图标名离线就能发现，并提示小写。"""
    result = run(HEADER + 'IconWidget("MDI:Home")\nIconWidget("home")\nIconWidget("mdi:home", fallback="Bad Name")\n')
    assert errors(result) == ["invalid_icon_name"] * 3
    assert "lowercase" in result["issues"][0]["suggestion"]  # type: ignore[index]


def test_icon_name_variables_are_skipped() -> None:
    """图标名不是字面量时不检查，并说明。"""
    result = run(HEADER + "IconWidget(name_var)\nget_icon(f'mdi:{kind}')\n")
    assert errors(result) == []
    assert "icon name is not a string literal" in skipped_text(result)


def test_offline_mode_says_names_were_not_verified() -> None:
    """离线模式明说没有核对图标是否存在。"""
    result = run(HEADER + 'IconWidget("mdi:home-filled")\n')
    assert result["ok"] is True
    assert "format only" in skipped_text(result)


def test_online_check_reports_missing_icons(api: IconifyApi) -> None:
    """联网核对：不存在的图标是 error，并带相近图标。"""
    result = run(HEADER + 'IconWidget("mdi:home-filled")\nIconWidget("mdi:home")\n', api=api, verify=True)
    assert errors(result) == ["icon_not_found"]
    issue = result["issues"][0]  # type: ignore[index]
    assert issue["line"] == 2
    assert "mdi:home" in issue["suggestion"]


def test_online_check_missing_icon_set(api: IconifyApi) -> None:
    """图标集不存在时说明是图标集不存在。"""
    result = run(HEADER + 'IconWidget("nosuchset:abc")\n', api=api, verify=True)
    assert errors(result) == ["icon_not_found"]
    assert "set 'nosuchset' does not exist" in result["issues"][0]["message"]  # type: ignore[index]


def test_fallback_icon_name_is_verified_too(api: IconifyApi) -> None:
    """fallback 里的图标名同样核对。"""
    result = run(HEADER + 'IconWidget("mdi:home", fallback="mdi:nope")\n', api=api, verify=True)
    assert errors(result) == ["icon_not_found"]


def test_network_failure_is_skipped_not_an_error(api: IconifyApi, fake: FakeIconify) -> None:
    """联网失败时不能把图标当成不存在：列入 skipped。"""
    fake.fail = ApiError("network", "cannot reach the Iconify API: boom")
    result = run(HEADER + 'IconWidget("mdi:home-filled")\n', api=api, verify=True)
    assert result["ok"] is True
    assert "was not verified" in skipped_text(result)


def test_locally_registered_icons_are_not_flagged(api: IconifyApi) -> None:
    """代码里 add_icon 注册的本地图标不会被当作不存在。"""
    code = (
        "from pyside_iconify import IconWidget, add_icon\n"
        'add_icon("myapp:logo", "<path d=\\"M0 0h1v1z\\"/>")\n'
        'IconWidget("myapp:logo")\n'
    )
    assert run(code, api=api, verify=True)["issues"] == []


def test_unknown_local_registration_demotes_to_warning(api: IconifyApi) -> None:
    """用 load_bundle / add_collection 等无法确定注册了什么时，不存在只给警告。"""
    code = (
        "from pyside_iconify import IconWidget, load_bundle\n"
        'load_bundle("icons.json")\n'
        'IconWidget("myapp:logo")\n'
    )
    result = run(code, api=api, verify=True)
    assert result["ok"] is True
    assert codes(result, "warning") == ["icon_not_found"]


# -- 联网后的提示 -----------------------------------------------------------


def test_single_color_on_fixed_color_icon_warns(api: IconifyApi) -> None:
    """对只有固定颜色的图标传单色没有效果。"""
    result = run(HEADER + 'IconWidget("logos:google-icon", color="red")\n', api=api, verify=True)
    assert result["ok"] is True
    assert codes(result, "warning") == ["color_has_no_effect"]
    assert "has no effect" in result["issues"][0]["message"]  # type: ignore[index]


def test_single_color_on_mixed_icon_explains_partial_effect(api: IconifyApi) -> None:
    """混合色图标：单色只改 currentColor 的部分。"""
    result = run(HEADER + 'IconWidget("logos:mixed", color="red")\n', api=api, verify=True)
    assert "only changes the currentColor parts" in result["issues"][0]["message"]  # type: ignore[index]


def test_mapping_color_on_fixed_color_icon_is_fine(api: IconifyApi) -> None:
    """用映射表给固定颜色换色是正确做法，不警告。"""
    result = run(HEADER + 'IconWidget("logos:google-icon", color={"#4285f4": "red"})\n', api=api, verify=True)
    assert result["issues"] == []


def test_animated_icon_with_static_entry_is_info(api: IconifyApi) -> None:
    """动画图标用了静态入口：提示不会播放；用 IconWidget 则没有提示。"""
    result = run(HEADER + 'get_icon("line-md:loading-loop")\nIconWidget("line-md:loading-loop")\n', api=api, verify=True)
    assert codes(result) == ["animation_not_played"]
    assert result["issues"][0]["severity"] == "info"  # type: ignore[index]
    assert result["ok"] is True


def test_issues_are_sorted_by_position() -> None:
    """问题按行列排序。"""
    result = run(HEADER + 'get_icon("mdi:home", scale=1)\nIconWidget("mdi:home", opacity=2)\n')
    lines = [issue["line"] for issue in result["issues"]]  # type: ignore[attr-defined]
    assert lines == sorted(lines)
