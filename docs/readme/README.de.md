# pyside-iconify-mcp

Hilft Ihrem KI-Assistenten, korrekten `pyside-iconify`-Code zu schreiben.

[English](../../README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | **Deutsch** | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

Ein [MCP](https://modelcontextprotocol.io)-Server für
[pyside-iconify](https://github.com/LingChen-tsjmdlc/pyside-iconify). Er ermöglicht es einem
KI-Assistenten, echte Icons nachzuschlagen, die genaue Verwendung der Bibliothek zu lesen und den
geschriebenen Code zu prüfen, statt zu raten.

> Dieses Projekt steht in **keiner** Verbindung zum Iconify-Projekt.

## Warum

KI-Assistenten machen bei `pyside-iconify`-Code oft Fehler, die erst zur Laufzeit auffallen:

- sie erfinden Icon-Namen, die es nicht gibt (`mdi:home-filled`)
- sie verwenden Parameternamen, die es nicht gibt oder die zu einem anderen Einstiegspunkt gehören
  (`get_icon(..., hover_color=...)`)
- sie übergeben einem mehrfarbigen Icon eine einzelne Farbe und erwarten eine Änderung
- sie wählen `get_icon`, obwohl sie ein animiertes Icon brauchen

Dieser Server lässt den Assistenten nachschlagen und seine Arbeit prüfen, statt zu raten.

## Werkzeuge

| Werkzeug        | Aufgabe                                                                                                                    | Netzwerk nötig |
| --------------- | -------------------------------------------------------------------------------------------------------------------------- | -------------- |
| `search_icons`  | Findet echte Icons per Stichwort über die offizielle Iconify-Such-API                                                      | ja             |
| `check_icons`   | Prüft, ob Icon-Namen existieren; meldet, ob ein Icon mehrfarbig oder animiert ist; schlägt für fehlende Icons ähnliche vor | ja             |
| `get_reference` | Liefert die genaue, zur Version passende Verwendung der Bibliothek nach Thema                                              | nein           |
| `check_code`    | Prüft die `pyside-iconify`-Aufrufe in einem Stück Python-Code, ohne ihn auszuführen                                        | optional       |

Alle vier sind schreibgeschützt. Der Server berührt nie Ihre Projektdateien und führt nie Ihren Code aus.
Der einzige Netzwerkzugriff gilt der öffentlichen Iconify-API (`https://api.iconify.design`); Ergebnisse
werden eine Stunde lang im Arbeitsspeicher zwischengespeichert.

### search_icons

Eingabe: `query` (Stichwörter; bei mehreren Wörtern müssen alle passen), optional `prefix` (ein Icon-Set
wie `mdi`), optional `limit` (1 bis 100, Standard 20).

Ausgabe: `status` (`ok` oder `unavailable`), `icons` (eine Liste von `prefix:name`) und `collections`
(Name, Lizenz und Größe der beteiligten Icon-Sets). `unavailable` bedeutet, dass die Abfrage fehlgeschlagen
ist, zum Beispiel ohne Netzwerk; es bedeutet nicht, dass nichts existiert.

### check_icons

Eingabe: `names`, eine Liste von 1 bis 50 Icon-Namen.

Ausgabe: ein Eintrag pro Name.

| `status`       | Bedeutung                                                                                 |
| -------------- | ----------------------------------------------------------------------------------------- |
| `ok`           | Das Icon existiert. Meldet außerdem `monotone`, `fixed_colors`, `animated` und `notes`    |
| `not_found`    | Das Icon (oder sein Icon-Set) existiert nicht. Enthält `suggestions`                      |
| `invalid_name` | Hat nicht die Form `prefix:name`                                                          |
| `unavailable`  | Die Prüfung ist fehlgeschlagen (etwa ohne Netzwerk). Sagt nichts darüber, ob es existiert |

Die Ergebnisse zu Einfarbigkeit, Farben und Animation berechnet `pyside-iconify` selbst; sie stimmen daher
mit dem Verhalten der Bibliothek zur Laufzeit überein.

### get_reference

Eingabe: optional `topic`. Ohne Thema werden die Themen aufgelistet: `overview`, `icon_widget`, `get_icon`,
`set_icon`, `colors`, `sizes`, `animation`, `pitfalls`, `runtime`.

Ausgabe: Markdown. Die Signaturen werden aus der installierten `pyside-iconify` erzeugt und passen daher
immer zu deren Version; Erklärungen und Beispiele sind von Hand geschrieben und gegen die Bibliothek
getestet.

### check_code

Eingabe: `code` (Python-Quelltext), optional `verify_icon_names` (Standard true).

Ausgabe: `ok` (true, wenn es keine Fehler gibt), `issues` (Zeile, Spalte, Schweregrad, Code, Meldung,
Vorschlag), `skipped` (was nicht geprüft werden konnte) und `checked` (Anzahlen).

Er sucht nach:

- Importen von Namen oder Modulen, die es nicht gibt
- unbekannten Parametern, Parametern am falschen Einstiegspunkt, fehlenden oder doppelten Argumenten
- ungültigen Werten: `size`, Farben, `opacity`, `rotate`, `animation`, Perioden, `speed`
- widersprüchlichen Optionen (`spin=True` mit einer anderen Animation, `animation_depth` mit spin)
- fehlerhaft aufgebauten und nicht existierenden Icon-Namen
- einer einzelnen Farbe bei einem mehrfarbigen Icon und animierten Icons, die mit `get_icon` verwendet werden

Was er zusichert: Gibt er `ok: true` zurück, ist die Verwendung, die er direkt aus dem Code lesen konnte
(Parameternamen, Literalwerte, literale Icon-Namen), korrekt. Was er nicht wissen kann, steht in `skipped`,
statt geraten zu werden: Werte aus Variablen oder Funktionsaufrufen, `*args` / `**kwargs` und alles, was erst
zur Laufzeit schiefgeht (keine `QApplication`, Widgets außerhalb des Hauptthreads erzeugt). Er meldet
niemals einen Fehler, bei dem er sich nicht sicher ist.

## Einrichtung

Fügen Sie es Ihrem KI-Client als stdio-Server hinzu, der `uvx pyside-iconify-mcp` ausführt.

### Claude Code

```bash
claude mcp add --transport stdio pyside-iconify -- uvx pyside-iconify-mcp
```

Mit `--scope project` wird der Eintrag in der `.mcp.json` des Projekts gespeichert und lässt sich mit dem Team
teilen. Siehe die [Claude-Code-Dokumentation](https://docs.anthropic.com/en/docs/claude-code/mcp).

### ChatGPT und Codex

Die ChatGPT-Desktop-App, die Codex-CLI und die Codex-IDE-Erweiterung teilen sich eine MCP-Konfiguration.

```bash
codex mcp add pyside-iconify -- uvx pyside-iconify-mcp
```

Oder fügen Sie Folgendes zu `~/.codex/config.toml` hinzu:

```toml
[mcp_servers.pyside-iconify]
command = "uvx"
args = ["pyside-iconify-mcp"]
```

Siehe die [Codex-Dokumentation](https://developers.openai.com/codex/mcp).

### Cursor

Legen Sie `.cursor/mcp.json` in Ihrem Projekt an, oder `~/.cursor/mcp.json`, um es in jedem Projekt zu nutzen:

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

Siehe die [Cursor-Dokumentation](https://cursor.com/docs/context/mcp).

### OpenCode

Fügen Sie es Ihrer `opencode.json` hinzu. Hier ist `command` ein einzelnes Array, das die Argumente enthält:

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

Siehe die [OpenCode-Dokumentation](https://opencode.ai/docs/mcp-servers/).

### VS Code

Legen Sie `.vscode/mcp.json` in Ihrem Projekt an. VS Code verwendet `servers` als Schlüssel der obersten Ebene,
nicht `mcpServers`:

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

Alternativ führen Sie in der Befehlspalette `MCP: Add Server` aus, wählen `Command (stdio)` und geben
`uvx pyside-iconify-mcp` ein. Siehe die
[VS-Code-Dokumentation](https://code.visualstudio.com/docs/copilot/customization/mcp-servers).

### WorkBuddy

Legen Sie `~/.workbuddy/mcp.json` an oder bearbeiten Sie sie (der Dateiname beginnt nicht mit einem Punkt):

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

Ein neuer Server wird nicht automatisch aktiviert: Öffnen Sie oben rechts auf der Seite zur Verwaltung der
Konnektoren den Eintrag für benutzerdefinierte Konnektoren und klicken Sie dort bei dem Server auf `Trust`.

### CodeBuddy

Der folgende Befehl gilt für die CodeBuddy-CLI:

```bash
codebuddy mcp add --scope user pyside-iconify -- uvx pyside-iconify-mcp
```

Mit `--scope project` wird er stattdessen in der `.mcp.json` des Projekts gespeichert. Siehe die
[CodeBuddy-Dokumentation](https://www.codebuddy.ai/docs/cli/mcp).

### TRAE

Öffnen Sie Settings, gehen Sie zu MCP, wählen Sie `Add` und dann `Create Manually` und fügen Sie ein:

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

Für ein einzelnes Projekt schalten Sie auf derselben Seite `Enable Project MCP` ein und legen dasselbe JSON in
`.trae/mcp.json` ab. Siehe die [TRAE-Dokumentation](https://docs.trae.ai/ide/add-mcp-servers).

### Andere Clients

Clients mit einer `mcpServers`-JSON-Konfiguration:

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

Konfigurationsdatei und Schlüsselnamen unterscheiden sich je nach Client; wie ein lokaler (stdio) MCP-Server
hinzugefügt wird, steht in der Dokumentation Ihres Clients.

### Aus einem Checkout starten

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

Kann Ihr Client `uv` nicht starten, verweisen Sie stattdessen direkt auf das Programm in der virtuellen Umgebung
des Projekts (zuvor mit `uv sync` anlegen): `.venv/Scripts/pyside-iconify-mcp.exe` unter Windows,
`.venv/bin/pyside-iconify-mcp` unter macOS und Linux.

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "/path/to/pyside-iconify-mcp/.venv/Scripts/pyside-iconify-mcp.exe"
        }
    }
}
```

## Voraussetzungen

Python 3.10 bis 3.14. Der Server hängt von `pyside-iconify` (ohne Qt-Extra, daher wird Qt nicht installiert)
und von [FastMCP](https://gofastmcp.com) 4.1.x ab. Die `pyside-iconify`-Version, gegen die er gebaut wurde,
ist auf einen Bereich einer Nebenversion festgelegt; eine neuere Nebenversion der Bibliothek erfordert eine
passende Veröffentlichung dieses Servers.

## Entwicklung

Benötigt [uv](https://docs.astral.sh/uv/).

```bash
uv sync --group test
uv run pytest -v
uv run pyside-iconify-mcp
```

Die Tests nutzen kein Netzwerk. Jedes Werkzeug liegt in einer eigenen, nach ihm benannten Datei unter
`src/pyside_iconify_mcp/tools/`; gemeinsam genutzter Code liegt in `common/`. Aufbau und das Hinzufügen
eines Werkzeugs sind in [docs/architecture.md](../architecture.md) (auf Englisch) beschrieben.

## Lizenz

[MIT](../../LICENSE). Icon-Sammlungen unterliegen ihren eigenen Lizenzen.
