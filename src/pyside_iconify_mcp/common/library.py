"""主库适配层：本项目对 pyside-iconify 的全部依赖都集中在这里。

只导入 pyside_iconify 顶层包和 core 层，二者都不会导入 Qt。
参数名清单不手抄，而是读取主库自带的 ``__init__.pyi`` 与 ``rendering/options.py``
（只解析源码文本，不导入，因为 rendering 包会导入 Qt）。
"""

from __future__ import annotations

import ast
import pkgutil
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pyside_iconify
from pyside_iconify._errors import (
    IconifyError,
    InvalidColorError,
    InvalidIconNameError,
    InvalidSizeError,
)
from pyside_iconify.core.colors import parse_color
from pyside_iconify.core.icon_data import parse_collection
from pyside_iconify.core.names import parse_icon_name
from pyside_iconify.core.sizes import parse_size
from pyside_iconify.core.smil import is_supported_animation
from pyside_iconify.core.svg import collect_paints

__all__ = [
    "ANIMATIONS",
    "DEPTH_ANIMATIONS",
    "ENTRY_POINTS",
    "HOVER_OPTIONS",
    "LIB_VERSION",
    "REGISTER_FUNCTIONS",
    "EntrySpec",
    "IconInfo",
    "IconifyError",
    "InvalidColorError",
    "InvalidIconNameError",
    "InvalidSizeError",
    "LibraryStubError",
    "Param",
    "Signature",
    "Signatures",
    "analyze_collection",
    "canonical_name",
    "entry_specs",
    "is_valid_prefix",
    "load_signatures",
    "parse_color",
    "parse_icon_name",
    "parse_size",
    "public_names",
    "split_icon_name",
    "submodule_names",
]

LIB_VERSION: str = pyside_iconify.__version__

# 以下常量与主库保持一致；tests/test_lib.py 会对照主库源码，主库改了就会失败。
ANIMATIONS: tuple[str, ...] = ("spin", "pulse", "breathe", "ping", "bounce")
DEPTH_ANIMATIONS: tuple[str, ...] = ("pulse", "breathe", "ping", "bounce")
HOVER_OPTIONS: tuple[str, ...] = (
    "hover_color",
    "hover_color_light_theme",
    "hover_color_dark_theme",
)
ENTRY_POINTS: tuple[str, ...] = ("IconWidget", "get_icon", "get_pixmap", "set_icon")
REGISTER_FUNCTIONS: tuple[str, ...] = ("add_icon", "add_collection", "load_bundle")


class LibraryStubError(RuntimeError):
    """找不到或读不懂主库自带的类型存根。"""


# -- 图标数据 ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IconInfo:
    """图标数据里和写代码有关的特性。

    Attributes:
        monotone: 没有固定颜色（与主库 ``is_monotone`` 一致）。
        fixed_colors: 固定颜色，``#rrggbb`` 形式（与主库 ``get_icon_colors`` 一致）。
        animated: 带有主库能播放的 SMIL 动画（与主库 ``is_animated`` 一致）。
        uses_current_color: 内容里出现 currentColor，即单个颜色参数可能生效。
    """

    monotone: bool
    fixed_colors: tuple[str, ...]
    animated: bool
    uses_current_color: bool


def analyze_collection(collection: Mapping[str, object]) -> dict[str, IconInfo]:
    """解析一份 Iconify JSON 集合，返回每个图标的特性。

    Args:
        collection: Iconify JSON 集合；须含 prefix 和 icons，可含 aliases。

    Returns:
        图标名（不含前缀）到特性的映射，包含别名。

    Raises:
        IconifyError: 集合内容不合法（别名循环、含脚本等）。
    """
    result: dict[str, IconInfo] = {}
    for icon_name, data in parse_collection(collection).items():
        paints = collect_paints(data.body)
        result[icon_name.name] = IconInfo(
            monotone=not paints,
            fixed_colors=tuple(
                f"#{color.red:02x}{color.green:02x}{color.blue:02x}" for color in paints
            ),
            animated=is_supported_animation(data.body),
            uses_current_color="currentColor" in data.body,
        )
    return result


# -- 图标名 -----------------------------------------------------------------


def split_icon_name(value: str) -> tuple[str, str]:
    """把 ``prefix:name`` 拆成前缀和名称。

    Args:
        value: 图标名；首尾空白会被去除。

    Returns:
        (前缀, 名称)。

    Raises:
        InvalidIconNameError: 格式不合法。
    """
    name = parse_icon_name(value)
    return name.prefix, name.name


def canonical_name(value: str) -> str:
    """返回标准化后的图标名（去掉首尾空白）。

    Args:
        value: 图标名。

    Returns:
        ``prefix:name`` 字符串。

    Raises:
        InvalidIconNameError: 格式不合法。
    """
    return str(parse_icon_name(value))


def is_valid_prefix(prefix: str) -> bool:
    """判断是否为合法的图标集前缀。

    Args:
        prefix: 图标集前缀，如 ``mdi``。

    Returns:
        合法为 True。
    """
    try:
        parse_icon_name(f"{prefix}:a")
    except InvalidIconNameError:
        return False
    return True


@lru_cache(maxsize=1)
def public_names() -> frozenset[str]:
    """返回 ``from pyside_iconify import X`` 能成功的全部名字。

    Returns:
        顶层已有的名字、``__all__`` 里的延迟导入名字，以及子模块名。
    """
    names = {name for name in vars(pyside_iconify) if not name.startswith("__")}
    names.update(getattr(pyside_iconify, "__all__", ()))
    names.update(submodule_names())
    names.add("__version__")
    return frozenset(names)


@lru_cache(maxsize=1)
def submodule_names() -> frozenset[str]:
    """返回主库的一级子模块名。

    Returns:
        子模块名集合，如 ``core``、``widgets``。
    """
    return frozenset(module.name for module in pkgutil.iter_modules(pyside_iconify.__path__))


# -- 签名 -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Param:
    """函数的一个参数。

    Attributes:
        name: 参数名。
        kind: positional、var_positional、keyword 或 var_keyword。
        annotation: 类型标注的源码文本；无标注为 None。
        default: 默认值的源码文本；必填为 None。
    """

    name: str
    kind: str
    annotation: str | None
    default: str | None


@dataclass(frozen=True, slots=True)
class Signature:
    """一个函数或方法的签名。

    Attributes:
        name: 函数名。
        params: 按声明顺序排列的参数（已去掉 self）。
        returns: 返回值标注的源码文本；无标注为 None。
    """

    name: str
    params: tuple[Param, ...]
    returns: str | None


@dataclass(frozen=True, slots=True)
class Signatures:
    """从 ``__init__.pyi`` 读到的、本项目关心的签名。

    Attributes:
        functions: get_icon、get_pixmap、set_icon 的签名。
        widget_init: IconWidget 构造函数的签名。
        widget_methods: IconWidget 的公开方法。
    """

    functions: Mapping[str, Signature]
    widget_init: Signature
    widget_methods: tuple[Signature, ...]


def _text(node: ast.expr | None) -> str | None:
    """把语法树节点还原成源码文本。"""
    return None if node is None else ast.unparse(node)


def _signature(node: ast.FunctionDef, *, method: bool) -> Signature:
    """把函数定义节点转成 Signature。

    Args:
        node: 函数定义节点。
        method: 是否为方法；True 时去掉第一个 self 参数。
    """
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    padded: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults))
    padded.extend(args.defaults)
    params = [
        Param(arg.arg, "positional", _text(arg.annotation), _text(default))
        for arg, default in zip(positional, padded, strict=True)
    ]
    if method and params and params[0].name in ("self", "cls"):
        params = params[1:]
    if args.vararg is not None:
        params.append(Param(args.vararg.arg, "var_positional", _text(args.vararg.annotation), None))
    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        params.append(Param(arg.arg, "keyword", _text(arg.annotation), _text(default)))
    if args.kwarg is not None:
        params.append(Param(args.kwarg.arg, "var_keyword", _text(args.kwarg.annotation), None))
    return Signature(node.name, tuple(params), _text(node.returns))


def _library_dir() -> Path:
    """返回主库包所在目录。"""
    return Path(pyside_iconify.__file__).parent


@lru_cache(maxsize=1)
def load_signatures() -> Signatures:
    """读取主库 ``__init__.pyi``，得到公开入口的签名。

    Returns:
        Signatures。

    Raises:
        LibraryStubError: 文件缺失、无法解析，或缺少预期的定义。
    """
    path = _library_dir() / "__init__.pyi"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as error:
        raise LibraryStubError(f"cannot read pyside-iconify stub file {path}: {error}") from error
    functions: dict[str, Signature] = {}
    widget: ast.ClassDef | None = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("get_icon", "get_pixmap", "set_icon"):
            functions[node.name] = _signature(node, method=False)
        elif isinstance(node, ast.ClassDef) and node.name == "IconWidget":
            widget = node
    if widget is None or len(functions) != 3:
        raise LibraryStubError(f"{path} does not define IconWidget, get_icon, get_pixmap and set_icon")
    init: Signature | None = None
    methods: list[Signature] = []
    for node in widget.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name == "__init__":
            init = _signature(node, method=True)
        elif not node.name.startswith("_"):
            methods.append(_signature(node, method=True))
    if init is None:
        raise LibraryStubError(f"{path}: IconWidget has no __init__")
    return Signatures(functions, init, tuple(methods))


@lru_cache(maxsize=1)
def _make_options_keywords() -> frozenset[str] | None:
    """读取 make_options 接受的关键字参数名（只解析源码，不导入）。

    get_pixmap 把多余的关键字原样交给 make_options，所以它实际接受的名字比
    get_icon 多。读不到时返回 None，调用方应放宽检查。

    Returns:
        参数名集合；文件缺失或找不到函数时为 None。
    """
    path = _library_dir() / "rendering" / "options.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "make_options":
            return frozenset(arg.arg for arg in node.args.kwonlyargs)
    return None


@dataclass(frozen=True, slots=True)
class EntrySpec:
    """一个公开入口（IconWidget、get_icon 等）接受哪些参数。

    Attributes:
        name: 入口名。
        positional: 位置参数名，按顺序。
        required: 必填的位置参数名。
        var_positional: 是否接受额外的位置参数。
        keywords: 可以按关键字传入的参数名。
        strict: 为 True 时，不在 keywords 里的关键字一定会出错；
            为 False 表示名单可能不完整，不应据此报错。
    """

    name: str
    positional: tuple[str, ...]
    required: tuple[str, ...]
    var_positional: bool
    keywords: frozenset[str]
    strict: bool


def _spec(name: str, sig: Signature, extra: frozenset[str], *, strict: bool = True) -> EntrySpec:
    """由签名生成 EntrySpec。"""
    positional = tuple(p.name for p in sig.params if p.kind == "positional")
    required = tuple(p.name for p in sig.params if p.kind == "positional" and p.default is None)
    keywords = frozenset(p.name for p in sig.params if p.kind in ("positional", "keyword"))
    return EntrySpec(
        name=name,
        positional=positional,
        required=required,
        var_positional=any(p.kind == "var_positional" for p in sig.params),
        keywords=keywords | extra,
        strict=strict,
    )


@lru_cache(maxsize=1)
def entry_specs() -> dict[str, EntrySpec]:
    """返回四个公开入口的参数规格。

    规则来自主库实现：get_icon 的参数是严格的；set_icon 先取走三个 hover 参数，
    其余原样交给 get_icon；get_pixmap 把多余关键字交给 make_options。

    Returns:
        入口名到 EntrySpec 的映射。

    Raises:
        LibraryStubError: 读不到主库存根。
    """
    sigs = load_signatures()
    get_icon = _spec("get_icon", sigs.functions["get_icon"], frozenset())
    options = _make_options_keywords()
    if options is None:
        pixmap = _spec("get_pixmap", sigs.functions["get_pixmap"], get_icon.keywords, strict=False)
    else:
        pixmap = _spec("get_pixmap", sigs.functions["get_pixmap"], get_icon.keywords | options)
    return {
        "IconWidget": _spec("IconWidget", sigs.widget_init, frozenset()),
        "get_icon": get_icon,
        "get_pixmap": pixmap,
        "set_icon": _spec(
            "set_icon", sigs.functions["set_icon"], get_icon.keywords | frozenset(HOVER_OPTIONS)
        ),
    }
