# pyside-iconify-mcp

Aidez votre assistant IA à écrire du code `pyside-iconify` correct.

[English](../../README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | **Français** | [Deutsch](README.de.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

Un serveur [MCP](https://modelcontextprotocol.io) pour
[pyside-iconify](https://github.com/LingChen-tsjmdlc/pyside-iconify). Il permet à un assistant IA de
chercher de vraies icônes, de lire l'usage exact de la bibliothèque et de vérifier le code qu'il a écrit,
au lieu de deviner.

> Ce projet n'est **pas** affilié au projet Iconify.

## Pourquoi

Les assistants IA se trompent souvent sur le code `pyside-iconify`, avec des erreurs qui n'apparaissent
qu'à l'exécution :

- ils inventent des noms d'icônes qui n'existent pas (`mdi:home-filled`)
- ils utilisent des noms de paramètres qui n'existent pas, ou qui appartiennent à un autre point d'entrée
  (`get_icon(..., hover_color=...)`)
- ils passent une seule couleur à une icône multicolore et s'attendent à ce qu'elle change
- ils choisissent `get_icon` alors qu'il leur faut une icône animée

Ce serveur permet à l'assistant de se renseigner et de vérifier son travail au lieu de deviner.

## Outils

| Outil           | Rôle                                                                                                                                              | Réseau requis |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| `search_icons`  | Trouve de vraies icônes par mot-clé, avec l'API de recherche officielle d'Iconify                                                                 | oui           |
| `check_icons`   | Vérifie que les noms d'icônes existent ; indique si chacune est multicolore ou animée ; propose des icônes proches pour celles qui n'existent pas | oui           |
| `get_reference` | Renvoie l'usage exact de la bibliothèque, correspondant à sa version, par thème                                                                   | non           |
| `check_code`    | Vérifie les appels à `pyside-iconify` dans un morceau de code Python, sans l'exécuter                                                             | facultatif    |

Les quatre outils sont en lecture seule. Le serveur ne touche jamais aux fichiers de votre projet et
n'exécute jamais votre code. Le seul accès réseau est l'API publique d'Iconify
(`https://api.iconify.design`) ; les résultats sont mis en cache en mémoire pendant une heure.

### search_icons

Entrée : `query` (mots-clés ; avec plusieurs mots, tous doivent correspondre), `prefix` facultatif (un jeu
d'icônes, comme `mdi`) et `limit` facultatif (de 1 à 100, 20 par défaut).

Sortie : `status` (`ok` ou `unavailable`), `icons` (une liste de `prefix:name`) et `collections` (nom,
licence et taille des jeux d'icônes concernés). `unavailable` signifie que la recherche a échoué, par
exemple sans réseau ; cela ne signifie pas que rien n'existe.

### check_icons

Entrée : `names`, une liste de 1 à 50 noms d'icônes.

Sortie : une entrée par nom.

| `status`       | Signification                                                                              |
| -------------- | ------------------------------------------------------------------------------------------ |
| `ok`           | L'icône existe. Indique aussi `monotone`, `fixed_colors`, `animated` et `notes`            |
| `not_found`    | L'icône (ou son jeu d'icônes) n'existe pas. Inclut `suggestions`                           |
| `invalid_name` | Ne respecte pas la forme `prefix:name`                                                     |
| `unavailable`  | La vérification a échoué (par exemple sans réseau). Ne dit rien sur l'existence de l'icône |

Les résultats sur la monochromie, les couleurs et l'animation sont calculés par `pyside-iconify`
elle-même ; ils correspondent donc à ce que fait la bibliothèque à l'exécution.

### get_reference

Entrée : `topic` facultatif. Sans thème, la liste des thèmes est renvoyée : `overview`, `icon_widget`,
`get_icon`, `set_icon`, `colors`, `sizes`, `animation`, `pitfalls`, `runtime`.

Sortie : Markdown. Les signatures sont générées à partir de la `pyside-iconify` installée ; elles
correspondent donc toujours à sa version. Les explications et les exemples sont écrits à la main et testés
avec la bibliothèque.

### check_code

Entrée : `code` (code source Python) et `verify_icon_names` facultatif (true par défaut).

Sortie : `ok` (true quand il n'y a aucune erreur), `issues` (ligne, colonne, gravité, code, message,
suggestion), `skipped` (ce qui n'a pas pu être vérifié) et `checked` (compteurs).

Il recherche :

- des imports de noms ou de modules qui n'existent pas
- des paramètres inconnus, des paramètres utilisés sur le mauvais point d'entrée, des arguments manquants
  ou en double
- des valeurs invalides : `size`, couleurs, `opacity`, `rotate`, `animation`, périodes, `speed`
- des options en conflit (`spin=True` avec une autre animation, `animation_depth` avec spin)
- des noms d'icônes mal formés, et des noms d'icônes qui n'existent pas
- une seule couleur sur une icône multicolore, et des icônes animées utilisées avec `get_icon`

Ce qu'il promet : quand il renvoie `ok: true`, l'usage qu'il a pu lire directement dans le code (noms de
paramètres, valeurs littérales, noms d'icônes littéraux) est correct. Ce qu'il ne peut pas savoir est
listé dans `skipped` au lieu d'être deviné : valeurs issues de variables ou d'appels de fonctions,
`*args` / `**kwargs`, et tout ce qui ne pose problème qu'à l'exécution (pas de `QApplication`, widgets
créés hors du thread principal). Il ne signale jamais une erreur dont il n'est pas sûr.

## Installation

Ajoutez-le à votre client IA comme serveur stdio qui exécute `uvx pyside-iconify-mcp`.

### Claude Code

```bash
claude mcp add --transport stdio pyside-iconify -- uvx pyside-iconify-mcp
```

Ajoutez `--scope project` pour l'enregistrer dans le `.mcp.json` du projet et le partager avec votre équipe.
Voir la [documentation de Claude Code](https://docs.anthropic.com/en/docs/claude-code/mcp).

### ChatGPT et Codex

L'application de bureau ChatGPT, la CLI Codex et l'extension Codex pour IDE partagent une même configuration MCP.

```bash
codex mcp add pyside-iconify -- uvx pyside-iconify-mcp
```

Ou ajoutez ceci à `~/.codex/config.toml` :

```toml
[mcp_servers.pyside-iconify]
command = "uvx"
args = ["pyside-iconify-mcp"]
```

Voir la [documentation de Codex](https://developers.openai.com/codex/mcp).

### Cursor

Créez `.cursor/mcp.json` dans votre projet, ou `~/.cursor/mcp.json` pour l'utiliser dans tous les projets :

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

Voir la [documentation de Cursor](https://cursor.com/docs/context/mcp).

### OpenCode

Ajoutez-le à votre `opencode.json`. Ici, `command` est un seul tableau qui inclut les arguments :

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

Voir la [documentation d'OpenCode](https://opencode.ai/docs/mcp-servers/).

### VS Code

Créez `.vscode/mcp.json` dans votre projet. VS Code utilise `servers` comme clé de premier niveau, et non
`mcpServers` :

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

Vous pouvez aussi lancer `MCP: Add Server` depuis la palette de commandes, choisir `Command (stdio)` et saisir
`uvx pyside-iconify-mcp`. Voir la
[documentation de VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers).

### WorkBuddy

Créez ou modifiez `~/.workbuddy/mcp.json` (le nom du fichier ne commence pas par un point) :

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

Un nouveau serveur n'est pas activé automatiquement : ouvrez l'entrée des connecteurs personnalisés, en haut à
droite de la page de gestion des connecteurs, et cliquez sur `Trust` pour ce serveur.

### CodeBuddy

La commande ci-dessous est destinée à la CLI de CodeBuddy :

```bash
codebuddy mcp add --scope user pyside-iconify -- uvx pyside-iconify-mcp
```

Utilisez `--scope project` pour l'enregistrer plutôt dans le `.mcp.json` du projet. Voir la
[documentation de CodeBuddy](https://www.codebuddy.ai/docs/cli/mcp).

### TRAE

Ouvrez Settings, allez dans MCP, choisissez `Add` puis `Create Manually`, et collez :

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

Pour un seul projet, activez `Enable Project MCP` sur la même page et placez le même JSON dans
`.trae/mcp.json`. Voir la [documentation de TRAE](https://docs.trae.ai/ide/add-mcp-servers).

### Autres clients

Clients qui utilisent une configuration JSON `mcpServers` :

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

Le fichier de configuration et les noms des clés diffèrent d'un client à l'autre ; consultez la
documentation du vôtre pour savoir comment ajouter un serveur MCP local (stdio).

### Lancer depuis une copie du dépôt

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

Si votre client ne peut pas lancer `uv`, pointez directement vers le programme installé dans l'environnement
virtuel du projet (créez-le d'abord avec `uv sync`) : `.venv/Scripts/pyside-iconify-mcp.exe` sous Windows,
`.venv/bin/pyside-iconify-mcp` sous macOS et Linux.

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "/path/to/pyside-iconify-mcp/.venv/Scripts/pyside-iconify-mcp.exe"
        }
    }
}
```

## Prérequis

Python 3.10 à 3.14. Le serveur dépend de `pyside-iconify` (sans extra Qt, donc Qt n'est pas installé) et
de [FastMCP](https://gofastmcp.com) 4.1.x. La version de `pyside-iconify` avec laquelle il a été construit
est limitée à une plage de version mineure ; une version mineure plus récente de la bibliothèque nécessite
une publication correspondante de ce serveur.

## Développement

Nécessite [uv](https://docs.astral.sh/uv/).

```bash
uv sync --group test
uv run pytest -v
uv run pyside-iconify-mcp
```

Les tests n'utilisent pas le réseau. Chaque outil se trouve dans son propre fichier sous
`src/pyside_iconify_mcp/tools/`, nommé d'après l'outil ; le code partagé est dans `common/`. L'organisation
et la façon d'ajouter un outil sont décrites dans [docs/architecture.md](../architecture.md) (en anglais).

## Licence

[MIT](../../LICENSE). Les collections d'icônes sont soumises à leurs propres licences.
