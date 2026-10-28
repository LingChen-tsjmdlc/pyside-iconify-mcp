"""check_code 工具：用 ast 静态检查代码里的 pyside-iconify 用法，不执行任何代码。

原则：宁可漏报，绝不误报。只对代码里直接写出来的字面量下结论；
拿不准的写法放进 skipped 告知调用方，而不是猜。
"""

from __future__ import annotations

import ast
import difflib
import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from pyside_iconify_mcp.common import library
from pyside_iconify_mcp.common.colors import CSS_COLOR_NAMES
from pyside_iconify_mcp.common.errors import InputError
from pyside_iconify_mcp.common.iconify_api import (
    STATUS_NOT_FOUND,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    IconifyApi,
    get_api,
)
from pyside_iconify_mcp.common.lookup import lookup_names
from pyside_iconify_mcp.common.tool_annotations import ONLINE_READ

NAME = "check_code"
DESCRIPTION = (
    "Check the pyside-iconify usage in a piece of Python code without running it. Finds "
    "unknown imports, unknown or misplaced parameters (for example hover_color on "
    "get_icon), invalid values (size, color, opacity, rotate, animation), conflicting "
    "options, malformed or non-existent icon names, and multi-color or animated icons "
    "used in ways that do not work. 'ok' is true when there are no errors. Only values "
    "written literally in the code are checked; anything else is listed under 'skipped' "
    "instead of being guessed. Run it on finished code and fix every error."
)

MAX_CODE_LENGTH = 200_000
MAX_SKIPPED = 30

ERROR = "error"
WARNING = "warning"
INFO = "info"

SIZE_PARAMS = frozenset({"size", "width", "height"})
COLOR_PARAMS = frozenset(
    {
        "color",
        "color_light_theme",
        "color_dark_theme",
        "hover_color",
        "hover_color_light_theme",
        "hover_color_dark_theme",
        "selected_color",
        "selected_color_light_theme",
        "selected_color_dark_theme",
    }
)
PERIOD_PARAMS = frozenset({"animation_period", "spin_period"})
# 只有 IconWidget 才有的动画与外观参数；其他入口返回的 QIcon / QPixmap 不能动
WIDGET_ONLY_PARAMS = frozenset(
    {"animation", "animation_period", "animation_depth", "autoplay", "speed", "spin_period"}
)
STATIC_ENTRIES = frozenset({"get_icon", "get_pixmap", "set_icon"})

# AI 常编造的参数名 -> 正确的参数名（或说明）
KNOWN_WRONG_PARAMS: dict[str, str] = {
    "light_color": "color_light_theme",
    "dark_color": "color_dark_theme",
    "light_theme_color": "color_light_theme",
    "dark_theme_color": "color_dark_theme",
    "class_name": "qss",
    "classname": "qss",
    "style": "qss",
    "scale": "size",
    "icon_size": "size",
    "name": "icon",
    "icon_name": "icon",
    "rotation": "rotate",
    "flip_h": "h_flip",
    "flip_horizontal": "h_flip",
    "hflip": "h_flip",
    "flip_v": "v_flip",
    "flip_vertical": "v_flip",
    "vflip": "v_flip",
    "animate": "animation",
    "hover": "hover_color",
    "fill": "color",
}


@dataclass(frozen=True, slots=True)
class Issue:
    """检查出的一个问题。

    Attributes:
        line: 行号，从 1 开始。
        column: 列号，从 1 开始。
        severity: error、warning 或 info。
        code: 问题类别的稳定标识。
        message: 问题说明（英文）。
        suggestion: 修改建议；没有为 None。
    """

    line: int
    column: int
    severity: str
    code: str
    message: str
    suggestion: str | None = None

    def to_dict(self) -> dict[str, object]:
        """转成可序列化的字典。"""
        data: dict[str, object] = {
            "line": self.line,
            "column": self.column,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.suggestion:
            data["suggestion"] = self.suggestion
        return data


@dataclass(frozen=True, slots=True)
class _NameUse:
    """代码里出现的一个图标名字面量。"""

    name: str
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class _CallRecord:
    """一次入口调用中，和图标特性有关的信息。"""

    entry: str
    name: str | None
    line: int
    column: int
    color_params: tuple[str, ...]


@dataclass
class _Context:
    """一次检查过程中累积的状态。"""

    specs: dict[str, library.EntrySpec]
    issues: list[Issue] = field(default_factory=list)
    skipped: list[dict[str, object]] = field(default_factory=list)
    skipped_overflow: int = 0
    uses: list[_NameUse] = field(default_factory=list)
    records: list[_CallRecord] = field(default_factory=list)
    local_names: set[str] = field(default_factory=set)
    local_unknown: bool = False
    calls: int = 0

    def add(
        self,
        node: ast.AST,
        severity: str,
        code: str,
        message: str,
        suggestion: str | None = None,
    ) -> None:
        """在语法树节点处记录一个问题。"""
        self.issues.append(Issue(*_position(node), severity, code, message, suggestion))

    def skip(self, node: ast.AST | None, reason: str) -> None:
        """记录一处没能检查的地方；node 为 None 表示与具体位置无关。"""
        self.skip_line(_position(node)[0] if node is not None else None, reason)

    def skip_line(self, line: int | None, reason: str) -> None:
        """按行号记录一处没能检查的地方；超过上限后只计数。"""
        if len(self.skipped) >= MAX_SKIPPED:
            self.skipped_overflow += 1
            return
        self.skipped.append({"line": line, "reason": reason})


def _position(node: ast.AST) -> tuple[int, int]:
    """返回节点的 (行, 列)，均从 1 开始。"""
    return getattr(node, "lineno", 1), getattr(node, "col_offset", 0) + 1


def _preview(node: ast.AST) -> str:
    """返回节点源码的简短预览。"""
    text = ast.unparse(node)
    return text if len(text) <= 40 else text[:37] + "..."


def _literal(node: ast.expr) -> tuple[bool, object]:
    """尝试把节点当作字面量求值。

    Returns:
        (是否成功, 值)。变量、函数调用等无法求值的写法返回 (False, None)。
    """
    try:
        return True, ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False, None


def _number(value: object) -> float | None:
    """把普通数字（不含布尔值）转成 float；其他类型返回 None。"""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


# -- 参数取值检查 -----------------------------------------------------------

_Problem = tuple[str, str, str | None]  # (code, message, suggestion)


def _validate_size(value: object) -> _Problem | None:
    """检查 size / width / height 的取值。"""
    if value is None or not isinstance(value, (int, float, str, tuple, list)):
        return None
    try:
        library.parse_size(value)
    except library.IconifyError as error:
        return (
            "invalid_size",
            str(error),
            "Use a positive number (pixels), '24px', '1.5em' or (width, height).",
        )
    return None


def _validate_opacity(value: object) -> _Problem | None:
    """检查 opacity：0 到 1 的数字。"""
    if value is None:
        return None
    number = _number(value)
    if number is None or not 0 <= number <= 1:
        return ("invalid_opacity", "opacity must be a number between 0 and 1", "Use e.g. 0.5, not 50.")
    return None


def _validate_rotate(value: object) -> _Problem | None:
    """检查 rotate：有限数字，单位为度（None 同样不被接受）。"""
    number = _number(value)
    if number is None or not math.isfinite(number):
        return ("invalid_rotation", "rotate must be a finite number of degrees", "Use e.g. rotate=90.")
    return None


def _validate_animation(value: object) -> _Problem | None:
    """检查 animation：内置动画名或 None。"""
    if value is None or (isinstance(value, str) and value in library.ANIMATIONS):
        return None
    allowed = ", ".join(repr(name) for name in library.ANIMATIONS)
    close = difflib.get_close_matches(str(value), library.ANIMATIONS, n=1) if isinstance(value, str) else []
    return (
        "invalid_animation",
        f"animation must be None or one of {allowed}",
        f"Did you mean {close[0]!r}?" if close else None,
    )


def _validate_period(value: object) -> _Problem | None:
    """检查周期：有限正数或 None。"""
    if value is None:
        return None
    number = _number(value)
    if number is None or not math.isfinite(number) or number <= 0:
        return ("invalid_period", "a period must be a finite positive number of seconds", None)
    return None


def _validate_depth(value: object) -> _Problem | None:
    """检查 animation_depth：0 到 1 的数字或 None。"""
    if value is None:
        return None
    number = _number(value)
    if number is None or not 0 <= number <= 1:
        return ("invalid_depth", "animation_depth must be a number between 0 and 1", None)
    return None


def _validate_speed(value: object) -> _Problem | None:
    """检查 speed：大于 0 的有限数字（None 不被接受）。"""
    number = _number(value)
    if number is None or not math.isfinite(number) or number <= 0:
        return ("invalid_speed", "speed must be a finite number greater than 0", None)
    return None


_VALIDATORS: dict[str, Callable[[object], _Problem | None]] = {
    "opacity": _validate_opacity,
    "rotate": _validate_rotate,
    "animation": _validate_animation,
    "animation_depth": _validate_depth,
    "speed": _validate_speed,
    **dict.fromkeys(SIZE_PARAMS, _validate_size),
    **dict.fromkeys(PERIOD_PARAMS, _validate_period),
}


def _color_problem(value: object) -> tuple[str, str, str] | None:
    """检查单个颜色字面量。

    Returns:
        (级别, 类别, 说明)；没问题为 None。颜色名在不依赖 Qt 的情况下无法核实，只给警告。
    """
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        try:
            library.parse_color(text)
        except library.IconifyError:
            pass
        else:
            return None
        if text.startswith("#"):
            digits = text[1:]
            # Qt 还接受 #RRRGGGBBB 与 #RRRRGGGGBBBB 两种写法，主库的纯 Python 解析不认
            if len(digits) in (9, 12) and all(c in "0123456789abcdefABCDEF" for c in digits):
                return (WARNING, "unverified_color", f"Cannot verify HEX color {value!r} without Qt.")
            return (ERROR, "invalid_color", f"{value!r} is not a valid HEX color (use 3, 4, 6 or 8 digits).")
        if "(" in text or ")" in text:
            return (
                ERROR,
                "invalid_color",
                f"{value!r} is not a valid color function; use comma separated rgb(), rgba(), hsl() or hsla().",
            )
        if text.lower().replace(" ", "") in CSS_COLOR_NAMES:
            return None
        return (
            WARNING,
            "unverified_color",
            f"{value!r} is not a standard CSS/SVG color name; Qt will reject it if it does not know the name.",
        )
    if isinstance(value, (tuple, list)):
        try:
            library.parse_color(value)
        except library.IconifyError as error:
            return (ERROR, "invalid_color", f"Invalid color tuple: {error}.")
        return None
    return (
        ERROR,
        "invalid_color",
        "A color must be a string, a tuple of 3 or 4 integers (0-255), a QColor or a Qt.GlobalColor.",
    )


def _check_color_mapping(param: str, node: ast.Dict, ctx: _Context) -> None:
    """检查 {原色: 新色} 映射表。"""
    if any(key is None for key in node.keys):
        ctx.skip(node, f"{param} uses dict unpacking; value not checked.")
        return
    keys = [key for key in node.keys if key is not None]
    literal_keys = [_literal(key) for key in keys]
    if keys and all(ok and isinstance(value, str) and value in ("light", "dark") for ok, value in literal_keys):
        ctx.add(
            node,
            ERROR,
            "invalid_color_mapping",
            f"{param}={_preview(node)} is not a light/dark mapping: the keys of a color "
            "mapping are the ORIGINAL colors to replace, and 'light'/'dark' are not colors.",
            "Use color_light_theme=... and color_dark_theme=... instead.",
        )
        return
    for key, (ok, value) in zip(keys, literal_keys, strict=True):
        if ok and value == "currentColor":
            continue
        _report_color(key, ok, value, ctx)
    for item in node.values:
        _report_color(item, *_literal(item), ctx)


def _report_color(node: ast.expr, ok: bool, value: object, ctx: _Context) -> None:
    """对一个颜色字面量报告问题；不是字面量则跳过。"""
    if not ok:
        return
    problem = _color_problem(value)
    if problem is not None:
        severity, code, message = problem
        ctx.add(node, severity, code, message)


# -- 导入与绑定 -------------------------------------------------------------


@dataclass
class _Bindings:
    """从导入语句得到的名字绑定。"""

    entries: dict[str, str] = field(default_factory=dict)  # 本地名 -> 入口名
    modules: set[str] = field(default_factory=set)  # 指向 pyside_iconify 包的本地名
    legit: Counter[str] = field(default_factory=Counter)  # 来自 pyside_iconify 的绑定次数


def _check_module_path(path: str, node: ast.AST, ctx: _Context) -> None:
    """检查 ``pyside_iconify.xxx`` 的一级子模块是否存在。"""
    parts = path.split(".")
    if len(parts) > 1 and parts[1] not in library.submodule_names():
        close = difflib.get_close_matches(parts[1], library.submodule_names(), n=3)
        ctx.add(
            node,
            ERROR,
            "unknown_module",
            f"pyside_iconify has no module '{parts[1]}'.",
            f"Did you mean: {', '.join(close)}" if close else None,
        )


def _collect_bindings(tree: ast.AST, ctx: _Context) -> _Bindings:
    """扫描导入语句，检查导入的名字，并记录入口函数的本地名。"""
    bindings = _Bindings()
    public = library.public_names()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] != "pyside_iconify":
                    continue
                _check_module_path(alias.name, node, ctx)
                if alias.asname is None:
                    bindings.modules.add("pyside_iconify")
                    bindings.legit["pyside_iconify"] += 1
                elif alias.name == "pyside_iconify":
                    bindings.modules.add(alias.asname)
                    bindings.legit[alias.asname] += 1
                else:
                    bindings.legit[alias.asname] += 1
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module or node.module.split(".")[0] != "pyside_iconify":
                continue
            _check_module_path(node.module, node, ctx)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                bindings.legit[local] += 1
                if node.module == "pyside_iconify" and alias.name not in public:
                    close = difflib.get_close_matches(alias.name, public, n=3)
                    ctx.add(
                        node,
                        ERROR,
                        "unknown_import",
                        f"pyside_iconify has no public name '{alias.name}'.",
                        f"Did you mean: {', '.join(close)}" if close else None,
                    )
                elif alias.name in library.ENTRY_POINTS:
                    bindings.entries[local] = alias.name
    return bindings


def _count_bindings(tree: ast.AST) -> Counter[str]:
    """统计每个名字在代码里被绑定了几次（导入、定义、赋值、参数等）。"""
    counts: Counter[str] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                counts[alias.asname or alias.name.split(".")[0]] += 1
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    counts[alias.asname or alias.name] += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            counts[node.name] += 1
        elif isinstance(node, ast.arg):
            counts[node.arg] += 1
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            counts[node.id] += 1
        elif isinstance(node, ast.ExceptHandler) and node.name:
            counts[node.name] += 1
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            counts[node.name] += 1
        elif isinstance(node, ast.MatchMapping) and node.rest:
            counts[node.rest] += 1
    return counts


def _entry_of(call: ast.Call, bindings: _Bindings, clean: set[str]) -> str | None:
    """判断一次调用是否调用了某个公开入口，是则返回入口名。"""
    func = call.func
    if isinstance(func, ast.Name):
        entry = bindings.entries.get(func.id)
        return entry if entry is not None and func.id in clean else None
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id in bindings.modules
        and func.value.id in clean
        and func.attr in library.ENTRY_POINTS
    ):
        return func.attr
    return None


def _note_registration(call: ast.Call, ctx: _Context) -> None:
    """识别 add_icon / add_collection / load_bundle：代码自己注册了本地图标。"""
    func = call.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
    if name not in library.REGISTER_FUNCTIONS:
        return
    if name == "add_icon":
        first = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "name"), None)
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            try:
                ctx.local_names.add(library.canonical_name(first.value))
            except library.InvalidIconNameError:
                ctx.local_unknown = True
            return
    ctx.local_unknown = True


# -- 单次调用 ---------------------------------------------------------------


def _icon_argument(call: ast.Call, spec: library.EntrySpec, keywords: dict[str, ast.keyword]) -> ast.expr | None:
    """取出调用里表示图标的那个实参。"""
    index = spec.positional.index("icon")
    if index < len(call.args) and not any(isinstance(a, ast.Starred) for a in call.args[: index + 1]):
        return call.args[index]
    keyword = keywords.get("icon")
    return keyword.value if keyword is not None else None


def _note_icon_name(node: ast.expr | None, ctx: _Context, label: str) -> str | None:
    """检查一个图标名实参；字面量字符串才检查，返回标准化后的名字。"""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and node.value is None and label == "fallback":
        return None
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        ctx.skip(node, f"{label} is not a string literal ({_preview(node)}); not checked.")
        return None
    try:
        canonical = library.canonical_name(node.value)
    except library.InvalidIconNameError:
        hint = "Icon names look like 'mdi:home': lowercase letters, digits and hyphens on both sides of one colon."
        lowered = node.value.strip().lower()
        try:
            library.canonical_name(lowered)
        except library.InvalidIconNameError:
            pass
        else:
            hint = f"Icon names are lowercase; try {lowered!r}."
        ctx.add(node, ERROR, "invalid_icon_name", f"{node.value!r} is not a valid icon name.", hint)
        return None
    ctx.uses.append(_NameUse(canonical, *_position(node)))
    return canonical


def _unknown_parameter(entry: str, name: str, keyword: ast.keyword, ctx: _Context) -> None:
    """报告一个不存在的参数名，并给出尽可能具体的建议。"""
    spec = ctx.specs[entry]
    # get_pixmap 宽松地接受许多只在 IconWidget 里有意义的参数，不把它当作推荐去向
    others = [
        other
        for other, s in ctx.specs.items()
        if other not in (entry, "get_pixmap") and name in s.keywords
    ]
    hints: list[str] = []
    if others:
        hints.append(f"'{name}' is accepted by {', '.join(o + '()' for o in others)}.")
    if name in library.HOVER_OPTIONS and entry in STATIC_ENTRIES and entry != "set_icon":
        hints.append(
            "For a button use set_icon(button, icon, hover_color=...); "
            "for a standalone icon use IconWidget(icon, hover_color=...)."
        )
    elif name in WIDGET_ONLY_PARAMS and entry in STATIC_ENTRIES:
        hints.append("A QIcon cannot animate; use IconWidget.")
    wrong = KNOWN_WRONG_PARAMS.get(name)
    if wrong is not None and wrong in spec.keywords:
        hints.append(
            "The first positional argument is the icon name." if wrong == "icon" else f"Did you mean '{wrong}'?"
        )
    elif not others:
        close = difflib.get_close_matches(name, sorted(spec.keywords), n=3)
        if close:
            hints.append(f"Similar parameters: {', '.join(close)}.")
    ctx.add(
        keyword,
        ERROR,
        "unknown_parameter",
        f"{entry}() has no parameter '{name}'.",
        " ".join(hints) or None,
    )


def _check_value(name: str, keyword: ast.keyword, ctx: _Context) -> bool:
    """检查一个参数的取值。

    Returns:
        值是直接写出来的颜色标量（字符串或元组）时为 True，供后续核对多色图标。
    """
    node = keyword.value
    if name in COLOR_PARAMS:
        if isinstance(node, ast.Dict):
            _check_color_mapping(name, node, ctx)
            return False
        ok, value = _literal(node)
        if not ok:
            ctx.skip(keyword, f"{name} is not a literal ({_preview(node)}); value not checked.")
            return False
        problem = _color_problem(value)
        if problem is not None:
            severity, code, message = problem
            ctx.add(keyword, severity, code, message)
        return isinstance(value, (str, tuple, list))
    validator = _VALIDATORS.get(name)
    if validator is None:
        return False
    ok, value = _literal(node)
    if not ok:
        ctx.skip(keyword, f"{name} is not a literal ({_preview(node)}); value not checked.")
        return False
    problem_ = validator(value)
    if problem_ is not None:
        code, message, suggestion = problem_
        ctx.add(keyword, ERROR, code, f"{name}={_preview(node)}: {message}.", suggestion)
    return False


def _check_animation_rules(
    spec: library.EntrySpec, keywords: dict[str, ast.keyword], has_splat: bool, ctx: _Context
) -> None:
    """检查 spin / animation / animation_depth 之间的冲突。"""
    animation = keywords.get("animation")
    spin = keywords.get("spin")
    anim_ok, anim_value = _literal(animation.value) if animation is not None else (False, None)
    if (
        animation is not None
        and spin is not None
        and isinstance(spin.value, ast.Constant)
        and spin.value.value is True
        and anim_ok
        and isinstance(anim_value, str)
        and anim_value in library.ANIMATIONS
        and anim_value != "spin"
    ):
        ctx.add(
            animation,
            ERROR,
            "conflicting_options",
            f"spin=True conflicts with animation={anim_value!r}; use only one of them.",
        )
    depth = keywords.get("animation_depth")
    if depth is None or "animation_depth" not in spec.keywords:
        return
    depth_ok, depth_value = _literal(depth.value)
    if not depth_ok or depth_value is None:
        return
    message = (
        "animation_depth only applies to animation "
        + ", ".join(repr(n) for n in library.DEPTH_ANIMATIONS)
        + "; it cannot be used with 'spin' or without an animation."
    )
    if animation is None:
        if not has_splat:
            ctx.add(depth, ERROR, "conflicting_options", message)
    elif anim_ok and (anim_value is None or anim_value == "spin"):
        ctx.add(depth, ERROR, "conflicting_options", message)


def _check_call(call: ast.Call, entry: str, ctx: _Context) -> None:
    """检查对公开入口的一次调用。"""
    spec = ctx.specs[entry]
    ctx.calls += 1
    has_star = any(isinstance(arg, ast.Starred) for arg in call.args)
    has_splat = any(keyword.arg is None for keyword in call.keywords)
    if has_star or has_splat:
        ctx.skip(call, f"{entry}(...) uses *args or **kwargs; its arguments may be incomplete.")
    count = len(call.args)
    if not has_star and not spec.var_positional and count > len(spec.positional):
        ctx.add(
            call.args[len(spec.positional)],
            ERROR,
            "too_many_positional_args",
            f"{entry}() takes {len(spec.positional)} positional argument(s); the rest must be passed by keyword.",
        )
    keywords = {kw.arg: kw for kw in call.keywords if kw.arg is not None}
    bound = set(spec.positional[:count]) if not has_star else set()
    color_params: list[str] = []
    for name, keyword in keywords.items():
        if name in bound:
            ctx.add(keyword, ERROR, "multiple_values", f"{entry}() got multiple values for '{name}'.")
        elif name not in spec.keywords:
            if spec.strict:
                _unknown_parameter(entry, name, keyword, ctx)
        elif _check_value(name, keyword, ctx):
            color_params.append(name)
    if not has_star and not has_splat:
        for index, required in enumerate(spec.required):
            if index >= count and required not in keywords:
                ctx.add(call, ERROR, "missing_argument", f"{entry}() is missing the required argument '{required}'.")
    _check_animation_rules(spec, keywords, has_splat, ctx)
    canonical = None
    if "icon" in spec.positional:
        canonical = _note_icon_name(_icon_argument(call, spec, keywords), ctx, "icon name")
    if "fallback" in keywords and "fallback" in spec.keywords:
        _note_icon_name(keywords["fallback"].value, ctx, "fallback")
    ctx.records.append(_CallRecord(entry, canonical, *_position(call), tuple(color_params)))


# -- 联网核对 ---------------------------------------------------------------


def _verify_names(ctx: _Context, api: IconifyApi) -> None:
    """联网核对图标名是否存在，并对多色、动画图标给出提示。"""
    names = list(dict.fromkeys(use.name for use in ctx.uses))
    if not names:
        return
    lookups = lookup_names(names, api, suggest=True)
    for use in ctx.uses:
        lookup = lookups[use.name]
        if lookup.status == STATUS_UNAVAILABLE:
            ctx.skip_line(use.line, f"Icon {use.name!r} was not verified: {lookup.reason}.")
        elif lookup.status == STATUS_NOT_FOUND and use.name not in ctx.local_names:
            message = lookup.reason or f"icon {use.name!r} does not exist"
            message = message[0].upper() + message[1:]
            severity = ERROR
            if ctx.local_unknown:
                severity = WARNING
                message += " (this code registers local icons, so it may be provided at run time)"
            suggestion = (
                f"Did you mean: {', '.join(lookup.suggestions)}"
                if lookup.suggestions
                else "Use the search_icons tool to find a real icon."
            )
            ctx.issues.append(Issue(use.line, use.column, severity, "icon_not_found", message, suggestion))
    for record in ctx.records:
        lookup = lookups.get(record.name) if record.name else None
        if lookup is None or lookup.status != STATUS_OK or lookup.info is None:
            continue
        info = lookup.info
        if record.color_params and info.fixed_colors:
            params = ", ".join(record.color_params)
            if info.uses_current_color:
                text = (
                    f"{record.name} mixes fixed colors with currentColor: {params} only changes the "
                    "currentColor parts."
                )
            else:
                text = f"{record.name} has only fixed colors ({', '.join(info.fixed_colors)}): {params} has no effect."
            ctx.issues.append(
                Issue(
                    record.line,
                    record.column,
                    WARNING,
                    "color_has_no_effect",
                    text,
                    "Pass a {original: new} mapping, e.g. color={'" + info.fixed_colors[0] + "': 'red'}.",
                )
            )
        if info.animated and record.entry in STATIC_ENTRIES:
            ctx.issues.append(
                Issue(
                    record.line,
                    record.column,
                    INFO,
                    "animation_not_played",
                    f"{record.name} is self-animating, but {record.entry}() returns a static image of its finished frame.",
                    "Use IconWidget to play the animation.",
                )
            )


# -- 入口 -------------------------------------------------------------------


def run(
    code: str, *, verify_icon_names: bool = True, api: IconifyApi | None = None
) -> dict[str, object]:
    """检查一段 Python 代码里的 pyside-iconify 用法。

    只做静态分析，不执行代码。无法确定的写法列入 skipped，不下结论。

    Args:
        code: Python 源码。
        verify_icon_names: 是否联网核对图标名是否存在；False 时只做离线检查。
        api: 客户端；None 时用共享实例。

    Returns:
        可直接序列化的结果字典：ok（没有 error）、issues、skipped、checked。

    Raises:
        InputError: 代码为空或过长。
        LibraryStubError: 读不到主库的类型存根。
    """
    if not code.strip():
        raise InputError("code must not be empty")
    if len(code) > MAX_CODE_LENGTH:
        raise InputError(f"code is too long (at most {MAX_CODE_LENGTH} characters)")
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError) as error:
        line = getattr(error, "lineno", None) or 1
        column = getattr(error, "offset", None) or 1
        message = getattr(error, "msg", None) or str(error)
        issue = Issue(line, column, ERROR, "syntax_error", f"Python cannot parse this code: {message}.")
        return _result([issue], [], 0, 0)
    ctx = _Context(specs=library.entry_specs())
    bindings = _collect_bindings(tree, ctx)
    counts = _count_bindings(tree)
    clean = {name for name in {*bindings.entries, *bindings.modules} if counts[name] == bindings.legit[name]}
    for name in sorted({*bindings.entries, *bindings.modules} - clean):
        ctx.skip(None, f"'{name}' is rebound elsewhere in this code, so calls through it were not checked.")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            _note_registration(node, ctx)
            entry = _entry_of(node, bindings, clean)
            if entry is not None:
                _check_call(node, entry, ctx)
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in bindings.modules
            and node.value.id in clean
            and not node.attr.startswith("__")
            and node.attr not in library.public_names()
        ):
            close = difflib.get_close_matches(node.attr, library.public_names(), n=3)
            ctx.add(
                node,
                ERROR,
                "unknown_attribute",
                f"pyside_iconify has no public name '{node.attr}'.",
                f"Did you mean: {', '.join(close)}" if close else None,
            )
    if ctx.uses:
        if verify_icon_names:
            _verify_names(ctx, api or get_api())
        else:
            ctx.skip(None, "Icon names were checked for format only (verify_icon_names is false).")
    if ctx.calls == 0 and not ctx.issues:
        ctx.skip(
            None,
            "No calls to IconWidget, get_icon, get_pixmap or set_icon were found; "
            "they must be imported from pyside_iconify to be recognized.",
        )
    return _result(ctx.issues, ctx.skipped, ctx.calls, len({use.name for use in ctx.uses}), ctx.skipped_overflow)


def _result(
    issues: list[Issue],
    skipped: list[dict[str, object]],
    calls: int,
    names: int,
    overflow: int = 0,
) -> dict[str, object]:
    """组装最终输出。"""
    ordered = sorted(issues, key=lambda issue: (issue.line, issue.column, issue.code))
    skipped_out = list(skipped)
    if overflow:
        skipped_out.append({"line": None, "reason": f"... and {overflow} more unchecked item(s)."})
    return {
        "ok": not any(issue.severity == ERROR for issue in ordered),
        "issues": [issue.to_dict() for issue in ordered],
        "skipped": skipped_out,
        "checked": {"calls": calls, "icon_names": names},
        "library_version": library.LIB_VERSION,
    }


def register(mcp: FastMCP) -> None:
    """把本工具注册到服务上。

    本模块用了 ``from __future__ import annotations``，注册函数里的标注是字符串，
    FastMCP 会按模块全局名解析，所以标注里只能用模块级导入的名字。

    Args:
        mcp: FastMCP 服务实例。
    """

    @mcp.tool(name=NAME, description=DESCRIPTION, annotations=ONLINE_READ)
    def check_code(
        code: Annotated[
            str, Field(description="Python source code to check (up to 200000 characters).")
        ],
        verify_icon_names: Annotated[
            bool,
            Field(
                description=(
                    "Look up icon names online to confirm they exist and to check color and "
                    "animation use. Set false to check offline."
                )
            ),
        ] = True,
    ) -> dict[str, object]:
        """检查代码里的 pyside-iconify 用法。"""
        try:
            return run(code, verify_icon_names=verify_icon_names)
        except (InputError, library.LibraryStubError) as error:
            raise ToolError(str(error)) from error
