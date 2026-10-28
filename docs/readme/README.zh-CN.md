# pyside-iconify-mcp

让你的 AI 助手写出正确的 `pyside-iconify` 代码。

[English](../../README.md) | **中文** | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

这是 [pyside-iconify](https://github.com/LingChen-tsjmdlc/pyside-iconify) 的
[MCP](https://modelcontextprotocol.io) 服务。它让 AI 助手去查真实存在的图标、读库的准确用法、
检查自己写的代码，而不是凭印象乱猜。

> 本项目 **不是** Iconify 官方项目。

## 为什么需要它

AI 助手写 `pyside-iconify` 代码时，常犯一些运行时才暴露的错误：

- 编造不存在的图标名（`mdi:home-filled`）
- 使用不存在的参数名，或把属于别的入口的参数用错地方（`get_icon(..., hover_color=...)`）
- 给多色图标传单个颜色，却以为会变色
- 需要动画图标时用了 `get_icon`

这个服务让助手去查、去检查，而不是猜。

## 工具

| 工具            | 作用                                                                         | 需要联网 |
| --------------- | ---------------------------------------------------------------------------- | -------- |
| `search_icons`  | 按关键词查找真实存在的图标，使用 Iconify 官方搜索接口                        | 是       |
| `check_icons`   | 核对图标名是否存在；报告图标是否多色、是否带动画；为不存在的图标给出相近建议 | 是       |
| `get_reference` | 按主题返回与库版本一致的准确用法                                             | 否       |
| `check_code`    | 检查一段 Python 代码里的 `pyside-iconify` 调用，不运行代码                   | 可选     |

四个工具都是只读的。服务不会碰你的项目文件，也不会运行你的代码。唯一的网络访问对象是
Iconify 公共 API（`https://api.iconify.design`），结果在内存里缓存一小时。

### search_icons

输入：`query`（关键词；多个词必须同时匹配）、可选的 `prefix`（图标集，如 `mdi`）、
可选的 `limit`（1 到 100，默认 20）。

输出：`status`（`ok` 或 `unavailable`）、`icons`（`prefix:name` 列表）、
`collections`（相关图标集的名称、许可证和图标总数）。`unavailable` 表示查询失败，
比如没有网络；它不代表“不存在”。

### check_icons

输入：`names`，1 到 50 个图标名组成的列表。

输出：每个名字一条结果。

| `status`       | 含义                                                                 |
| -------------- | -------------------------------------------------------------------- |
| `ok`           | 图标存在。同时给出 `monotone`、`fixed_colors`、`animated` 和 `notes` |
| `not_found`    | 图标（或它所在的图标集）不存在。附带 `suggestions`                   |
| `invalid_name` | 不是 `prefix:name` 的形式                                            |
| `unavailable`  | 核对失败（比如没有网络）。这不能说明图标是否存在                     |

单色、颜色和动画的判断由 `pyside-iconify` 自己完成，所以与库在运行时的行为一致。

### get_reference

输入：可选的 `topic`。不传则列出全部主题：`overview`、`icon_widget`、`get_icon`、
`set_icon`、`colors`、`sizes`、`animation`、`pitfalls`、`runtime`。

输出：Markdown。函数签名由已安装的 `pyside-iconify` 生成，所以永远与它的版本一致；
说明和示例是手写的，并且用库来测试过。

### check_code

输入：`code`（Python 源码）、可选的 `verify_icon_names`（默认 true）。

输出：`ok`（没有错误时为 true）、`issues`（行、列、级别、类别、说明、建议）、
`skipped`（没能检查的部分）、`checked`（统计）。

它会检查：

- 导入了不存在的名字或模块
- 未知参数、用在错误入口上的参数、缺少或重复的参数
- 非法取值：`size`、颜色、`opacity`、`rotate`、`animation`、周期、`speed`
- 互相冲突的选项（`spin=True` 同时给了别的动画，`animation_depth` 搭配 spin）
- 格式错误的图标名，以及不存在的图标名
- 对多色图标传单个颜色，以及对动画图标使用 `get_icon`

它承诺的是：返回 `ok: true` 时，凡是能直接从代码里读到的用法（参数名、字面量取值、字面量图标名）都是对的。
它无法知道的部分会列在 `skipped` 里，而不是去猜：来自变量或函数调用的值、`*args` / `**kwargs`，
以及只在运行时才出错的问题（没有 `QApplication`、在非主线程创建控件）。它不会报告自己不确定的错误。

## 安装配置

把它作为 stdio 服务添加到你的 AI 客户端，命令是 `uvx pyside-iconify-mcp`。

### Claude Code

```bash
claude mcp add --transport stdio pyside-iconify -- uvx pyside-iconify-mcp
```

加上 `--scope project`，会把配置存到项目的 `.mcp.json` 里，方便与团队共享。
详见 [Claude Code 文档](https://docs.anthropic.com/en/docs/claude-code/mcp)。

### ChatGPT 与 Codex

ChatGPT 桌面应用、Codex CLI 和 Codex IDE 扩展共用同一份 MCP 配置。

```bash
codex mcp add pyside-iconify -- uvx pyside-iconify-mcp
```

或者把下面的内容加到 `~/.codex/config.toml`：

```toml
[mcp_servers.pyside-iconify]
command = "uvx"
args = ["pyside-iconify-mcp"]
```

详见 [Codex 文档](https://developers.openai.com/codex/mcp)。

### Cursor

在项目里创建 `.cursor/mcp.json`；要在所有项目里使用，则创建 `~/.cursor/mcp.json`：

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

详见 [Cursor 文档](https://cursor.com/docs/context/mcp)。

### OpenCode

加到 `opencode.json` 里。这里的 `command` 是一个数组，参数也写在里面：

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

详见 [OpenCode 文档](https://opencode.ai/docs/mcp-servers/)。

### VS Code

在项目里创建 `.vscode/mcp.json`。VS Code 的顶层键是 `servers`，不是 `mcpServers`：

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

也可以在命令面板运行 `MCP: Add Server`，选择 `Command (stdio)`，然后输入
`uvx pyside-iconify-mcp`。详见
[VS Code 文档](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)。

### WorkBuddy

创建或编辑 `~/.workbuddy/mcp.json`（文件名前面没有点）：

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

新添加的服务不会自动启用：在连接器管理页面右上角打开自定义连接器入口，对它点击 `Trust`（信任）。

### CodeBuddy

下面的命令适用于 CodeBuddy CLI：

```bash
codebuddy mcp add --scope user pyside-iconify -- uvx pyside-iconify-mcp
```

改用 `--scope project` 则存到项目的 `.mcp.json` 里。详见
[CodeBuddy 文档](https://www.codebuddy.ai/docs/cli/mcp)。

### TRAE

打开 Settings，进入 MCP，点击 `Add`，选择 `Create Manually`，粘贴：

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

只想对某个项目生效的话，在同一页面打开 `Enable Project MCP`，并把同样的 JSON 放进
`.trae/mcp.json`。详见 [TRAE 文档](https://docs.trae.ai/ide/add-mcp-servers)。

### 其他客户端

使用 `mcpServers` JSON 配置的客户端：

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

不同客户端的配置文件和键名各不相同，请查阅你所用客户端的文档，了解如何添加本地（stdio）MCP 服务。

### 从源码目录运行

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

如果你的客户端无法启动 `uv`，可以改为指向项目虚拟环境里已安装的程序（先用 `uv sync` 创建环境）：
Windows 上是 `.venv/Scripts/pyside-iconify-mcp.exe`，macOS 和 Linux 上是 `.venv/bin/pyside-iconify-mcp`。

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "/path/to/pyside-iconify-mcp/.venv/Scripts/pyside-iconify-mcp.exe"
        }
    }
}
```

## 运行要求

Python 3.10 到 3.14。服务依赖 `pyside-iconify`（不带任何 Qt extra，所以不会安装 Qt）和
[FastMCP](https://gofastmcp.com) 4.1.x。它所依赖的 `pyside-iconify` 版本被限定在一个次版本范围内；
库出了新的次版本，本服务需要对应发布一个版本。

## 开发

需要 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync --group test
uv run pytest -v
uv run pyside-iconify-mcp
```

测试不使用网络。每个工具都放在 `src/pyside_iconify_mcp/tools/` 下以工具名命名的文件里；
共用代码在 `common/`。目录结构和新增工具的方法见
[docs/architecture.md](../architecture.md)（英文）。

## 许可证

[MIT](../../LICENSE)。图标集合遵循其各自许可。
