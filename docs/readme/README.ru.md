# pyside-iconify-mcp

Помогает вашему ИИ-ассистенту писать правильный код с `pyside-iconify`.

[English](../../README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | **Русский** | [Português (BR)](README.pt-BR.md)

[MCP](https://modelcontextprotocol.io)-сервер для
[pyside-iconify](https://github.com/LingChen-tsjmdlc/pyside-iconify). Он позволяет ИИ-ассистенту искать
настоящие иконки, читать точное описание использования библиотеки и проверять написанный код, вместо того
чтобы угадывать.

> Этот проект **не** связан с проектом Iconify.

## Зачем это нужно

ИИ-ассистенты часто делают в коде с `pyside-iconify` ошибки, которые проявляются только во время
выполнения:

- придумывают имена иконок, которых не существует (`mdi:home-filled`)
- используют несуществующие имена параметров или параметры, относящиеся к другой точке входа
  (`get_icon(..., hover_color=...)`)
- передают один цвет многоцветной иконке и ожидают, что она перекрасится
- выбирают `get_icon`, когда нужна анимированная иконка

Этот сервер позволяет ассистенту искать и проверять свою работу, а не гадать.

## Инструменты

| Инструмент      | Что делает                                                                                                                           | Нужна сеть |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ---------- |
| `search_icons`  | Находит настоящие иконки по ключевому слову через официальный поисковый API Iconify                                                  | да         |
| `check_icons`   | Проверяет, что имена иконок существуют; сообщает, многоцветная ли иконка и анимирована ли она; для несуществующих предлагает похожие | да         |
| `get_reference` | Возвращает точное описание использования библиотеки, соответствующее её версии, по темам                                             | нет        |
| `check_code`    | Проверяет вызовы `pyside-iconify` в куске кода на Python, не выполняя его                                                            | по желанию |

Все четыре инструмента только читают. Сервер никогда не трогает файлы вашего проекта и не выполняет ваш
код. Единственный сетевой доступ — к публичному API Iconify (`https://api.iconify.design`); результаты
кэшируются в памяти на один час.

### search_icons

Вход: `query` (ключевые слова; если слов несколько, должны совпасть все), необязательный `prefix`
(набор иконок, например `mdi`), необязательный `limit` (от 1 до 100, по умолчанию 20).

Выход: `status` (`ok` или `unavailable`), `icons` (список `prefix:name`) и `collections` (название,
лицензия и размер соответствующих наборов иконок). `unavailable` означает, что запрос не удался, например
из-за отсутствия сети; это не значит, что ничего не существует.

### check_icons

Вход: `names` — список из 1–50 имён иконок.

Выход: по одной записи на каждое имя.

| `status`       | Значение                                                                                |
| -------------- | --------------------------------------------------------------------------------------- |
| `ok`           | Иконка существует. Также сообщаются `monotone`, `fixed_colors`, `animated` и `notes`    |
| `not_found`    | Иконка (или её набор) не существует. Содержит `suggestions`                             |
| `invalid_name` | Имя не имеет вид `prefix:name`                                                          |
| `unavailable`  | Проверка не удалась (например, нет сети). Ничего не говорит о том, существует ли иконка |

Результаты об одноцветности, цветах и анимации вычисляет сама `pyside-iconify`, поэтому они совпадают с тем,
что библиотека делает во время выполнения.

### get_reference

Вход: необязательный `topic`. Без темы возвращается список тем: `overview`, `icon_widget`, `get_icon`,
`set_icon`, `colors`, `sizes`, `animation`, `pitfalls`, `runtime`.

Выход: Markdown. Сигнатуры генерируются из установленной `pyside-iconify`, поэтому всегда соответствуют её
версии; пояснения и примеры написаны вручную и проверяются тестами на самой библиотеке.

### check_code

Вход: `code` (исходный код на Python), необязательный `verify_icon_names` (по умолчанию true).

Выход: `ok` (true, если ошибок нет), `issues` (строка, столбец, серьёзность, код, сообщение, подсказка),
`skipped` (что не удалось проверить) и `checked` (количества).

Он находит:

- импорты несуществующих имён или модулей
- неизвестные параметры, параметры, использованные не в той точке входа, пропущенные или повторяющиеся
  аргументы
- недопустимые значения: `size`, цвета, `opacity`, `rotate`, `animation`, периоды, `speed`
- конфликтующие параметры (`spin=True` вместе с другой анимацией, `animation_depth` вместе со spin)
- неправильно составленные и несуществующие имена иконок
- один цвет для многоцветной иконки и анимированные иконки, используемые через `get_icon`

Что он обещает: если возвращено `ok: true`, то использование, которое удалось прочитать прямо из кода
(имена параметров, литеральные значения, литеральные имена иконок), корректно. То, что он узнать не может,
перечисляется в `skipped`, а не угадывается: значения из переменных или вызовов функций, `*args` /
`**kwargs`, а также всё, что ломается только во время выполнения (нет `QApplication`, виджеты созданы не в
главном потоке). Он никогда не сообщает об ошибке, в которой не уверен.

## Настройка

Добавьте его в ваш ИИ-клиент как stdio-сервер, запускающий `uvx pyside-iconify-mcp`.

### Claude Code

```bash
claude mcp add --transport stdio pyside-iconify -- uvx pyside-iconify-mcp
```

Добавьте `--scope project`, чтобы сохранить настройку в `.mcp.json` проекта и делиться ею с командой.
См. [документацию Claude Code](https://docs.anthropic.com/en/docs/claude-code/mcp).

### ChatGPT и Codex

Приложение ChatGPT для компьютера, Codex CLI и расширение Codex для IDE используют одну и ту же настройку MCP.

```bash
codex mcp add pyside-iconify -- uvx pyside-iconify-mcp
```

Или добавьте следующее в `~/.codex/config.toml`:

```toml
[mcp_servers.pyside-iconify]
command = "uvx"
args = ["pyside-iconify-mcp"]
```

См. [документацию Codex](https://developers.openai.com/codex/mcp).

### Cursor

Создайте `.cursor/mcp.json` в проекте или `~/.cursor/mcp.json`, чтобы использовать его во всех проектах:

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

См. [документацию Cursor](https://cursor.com/docs/context/mcp).

### OpenCode

Добавьте в `opencode.json`. Здесь `command` — один массив, включающий и аргументы:

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

См. [документацию OpenCode](https://opencode.ai/docs/mcp-servers/).

### VS Code

Создайте `.vscode/mcp.json` в проекте. В VS Code ключ верхнего уровня называется `servers`, а не `mcpServers`:

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

Можно также выполнить `MCP: Add Server` в палитре команд, выбрать `Command (stdio)` и ввести
`uvx pyside-iconify-mcp`. См. [документацию VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers).

### WorkBuddy

Создайте или отредактируйте `~/.workbuddy/mcp.json` (имя файла не начинается с точки):

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

Новый сервер не включается автоматически: откройте пункт пользовательских коннекторов в правом верхнем углу
страницы управления коннекторами и нажмите для него `Trust`.

### CodeBuddy

Команда ниже предназначена для CodeBuddy CLI:

```bash
codebuddy mcp add --scope user pyside-iconify -- uvx pyside-iconify-mcp
```

С `--scope project` настройка сохраняется в `.mcp.json` проекта. См.
[документацию CodeBuddy](https://www.codebuddy.ai/docs/cli/mcp).

### TRAE

Откройте Settings, перейдите в MCP, выберите `Add`, затем `Create Manually` и вставьте:

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

Чтобы настройка действовала только в одном проекте, включите `Enable Project MCP` на той же странице и поместите
тот же JSON в `.trae/mcp.json`. См. [документацию TRAE](https://docs.trae.ai/ide/add-mcp-servers).

### Другие клиенты

Клиенты, использующие JSON-конфигурацию `mcpServers`:

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

Файл конфигурации и имена ключей различаются от клиента к клиенту; как добавить локальный (stdio)
MCP-сервер, смотрите в документации вашего клиента.

### Запуск из клона репозитория

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

Если ваш клиент не может запустить `uv`, укажите напрямую программу, установленную в виртуальном окружении
проекта (сначала создайте его командой `uv sync`): `.venv/Scripts/pyside-iconify-mcp.exe` в Windows,
`.venv/bin/pyside-iconify-mcp` в macOS и Linux.

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "/path/to/pyside-iconify-mcp/.venv/Scripts/pyside-iconify-mcp.exe"
        }
    }
}
```

## Требования

Python 3.10–3.14. Сервер зависит от `pyside-iconify` (без каких-либо extra для Qt, поэтому Qt не
устанавливается) и от [FastMCP](https://gofastmcp.com) 4.1.x. Версия `pyside-iconify`, с которой он
собран, ограничена диапазоном минорной версии; для более новой минорной версии библиотеки нужен
соответствующий релиз этого сервера.

## Разработка

Нужен [uv](https://docs.astral.sh/uv/).

```bash
uv sync --group test
uv run pytest -v
uv run pyside-iconify-mcp
```

Тесты не используют сеть. Каждый инструмент лежит в отдельном файле в `src/pyside_iconify_mcp/tools/`,
названном по имени инструмента; общий код находится в `common/`. Структура проекта и способ добавления
инструмента описаны в [docs/architecture.md](../architecture.md) (на английском).

## Лицензия

[MIT](../../LICENSE). Коллекции иконок распространяются на условиях собственных лицензий.
