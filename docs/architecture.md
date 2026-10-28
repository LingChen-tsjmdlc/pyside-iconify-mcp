# Architecture

This page is for contributors: how the code is laid out, how a tool is built, and the
rules that keep it tidy as tools are added. Usage is in the [README](../README.md).

## Layout

```text
src/pyside_iconify_mcp/
├── server.py          # creates the FastMCP server and registers the tools; no tool logic
├── __main__.py        # python -m pyside_iconify_mcp
├── tools/             # one file per tool, named after the tool
│   ├── __init__.py    # the TOOLS list and register_all()
│   ├── search_icons.py
│   ├── check_icons.py
│   ├── get_reference.py
│   └── check_code.py
└── common/            # code shared by tools, and wrappers around the outside world
    ├── library.py     # the only file that imports pyside-iconify
    ├── iconify_api.py # Iconify public API client (urllib, in-memory cache)
    ├── lookup.py      # check icon names in bulk and suggest similar ones
    ├── colors.py      # CSS / SVG standard color names
    ├── errors.py      # InputError
    └── tool_annotations.py
```

`tests/` mirrors this: `tests/tools/test_<tool>.py`, `tests/common/test_<module>.py`.

## How a tool is built

Every file in `tools/` has the same four parts:

| Part            | What it is                                                                                                     |
| --------------- | -------------------------------------------------------------------------------------------------------------- |
| `NAME`          | The tool name. Must equal the file name                                                                        |
| `DESCRIPTION`   | What the AI reads to decide when to call the tool                                                              |
| `run(...)`      | The real logic. Plain Python, easy to test, raises `InputError` for bad input                                  |
| `register(mcp)` | Registers the tool on the server: declares the parameters the AI sees and turns `InputError` into a tool error |

Keep logic in `run()`. `register()` only describes the parameters and calls `run()`.

## Adding a tool

1. Create `tools/<tool_name>.py` with the four parts above.
2. Add the module to `TOOLS` in `tools/__init__.py`.
3. Add `tests/tools/test_<tool_name>.py`.

If something is useful to more than one tool, move it to `common/` instead of importing
one tool from another. If a tool file grows too long to read, turn it into a package of
the same name (`tools/<tool_name>/__init__.py`); import paths do not change.

`register()` is a function inside the module, and FastMCP reads its parameter annotations
to build the tool's schema. If a module uses `from __future__ import annotations`,
annotations in `register()` are strings that FastMCP resolves against the module's
globals, so use only names imported at module level there.

## Rules checked by tests

`tests/test_layout.py` fails when one of these is broken:

| Rule                                                                          | Why                                                           |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Every file in `tools/` is listed in `TOOLS`, and every listed tool has a file | A forgotten step should fail loudly, not silently drop a tool |
| `NAME` equals the file name, and the registered tool name equals `NAME`       | One name everywhere: file, module, tool                       |
| Tools do not import each other                                                | Tools stay independent; shared code goes to `common/`         |
| `common/` does not import `tools/` or `server`                                | Dependencies point one way: `server` to `tools` to `common`   |
| Only `common/library.py` imports `pyside-iconify`                             | One place to fix when the library changes                     |
| No `utils`, `helpers` or `misc`                                               | A shared file needs a name that says what it does             |
| `server.py` defines no tools                                                  | Tool logic lives in `tools/` only                             |

## Why shared code is called `common`

The usual name for this is `utils`, but it tends to become a drawer for anything that did
not fit elsewhere. `common/` has a stricter rule, stated in its `__init__.py`: code goes
there only if at least two tools use it, or if it wraps something outside this project
(the `pyside-iconify` library, the Iconify API, the CSS color names).

## Depending on pyside-iconify

`pyside-iconify` is installed without a Qt extra, so Qt is never installed. `library.py`
uses only the parts of the library that do not import Qt (the top-level package and
`core/`), and reads `__init__.pyi` and `rendering/options.py` as text, because importing
`rendering` would load Qt. The library's download client is not used: it is built on Qt,
so `iconify_api.py` makes its own requests with the standard library.
