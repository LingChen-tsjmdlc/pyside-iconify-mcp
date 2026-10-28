# pyside-iconify-mcp

AI アシスタントに、正しい `pyside-iconify` のコードを書かせるために。

[English](../../README.md) | [中文](README.zh-CN.md) | **日本語** | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

[pyside-iconify](https://github.com/LingChen-tsjmdlc/pyside-iconify) 用の
[MCP](https://modelcontextprotocol.io) サーバーです。AI アシスタントが、推測ではなく、
実在するアイコンを調べ、ライブラリの正確な使い方を読み、自分が書いたコードを検査できるようにします。

> このプロジェクトは Iconify プロジェクトとは**無関係**です。

## なぜ必要か

AI アシスタントは `pyside-iconify` のコードで、実行時にしか分からない間違いをよく犯します。

- 存在しないアイコン名をでっち上げる（`mdi:home-filled`）
- 存在しないパラメータ名を使う、または別の入口のパラメータを間違った場所で使う
  （`get_icon(..., hover_color=...)`）
- 複数色のアイコンに単色を渡し、色が変わると思い込む
- アニメーションするアイコンが必要なのに `get_icon` を選ぶ

このサーバーは、アシスタントが推測する代わりに調べ、自分の仕事を確認できるようにします。

## ツール

| ツール          | 内容                                                                                                   | ネットワーク |
| --------------- | ------------------------------------------------------------------------------------------------------ | ------------ |
| `search_icons`  | Iconify 公式の検索 API で、キーワードから実在するアイコンを探す                                        | 必要         |
| `check_icons`   | アイコン名が実在するか確認し、複数色か・アニメーションするかを報告し、存在しない名前には近い候補を示す | 必要         |
| `get_reference` | ライブラリのバージョンに一致した正確な使い方を、トピックごとに返す                                     | 不要         |
| `check_code`    | Python コード中の `pyside-iconify` の呼び出しを、実行せずに検査する                                    | 任意         |

4 つとも読み取り専用です。サーバーはプロジェクトのファイルに触れず、コードも実行しません。
ネットワークで接続するのは Iconify の公開 API（`https://api.iconify.design`）だけで、
結果はメモリ上に 1 時間キャッシュされます。

### search_icons

入力：`query`（キーワード。複数の語はすべて一致する必要があります）、任意の `prefix`
（`mdi` などのアイコンセット）、任意の `limit`（1 から 100、既定は 20）。

出力：`status`（`ok` または `unavailable`）、`icons`（`prefix:name` のリスト）、
`collections`（関係するアイコンセットの名前・ライセンス・総数）。`unavailable` は、
ネットワークがないなどで検索に失敗したことを表し、「存在しない」という意味ではありません。

### check_icons

入力：`names`。1 から 50 個のアイコン名のリスト。

出力：名前ごとに 1 件。

| `status`       | 意味                                                                       |
| -------------- | -------------------------------------------------------------------------- |
| `ok`           | アイコンが存在する。`monotone`、`fixed_colors`、`animated`、`notes` も返す |
| `not_found`    | アイコン（またはそのアイコンセット）が存在しない。`suggestions` を含む     |
| `invalid_name` | `prefix:name` の形式ではない                                               |
| `unavailable`  | 確認に失敗した（ネットワークがないなど）。存在するかどうかは分からない     |

単色かどうか、色、アニメーションの判定は `pyside-iconify` 自身が行うため、
ライブラリの実行時の動作と一致します。

### get_reference

入力：任意の `topic`。省略するとトピック一覧を返します：`overview`、`icon_widget`、
`get_icon`、`set_icon`、`colors`、`sizes`、`animation`、`pitfalls`、`runtime`。

出力：Markdown。シグネチャはインストール済みの `pyside-iconify` から生成されるため、
常にそのバージョンと一致します。説明と例は手書きで、ライブラリに対してテストされています。

### check_code

入力：`code`（Python のソースコード）、任意の `verify_icon_names`（既定は true）。

出力：`ok`（エラーがなければ true）、`issues`（行、列、重大度、コード、メッセージ、提案）、
`skipped`（検査できなかったもの）、`checked`（件数）。

次のものを検出します。

- 存在しない名前やモジュールのインポート
- 未知のパラメータ、間違った入口で使われたパラメータ、不足または重複した引数
- 不正な値：`size`、色、`opacity`、`rotate`、`animation`、周期、`speed`
- 矛盾するオプション（`spin=True` と別のアニメーション、spin に対する `animation_depth`）
- 形式が正しくないアイコン名、および存在しないアイコン名
- 複数色アイコンへの単色指定、アニメーションするアイコンを `get_icon` で使うこと

約束できるのは次の点です。`ok: true` が返ったとき、コードから直接読み取れた使い方
（パラメータ名、リテラルの値、リテラルのアイコン名）は正しいということ。
分からない部分は推測せず `skipped` に挙げます。変数や関数呼び出しから来る値、`*args` / `**kwargs`、
実行時にしか起きない問題（`QApplication` がない、メインスレッド以外でウィジェットを作る）がそれにあたります。
確信のないエラーは報告しません。

## セットアップ

`uvx pyside-iconify-mcp` を実行する stdio サーバーとして AI クライアントに追加します。

### Claude Code

```bash
claude mcp add --transport stdio pyside-iconify -- uvx pyside-iconify-mcp
```

`--scope project` を付けると、プロジェクトの `.mcp.json` に保存され、チームで共有できます。
詳しくは [Claude Code のドキュメント](https://docs.anthropic.com/en/docs/claude-code/mcp)を参照してください。

### ChatGPT と Codex

ChatGPT デスクトップアプリ、Codex CLI、Codex IDE 拡張機能は、同じ MCP 設定を共有します。

```bash
codex mcp add pyside-iconify -- uvx pyside-iconify-mcp
```

または、次の内容を `~/.codex/config.toml` に追加します。

```toml
[mcp_servers.pyside-iconify]
command = "uvx"
args = ["pyside-iconify-mcp"]
```

詳しくは [Codex のドキュメント](https://developers.openai.com/codex/mcp)を参照してください。

### Cursor

プロジェクトに `.cursor/mcp.json` を作成します。すべてのプロジェクトで使うには `~/.cursor/mcp.json` を作成します。

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

詳しくは [Cursor のドキュメント](https://cursor.com/docs/context/mcp)を参照してください。

### OpenCode

`opencode.json` に追加します。ここでは `command` は引数も含めた 1 つの配列です。

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

詳しくは [OpenCode のドキュメント](https://opencode.ai/docs/mcp-servers/)を参照してください。

### VS Code

プロジェクトに `.vscode/mcp.json` を作成します。VS Code の最上位キーは `mcpServers` ではなく `servers` です。

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

コマンドパレットで `MCP: Add Server` を実行し、`Command (stdio)` を選んで
`uvx pyside-iconify-mcp` を入力することもできます。詳しくは
[VS Code のドキュメント](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)を参照してください。

### WorkBuddy

`~/.workbuddy/mcp.json` を作成または編集します（ファイル名の先頭にドットは付けません）。

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

追加したサーバーは自動では有効になりません。コネクター管理ページの右上にあるカスタムコネクターの入口を開き、
そのサーバーで `Trust` をクリックしてください。

### CodeBuddy

次のコマンドは CodeBuddy CLI 用です。

```bash
codebuddy mcp add --scope user pyside-iconify -- uvx pyside-iconify-mcp
```

代わりに `--scope project` を使うと、プロジェクトの `.mcp.json` に保存されます。詳しくは
[CodeBuddy のドキュメント](https://www.codebuddy.ai/docs/cli/mcp)を参照してください。

### TRAE

Settings を開き、MCP に進み、`Add`、`Create Manually` の順に選んで、次を貼り付けます。

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

特定のプロジェクトだけで使う場合は、同じページで `Enable Project MCP` をオンにし、同じ JSON を
`.trae/mcp.json` に置きます。詳しくは [TRAE のドキュメント](https://docs.trae.ai/ide/add-mcp-servers)を参照してください。

### その他のクライアント

`mcpServers` 形式の JSON 設定を使うクライアント：

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

設定ファイルやキー名はクライアントごとに異なります。ローカル（stdio）MCP サーバーの追加方法は、
お使いのクライアントのドキュメントを参照してください。

### チェックアウトから実行する

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

お使いのクライアントが `uv` を起動できない場合は、プロジェクトの仮想環境にインストールされたプログラムを直接指定します
（先に `uv sync` で環境を作成してください）。Windows では `.venv/Scripts/pyside-iconify-mcp.exe`、
macOS と Linux では `.venv/bin/pyside-iconify-mcp` です。

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "/path/to/pyside-iconify-mcp/.venv/Scripts/pyside-iconify-mcp.exe"
        }
    }
}
```

## 動作要件

Python 3.10 から 3.14。サーバーは `pyside-iconify`（Qt の extra は付けないので Qt はインストールされません）と
[FastMCP](https://gofastmcp.com) 4.1.x に依存します。ビルドに使った `pyside-iconify` のバージョンは
マイナーバージョンの範囲に固定されており、ライブラリの新しいマイナーバージョンには、
このサーバーの対応リリースが必要です。

## 開発

[uv](https://docs.astral.sh/uv/) が必要です。

```bash
uv sync --group test
uv run pytest -v
uv run pyside-iconify-mcp
```

テストはネットワークを使いません。各ツールは `src/pyside_iconify_mcp/tools/` 以下の、
ツール名と同じ名前のファイルにあります。共通のコードは `common/` にあります。
構成と新しいツールの追加方法は [docs/architecture.md](../architecture.md)（英語）を参照してください。

## ライセンス

[MIT](../../LICENSE)。アイコンコレクションはそれぞれのライセンスに従います。
