# Moondex

프로젝트별 코딩 지침, 코드 품질 설정, 선택형 TDD와 깊이 있는 작업 재구성을 제공하는 네 개의 Codex 스킬입니다.
글로벌에 코딩 절차를 강제하지 않고, 필요한 프로젝트에 로컬 지침과 검사 설정을 남깁니다.

| 스킬 | 역할 |
|---|---|
| `project-guidelines` | 기존 `AGENTS.md`를 보존하며 구현 범위·검증·종료 원칙 작성 |
| `code-quality-setup` | 기존 lint·타입 검사 설정 보완과 미검출 항목의 리뷰 기준 작성 |
| `tdd-tidy-first` | 프로젝트에 맞춘 엄격한 TDD·Tidy First 지침 설치 또는 `go` 한 번에 계획된 테스트 하나 실행 |
| `deeper-prompt` | 원문 프롬프트로 작업을 깊이 있게 재구성하고 사용자에게 선택권 제공 |

네 스킬은 독립적으로 사용할 수 있습니다. 실행기, 자동 훅, 작업 상태 관리,
고정 리뷰 라운드를 요구하지 않습니다. 일반 글쓰기·조사·브레인스토밍에는
코딩 지침을 적용하지 않도록 범위를 명시합니다.

## 사용

플러그인 설치·활성화 후 대상 프로젝트에서 호출합니다.

```text
$moondex:project-guidelines 이 프로젝트의 AGENTS.md에 코딩·검증 지침을 적용해줘
$moondex:code-quality-setup 기존 검사 설정을 보존하며 이 프로젝트의 코드 품질 규칙을 설정해줘
$moondex:tdd-tidy-first 이 프로젝트의 언어와 검사 도구에 맞춰 AGENTS.md에 TDD와 Tidy First 지침을 적용해줘
$moondex:deeper-prompt 이 작업을 더 깊이 있게 수행할 프롬프트로 재작성해줘
```

`project-guidelines`는 요청한 로컬 지침 파일을 작성합니다. `code-quality-setup`은
프로젝트의 언어와 기존 도구를 확인하고 필요한 설정을 수정합니다. TS·Python·Rust·C++의
참고 파일 중 필요한 것만 읽습니다. 자동 검사와 리뷰 판단을 구분하며,
기존 코드의 일괄 수정은 기본 작업에 포함하지 않습니다.

설정 후에는 프로젝트에 남긴 지침과 검사 명령을 사용합니다. 매 코딩 작업마다
두 설정 스킬을 다시 실행할 필요는 없습니다.

`tdd-tidy-first`는 명시 호출 전용이며 다른 두 스킬의 기본 절차를 덮어쓰지 않습니다.
JS·TS, Python, Rust, C++의 코드·테스트 관용구를 별도 참고 파일로 제공하고, 실제
소스·매니페스트·테스트·CI를 확인하여 기존 도구에 맞춥니다. 다른 언어는 공통 절차를
사용하되 전용 참고 자료가 없음을 밝히고 프로젝트 관례를 확인합니다.

지침 적용은 로컬 `AGENTS.md`만 병합하며 제품 코드·테스트·`plan.md`를 생성하지 않습니다.
적용된 프로젝트에서 `go`라고 하면 `plan.md`의 첫 미완료 테스트 하나만
Red → Green → Refactor로 처리합니다. 계획이 없거나 다음 테스트가 없으면 구현하지 않습니다.
각 Red·Green 확인과 리팩터링 단계마다 장시간 테스트를 제외한 전체 테스트를 실행하고
제외 범위를 보고합니다. 린트·타입 검사는 동작 테스트를 대신하지 않습니다.
구조 변경과 동작 변경은 분리하며, 커밋은 장시간 테스트를 포함한 모든 테스트 통과와
컴파일러·린터 경고·오류 해소가 필요합니다. 이 규칙이 자동 커밋·push·공개·배포 권한을
부여하지는 않습니다. 지침만 수정할 때는 문서의 충돌·중복을 확인합니다.

`deeper-prompt`는 명시적으로 호출해 사용합니다. 원문에 담긴 네 질문에 답하고
재작성한 프롬프트를 제시한 뒤, 사용자가 적용 여부를 결정합니다. 호출만으로
재작성된 작업을 실행하거나 파일을 수정하지 않습니다. 코딩 외 작업에도 쓸 수 있습니다.

## 설치

repo-local marketplace는 `.codex-plugin/marketplace.json`입니다. 그 파일의
`source.path`인 `../`는 현재 플러그인 루트를 가리킵니다.
Codex의 플러그인 설치 화면에서 이 marketplace를 등록하고 `moondex`를 설치·활성화하세요.
기존 설치본은 새 버전으로 갱신해야 네 스킬 구성이 반영됩니다.

플러그인 없이 쓰려면 필요한 스킬 디렉터리를 에이전트의 스킬 설치 위치에 복사할 수
있습니다. 각 스킬의 디렉터리 전체를 복사하세요. `references/`와 `tdd-tidy-first`의
`agents/openai.yaml`(명시 호출 정책)도 포함해야 합니다.
이는 스킬을 등록하는 것이며 프로젝트나 글로벌 `AGENTS.md`에 규칙을 자동 추가하지 않습니다.

## 구성

```text
skills/
├── deeper-prompt/
│   ├── SKILL.md
│   └── agents/openai.yaml
├── project-guidelines/SKILL.md
├── code-quality-setup/
│   ├── SKILL.md
│   └── references/
│       ├── typescript.md
│       ├── python.md
│       ├── rust.md
│       └── cpp.md
└── tdd-tidy-first/
    ├── SKILL.md
    ├── agents/openai.yaml
    └── references/
        ├── typescript.md
        ├── python.md
        ├── rust.md
        └── cpp.md
```

## 개발 검증

외부 Python 패키지 없이 패키징 검사를 실행합니다.

```bash
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool .codex-plugin/marketplace.json >/dev/null
python3 -m unittest discover -s tests -v
git diff --check
```

검사는 플러그인 메타데이터, 네 스킬의 탐색 가능 여부, 설치 경로에서의 참고 파일
접근과 선택형 스킬의 명시 호출 정책 파일을 확인합니다. 실제 호스트에서의 호출 정책
집행, 프로젝트의 lint·테스트 통과나 미래 모델의 지침 준수까지 보증하지 않습니다.

MIT 라이선스이며 각 스킬의 참고 원문은 해당 문서에 표시되어 있습니다.
