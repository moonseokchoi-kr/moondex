# Moondex

Moondex는 아이디어 탐색, controller-first SDD, 로컬 검증, 리뷰 수렴을
프로젝트 안에서 재현 가능하게 실행하는 Codex 플러그인입니다. manifest가
공개하는 실행 표면은 `skills/`뿐이며, `agents/`는 오케스트레이터가 주입할
수 있는 역할 프로필입니다. 역할 프로필 파일이 존재한다고 worker가 자동으로
등록되거나 실행되지는 않습니다.

## 설치 및 Codex 등록

### 현재 clone을 repo-local marketplace로 사용

이 저장소의 marketplace는 `.codex-plugin/marketplace.json`입니다. 일반적인
개인 marketplace의 source는 `./plugins/moondex`이지만, 이 파일은 플러그인
루트 내부의 `.codex-plugin/`에 있으므로 source `../`가 정확히 현재 플러그인
루트를 가리키는 의도적 예외입니다.

clone 루트에서 다음 검증을 실행하면 manifest와 marketplace가 유효하고 source가
다른 디렉터리가 아닌 현재 clone을 가리키는지 확인할 수 있습니다.

```bash
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool .codex-plugin/marketplace.json >/dev/null
python3 - <<'PY'
import json
from pathlib import Path

root = Path.cwd().resolve(strict=True)
marketplace = (root / ".codex-plugin/marketplace.json").resolve(strict=True)
entry = json.loads(marketplace.read_text(encoding="utf-8"))["plugins"][0]
source = (marketplace.parent / entry["source"]["path"]).resolve(strict=True)
if entry["name"] != "moondex" or source != root:
    raise SystemExit("marketplace source does not resolve to this Moondex clone")
print(f"verified repo-local Moondex source: {source}")
PY
```

현재 clone의 절대 marketplace 경로를 사용한 Codex View/Share deeplink는 다음처럼
재현 가능하게 생성합니다. 출력된 링크를 열면 Codex가 marketplace와 `moondex`
플러그인을 식별합니다. clone 경로를 문서에 하드코딩할 필요가 없습니다.

<!-- repo-marketplace-deeplink -->
```python
from pathlib import Path
from urllib.parse import quote

marketplace = (
    Path.cwd() / ".codex-plugin/marketplace.json"
).resolve(strict=True)
query = quote(str(marketplace), safe="")
view = f"codex://plugins/moondex?marketplacePath={query}"
share = f"{view}&mode=share"
print(f"View moondex: {view}")
print(f"Share moondex: {share}")
```

clone 루트에서 위 Python 블록을 실행하세요. 예를 들어 파일로 저장하지 않고
`python3 -c '<블록 내용>'`으로 실행해도 됩니다.

### 표준 개인 marketplace로 등록

repo-local 예외 대신 plugin-creator의 표준 개인 배치를 사용하려면 아래 블록을
clone 루트에서 한 번 실행합니다. 현재 clone을 `~/plugins/moondex`에 안전하게
symlink하고 `~/.agents/plugins/marketplace.json`의 다른 항목은 보존하면서
`./plugins/moondex` 항목만 결정적으로 갱신합니다. 기존 destination이 다른
플러그인을 가리키면 덮어쓰지 않고 중단합니다.

<!-- personal-marketplace-setup -->
```python
import json
from pathlib import Path
from urllib.parse import quote

source = Path.cwd().resolve(strict=True)
home = Path.home()
plugin = home / "plugins/moondex"
plugin.parent.mkdir(parents=True, exist_ok=True)
if plugin.exists() or plugin.is_symlink():
    if plugin.resolve(strict=True) != source:
        raise SystemExit(f"refusing to replace existing destination: {plugin}")
else:
    plugin.symlink_to(source, target_is_directory=True)

marketplace = home / ".agents/plugins/marketplace.json"
marketplace.parent.mkdir(parents=True, exist_ok=True)
if marketplace.exists():
    document = json.loads(marketplace.read_text(encoding="utf-8"))
else:
    document = {
        "name": "personal",
        "interface": {"displayName": "Personal"},
        "plugins": [],
    }
plugins = [
    entry for entry in document.get("plugins", [])
    if entry.get("name") != "moondex"
]
plugins.append({
    "name": "moondex",
    "source": {"source": "local", "path": "./plugins/moondex"},
    "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    },
    "category": "Productivity",
})
document["plugins"] = plugins
temporary = marketplace.with_suffix(".json.tmp")
rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
if not marketplace.exists() or marketplace.read_text(encoding="utf-8") != rendered:
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(marketplace)

absolute_marketplace = marketplace.resolve(strict=True)
query = quote(str(absolute_marketplace), safe="")
view = f"codex://plugins/moondex?marketplacePath={query}"
share = f"{view}&mode=share"
print(f"View moondex: {view}")
print(f"Share moondex: {share}")
```

이 블록은 Moondex를 `AVAILABLE` catalog 항목으로 등록할 뿐 자동 설치하거나
활성화하지 않습니다. 출력된 **View moondex** 링크를 Codex 앱에서 열고
Moondex의 **Install/Enable** 동작을 완료하세요. 설치·활성화가 확인된 뒤에만
아래 `$moondex:*` 명령을 사용합니다. **Share moondex** 링크는 같은 개인
marketplace를 공유 모드로 여는 별도 handoff입니다.

## 사용자 실행

위 View handoff에서 Codex 앱의 Install/Enable을 완료한 후, 소비자 프로젝트에서
checkout 스크립트나 `PYTHONPATH`를 직접 다루지 않고 플러그인 스킬을 호출합니다.

```text
$moondex:sdd start <feature>
$moondex:pr-converge
$moondex:self-improve
$moondex:code-mapper
$moondex:harness audit
```

각 스킬은 현재 로드된 스킬 패키지에서 `<moondex-runtime>`을 package-relative
절대 경로로 해석합니다. 따라서 사용자는 플러그인의 설치 경로를 알 필요가 없고,
소비자 프로젝트가 Moondex checkout이 아니어도 됩니다. 런타임 상태는 소비자
프로젝트의 `.harness/state/`에, SDD 문서는 `docs/sdd/`에 기록됩니다.

`$moondex:sdd`의 controller 결과는 다음 의미를 가집니다.

- `ACTION`: 반환된 한 단계만 수행합니다.
- `WAITING_USER`: 명시된 spec, design 또는 plan 승인을 요청합니다.
- `BLOCKED_ARTIFACT`: 지목된 산출물만 복구한 뒤 다시 재개합니다.
- `COMPLETE`: durable result를 보고합니다.
- `ADVISORY_UNAVAILABLE`: 선택적 로컬 통합이 없다는 진단이며 진행 차단이 아닙니다.

`status`와 `resume`은 읽기 전용이고, 승인은 현재 요청된 전이에만 적용됩니다.
worker는 결과와 검증 evidence를 반환할 뿐 `.harness/state/`나
`docs/sdd/ORCHESTRATOR_STATE.md`를 직접 쓰지 않습니다.

## 로컬 데이터와 선택 기능

- PR 코멘트는 정합성·소유 범위·검증 evidence에 따라 `SAFE_FIX`, `REJECTED`,
  `ESCALATED`로 처분합니다.
- 원문 재현 evidence는 소비자 프로젝트의 `.harness/audit/`에, redacted 표현은
  `.harness/reports/`에 둡니다.
- RESULT 지식 동기화는 명시적 설정이 없으면 `SYNC_SKIPPED`이며, 성공한 명시적
  동기화만 `SYNC_APPLIED`입니다.
- 개인 경로나 조직 destination의 기본값은 없습니다.
- optional Git hook과 원격 `moondex-verify` check는 빠른 피드백/CI 확장입니다.
  원격 CI나 게시 기능은 로컬 baseline의 전제조건이 아닙니다.

## 주요 스킬

| 호출 | 역할 |
|---|---|
| `$moondex:idea-workshop` | 아이디어 발산, 검증, PRD |
| `$moondex:sdd start <feature>` | Spec → Design → Plan → Execute → Result |
| `$moondex:pr-converge` | 리뷰 코멘트 apply/reject/escalate 수렴 |
| `$moondex:self-improve` | 검증된 로컬 학습 후보 처리 |
| `$moondex:code-mapper` | 코드 영향 탐색과 명시적 fallback |
| `$moondex:harness audit` | 프로젝트 하네스 점검 |
| `$moondex:handoff` | 세션 컨텍스트 보존 |

## 플러그인 개발자 전용

아래 명령은 설치된 플러그인의 일반 사용자 명령이 아닙니다. Moondex checkout
자체를 개발할 때만 checkout 루트에서 실행합니다.

```bash
python3 -m harness_core state --project-root . status <feature>
python3 -m harness_core preflight --help
python3 scripts/verify.py --help
python3 scripts/pr_converge_adapter.py --help
python3 skills/sdd-orchestrator/scripts/result-action.py --help
python3 scripts/run-benchmarks.py --help
# Optional and mutating: installs wrappers in this checkout's .git/hooks/
bash scripts/install-hooks.sh
python3 -m pytest tests -q
```

`skills/sdd/runtime/runtime-inventory.json`은 설치 런타임의 manifest, 크기, SHA-256,
파일 종류를 고정합니다. 런타임 의존 파일을 변경했다면 별도의 공개 재생성 명령을
추정하지 말고, 같은 변경에서 인벤토리를 갱신한 뒤 전체 테스트와 plugin validator를
실행하세요. `tests/test_agent_profiles.py`가 인벤토리와 재귀 로컬 의존성 폐쇄의
정합성을 검사합니다.

## Porting notes

`Claude Design`과 `claude-design`은 외부 시각 도구의 고유 이름이므로 해당
워크플로우를 교체하기 전에는 이름을 바꾸지 않습니다.

## License

MIT
