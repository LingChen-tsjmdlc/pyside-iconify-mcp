# pyside-iconify-mcp

Help your AI assistant write correct `pyside-iconify` code.

English | [中文](https://github.com/LingChen-tsjmdlc/pyside-iconify-mcp/blob/main/docs/readme/README.zh-CN.md) | [日本語](https://github.com/LingChen-tsjmdlc/pyside-iconify-mcp/blob/main/docs/readme/README.ja.md) | [한국어](https://github.com/LingChen-tsjmdlc/pyside-iconify-mcp/blob/main/docs/readme/README.ko.md) | [Español](https://github.com/LingChen-tsjmdlc/pyside-iconify-mcp/blob/main/docs/readme/README.es.md) | [Français](https://github.com/LingChen-tsjmdlc/pyside-iconify-mcp/blob/main/docs/readme/README.fr.md) | [Deutsch](https://github.com/LingChen-tsjmdlc/pyside-iconify-mcp/blob/main/docs/readme/README.de.md) | [Русский](https://github.com/LingChen-tsjmdlc/pyside-iconify-mcp/blob/main/docs/readme/README.ru.md) | [Português (BR)](https://github.com/LingChen-tsjmdlc/pyside-iconify-mcp/blob/main/docs/readme/README.pt-BR.md)

An [MCP](https://modelcontextprotocol.io) server for
[pyside-iconify](https://github.com/LingChen-tsjmdlc/pyside-iconify). It lets an AI
assistant look up real icons, read the library's exact usage, and check the code it
wrote, instead of guessing.

> This project is **not** affiliated with the Iconify project.

## Why

AI assistants often get `pyside-iconify` code wrong in ways that only show up at
run time:

- they invent icon names that do not exist (`mdi:home-filled`)
- they use parameter names that do not exist, or that belong to a different
  entry point (`get_icon(..., hover_color=...)`)
- they pass a single color to a multi-color icon and expect it to change
- they pick `get_icon` when they need an animated icon

This server lets the assistant look things up and check its work instead of
guessing.

## Tools

| Tool            | What it does                                                                                                        | Needs network |
| --------------- | ------------------------------------------------------------------------------------------------------------------- | ------------- |
| `search_icons`  | Find real icons by keyword, using the official Iconify search API                                                   | yes           |
| `check_icons`   | Check that icon names exist; report whether each is multi-color or animated; suggest similar icons for missing ones | yes           |
| `get_reference` | Return the exact, version-matched usage of the library by topic                                                     | no            |
| `check_code`    | Check the `pyside-iconify` calls in a piece of Python code, without running it                                      | optional      |

All four are read-only. The server never touches your project files and never runs
your code. The only network access is to the public Iconify API
(`https://api.iconify.design`); results are cached in memory for an hour.

### search_icons

Input: `query` (keywords; several words must all match), optional `prefix` (an icon set
such as `mdi`), optional `limit` (1 to 100, default 20).

Output: `status` (`ok` or `unavailable`), `icons` (a list of `prefix:name`),
`collections` (name, license and size of the icon sets involved). `unavailable` means the
lookup failed, for example without network; it does not mean nothing exists.

### check_icons

Input: `names`, a list of 1 to 50 icon names.

Output: one entry per name.

| `status`       | Meaning                                                                          |
| -------------- | -------------------------------------------------------------------------------- |
| `ok`           | The icon exists. Also reports `monotone`, `fixed_colors`, `animated` and `notes` |
| `not_found`    | The icon (or its icon set) does not exist. Includes `suggestions`                |
| `invalid_name` | Not of the form `prefix:name`                                                    |
| `unavailable`  | The check failed (for example no network). Says nothing about whether it exists  |

The monotone, color and animation results are computed by `pyside-iconify` itself, so
they match what the library does at run time.

### get_reference

Input: optional `topic`. Without a topic it lists them: `overview`, `icon_widget`,
`get_icon`, `set_icon`, `colors`, `sizes`, `animation`, `pitfalls`, `runtime`.

Output: Markdown. The signatures are generated from the installed `pyside-iconify`, so
they always match its version; explanations and examples are written by hand and tested
against the library.

### check_code

Input: `code` (Python source), optional `verify_icon_names` (default true).

Output: `ok` (true when there are no errors), `issues` (line, column, severity, code,
message, suggestion), `skipped` (what could not be checked), `checked` (counts).

It looks for:

- imports of names or modules that do not exist
- unknown parameters, parameters used on the wrong entry point, missing or duplicated
  arguments
- invalid values: `size`, colors, `opacity`, `rotate`, `animation`, periods, `speed`
- conflicting options (`spin=True` with another animation, `animation_depth` with spin)
- malformed icon names, and icon names that do not exist
- a single color on a multi-color icon, and animated icons used with `get_icon`

What it promises: when it returns `ok: true`, the usage it could read directly from the
code (parameter names, literal values, literal icon names) is correct. What it cannot
know is listed under `skipped` instead of being guessed: values that come from variables
or function calls, `*args` / `**kwargs`, and anything that only goes wrong at run time
(no `QApplication`, widgets created off the main thread). It never reports an error it is
not sure about.

## Setup

Add it to your AI client as a stdio server that runs `uvx pyside-iconify-mcp`.

### Claude Code

```bash
claude mcp add --transport stdio pyside-iconify -- uvx pyside-iconify-mcp
```

Add `--scope project` to store it in the project's `.mcp.json` and share it with your team.
See the [Claude Code documentation](https://docs.anthropic.com/en/docs/claude-code/mcp).

### ChatGPT and Codex

The ChatGPT desktop app, the Codex CLI and the Codex IDE extension share one MCP configuration.

```bash
codex mcp add pyside-iconify -- uvx pyside-iconify-mcp
```

Or add this to `~/.codex/config.toml`:

```toml
[mcp_servers.pyside-iconify]
command = "uvx"
args = ["pyside-iconify-mcp"]
```

See the [Codex documentation](https://developers.openai.com/codex/mcp).

### Cursor

Create `.cursor/mcp.json` in your project, or `~/.cursor/mcp.json` to use it in every project:

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "type": "stdio",
            "command": "uvx",
            "args": ["pyside-iconify-mcp"]
        }
    }
}
```

See the [Cursor documentation](https://cursor.com/docs/context/mcp).

### OpenCode

Add it to your `opencode.json`. Here `command` is a single array that includes the arguments:

```json
{
    "$schema": "https://opencode.ai/config.json",
    "mcp": {
        "pyside-iconify": {
            "type": "local",
            "command": ["uvx", "pyside-iconify-mcp"],
            "enabled": true
        }
    }
}
```

See the [OpenCode documentation](https://opencode.ai/docs/mcp-servers/).

### VS Code

Create `.vscode/mcp.json` in your project. VS Code uses `servers` as the top-level key, not
`mcpServers`:

```json
{
    "servers": {
        "pyside-iconify": {
            "type": "stdio",
            "command": "uvx",
            "args": ["pyside-iconify-mcp"]
        }
    }
}
```

You can also run `MCP: Add Server` from the Command Palette, choose `Command (stdio)` and enter
`uvx pyside-iconify-mcp`. See the
[VS Code documentation](https://code.visualstudio.com/docs/copilot/customization/mcp-servers).

### WorkBuddy

Create or edit `~/.workbuddy/mcp.json` (the file name has no leading dot):

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "uvx",
            "args": ["pyside-iconify-mcp"]
        }
    }
}
```

A new server is not enabled automatically: open the custom connectors entry at the top right of
the connector management page and click `Trust` on it.

### CodeBuddy

The command below is for the CodeBuddy CLI:

```bash
codebuddy mcp add --scope user pyside-iconify -- uvx pyside-iconify-mcp
```

Use `--scope project` to store it in the project's `.mcp.json` instead. See the
[CodeBuddy documentation](https://www.codebuddy.ai/docs/cli/mcp).

### TRAE

Open Settings, then MCP, choose `Add`, then `Create Manually`, and paste:

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "uvx",
            "args": ["pyside-iconify-mcp"]
        }
    }
}
```

For a single project, turn on `Enable Project MCP` on the same page and put the same JSON in
`.trae/mcp.json`. See the [TRAE documentation](https://docs.trae.ai/ide/add-mcp-servers).

### Other clients

Clients that use an `mcpServers` JSON config:

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "uvx",
            "args": ["pyside-iconify-mcp"]
        }
    }
}
```

The exact config file and key names differ between clients; check your client's
documentation for how to add a local (stdio) MCP server.

### Run from a checkout

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "uv",
            "args": [
                "run",
                "--directory",
                "/path/to/pyside-iconify-mcp",
                "pyside-iconify-mcp"
            ]
        }
    }
}
```

If your client cannot start `uv`, point it at the program installed in the project's virtual
environment instead (create it first with `uv sync`): `.venv/Scripts/pyside-iconify-mcp.exe` on
Windows, `.venv/bin/pyside-iconify-mcp` on macOS and Linux.

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "/path/to/pyside-iconify-mcp/.venv/Scripts/pyside-iconify-mcp.exe"
        }
    }
}
```

## Requirements

Python 3.10 to 3.14. The server depends on `pyside-iconify` (without any Qt extra, so
Qt is not installed) and on [FastMCP](https://gofastmcp.com) 4.1.x. The version of
`pyside-iconify` it was built against is pinned to a minor range; a newer minor version
of the library needs a matching release of this server.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --group test
uv run pytest -v
uv run pyside-iconify-mcp
```

The tests do not use the network. Every tool lives in its own file under
`src/pyside_iconify_mcp/tools/`, named after the tool; shared code is in `common/`. See
[docs/architecture.md](https://github.com/LingChen-tsjmdlc/pyside-iconify-mcp/blob/main/docs/architecture.md)
for the layout and how to add a tool.

## License

[MIT](https://github.com/LingChen-tsjmdlc/pyside-iconify-mcp/blob/main/LICENSE). Icon collections are subject to their own licenses.
