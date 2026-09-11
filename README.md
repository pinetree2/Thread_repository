# Trend2Threads AI

> AI/Tech 트렌드를 근거 기반으로 조사하고, 검증된 사실만 Threads 게시 초안으로
> 변환하는 LangGraph 멀티 에이전트 프로젝트입니다.

이 저장소는 단순한 자동 글쓰기 도구가 아니라 **관심 신호 수집 → 근거 조사 →
팩트 체크 → 콘텐츠 생성 → 사람 승인 → 게시**를 분리한 안전한 콘텐츠 리서치
파이프라인을 제공합니다. 기본값은 게시하지 않는(`auto_publish=false`) 모드이며,
실제 외부 게시 요청은 Human Approval 이후에만 실행됩니다.

## GitHub 공개 전 보안 체크

- 실제 키와 토큰이 들어 있는 `.env`는 커밋하지 않습니다. 이 파일은 `.gitignore`에 등록되어 있습니다.
- 커밋 대상은 `.env.example`의 빈 값과 환경변수 이름만 포함합니다.
- `GITHUB_TOKEN`, `OPENAI_API_KEY`, `SERPAPI_API_KEY`, `NAVER_CLIENT_SECRET`,
  `THREADS_ACCESS_TOKEN` 및 로그·캐시·가상환경은 원격 저장소에 올리지 않습니다.
- 키가 과거에 노출된 적이 있다면 GitHub 및 각 제공자 콘솔에서 폐기·재발급합니다.
- GitHub Fine-grained PAT를 사용할 경우 대상 저장소에 `Contents: Read and write`만 부여합니다.

저장소를 내려받은 뒤에는 다음처럼 로컬에서만 비밀값을 설정합니다.

```powershell
Copy-Item .env.example .env
# .env에 필요한 키를 직접 입력한 뒤 실행
python run.py
```

글로벌 AI/Tech 트렌드를 여러 실시간 Source에서 탐지하고, 별도 Research와 Fact Check를 거쳐 검증된 사실만으로 Threads 글을 작성한 뒤, 사용자의 명시적 승인 후 Meta Threads API로 게시하는 실행 가능한 LangGraph Multi-Agent System입니다.

이 프로젝트의 핵심은 “AI 글쓰기”가 아니라 아래 역할을 분리하고 상태·조건·Loop로 통제하는 것입니다.

```text
Trend Detection → Research → Fact Verification → Content Generation
                → Content Review → Human Approval → Publishing
```

## 해결하는 문제

빠르게 변하는 AI/Tech 분야에서 인기 신호는 곧 사실이 아닙니다. Hacker News의 반응이나 YouTube 조회수를 바로 콘텐츠 근거로 쓰면 과장과 오정보가 섞일 수 있습니다. Trend2Threads AI는 관심도 신호와 Fact Source를 분리하고, 검증된 문장만 Writer에 전달합니다. 게시 작업은 별도의 Human Interrupt 뒤에서만 실행합니다.

## 기본 Input / Output

```json
{
  "region": "GLOBAL",
  "language": "ko",
  "category": "AI",
  "period": "14d",
  "min_trend_score": 50,
  "content_style": "informative",
  "auto_publish": false
}
```

`region`은 트렌드 탐색 범위, `language`는 최종 Threads 글 언어입니다. 두 값은 독립적입니다. `auto_publish` 기본값은 `false`이며, 값과 관계없이 Human Approval은 우회할 수 없습니다.

최종 응답에는 Topic/Score/Signal, 검증 사실과 출처, confidence, `thread_post.full_text`, hashtag, review, publish 상태, Threads post ID/permalink가 포함됩니다.

## Architecture

```text
Browser / CLI
      │
FastAPI + NDJSON progress
      │
LangGraph StateGraph + MemorySaver
      │
Trend Discovery ── AI Model Watch / Hacker News / GitHub / SerpAPI YouTube
      ↓
Normalizer + Topic Clustering
      ↓
Code-based Trend Analyzer ── score < threshold → END
      ↓
Research ── Official URLs / Google News RSS / optional Naver News
      ↓                                  ↑
Fact Check ── confidence < .80, max 2 ──┘
      ↓
Threads Writer ←── review fail, max 2 ── Content Review
      ↓                                      │ pass
Awaiting Approval → LangGraph interrupt ─────┘
      ├─ Reject → END
      ├─ Edit → Content Review
      └─ Approve → Threads Publishing Tool → END
```

개발용 checkpointer는 프로세스 메모리 기반입니다. 서버 재시작 후에도 승인 대기 run을 보존해야 하는 운영 환경에서는 PostgreSQL/Redis 계열 영속 checkpointer로 교체해야 합니다.

## Agent / Node

| Node | 판단 역할 | Input | Output / 사용 Tool |
|---|---|---|---|
| Trend Discovery | 서로 다른 관심 신호 수집 | region, category, period | candidates / AI Model Watch, HN, GitHub, SerpAPI |
| Trend Normalizer | 공통 schema 검증·동일 Topic 병합 | candidates | clusters / Pydantic, 문자열 유사도 |
| Trend Analyzer | 코드 기반 점수 계산·후보 선택 | clusters, min score | topic, score, breakdown |
| Research | 관심 신호와 사실 근거 분리·자료 조사 | topic, period | sources, raw facts / Official URL, RSS, Naver |
| Fact Check | 출처 품질·교차 확인·신뢰도 계산 | sources, facts | verified facts, confidence |
| Threads Writer | 검증 사실만으로 500자 이하 글 작성 | facts, language, style | thread post, hashtags / optional OpenAI |
| Content Review | 근거 숫자·출처·길이·과장·중복 검사 | post, facts, sources | review, quality score |
| Human Approval | 실행을 중단하고 사람 결정을 수신 | reviewed post | approve/edit/reject / `interrupt()` |
| Threads Publisher | 승인된 텍스트만 게시 | approved full_text | post ID, permalink / Meta Threads API |

## State

`app/graph/state.py`의 `TrendThreadsState(TypedDict)`가 노드 간 계약입니다.

| 그룹 | 주요 필드 | 생성 → 소비 |
|---|---|---|
| Input | region, language, category, period, min_trend_score, content_style, auto_publish | API/CLI → Discovery/Writer |
| Trend | candidates, clusters, selected_topic, score, breakdown | Discovery/Normalizer/Analyzer → Router/Research/UI |
| Evidence | sources, raw_facts, verified_facts, confidence, research_retry_count | Research/Fact Check → Writer |
| Content | thread_post, hashtags | Writer/Edit → Review/Publisher |
| Review | review, content_retry_count | Review → Router/Human Approval |
| Approval | approval_decision, approved | Interrupt resume → Publisher |
| Publish | publish_status, threads_post_id, threads_permalink | Publisher → API/UI |
| Operations | available_sources, successful_sources, api_errors, warnings, trace | 각 Node → UI |

## Trend Score

점수는 LLM이 만들지 않습니다. `app/tools/scoring.py`가 수집된 값만 사용합니다.

- Recency: 20%
- Community engagement: 25%
- Video engagement: 25%
- Ecosystem/technology signal: 15%
- Cross-source confirmation: 15%

없는 신호는 분모에서 제외하고 가중치를 재정규화합니다. 단일 독립 Source는 최대 69점, 2개 Source는 최대 89점으로 제한해 기본 threshold 70이 교차 Source를 요구하도록 했습니다.

## Tool / API 선택

| API | 역할 | Endpoint / 인증 | 선택 이유 |
|---|---|---|---|
| AI Model Watch | 새 모델·변경 감지 | `aimodelwatch.dev/api/models.json`, key 없음 | 기술 등장 신호 |
| Hacker News | 개발자 관심 | Firebase `/v0/*stories.json`, key 없음 | score/comment/recency |
| GitHub REST | 오픈소스 생태계 | `/search/repositories`, token 선택 | star/fork/creation signal |
| SerpAPI YouTube | 영상 소비 관심 | `search?engine=youtube`, `engine=youtube_video`, key | 선택적 popularity signal |
| Google News RSS | Fact Research | RSS, key 없음 | 글로벌 뉴스 근거 후보 |
| Naver Search News | KR Fact Research | client id/secret | KR region 보완 |
| OpenAI Responses | 한국어 structured writing | API key | 선택적 표현 품질 개선 |
| Meta Threads API | 승인 후 텍스트 게시 | `graph.threads.com`, user token | 실제 publishing |

Hacker News/YouTube/GitHub의 관심 표현은 Fact로 사용하지 않습니다. Research가 공식 자료와 뉴스에서 다시 확인합니다. Selenium collector는 API가 없는 동적 페이지를 위한 선택적 구현만 남아 있으며 기본 Graph에서는 사용하지 않습니다.

### Meta Threads 게시 사양

현재 구현은 Meta 공식 Publishing 흐름을 그대로 따릅니다.

1. `POST /{threads-user-id}/threads` — `media_type=TEXT`, `text`로 container 생성
2. `POST /{threads-user-id}/threads_publish` — `creation_id`로 게시
3. `GET /{threads-media-id}?fields=id,permalink` — permalink 조회

필수 권한은 최소 `threads_basic`, `threads_content_publish`입니다. 본문은 일반 게시물 제한에 맞춰 500자로 검토합니다.

- [Meta Threads API Publishing](https://developers.facebook.com/docs/threads/reference/publishing)
- [Meta 공식 Threads API Sample App](https://github.com/fbsamples/threads_api)
- [Meta 공식 500자 게시물 안내](https://about.fb.com/news/2023/07/introducing-threads-new-app-text-sharing/)

## 설치

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

브라우저: `http://127.0.0.1:8000`

## 환경 변수

키 없이도 AI Model Watch, Hacker News, GitHub public search, Google News RSS를 사용해 live Graph를 실행할 수 있습니다. OpenAI 키가 없으면 검증 사실 기반 deterministic Writer를 사용합니다.

실제 Threads 게시 검증에 필요한 값:

```env
THREADS_ACCESS_TOKEN=
THREADS_USER_ID=
```

앱 Dashboard에서 OAuth로 토큰을 발급하는 기능까지 확장할 때는 Threads API 전용 App ID/Secret 및 HTTPS redirect URI가 추가로 필요합니다. 현재 MVP는 이미 발급된 사용자 토큰을 서버에서 사용하는 구조이므로 `THREADS_APP_ID`, `THREADS_APP_SECRET`을 런타임 필수값으로 요구하지 않습니다.

선택 값:

```env
SERPAPI_API_KEY=
GITHUB_TOKEN=
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
OPENAI_API_KEY=
```

Secret은 API 응답, 로그, 브라우저에 반환하지 않습니다.

## 실행 방법

Web UI:

```powershell
python run.py
```

CLI — Graph는 승인 interrupt에서 멈추며 JSON draft를 출력합니다.

```powershell
python -m app.cli --region GLOBAL --language ko --category AI --period 14d --min-score 70 --style informative --demo
```

API:

```text
GET  /api/health
POST /api/analyze
POST /api/analyze/stream
GET  /api/runs/{run_id}
POST /api/runs/{run_id}/decision
GET  /api/graph
```

승인 재개 예시:

```json
{"action":"approve"}
{"action":"edit","edited_text":"수정한 500자 이하 본문"}
{"action":"reject"}
```

## 테스트

```powershell
python -m pytest tests -q -p no:cacheprovider
```

테스트는 State/input validation, 정규화·clustering, Trend Score, 조건 Router, Research retry 상한, 500자 제한, approval interrupt/resume, 승인 없는 게시 차단, Threads container→publish→permalink 요청 parsing, FastAPI 계약을 포함합니다. 외부 게시 테스트는 `httpx`를 명시적으로 mock하며 live API 결과인 것처럼 표시하지 않습니다.

## 발표 자료

- Architecture: `docs/architecture.html`
- Presentation: `docs/presentation.html`

두 파일 모두 외부 라이브러리 없이 브라우저에서 바로 열 수 있습니다. 발표 자료는 좌우 방향키, Space, 화면 버튼으로 이동합니다.

## 안전 및 운영 한계

- 기본값은 `auto_publish=false`; 분석 API는 게시 API를 호출하지 않습니다.
- Publisher는 `approved=true`와 승인 decision을 모두 확인합니다.
- 게시 실패는 Trend/Research/Writer를 재실행하지 않고 `api_errors`와 publish 상태만 갱신합니다.
- keyless Research는 RSS title/summary 중심입니다. 본문 라이선스와 claim-level entailment가 필요한 운영 환경에서는 허가된 원문 provider와 별도 검증기를 추가해야 합니다.
- MemorySaver는 개발용입니다. 운영 배포에는 영속 checkpointer, 사용자별 OAuth token vault, CSRF/인증, 감사 로그가 필요합니다.
