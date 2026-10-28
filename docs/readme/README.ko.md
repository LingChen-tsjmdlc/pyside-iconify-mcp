# pyside-iconify-mcp

AI 어시스턴트가 올바른 `pyside-iconify` 코드를 작성하도록 돕습니다.

[English](../../README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md) | **한국어** | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

[pyside-iconify](https://github.com/LingChen-tsjmdlc/pyside-iconify)를 위한
[MCP](https://modelcontextprotocol.io) 서버입니다. AI 어시스턴트가 추측하는 대신 실제로 존재하는
아이콘을 찾아보고, 라이브러리의 정확한 사용법을 읽고, 자신이 작성한 코드를 검사할 수 있게 해 줍니다.

> 이 프로젝트는 Iconify 프로젝트와 **관련이 없습니다**.

## 왜 필요한가

AI 어시스턴트는 `pyside-iconify` 코드에서 실행할 때에야 드러나는 실수를 자주 합니다.

- 존재하지 않는 아이콘 이름을 지어냄 (`mdi:home-filled`)
- 존재하지 않는 매개변수 이름을 쓰거나, 다른 진입점의 매개변수를 엉뚱한 곳에 사용함
  (`get_icon(..., hover_color=...)`)
- 여러 색을 가진 아이콘에 단일 색을 넘기고 색이 바뀔 것이라 기대함
- 애니메이션 아이콘이 필요한데 `get_icon`을 선택함

이 서버는 어시스턴트가 추측하는 대신 직접 찾아보고 자신의 작업을 확인할 수 있게 합니다.

## 도구

| 도구            | 기능                                                                                                             | 네트워크 필요 |
| --------------- | ---------------------------------------------------------------------------------------------------------------- | ------------- |
| `search_icons`  | Iconify 공식 검색 API로 키워드에 맞는 실제 아이콘을 찾음                                                         | 예            |
| `check_icons`   | 아이콘 이름이 존재하는지 확인하고, 여러 색인지·애니메이션이 있는지 알려 주며, 없는 이름에는 비슷한 후보를 제안함 | 예            |
| `get_reference` | 라이브러리 버전과 일치하는 정확한 사용법을 주제별로 반환함                                                       | 아니요        |
| `check_code`    | Python 코드 안의 `pyside-iconify` 호출을 실행하지 않고 검사함                                                    | 선택          |

네 도구 모두 읽기 전용입니다. 서버는 프로젝트 파일을 건드리지 않으며 코드를 실행하지도 않습니다.
네트워크 접속 대상은 Iconify 공개 API(`https://api.iconify.design`)뿐이며, 결과는 메모리에 한 시간 동안
캐시됩니다.

### search_icons

입력: `query`(키워드, 여러 단어는 모두 일치해야 함), 선택 사항인 `prefix`(`mdi` 같은 아이콘 세트),
선택 사항인 `limit`(1~100, 기본값 20).

출력: `status`(`ok` 또는 `unavailable`), `icons`(`prefix:name` 목록),
`collections`(관련 아이콘 세트의 이름, 라이선스, 전체 개수). `unavailable`은 네트워크가 없는 등의 이유로
검색에 실패했다는 뜻이며, 아무것도 존재하지 않는다는 뜻이 아닙니다.

### check_icons

입력: `names`, 1~50개의 아이콘 이름 목록.

출력: 이름마다 하나의 항목.

| `status`       | 의미                                                                           |
| -------------- | ------------------------------------------------------------------------------ |
| `ok`           | 아이콘이 존재함. `monotone`, `fixed_colors`, `animated`, `notes`도 함께 반환   |
| `not_found`    | 아이콘(또는 해당 아이콘 세트)이 존재하지 않음. `suggestions` 포함              |
| `invalid_name` | `prefix:name` 형식이 아님                                                      |
| `unavailable`  | 확인에 실패함(예: 네트워크 없음). 존재 여부에 대해서는 아무것도 알려 주지 않음 |

단색 여부, 색, 애니메이션 판정은 `pyside-iconify`가 직접 계산하므로 라이브러리가 실행 시점에 하는 동작과
일치합니다.

### get_reference

입력: 선택 사항인 `topic`. 생략하면 주제 목록을 반환합니다: `overview`, `icon_widget`, `get_icon`,
`set_icon`, `colors`, `sizes`, `animation`, `pitfalls`, `runtime`.

출력: Markdown. 시그니처는 설치된 `pyside-iconify`에서 생성되므로 항상 해당 버전과 일치합니다.
설명과 예제는 직접 작성했으며 라이브러리를 대상으로 테스트합니다.

### check_code

입력: `code`(Python 소스 코드), 선택 사항인 `verify_icon_names`(기본값 true).

출력: `ok`(오류가 없으면 true), `issues`(줄, 열, 심각도, 코드, 메시지, 제안),
`skipped`(검사하지 못한 항목), `checked`(개수).

다음을 찾아냅니다.

- 존재하지 않는 이름이나 모듈의 import
- 알 수 없는 매개변수, 잘못된 진입점에 쓰인 매개변수, 누락되거나 중복된 인수
- 잘못된 값: `size`, 색, `opacity`, `rotate`, `animation`, 주기, `speed`
- 서로 충돌하는 옵션(`spin=True`와 다른 애니메이션, spin에 `animation_depth`)
- 형식이 잘못된 아이콘 이름과 존재하지 않는 아이콘 이름
- 여러 색 아이콘에 단일 색 지정, 애니메이션 아이콘에 `get_icon` 사용

보장하는 것은 다음과 같습니다. `ok: true`를 반환했다면, 코드에서 직접 읽을 수 있었던 사용법
(매개변수 이름, 리터럴 값, 리터럴 아이콘 이름)은 올바릅니다. 알 수 없는 부분은 추측하지 않고
`skipped`에 나열합니다. 변수나 함수 호출에서 오는 값, `*args` / `**kwargs`, 실행 시점에만 문제가 되는 것
(`QApplication` 없음, 메인 스레드가 아닌 곳에서 위젯 생성)이 여기에 해당합니다.
확신하지 못하는 오류는 절대 보고하지 않습니다.

## 설정

`uvx pyside-iconify-mcp`를 실행하는 stdio 서버로 AI 클라이언트에 추가하세요.

### Claude Code

```bash
claude mcp add --transport stdio pyside-iconify -- uvx pyside-iconify-mcp
```

`--scope project`를 붙이면 프로젝트의 `.mcp.json`에 저장되어 팀과 공유할 수 있습니다.
자세한 내용은 [Claude Code 문서](https://docs.anthropic.com/en/docs/claude-code/mcp)를 참고하세요.

### ChatGPT 및 Codex

ChatGPT 데스크톱 앱, Codex CLI, Codex IDE 확장은 하나의 MCP 설정을 공유합니다.

```bash
codex mcp add pyside-iconify -- uvx pyside-iconify-mcp
```

또는 아래 내용을 `~/.codex/config.toml`에 추가하세요.

```toml
[mcp_servers.pyside-iconify]
command = "uvx"
args = ["pyside-iconify-mcp"]
```

자세한 내용은 [Codex 문서](https://developers.openai.com/codex/mcp)를 참고하세요.

### Cursor

프로젝트에 `.cursor/mcp.json`을 만드세요. 모든 프로젝트에서 쓰려면 `~/.cursor/mcp.json`을 만드세요.

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

자세한 내용은 [Cursor 문서](https://cursor.com/docs/context/mcp)를 참고하세요.

### OpenCode

`opencode.json`에 추가하세요. 여기서 `command`는 인수까지 포함한 하나의 배열입니다.

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

자세한 내용은 [OpenCode 문서](https://opencode.ai/docs/mcp-servers/)를 참고하세요.

### VS Code

프로젝트에 `.vscode/mcp.json`을 만드세요. VS Code의 최상위 키는 `mcpServers`가 아니라 `servers`입니다.

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

명령 팔레트에서 `MCP: Add Server`를 실행하고 `Command (stdio)`를 선택한 뒤
`uvx pyside-iconify-mcp`를 입력해도 됩니다. 자세한 내용은
[VS Code 문서](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)를 참고하세요.

### WorkBuddy

`~/.workbuddy/mcp.json`을 만들거나 수정하세요(파일 이름 앞에 점이 없습니다).

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

새로 추가한 서버는 자동으로 활성화되지 않습니다. 커넥터 관리 페이지 오른쪽 위의 사용자 지정 커넥터 항목을 열고,
해당 서버에서 `Trust`를 클릭하세요.

### CodeBuddy

아래 명령은 CodeBuddy CLI용입니다.

```bash
codebuddy mcp add --scope user pyside-iconify -- uvx pyside-iconify-mcp
```

`--scope project`를 쓰면 프로젝트의 `.mcp.json`에 저장됩니다. 자세한 내용은
[CodeBuddy 문서](https://www.codebuddy.ai/docs/cli/mcp)를 참고하세요.

### TRAE

Settings를 열고 MCP로 이동해 `Add`, `Create Manually`를 차례로 선택한 뒤 다음을 붙여 넣으세요.

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

특정 프로젝트에만 적용하려면 같은 페이지에서 `Enable Project MCP`를 켜고 같은 JSON을
`.trae/mcp.json`에 넣으세요. 자세한 내용은 [TRAE 문서](https://docs.trae.ai/ide/add-mcp-servers)를 참고하세요.

### 다른 클라이언트

`mcpServers` JSON 설정을 사용하는 클라이언트:

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

설정 파일과 키 이름은 클라이언트마다 다릅니다. 로컬(stdio) MCP 서버를 추가하는 방법은 사용 중인
클라이언트의 문서를 확인하세요.

### 소스 저장소에서 실행

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

클라이언트가 `uv`를 실행하지 못한다면, 프로젝트 가상 환경에 설치된 프로그램을 직접 지정하세요
(먼저 `uv sync`로 환경을 만들어야 합니다). Windows에서는 `.venv/Scripts/pyside-iconify-mcp.exe`,
macOS와 Linux에서는 `.venv/bin/pyside-iconify-mcp`입니다.

```json
{
    "mcpServers": {
        "pyside-iconify": {
            "command": "/path/to/pyside-iconify-mcp/.venv/Scripts/pyside-iconify-mcp.exe"
        }
    }
}
```

## 요구 사항

Python 3.10~3.14. 서버는 `pyside-iconify`(Qt extra 없이 설치하므로 Qt는 설치되지 않음)와
[FastMCP](https://gofastmcp.com) 4.1.x에 의존합니다. 빌드에 사용한 `pyside-iconify` 버전은 마이너 버전
범위로 고정되어 있으며, 라이브러리의 새 마이너 버전에는 이 서버의 대응 릴리스가 필요합니다.

## 개발

[uv](https://docs.astral.sh/uv/)가 필요합니다.

```bash
uv sync --group test
uv run pytest -v
uv run pyside-iconify-mcp
```

테스트는 네트워크를 사용하지 않습니다. 각 도구는 `src/pyside_iconify_mcp/tools/` 아래에 도구 이름과
같은 이름의 파일로 들어 있고, 공용 코드는 `common/`에 있습니다. 구조와 새 도구를 추가하는 방법은
[docs/architecture.md](../architecture.md)(영어)를 참고하세요.

## 라이선스

[MIT](../../LICENSE). 아이콘 컬렉션은 각자의 라이선스를 따릅니다.
