# pyside-iconify-mcp

Ajude seu assistente de IA a escrever código correto com `pyside-iconify`.

[English](../../README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Русский](README.ru.md) | **Português (BR)**

Um servidor [MCP](https://modelcontextprotocol.io) para
[pyside-iconify](https://github.com/LingChen-tsjmdlc/pyside-iconify). Ele permite que um assistente de IA
procure ícones reais, leia o uso exato da biblioteca e verifique o código que escreveu, em vez de adivinhar.

> Este projeto **não** é afiliado ao projeto Iconify.

## Por que

Assistentes de IA costumam errar no código de `pyside-iconify` de formas que só aparecem em tempo de
execução:

- inventam nomes de ícones que não existem (`mdi:home-filled`)
- usam nomes de parâmetros que não existem, ou que pertencem a outro ponto de entrada
  (`get_icon(..., hover_color=...)`)
- passam uma única cor para um ícone de várias cores e esperam que ele mude
- escolhem `get_icon` quando precisam de um ícone animado

Este servidor permite que o assistente consulte e confira o próprio trabalho, em vez de adivinhar.

## Ferramentas

| Ferramenta      | O que faz                                                                                                                                | Precisa de rede |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `search_icons`  | Encontra ícones reais por palavra-chave, usando a API de busca oficial do Iconify                                                        | sim             |
| `check_icons`   | Confere se os nomes de ícones existem; informa se cada um tem várias cores ou é animado; sugere ícones parecidos para os que não existem | sim             |
| `get_reference` | Retorna o uso exato da biblioteca, compatível com a sua versão, por tema                                                                 | não             |
| `check_code`    | Verifica as chamadas a `pyside-iconify` em um trecho de código Python, sem executá-lo                                                    | opcional        |

As quatro são somente leitura. O servidor nunca mexe nos arquivos do seu projeto nem executa o seu código.
O único acesso à rede é à API pública do Iconify (`https://api.iconify.design`); os resultados ficam em
cache na memória por uma hora.

### search_icons

Entrada: `query` (palavras-chave; com várias palavras, todas precisam coincidir), `prefix` opcional (um
conjunto de ícones, como `mdi`) e `limit` opcional (de 1 a 100, padrão 20).

Saída: `status` (`ok` ou `unavailable`), `icons` (uma lista de `prefix:name`) e `collections` (nome,
licença e tamanho dos conjuntos de ícones envolvidos). `unavailable` significa que a consulta falhou, por
exemplo sem rede; não significa que nada existe.

### check_icons

Entrada: `names`, uma lista de 1 a 50 nomes de ícones.

Saída: uma entrada por nome.

| `status`       | Significado                                                                            |
| -------------- | -------------------------------------------------------------------------------------- |
| `ok`           | O ícone existe. Também informa `monotone`, `fixed_colors`, `animated` e `notes`        |
| `not_found`    | O ícone (ou o seu conjunto de ícones) não existe. Inclui `suggestions`                 |
| `invalid_name` | Não tem a forma `prefix:name`                                                          |
| `unavailable`  | A verificação falhou (por exemplo, sem rede). Não diz nada sobre a existência do ícone |

Os resultados sobre monocromia, cores e animação são calculados pela própria `pyside-iconify`, então
coincidem com o que a biblioteca faz em tempo de execução.

### get_reference

Entrada: `topic` opcional. Sem tema, lista os temas: `overview`, `icon_widget`, `get_icon`, `set_icon`,
`colors`, `sizes`, `animation`, `pitfalls`, `runtime`.

Saída: Markdown. As assinaturas são geradas a partir da `pyside-iconify` instalada, portanto sempre
correspondem à sua versão; as explicações e os exemplos são escritos à mão e testados com a biblioteca.

### check_code

Entrada: `code` (código-fonte Python) e `verify_icon_names` opcional (padrão true).

Saída: `ok` (true quando não há erros), `issues` (linha, coluna, gravidade, código, mensagem, sugestão),
`skipped` (o que não pôde ser verificado) e `checked` (contagens).

Ele procura:

- importações de nomes ou módulos que não existem
- parâmetros desconhecidos, parâmetros usados no ponto de entrada errado, argumentos ausentes ou duplicados
- valores inválidos: `size`, cores, `opacity`, `rotate`, `animation`, períodos, `speed`
- opções em conflito (`spin=True` com outra animação, `animation_depth` com spin)
- nomes de ícones malformados e nomes de ícones que não existem
- uma única cor em um ícone de várias cores, e ícones animados usados com `get_icon`

O que ele promete: quando retorna `ok: true`, o uso que ele conseguiu ler diretamente do código (nomes de
parâmetros, valores literais, nomes de ícones literais) está correto. O que ele não consegue saber é listado
em `skipped` em vez de ser adivinhado: valores vindos de variáveis ou de chamadas de função,
`*args` / `**kwargs`, e tudo o que só dá errado em tempo de execução (sem `QApplication`, widgets criados
fora da thread principal). Ele nunca relata um erro de que não tenha certeza.

## Configuração

Adicione-o ao seu cliente de IA como um servidor stdio que executa `uvx pyside-iconify-mcp`.

### Claude Code

```bash
claude mcp add --transport stdio pyside-iconify -- uvx pyside-iconify-mcp
```

Adicione `--scope project` para guardá-lo no `.mcp.json` do projeto e compartilhá-lo com a sua equipe.
Veja a [documentação do Claude Code](https://docs.anthropic.com/en/docs/claude-code/mcp).

### ChatGPT e Codex

O aplicativo de desktop do ChatGPT, a CLI do Codex e a extensão do Codex para IDE compartilham uma única
configuração de MCP.

```bash
codex mcp add pyside-iconify -- uvx pyside-iconify-mcp
```

Ou adicione isto a `~/.codex/config.toml`:

```toml
[mcp_servers.pyside-iconify]
command = "uvx"
args = ["pyside-iconify-mcp"]
```

Veja a [documentação do Codex](https://developers.openai.com/codex/mcp).

### Cursor

Crie `.cursor/mcp.json` no seu projeto, ou `~/.cursor/mcp.json` para usá-lo em todos os projetos:

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

Veja a [documentação do Cursor](https://cursor.com/docs/context/mcp).

### OpenCode

Adicione ao seu `opencode.json`. Aqui `command` é um único array que inclui os argumentos:

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

Veja a [documentação do OpenCode](https://opencode.ai/docs/mcp-servers/).

### VS Code

Crie `.vscode/mcp.json` no seu projeto. O VS Code usa `servers` como chave de nível superior, e não `mcpServers`:

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

Você também pode executar `MCP: Add Server` na paleta de comandos, escolher `Command (stdio)` e digitar
`uvx pyside-iconify-mcp`. Veja a
[documentação do VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers).

### WorkBuddy

Crie ou edite `~/.workbuddy/mcp.json` (o nome do arquivo não começa com ponto):

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

Um servidor novo não é ativado automaticamente: abra a entrada de conectores personalizados, no canto superior
direito da página de gerenciamento de conectores, e clique em `Trust` nele.

### CodeBuddy

O comando abaixo é para a CLI do CodeBuddy:

```bash
codebuddy mcp add --scope user pyside-iconify -- uvx pyside-iconify-mcp
```

Use `--scope project` para guardá-lo no `.mcp.json` do projeto. Veja a
[documentação do CodeBuddy](https://www.codebuddy.ai/docs/cli/mcp).

### TRAE

Abra Settings, entre em MCP, escolha `Add` e depois `Create Manually`, e cole:

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

Para um único projeto, ative `Enable Project MCP` na mesma página e coloque o mesmo JSON em
`.trae/mcp.json`. Veja a [documentação do TRAE](https://docs.trae.ai/ide/add-mcp-servers).

### Outros clientes

Clientes que usam uma configuração JSON com `mcpServers`:

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

O arquivo de configuração e os nomes das chaves variam entre os clientes; consulte a documentação do seu
para saber como adicionar um servidor MCP local (stdio).

### Executar a partir de uma cópia do repositório

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

Se o seu cliente não conseguir iniciar o `uv`, aponte diretamente para o programa instalado no ambiente virtual
do projeto (crie-o antes com `uv sync`): `.venv/Scripts/pyside-iconify-mcp.exe` no Windows,
`.venv/bin/pyside-iconify-mcp` no macOS e no Linux.

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

Python 3.10 a 3.14. O servidor depende de `pyside-iconify` (sem nenhum extra de Qt, então o Qt não é
instalado) e do [FastMCP](https://gofastmcp.com) 4.1.x. A versão de `pyside-iconify` com a qual ele foi
construído está fixada em uma faixa de versão menor; uma versão menor mais nova da biblioteca exige uma
publicação correspondente deste servidor.

## Desenvolvimento

Requer o [uv](https://docs.astral.sh/uv/).

```bash
uv sync --group test
uv run pytest -v
uv run pyside-iconify-mcp
```

Os testes não usam a rede. Cada ferramenta fica em seu próprio arquivo em
`src/pyside_iconify_mcp/tools/`, com o nome da ferramenta; o código compartilhado fica em `common/`. A
estrutura e a forma de adicionar uma ferramenta estão em [docs/architecture.md](../architecture.md)
(em inglês).

## Licença

[MIT](../../LICENSE). As coleções de ícones estão sujeitas às suas próprias licenças.
