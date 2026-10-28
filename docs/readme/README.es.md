# pyside-iconify-mcp

Ayuda a tu asistente de IA a escribir código correcto con `pyside-iconify`.

[English](../../README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | **Español** | [Français](README.fr.md) | [Deutsch](README.de.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

Un servidor [MCP](https://modelcontextprotocol.io) para
[pyside-iconify](https://github.com/LingChen-tsjmdlc/pyside-iconify). Permite que un asistente de IA
busque iconos reales, lea el uso exacto de la biblioteca y revise el código que ha escrito, en lugar de
adivinar.

> Este proyecto **no** está afiliado al proyecto Iconify.

## Por qué

Los asistentes de IA suelen cometer errores en el código de `pyside-iconify` que solo se descubren al
ejecutarlo:

- inventan nombres de icono que no existen (`mdi:home-filled`)
- usan nombres de parámetro que no existen, o que pertenecen a otro punto de entrada
  (`get_icon(..., hover_color=...)`)
- pasan un solo color a un icono de varios colores y esperan que cambie
- eligen `get_icon` cuando necesitan un icono animado

Este servidor permite que el asistente consulte y compruebe su trabajo en lugar de adivinar.

## Herramientas

| Herramienta     | Qué hace                                                                                                                                    | Necesita red |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| `search_icons`  | Busca iconos reales por palabra clave con la API de búsqueda oficial de Iconify                                                             | sí           |
| `check_icons`   | Comprueba que los nombres de icono existen; indica si cada uno es de varios colores o animado; sugiere iconos parecidos para los que faltan | sí           |
| `get_reference` | Devuelve el uso exacto de la biblioteca, acorde a su versión, por tema                                                                      | no           |
| `check_code`    | Revisa las llamadas a `pyside-iconify` en un fragmento de código Python, sin ejecutarlo                                                     | opcional     |

Las cuatro son de solo lectura. El servidor nunca toca los archivos de tu proyecto ni ejecuta tu código.
El único acceso a la red es a la API pública de Iconify (`https://api.iconify.design`); los resultados se
guardan en memoria durante una hora.

### search_icons

Entrada: `query` (palabras clave; si hay varias, deben coincidir todas), `prefix` opcional (un conjunto de
iconos, como `mdi`) y `limit` opcional (de 1 a 100, 20 por defecto).

Salida: `status` (`ok` o `unavailable`), `icons` (una lista de `prefix:name`) y `collections` (nombre,
licencia y tamaño de los conjuntos de iconos implicados). `unavailable` significa que la consulta falló,
por ejemplo por falta de red; no significa que no exista nada.

### check_icons

Entrada: `names`, una lista de 1 a 50 nombres de icono.

Salida: una entrada por nombre.

| `status`       | Significado                                                                          |
| -------------- | ------------------------------------------------------------------------------------ |
| `ok`           | El icono existe. También informa de `monotone`, `fixed_colors`, `animated` y `notes` |
| `not_found`    | El icono (o su conjunto de iconos) no existe. Incluye `suggestions`                  |
| `invalid_name` | No tiene la forma `prefix:name`                                                      |
| `unavailable`  | La comprobación falló (por ejemplo, sin red). No dice nada sobre si existe           |

Los resultados sobre monocromía, colores y animación los calcula la propia `pyside-iconify`, así que
coinciden con lo que hace la biblioteca en tiempo de ejecución.

### get_reference

Entrada: `topic` opcional. Sin tema, los enumera: `overview`, `icon_widget`, `get_icon`, `set_icon`,
`colors`, `sizes`, `animation`, `pitfalls`, `runtime`.

Salida: Markdown. Las firmas se generan a partir de la `pyside-iconify` instalada, por lo que siempre
coinciden con su versión; las explicaciones y los ejemplos están escritos a mano y probados con la
biblioteca.

### check_code

Entrada: `code` (código fuente Python) y `verify_icon_names` opcional (por defecto, true).

Salida: `ok` (true cuando no hay errores), `issues` (línea, columna, gravedad, código, mensaje,
sugerencia), `skipped` (lo que no se pudo comprobar) y `checked` (recuentos).

Busca:

- importaciones de nombres o módulos que no existen
- parámetros desconocidos, parámetros usados en el punto de entrada equivocado, argumentos que faltan o
  están duplicados
- valores no válidos: `size`, colores, `opacity`, `rotate`, `animation`, periodos, `speed`
- opciones en conflicto (`spin=True` con otra animación, `animation_depth` con spin)
- nombres de icono mal formados y nombres de icono que no existen
- un solo color en un icono de varios colores, e iconos animados usados con `get_icon`

Lo que promete: cuando devuelve `ok: true`, el uso que pudo leer directamente del código (nombres de
parámetro, valores literales, nombres de icono literales) es correcto. Lo que no puede saber se lista en
`skipped` en lugar de adivinarse: valores que provienen de variables o llamadas a funciones,
`*args` / `**kwargs`, y todo lo que solo falla en tiempo de ejecución (sin `QApplication`, widgets creados
fuera del hilo principal). Nunca informa de un error del que no esté seguro.

## Configuración

Añádelo a tu cliente de IA como servidor stdio que ejecute `uvx pyside-iconify-mcp`.

### Claude Code

```bash
claude mcp add --transport stdio pyside-iconify -- uvx pyside-iconify-mcp
```

Añade `--scope project` para guardarlo en el `.mcp.json` del proyecto y compartirlo con tu equipo.
Consulta la [documentación de Claude Code](https://docs.anthropic.com/en/docs/claude-code/mcp).

### ChatGPT y Codex

La aplicación de escritorio de ChatGPT, la CLI de Codex y la extensión de Codex para IDE comparten una misma
configuración de MCP.

```bash
codex mcp add pyside-iconify -- uvx pyside-iconify-mcp
```

O añade esto a `~/.codex/config.toml`:

```toml
[mcp_servers.pyside-iconify]
command = "uvx"
args = ["pyside-iconify-mcp"]
```

Consulta la [documentación de Codex](https://developers.openai.com/codex/mcp).

### Cursor

Crea `.cursor/mcp.json` en tu proyecto, o `~/.cursor/mcp.json` para usarlo en todos los proyectos:

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

Consulta la [documentación de Cursor](https://cursor.com/docs/context/mcp).

### OpenCode

Añádelo a tu `opencode.json`. Aquí `command` es un único array que incluye los argumentos:

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

Consulta la [documentación de OpenCode](https://opencode.ai/docs/mcp-servers/).

### VS Code

Crea `.vscode/mcp.json` en tu proyecto. VS Code usa `servers` como clave de nivel superior, no `mcpServers`:

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

También puedes ejecutar `MCP: Add Server` desde la paleta de comandos, elegir `Command (stdio)` e introducir
`uvx pyside-iconify-mcp`. Consulta la
[documentación de VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers).

### WorkBuddy

Crea o edita `~/.workbuddy/mcp.json` (el nombre del archivo no empieza por punto):

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

Un servidor nuevo no se activa automáticamente: abre la entrada de conectores personalizados, arriba a la
derecha en la página de gestión de conectores, y pulsa `Trust` en él.

### CodeBuddy

El siguiente comando es para la CLI de CodeBuddy:

```bash
codebuddy mcp add --scope user pyside-iconify -- uvx pyside-iconify-mcp
```

Usa `--scope project` para guardarlo en el `.mcp.json` del proyecto. Consulta la
[documentación de CodeBuddy](https://www.codebuddy.ai/docs/cli/mcp).

### TRAE

Abre Settings, entra en MCP, elige `Add` y después `Create Manually`, y pega:

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

Para un solo proyecto, activa `Enable Project MCP` en la misma página y coloca el mismo JSON en
`.trae/mcp.json`. Consulta la [documentación de TRAE](https://docs.trae.ai/ide/add-mcp-servers).

### Otros clientes

Clientes que usan una configuración JSON con `mcpServers`:

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

El archivo de configuración y los nombres de las claves varían según el cliente; consulta la documentación
del tuyo para saber cómo añadir un servidor MCP local (stdio).

### Ejecutar desde una copia del repositorio

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

Si tu cliente no puede iniciar `uv`, apunta directamente al programa instalado en el entorno virtual del
proyecto (créalo antes con `uv sync`): `.venv/Scripts/pyside-iconify-mcp.exe` en Windows,
`.venv/bin/pyside-iconify-mcp` en macOS y Linux.

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "/path/to/pyside-iconify-mcp/.venv/Scripts/pyside-iconify-mcp.exe"
        }
    }
}
```

## Requisitos

Python 3.10 a 3.14. El servidor depende de `pyside-iconify` (sin ningún extra de Qt, por lo que no se
instala Qt) y de [FastMCP](https://gofastmcp.com) 4.1.x. La versión de `pyside-iconify` con la que se
construyó está fijada a un rango de versión menor; una versión menor más reciente de la biblioteca
requiere una publicación correspondiente de este servidor.

## Desarrollo

Requiere [uv](https://docs.astral.sh/uv/).

```bash
uv sync --group test
uv run pytest -v
uv run pyside-iconify-mcp
```

Las pruebas no usan la red. Cada herramienta está en su propio archivo dentro de
`src/pyside_iconify_mcp/tools/`, con el nombre de la herramienta; el código compartido está en `common/`.
La estructura y la forma de añadir una herramienta están en
[docs/architecture.md](../architecture.md) (en inglés).

## Licencia

[MIT](../../LICENSE). Las colecciones de iconos están sujetas a sus propias licencias.
