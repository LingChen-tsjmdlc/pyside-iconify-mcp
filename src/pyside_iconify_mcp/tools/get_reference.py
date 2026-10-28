"""get_reference 工具：按主题返回 pyside-iconify 的权威用法（英文 Markdown）。

签名部分在运行时从主库自带的 ``__init__.pyi`` 生成，保证与安装的版本一致；
说明文字是手写的，tests/tools/test_get_reference.py 会核对每个参数、每个方法都有说明，
并且示例代码都能通过 check_code。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from pyside_iconify_mcp.common import library
from pyside_iconify_mcp.common.errors import InputError
from pyside_iconify_mcp.common.tool_annotations import OFFLINE_READ

NAME = "get_reference"
DESCRIPTION = (
    "Read the authoritative, version-matched usage of pyside-iconify: exact signatures, "
    "accepted values, working examples and a table of common mistakes. Call it before "
    "writing pyside-iconify code; start with topic 'overview'. Call without a topic to "
    "list the topics."
)

PARAM_DOCS: dict[str, str] = {
    "icon": (
        "Icon name `prefix:name` (lowercase letters, digits, hyphens). `IconWidget` and `get_icon` "
        "also accept inline `IconData`."
    ),
    "target": "The widget or item that receives the icon (see the target table).",
    "size": (
        "Number (square pixels), `(width, height)`, `QSize`, `\"24px\"` or `\"1.5em\"` "
        "(em follows the font). `None` uses the default, 24."
    ),
    "color": (
        "One color, or a `{original: replacement}` mapping for icons with fixed colors. "
        "`None` follows the widget text color."
    ),
    "color_light_theme": "Color on a light theme. Wins over `color`.",
    "color_dark_theme": "Color on a dark theme. Wins over `color`.",
    "hover_color": "Color while the mouse is over the icon. Opt-in: nothing changes unless set.",
    "hover_color_light_theme": "Hover color on a light theme. Falls back to `hover_color`.",
    "hover_color_dark_theme": "Hover color on a dark theme. Falls back to `hover_color`.",
    "selected_color": "Color when the item is selected (item views).",
    "selected_color_light_theme": "Selected color on a light theme.",
    "selected_color_dark_theme": "Selected color on a dark theme.",
    "opacity": "Overall opacity from 0 to 1 (multiplied with color alpha). Not 0 to 100.",
    "width": "Overrides the width of `size`. Same accepted forms as `size`.",
    "height": "Overrides the height of `size`. Same accepted forms as `size`.",
    "rotate": "Static rotation in degrees, any angle (wraps at 360). A number, not `\"90deg\"`.",
    "rotate_overflow": (
        "`True` keeps the original size while rotating (corners may be clipped); "
        "`False` shrinks the icon so nothing is clipped."
    ),
    "spin": "Continuous rotation. Shorthand for `animation=\"spin\"`; cannot be combined with another animation.",
    "spin_period": "Seconds per turn for the spin animation. Positive number.",
    "animation": "Built-in effect: `\"spin\"`, `\"pulse\"`, `\"breathe\"`, `\"ping\"` or `\"bounce\"`. `None` for none.",
    "animation_period": (
        "Seconds per cycle (positive). Defaults: pulse 1, breathe 2, ping 1, bounce 1; "
        "spin uses `spin_period`."
    ),
    "animation_depth": (
        "Effect strength from 0 to 1. Defaults: pulse 0.25, breathe 0.7, ping 1, bounce 0.25. "
        "Not allowed with spin, or without an animation."
    ),
    "autoplay": (
        "Play the icon's own SMIL animation automatically. `False` stops on the finished frame "
        "until `play()` is called."
    ),
    "speed": "Playback speed multiplier for the icon's own animation. Must be greater than 0.",
    "h_flip": "Flip horizontally.",
    "v_flip": "Flip vertically.",
    "qss": "Tag for QSS grouping; style with `IconWidget[qss~=\"tag\"]` selectors.",
    "fallback": (
        "Icon name shown when loading fails. `None` shows nothing; when unset, the library's "
        "placeholder (or the configured default) is shown."
    ),
    "parent": "Parent `QWidget`.",
    "options": "Other rendering options, same names and values as `get_icon`.",
    "args": "Extra positional arguments passed to the target adapter (tab index, tree column).",
}

METHOD_DOCS: dict[str, str] = {
    "iconName": "Current icon name.",
    "setIcon": "Change the icon by name.",
    "setSize": "Change the size (same forms as `size`).",
    "setColor": "Set the color or color mapping; `None` restores the default.",
    "setColorLightTheme": "Set the light-theme color; `None` restores the default.",
    "setColorDarkTheme": "Set the dark-theme color; `None` restores the default.",
    "setOpacity": "Set the opacity, 0 to 1.",
    "setRotation": "Set the static rotation in degrees.",
    "setRotateOverflow": "Set whether rotation keeps the original size.",
    "isAnimated": "True once the icon data is loaded and has a playable SMIL animation.",
    "isPlaying": "True while the icon's own animation is running.",
    "play": "Start or resume the icon's own animation.",
    "pause": "Pause the icon's own animation on the current frame.",
    "replay": "Restart the icon's own animation from the beginning.",
    "setSpeed": "Set the playback speed multiplier (greater than 0).",
    "setAnimation": "Start a built-in effect, or stop it with `None`.",
    "setSpin": "Start or stop the spin effect.",
    "setFlips": "Set horizontal and vertical flip together.",
}

_EXAMPLE_PREAMBLE = "from PySide6.QtWidgets import QApplication, QPushButton\n"


def _format_default(param: library.Param) -> str:
    """把参数的默认值转成表格里的文字。"""
    if param.kind in ("var_positional", "var_keyword"):
        return "any number"
    if param.default is None:
        return "required"
    if param.default == "...":
        return "unset"
    return f"`{param.default}`"


def signature_block(sig: library.Signature, call_name: str) -> str:
    """把签名排版成多行代码块（不是可运行的 Python，标为 text）。

    Args:
        sig: 签名。
        call_name: 展示用的名称，如 ``IconWidget``。

    Returns:
        Markdown 代码块文本。
    """
    lines = [f"{call_name}("]
    star_done = any(p.kind == "var_positional" for p in sig.params)
    for param in sig.params:
        if param.kind == "keyword" and not star_done:
            lines.append("    *,")
            star_done = True
        prefix = {"var_positional": "*", "var_keyword": "**"}.get(param.kind, "")
        text = f"    {prefix}{param.name}"
        if param.annotation:
            text += f": {param.annotation}"
        if param.default is not None:
            text += f" = {param.default}"
        lines.append(text + ",")
    ret = f" -> {sig.returns}" if sig.returns else ""
    lines.append(f"){ret}")
    return "```text\n" + "\n".join(lines) + "\n```"


def param_table(sig: library.Signature) -> str:
    """生成参数说明表。

    Args:
        sig: 签名。

    Returns:
        Markdown 表格文本。
    """
    rows = ["| Parameter | Default | Meaning |", "| --- | --- | --- |"]
    for param in sig.params:
        meaning = PARAM_DOCS.get(param.name, "See the pyside-iconify documentation.")
        rows.append(f"| `{param.name}` | {_format_default(param)} | {meaning} |")
    return "\n".join(rows)


def _overview() -> str:
    return f"""# pyside-iconify overview

Library version this reference was generated for: {library.LIB_VERSION}.

pyside-iconify gives Qt's `QIcon` an Iconify data source. Icons are fetched by name
(for example `mdi:home`) from the Iconify ecosystem on first use, cached on disk and
rendered locally. It supports PySide6 and PyQt6 (primary), PyQt5 and PySide2 (compatible).
It is not affiliated with the Iconify project.

## Install

```bash
pip install "pyside-iconify[pyside6]"   # or [pyqt6], [pyqt5], [pyside2]
```

Without an extra the library installs but brings no Qt; it uses whichever binding the
program has already imported.

## Which entry point?

| Need | Use | Returns |
| --- | --- | --- |
| A standalone icon in a layout; animation; hover color | `IconWidget(icon, ...)` | a `QWidget` |
| An icon for any widget or item view that takes a `QIcon` | `get_icon(icon, ...)` | `QIcon` |
| Put an icon on an existing button, action, tab, list or tree item, or window in one call | `set_icon(target, icon, ...)` | `QIcon` (also applied) |
| A static image | `get_pixmap(icon, ...)` | `QPixmap` |

The first parameter of all four is named `icon`, and it is positional: write
`get_icon("mdi:home")`, not `get_icon(name="mdi:home")`.

## Icon names

An icon name is `prefix:name`. Both parts use only lowercase letters, digits and hyphens
and start with a letter or digit. The prefix is the icon set (`mdi`, `lucide`, `line-md`).
Names are not guessable: there are hundreds of thousands of icons. Find real ones with the
`search_icons` tool and verify every name with `check_icons` before using it.

## Minimal example

```python
from PySide6.QtWidgets import QApplication, QPushButton
from pyside_iconify import IconWidget, get_icon, set_icon

app = QApplication([])

icon = IconWidget("mdi:home", size=24, color="red")   # standalone icon widget
button = QPushButton("Settings")
button.setIcon(get_icon("mdi:cog", size=20))           # a standard QIcon
set_icon(button, "mdi:home", size=20, hover_color="red")  # or apply it and add a hover color

app.exec()
```

## Rules that prevent most mistakes

- Create the `QApplication` first, and create widgets and icons on the main thread.
- Invalid values raise (`InvalidColorError`, `InvalidSizeError`, ...); nothing silently
  falls back. Check values before shipping.
- `get_icon`, `get_pixmap` and `set_icon` produce static images: no animation parameters
  and no hover on a bare `QIcon`. Use `IconWidget` for animation, `set_icon` or
  `IconWidget` for hover.
- A multi-color icon ignores a single `color`; pass a `{{original: new}}` mapping.

## Suggested workflow with this server

1. Read the topic you need with `get_reference` before writing code.
2. Find icons with `search_icons`; verify every icon name with `check_icons`.
3. Run the finished code through `check_code`.
"""


def _icon_widget() -> str:
    sigs = library.load_signatures()
    methods = "\n".join(
        f"| `{m.name}({', '.join(p.name for p in m.params)})` | {METHOD_DOCS.get(m.name, '')} |"
        for m in sigs.widget_methods
    )
    return f"""# IconWidget

A fixed-size widget that draws one icon. It can sit in any layout and supports hover
color, built-in effects and the icon's own animation. Create it after the `QApplication`,
on the main thread.

{signature_block(sigs.widget_init, "IconWidget")}

{param_table(sigs.widget_init)}

## Methods

| Method | Effect |
| --- | --- |
{methods}

There are no `setHoverColor` or `setLightColor` methods; hover and theme colors are set
through the constructor, or `setColorLightTheme` / `setColorDarkTheme` for theme colors.

## Signals

- `loaded(str)`: the icon data is ready; the argument is the icon name.
- `failed(str, object)`: loading or rendering failed (once per icon name); the arguments
  are the icon name and the exception.
- `statusChanged(str)`: one of `"empty"`, `"loading"`, `"ready"`, `"missing"`, `"error"`.

While loading, the widget draws nothing. A confirmed missing icon draws the `fallback`
icon, nothing, or a built-in placeholder, depending on `fallback`.

## Example

```python
from pyside_iconify import IconWidget

spinner = IconWidget("line-md:loading-loop", size=48)             # plays by itself
home = IconWidget("mdi:home", size="1.5em", color_dark_theme="white", hover_color="red")
pulse = IconWidget("mdi:cog", animation="pulse", animation_period=1.5, animation_depth=0.3)
```
"""


def _get_icon() -> str:
    sigs = library.load_signatures()
    return f"""# get_icon and get_pixmap

`get_icon` returns a standard `QIcon` that works with any widget or item view. It is the
right choice for lists, trees, menus and toolbars. `get_pixmap` returns a static `QPixmap`.

{signature_block(sigs.functions["get_icon"], "get_icon")}

{param_table(sigs.functions["get_icon"])}

{signature_block(sigs.functions["get_pixmap"], "get_pixmap")}

`get_pixmap` takes the same options as `get_icon`.

## What these do NOT support

- Hover colors: a bare `QIcon` cannot express hover. Use `set_icon(button, icon, hover_color=...)`
  for buttons or `IconWidget(icon, hover_color=...)` for a standalone icon.
- Animation parameters (`animation`, `autoplay`, `speed`, ...): a `QIcon` cannot move. A
  self-animating icon (such as `line-md:loading-loop`) shows only its finished frame. Use
  `IconWidget` to play it.
- `selected_color` and its theme variants are supported here (and in `set_icon`), but not
  by `IconWidget`.

## Example

```python
from pyside_iconify import get_icon, get_pixmap

home = get_icon("mdi:home", size=20, color_light_theme="black", color_dark_theme="white")
flipped = get_icon("mdi:cog", rotate=90, h_flip=True, opacity=0.8)
picture = get_pixmap("mdi:home", size=64, color="red")
```
"""


def _set_icon() -> str:
    sigs = library.load_signatures()
    return f"""# set_icon

Puts an icon on an existing target in one call and returns the `QIcon` that was applied.

{signature_block(sigs.functions["set_icon"], "set_icon")}

{param_table(sigs.functions["set_icon"])}

Options are the options of `get_icon`, plus `hover_color`, `hover_color_light_theme` and
`hover_color_dark_theme`. Anything else is an error.

## Targets

| Target type | Extra positional argument | Effect |
| --- | --- | --- |
| `QAbstractButton` (buttons) | none | Sets the button icon; hover color is applied when a `hover_color*` option is given |
| `QAction` | none | Sets the action icon |
| `QTabWidget` | tab index | `set_icon(tabs, "mdi:home", 0)` sets the icon of tab 0 |
| `QListWidgetItem` | none | Sets the item icon |
| `QTreeWidgetItem` | column (default 0) | `set_icon(item, "mdi:home", 1)` sets column 1 |
| `QStandardItem` | none | Sets the item icon |
| any other `QWidget` | none | Sets the window icon |

An unsupported target raises `UnsupportedTargetError`. Support for a custom type is added
with `register_icon_target(target_type, applier)`, where `applier(target, icon, *args)`
applies the `QIcon`.

Hover is opt-in: without a `hover_color*` option there is no hover effect.

## Example

```python
from pyside_iconify import set_icon

set_icon(button, "mdi:cog", size=20, hover_color="red")
set_icon(tabs, "mdi:home", 0, size=16)
set_icon(window, "mdi:home", size=32)
```
"""


def _colors() -> str:
    return """# Colors

## Accepted color values

| Form | Example | Notes |
| --- | --- | --- |
| CSS / SVG color name | `"red"`, `"rebeccapurple"` | Resolved by Qt |
| HEX | `"#f00"`, `"#ff0000"`, `"#ff000080"` | 3, 4, 6 or 8 digits. The 8-digit form is `#RRGGBBAA` (alpha last, CSS order), not Qt's `#AARRGGBB` |
| `rgb()` / `rgba()` | `"rgb(255, 0, 0)"`, `"rgba(255, 0, 0, 0.5)"` | Comma separated. Channels are integers 0-255 or percentages; alpha is 0-1 or a percentage |
| `hsl()` / `hsla()` | `"hsl(210, 50%, 40%)"` | Comma separated. Saturation and lightness must be percentages |
| Tuple | `(255, 0, 0)`, `(255, 0, 0, 128)` | 3 or 4 integers, 0-255 |
| `"transparent"` | | Fully transparent |
| `QColor`, `Qt.GlobalColor` | `QColor("red")`, `Qt.GlobalColor.red` | Qt objects |

Anything else raises `InvalidColorError`; an unparseable color never turns black silently.

## Single color versus mapping

- A single color recolors the parts of the icon drawn with `currentColor`. Monochrome
  icons are entirely `currentColor`.
- Multi-color icons (brand logos, flags) hard-code their colors and ignore a single color.
  To recolor them, pass a `{original: replacement}` mapping. `check_icons` lists an icon's
  fixed colors in `fixed_colors`.
- The key `"currentColor"` may be used in a mapping to recolor the `currentColor` parts.
- The keys of a mapping are the ORIGINAL colors. `color={"light": ..., "dark": ...}` is
  wrong; use `color_light_theme` and `color_dark_theme`.

```python
from pyside_iconify import IconWidget

logo = IconWidget("logos:google-icon", size=32, color={"#4285f4": "red"})
tinted = IconWidget("mdi:home", color="#d4af37")
themed = IconWidget("mdi:home", color_light_theme="black", color_dark_theme="white")
```

## Theme and state colors

| Parameter | Where | Meaning |
| --- | --- | --- |
| `color` | all entry points | Base color; `None` follows the widget text color and the theme |
| `color_light_theme`, `color_dark_theme` | all | Win over `color` on a light or dark theme |
| `hover_color`, `hover_color_light_theme`, `hover_color_dark_theme` | `IconWidget`, `set_icon` | Hover color, opt-in |
| `selected_color`, `selected_color_light_theme`, `selected_color_dark_theme` | `get_icon`, `set_icon` | Selected item color |

With no color set, icons follow the widget's text color and switch between light and dark
themes automatically. Disabled icons fade (alpha) instead of turning gray.
"""


def _sizes() -> str:
    return """# Sizes

| Form | Example | Meaning |
| --- | --- | --- |
| Number | `24` | Square, in logical pixels |
| Tuple or list | `(24, 16)` | Width, height |
| `QSize` | `QSize(24, 16)` | Width, height (must be positive) |
| Pixel string | `"24px"` | Square pixels |
| Em string | `"1.5em"` | Follows the widget font height (the application font for `get_pixmap`) |

A bare numeric string such as `"24"` is invalid: a unit is required. Values must be finite
and positive; booleans are rejected. Invalid sizes raise `InvalidSizeError`.

`width` and `height` override one dimension of `size`. The default size is 24; change it with
`set_default_config(size=...)`.

Sizes are logical pixels. The library renders physical pixels per screen scale factor, so no
`@2x` assets are needed.

```python
from pyside_iconify import IconWidget, get_icon

a = IconWidget("mdi:home", size=32)
b = IconWidget("mdi:home", size=(32, 24))
c = get_icon("mdi:home", size="1.5em")
d = IconWidget("mdi:home", size=24, width=40)
```
"""


def _animation() -> str:
    return """# Animation

There are two independent mechanisms.

## 1. Built-in effects (IconWidget only)

| `animation=` | Effect | Default period | Default `animation_depth` |
| --- | --- | --- | --- |
| `"spin"` | Continuous rotation | `spin_period` (1 s) | not allowed |
| `"pulse"` | Scales down and back | 1 s | 0.25 |
| `"breathe"` | Fades and back | 2 s | 0.7 |
| `"ping"` | Ripple that expands | 1 s | 1 |
| `"bounce"` | Jumps up and back | 1 s | 0.25 |

- `animation_period` is seconds per cycle (positive number).
- `animation_depth` is the strength, 0 to 1. It cannot be used with `"spin"` or without an
  animation (`InvalidAnimationError`).
- `spin=True` is shorthand for `animation="spin"` and cannot be combined with a different
  animation.
- `ping` and `bounce` draw the icon at 1 / (1 + depth) of the widget to leave room for the
  ripple or jump.
- `get_icon` accepts `spin`, but not the other effects; it has no `animation` parameter.

```python
from pyside_iconify import IconWidget

loading = IconWidget("mdi:cog", animation="spin", animation_period=2)
alert = IconWidget("mdi:home", animation="ping", animation_depth=0.5)
```

## 2. The icon's own animation (SMIL)

Some Iconify sets (`line-md`, `meteocons`, `svg-spinners`, `eos-icons`, ...) contain icons
that animate themselves. `IconWidget` plays them with no extra code.

```python
from pyside_iconify import IconWidget

looping = IconWidget("line-md:loading-loop", size=48)
once = IconWidget("line-md:account", autoplay=False, speed=0.5)
once.play()
once.setSpeed(2)
```

- Controls: `autoplay`, `speed`, and the methods `play()`, `pause()`, `replay()`,
  `setSpeed()`, `isAnimated()`, `isPlaying()`.
- Only SMIL is supported (`<animate>`, `<set>`, `<animateTransform>`, `<animateMotion>`). CSS
  animation, scripts, Lottie and GIF are not played. An icon that uses an unsupported SMIL
  feature is drawn as a static image of its finished state, and a warning is logged once.
- `get_icon`, `get_pixmap` and `set_icon` return static images: a self-animating icon shows
  its finished frame. Use `IconWidget` for the animated version.
- Animated frames are cached as bitmaps. Many large looping icons can exceed the default
  32 MiB cache; raise it with `set_cache_limits(pixmap_mib=...)`.
- `check_icons` reports `animated: true` for icons that animate themselves.
"""


_PITFALLS: list[tuple[str, str, str]] = [
    ("`get_icon(name=\"mdi:home\")`", "`get_icon(\"mdi:home\")` or `get_icon(icon=\"mdi:home\")`", "The parameter is named `icon`, not `name`."),
    ("Inventing icon names such as `mdi:home-filled`", "Find names with `search_icons`, verify with `check_icons`", "A missing icon shows a placeholder at run time."),
    ("`light_color=` / `dark_color=`", "`color_light_theme=` / `color_dark_theme=`", "Those are the real parameter names."),
    ("`color={\"light\": \"#fff\", \"dark\": \"#000\"}`", "`color_light_theme=\"#fff\", color_dark_theme=\"#000\"`", "A mapping's keys are the original colors to replace."),
    ("`class_name=` or `style=`", "`qss=\"tag\"` plus `setStyleSheet()` on the widget", "There is no CSS class; `qss` is a tag for QSS selectors."),
    ("`scale=2`", "`size=48`", "There is no scale parameter; set the size."),
    ("`get_icon(..., hover_color=...)`", "`set_icon(button, icon, hover_color=...)` or `IconWidget(icon, hover_color=...)`", "A bare `QIcon` cannot express hover."),
    ("`get_icon(..., animation=\"pulse\")`", "`IconWidget(icon, animation=\"pulse\")`", "A `QIcon` cannot animate."),
    ("`color=\"red\"` on a multi-color icon", "`color={\"#4285f4\": \"red\"}`", "Fixed colors ignore a single color; check `fixed_colors` with `check_icons`."),
    ("`rotate=\"90deg\"`", "`rotate=90`", "A number of degrees."),
    ("`opacity=50`", "`opacity=0.5`", "Opacity runs from 0 to 1."),
    ("`size=\"24\"`", "`size=24` or `size=\"24px\"`", "A string size needs a unit."),
    ("`spin=True, animation=\"pulse\"`", "Use only one of them", "They conflict (`InvalidAnimationError`)."),
    ("`animation=\"spin\", animation_depth=0.5`", "Remove `animation_depth`", "Depth does not apply to spin."),
    ("`\"#80ff0000\"` meaning alpha first", "`\"#ff000080\"`", "The 8-digit HEX is `#RRGGBBAA` (alpha last)."),
    ("`widget.setLightColor(...)`", "`widget.setColorLightTheme(...)`", "Only the documented setter names exist."),
    ("A grid of hundreds of `IconWidget`", "An item view with `get_icon`", "`IconWidget` is for standalone icon slots."),
    ("Creating icons before the `QApplication`", "Create the `QApplication` first", "`NoApplicationError`."),
    ("Creating widgets or icons from a worker thread", "Use the main thread", "`WrongThreadError`."),
    ("`pip install pyside-iconify` and expecting Qt", "`pip install \"pyside-iconify[pyside6]\"`", "Without an extra no Qt binding is installed."),
]


def _pitfalls() -> str:
    rows = ["| Wrong | Right | Why |", "| --- | --- | --- |"]
    rows.extend(f"| {wrong} | {right} | {why} |" for wrong, right, why in _PITFALLS)
    return "# Common mistakes\n\n" + "\n".join(rows) + (
        "\n\nRun finished code through `check_code`; it catches the parameter, value and "
        "icon-name mistakes above automatically.\n"
    )


def _runtime() -> str:
    return """# Runtime requirements and configuration

## Qt application and threads

- A `QApplication` must exist before any widget or icon is created (`NoApplicationError`).
- Widgets and icons must be created on the main thread (`WrongThreadError`).

## Choosing a Qt binding

Import your own binding as usual; the library follows it. Order of choice:

1. The environment variable `PYSIDE_ICONIFY_QT_API` (`pyside6`, `pyqt6`, `pyqt5` or `pyside2`).
2. The binding the program already imported before `pyside_iconify`.
3. The first installed one: PySide6, PyQt6, PyQt5, PySide2.

Never mix bindings in one process. On Qt 5, sharp icons on high-DPI screens need
`Qt.AA_UseHighDpiPixmaps` set before the `QApplication` is created.

## Loading, missing and failed icons

Icons download on first use and are cached on disk. While loading, an icon is blank. A
confirmed missing icon shows a placeholder and emits `failed`. Preload with
`load_icons([...])`; its result has `wait(timeout_ms)` (main thread only).

## Defaults

```python
from pyside_iconify import set_default_config

set_default_config(size=20, color_dark_theme="white", fallback="mdi:home")
```

Fields: `size`, `color`, `color_light_theme`, `color_dark_theme`, `opacity`, `fallback`,
`disabled_opacity`, `spin_period`. Passing `None` restores the built-in value.
`set_cache_limits(pixmap_mib=..., data_entries=...)` adjusts cache sizes.

## Offline use

Pack icons at release time with `python -m pyside_iconify.pack -o icons.json`, then call
`load_bundle("icons.json")` at startup. `set_offline(True)` forbids network access. Local data
always wins over the network.

## Logging

The library logs through the standard `logging` module under the name `pyside_iconify`; it
is silent by default.
"""


@dataclass(frozen=True, slots=True)
class Topic:
    """一个参考主题。

    Attributes:
        key: 主题名。
        summary: 一句话说明。
        render: 生成正文的函数。
    """

    key: str
    summary: str
    render: Callable[[], str]


TOPICS: tuple[Topic, ...] = (
    Topic("overview", "What the library is, which entry point to use, icon names, rules", _overview),
    Topic("icon_widget", "IconWidget: full signature, methods and signals", _icon_widget),
    Topic("get_icon", "get_icon and get_pixmap: signature, and what they do not support", _get_icon),
    Topic("set_icon", "set_icon: putting icons on buttons, actions, tabs, items, windows", _set_icon),
    Topic("colors", "Every accepted color form, mappings, theme and state colors", _colors),
    Topic("sizes", "Every accepted size form", _sizes),
    Topic("animation", "Built-in effects and the icon's own SMIL animation", _animation),
    Topic("pitfalls", "Wrong -> right table of common mistakes", _pitfalls),
    Topic("runtime", "QApplication, threads, Qt binding, defaults, offline, logging", _runtime),
)
TOPIC_KEYS: tuple[str, ...] = tuple(topic.key for topic in TOPICS)


def run(topic: str | None = None) -> str:
    """返回指定主题的参考文档；不指定则返回主题目录。

    Args:
        topic: 主题名；None 返回目录。

    Returns:
        Markdown 文本。

    Raises:
        InputError: 主题名不存在。
        LibraryStubError: 读不到主库的类型存根。
    """
    if topic is None:
        lines = [
            "# pyside-iconify reference topics",
            "",
            f"Generated for pyside-iconify {library.LIB_VERSION}. Call get_reference with one of:",
            "",
            *(f"- `{t.key}`: {t.summary}" for t in TOPICS),
            "",
            "Start with `overview`. Verify icon names with `check_icons` and finished code with `check_code`.",
        ]
        return "\n".join(lines) + "\n"
    for item in TOPICS:
        if item.key == topic:
            return item.render()
    raise InputError(f"unknown topic {topic!r}; choose one of: {', '.join(TOPIC_KEYS)}")


def register(mcp: FastMCP) -> None:
    """把本工具注册到服务上。

    本模块用了 ``from __future__ import annotations``，注册函数里的标注是字符串，
    FastMCP 会按模块全局名解析，所以标注里只能用模块级导入的名字。

    Args:
        mcp: FastMCP 服务实例。
    """

    @mcp.tool(name=NAME, description=DESCRIPTION, annotations=OFFLINE_READ)
    def get_reference(
        topic: Annotated[
            Literal[
                "overview",
                "icon_widget",
                "get_icon",
                "set_icon",
                "colors",
                "sizes",
                "animation",
                "pitfalls",
                "runtime",
            ]
            | None,
            Field(description="Topic to read. Omit to list all topics."),
        ] = None,
    ) -> str:
        """返回指定主题的参考文档。"""
        try:
            return run(topic)
        except (InputError, library.LibraryStubError) as error:
            raise ToolError(str(error)) from error
