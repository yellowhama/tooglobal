# WORKFLOW GUIDE — 지구촌 반상회 에피소드 제작 가이드

> **🔴 제1 헌법: 워크플로우 절대 준수 및 단계별 QC 필수**
> 1. 모든 작업자는 정의된 11단계 공정을 **순서대로** 수행해야 하며, 임의로 단계를 건너뛰거나 순서를 바꾸는 행위를 엄격히 금지함.
> 2. 각 단계 완료 후에는 반드시 **QC(Quality Control)**를 수행하여 통과(PASS) 판정을 받아야 함. QC 미통과 시 다음 단계 진입 불가.
> 3. 기존의 'Golden' 스크립트 및 설정 파일은 직접 수정하지 말 것. 새로운 시도는 복사본에서 수행 후 컨펌 시 교체함.

---

## Alignment Status (2026-03-28)

- 이 문서는 사람 기준의 목표 워크플로우를 설명한다.
- 현재 코드/문서 정렬 상태, 불일치 표, 구현 우선순위는 `work/workflow_alignment_plan/MASTER_PLAN.md`를 기준으로 관리한다.
- 정렬 작업이 끝날 때까지 `/deep-research`, 루트 경로 해석, 오케스트레이터 동작은 구현과 문서가 일부 다를 수 있다.
- 애니메이션 데이터 계층은 `2026-04-01` 기준 태깅 배치 완료 후 refresh 상태다.
- 최신 activation 후속 작업은 `work/post_tagging_activation_plan/MASTER_PLAN.md`를 기준으로 관리한다.
- `openclaw` + `paperclip` reference archaeology 및 control-plane 흡수 계획은 `context/OPENCLAW_PAPERCLIP_WORKFLOW_COMPARISON.md`, `work/openclaw_paperclip_integration_plan/MASTER_PLAN.md`를 기준으로 관리한다.
- studio issue 계층의 현재 계약은 `context/STUDIO_ISSUE_MODEL_CONTRACT.md`를 기준으로 관리한다.
- worker run/session, approval/event, heartbeat, operator surface의 control-plane 계약은 `context/WORKER_RUN_SESSION_CONTRACT.md`, `context/APPROVAL_EVENT_LOG_CONTRACT.md`, `context/HEARTBEAT_SCHEDULER_CONTRACT.md`, `context/STUDIO_OPERATOR_SURFACE_CONTRACT.md`, `context/STUDIO_CONTROL_PLANE_ADDENDUM.md`를 기준으로 관리한다.
- 실제 lightweight runtime은 `context/STUDIO_CONTROL_PLANE_RUNTIME.md`, `work/studio_control_plane_runtime_plan/MASTER_PLAN.md`, `context/studio_control_plane.db`를 기준으로 관리한다.
- orchestrator / QC 자동 연결 상태는 `context/STUDIO_CONTROL_PLANE_ACTIVATION.md`, `work/studio_control_plane_activation_plan/MASTER_PLAN.md`를 기준으로 관리한다.
- `CLI-Anything` 비교와 전용 control-plane MCP 분리는 `context/CLI_ANYTHING_CONTROL_PLANE_COMPARISON.md`, `work/cli_anything_control_plane_plan/MASTER_PLAN.md`를 기준으로 관리한다.
- company/gateway 통합 후 operator front door는 `context/STUDIO_GATEWAY_OPERATOR_LOOP.md`, `work/company_gateway_integration_plan/MASTER_PLAN.md`를 기준으로 관리한다.
- 워크플로우의 live-path 정리와 ComfyUI/FLUX 수렴 작업은 `context/WORKFLOW_COMPLETION_SPEC.md`, `work/workflow_completion_plan/MASTER_PLAN.md`를 기준으로 관리한다.
- 로컬 Paperclip은 자체 `paperclipai` CLI를 우선 사용하고, youtube-studio에서는 `paperclip-status`로 health/config/UI/API만 얇게 노출한다.
- `2026-04-03` 기준 교정: `scene 1개 = shot 1개` 규칙은 폐기한다. 실제 애니메이션 제작은 반드시 `scene -> beat -> shot -> storyboard -> animatic -> layout -> keyframe -> motion -> assembly` 순서를 따른다.

---

## 0. 사전 준비

### 환경
| 항목 | 값 |
|------|-----|
| 프로젝트 루트 | `/home/hugh/youtube-studio-copy/` (= `E:\youtube-studio\`) |
| GPU | RTX 5070 Ti 16GB |
| Python venv | `~/venvs/phase3-gpu/` (ML 도구) |
| ComfyUI | `~/ComfyUI/app/` (포트 8188) |
| TTS | Chatterbox (`~/chatterbox/`, EN only) + Edge-TTS (KO) |
| BGM | ACE-Step (`~/ACE-Step/`) |
| Neo4j | Docker `neo4j-research` (포트 7474/7687, pw: research2026) |

### Claude Code 스킬 목록 + 파일 위치

모든 스킬은 `.claude/commands/` 디렉토리에 마크다운 파일로 정의됨.
다른 AI가 실행할 때는 해당 .md 파일을 시스템 프롬프트로 로드하면 됨.

| 스킬 | 파일 위치 | 역할 |
|------|-----------|------|
| `/find-topic` | `~/.claude/commands/find-topic.md` | 주제 발굴 (13-Metric 드라마 스코어) |
| `/deep-research` | `~/.claude/commands/deep-research.md` | 딥 리서치 (STORM + 팩트 검증) |
| `/plan-visual` | `~/.claude/commands/plan-visual.md` | **(신규) Obsidian Knowledge Map 구축 (Fact-to-Beat)** |
| `/write-script` | `~/.claude/commands/write-script.md` | 대본 작성 (Fountain 포맷 + lib_ai/screenplain) |
| `/storyboard` | `~/.claude/commands/storyboard.md` | 콘티 (lib_ai/storyboarder 연동) |
| `/generate-visuals` | `~/.claude/commands/generate-visuals.md` | 이미지 생성 (ComfyUI + lib_ai/LivePortrait) |
| `/generate-voice` | `~/.claude/commands/generate-voice.md` | 음성 (Chatterbox + lib_ai/whisperX) |
| `/assemble-video` | `~/.claude/commands/assemble-video.md` | 최종 MP4 조립 (FFmpeg) |

### 🧰 AI 도구 창고 (lib_ai/)

모든 외부 엔진은 `lib_ai/`에 집중 관리하며 파이프라인에서 호출함.

| 도구 | 용도 | 위치 |
|------|------|------|
| **LivePortrait** | 광기 어린 표정/입모양 생성 | `lib_ai/LivePortrait` |
| **whisperX** | 단어 단위 음성 동기화 (자막/타이밍) | `lib_ai/whisperX` |
| **storyboarder** | 대본 시각화 및 컷 검토 | `lib_ai/storyboarder` |
| **screenplain** | Fountain 대본 파서 | `lib_ai/screenplain` |
| **gazu (Kitsu)** | 생산 관리 및 샷 상태 추적 | `lib_ai/gazu` |
| **KITScenarist** | 캐릭터 서사/부상 이력 관리 | `lib_ai/KITScenarist` |

### 핵심 컨텍스트 파일 (스킬이 참조)

| 파일 | 위치 | 용도 |
|------|------|------|
| SHOW_BIBLE.md | `context/SHOW_BIBLE.md` | 세계관, 캐릭터, 톤, 포맷 |
| CHARACTER_SHEETS.md | `context/CHARACTER_SHEETS.md` | 16캐릭터 시트 + 에셋 현황 |
| STORY_STRUCTURE.md | `context/STORY_STRUCTURE.md` | **7블록 흐름 + 6개 패턴 라이브러리** |
| SCORING_RUBRICS.md | `context/SCORING_RUBRICS.md` | 단계별 채점 기준 |
| QUALITY_GATES.md | `context/QUALITY_GATES.md` | PASS/CONDITIONAL/FAIL 규칙 |
| **SHOT_TAXONOMY.md** | **`context/SHOT_TAXONOMY.md`** | **6축 영상 연출 태그 체계 (SSOT) — 태깅, 대본, 콘티, 검색 전부 이 용어** |
| COMPOSITION_PROFILE_CONTRACT.md | `context/COMPOSITION_PROFILE_CONTRACT.md` | composition-focused semantic read 계약 |
| SUBJECT_BACKGROUND_SCHEMA.md | `context/SUBJECT_BACKGROUND_SCHEMA.md` | subject/background coarse read 스키마 |
| STORYBOARD_REFERENCE_BUNDLE_CONTRACT.md | `context/STORYBOARD_REFERENCE_BUNDLE_CONTRACT.md` | composition / character / background reference bundle 계약 |
| PENCIL_STYLE_READ_SURFACE_DRAFT.md | `context/PENCIL_STYLE_READ_SURFACE_DRAFT.md` | storyboard/QC용 purpose-built read surface 초안 |
| SEMANTIC_SCENE_DECOMPOSITION_DRAFT.md | `context/SEMANTIC_SCENE_DECOMPOSITION_DRAFT.md` | subject/background/composition 분해 초안 |
| shot_presets.json | `context/shot_presets.json` | 14종 상황별 카메라+스테이징 프리셋 |
| unified_reference_db.json | `context/unified_reference_db.json` | 174장 통합 레퍼런스 DB |
| ANIME_DATA_CAPABILITIES.md | `context/ANIME_DATA_CAPABILITIES.md` | 애니메이션 데이터 활용 리포트 (8가지 활용법) |
| sentiment_to_visual_matrix.json | `context/sentiment_to_visual_matrix.json` | 감정→카메라 매트릭스 |

### 파이프라인 스크립트 (Python)

| 스크립트 | 위치 | 용도 |
|----------|------|------|
| orchestrator.py | `pipeline/orchestrator.py` | 7단계 자동 체이닝 + QC |
| quality_checker.py | `pipeline/quality_checker.py` | 단계별 실제 콘텐츠 QC |
| fetch_references.py | `pipeline/stage0_research/fetch_references.py` | YouTube 자막 + 칼럼 수집 |
| storm_perspectives.py | `pipeline/stage0_research/storm_perspectives.py` | STORM 다시점 분석 |
| knowledge_graph.py | `pipeline/stage0_research/knowledge_graph.py` | Neo4j 지식 그래프 |
| fact_checker.py | `pipeline/stage0_research/fact_checker.py` | 팩트 검증 (오프라인) |
| suggest_visuals.py | `pipeline/shared/suggest_visuals.py` | 연출 조수 (--semantic) |
| validate_camera_rules.py | `pipeline/shared/validate_camera_rules.py` | FilmAgent 8규칙 검증 |
| storyboard_reference_adapter.py | `pipeline/shared/storyboard_reference_adapter.py` | manifest shot 기준 reference selector 추론 + 자동 부착 |
| vector_search.py | `pipeline/shared/vector_search.py` | CLIP + 자막 벡터 검색 |
| analyze_reference_patterns.py | `pipeline/shared/analyze_reference_patterns.py` | 감정→카메라 매트릭스 생성 |
| batch_tagger.py | `pipeline/shared/batch_tagger.py` | 자막 감정 태깅 (Ollama qwen2.5) |
| screenshot_tagger.py | `pipeline/shared/screenshot_tagger.py` | 스크린샷 6축 비전 태깅 (Ollama qwen3-vl:8b) |
| extract_frames.py | `pipeline/shared/extract_frames.py` | 영상 → 1fps 프레임 추출 (ffmpeg) |
| cleanup_screenshots.py | `pipeline/shared/cleanup_screenshots.py` | 스크린샷 폴더 정리 (빈 폴더 삭제 + 리네임) |
| **rebuild_data_pipeline.py** | **`pipeline/shared/rebuild_data_pipeline.py`** | **태깅 후 자동 체인: merge→stats→crossref→emotion→rhythm (2초)** |
| merge_tags.py | `pipeline/shared/merge_tags.py` | 태그 파일 통합 → merged_screenshot_tags.json |
| shot_stats.py | `pipeline/shared/shot_stats.py` | 구도 통계 + 프리셋 검증 |
| timestamp_mapper.py | `pipeline/shared/timestamp_mapper.py` | 자막↔프레임 타임스탬프 매핑 |
| emotion_shot_crossref.py | `pipeline/shared/emotion_shot_crossref.py` | 감정×구도 크로스 매트릭스 |
| cut_rhythm_analyzer.py | `pipeline/shared/cut_rhythm_analyzer.py` | 컷 리듬 분석 (장르별 패턴) |
| qc_tagger.py | `pipeline/shared/qc_tagger.py` | 생성 이미지 QC (PASS/PARTIAL/FAIL) |
| script_artifact_splitter.py | `pipeline/shared/script_artifact_splitter.py` | manifest → writer/TTS/subtitle/visual/timing 파생 |
| channel_reference_builder.py | `pipeline/shared/channel_reference_builder.py` | YouTube reference_index → 채널 스타일/가이드 프로파일 |
| **scene_cluster.py** | **`pipeline/shared/scene_cluster.py`** | **씬 클러스터링 (17K 프레임 → 5,518 씬) + 씬 단위 레퍼런스 검색 + 작품 스타일 가중치** |
| **filmagent_camera.py** | **`pipeline/shared/filmagent_camera.py`** | **FilmAgent Debate-Judge 카메라 선택 (LLM 2명 독립 플랜 → 교차 리뷰 → 심사)** |

> Stage 1 visuals canonical path: `generate_character.py`, `generate_backgrounds.py`, `generate_keyframes.py`, `refine_consistency_kontext.py`
>
> `compose_keyframe_ep*.py` 계열은 episode-specific experiment/legacy surface로 남아 있으며, 운영 기준 canonical entrypoint는 아니다.

> YouTube 채널 레퍼런스 지식층: `python3 tools/youtube_studio_frontdoor.py channel-profiles --rebuild`

---

## Stage 0a: 주제 찾기 — `/find-topic`

### 실행
```
/find-topic
```
또는 키워드 지정:
```
/find-topic Iran war
```

### 무슨 일이 일어나는가
1. WebSearch로 최신 국제뉴스 광역 스캔 (4개 카테고리)
2. 각 뉴스에 **13-Metric 드라마 스코어** 채점:
   - TIER 1 (45%): 대립 강도, 감정 전압, 판돈 크기
   - TIER 2 (30%): 시의성, 호기심 갭, 반전 잠재력, 리텐션 구조
   - TIER 3 (25%): 캐릭터 드라마, 비유 품질, 시각화, 공유성, 시리즈 잠재력
3. 상위 3~5개 주제 카드 생성
4. 사용자가 선택

### 산출물
- 선택된 주제 + composite 점수
- `다음 단계: /deep-research {주제}`

### 통과 기준
- composite ≥ 7.0 → PASS
- 6.0~7.0 → CONDITIONAL (진행/재작업 선택)
- < 6.0 → FAIL (재검색)

---

## Stage 0b: 딥 리서치 — `/deep-research`

### 실행
```
/deep-research 미-이스라엘 이란 전쟁 28일
```

### 무슨 일이 일어나는가 (3 Step)

**Step 1: 팩트 딥다이브**
- WebSearch로 주제 심층 조사, 역사적 맥락(Historical Context) 및 타임라인 구축.
- **출력**: `episodes/ep{XX}/research_brief.md`

**Step 2: 다시점 분석 (STORM)**
- 각 세력 시점 분석 및 갈등 매트릭스 도출.
- **출력**: `episodes/ep{XX}/perspectives.md`

**Step 3: 팩트 검증 (Loki)**
- 팩트 10개 추출 및 진위 판정.
- **출력**: `episodes/ep{XX}/fact_check.md`

---

## Stage 0c: 시각적 기획 (Knowledge Map) — `/plan-visual`

### 실행
```
/plan-visual ep{XX}
```

### 목표
- 리서치된 **팩트(Fact)**와 **이야기 비트(Story Beat)**를 시각적으로 연결.
- 이번 에피소드의 **세계관(Metaphorical Setting)** 확정.

### 무슨 일이 일어나는가
1. `episodes/ep{XX}/planning_vault/` 생성.
2. Obsidian Canvas를 사용하여 팩트 노드와 비유(Metaphor) 노드 연결.
3. **핵심 서사(Core Narrative) 설계**: 리서치된 팩트를 기반으로 각 세력의 갈등과 목표를 시각적으로 기획.
4. **출력**: `ep01_knowledge_map.canvas`, `episode_plan.md`

---

## Stage 0d: 대본 작성 및 프롬프트 파싱 — `/write-script`

### 실행
```
/write-script ep{XX}
```

### 목표
- **Fountain** 포맷을 기반으로 대사와 시각 연출이 완벽히 분리된 대본 작성.
- 작성된 대본을 AI 비주얼 생성을 위한 **Prompt Book(Manifest)**으로 변환.

### 사용되는 도구 (lib_ai)
- **`KITScenarist` DB 참조**: 이전 에피소드의 서사 및 캐릭터 관계 데이터를 불러와 대본에 연속성을 부여합니다.
- **`screenplain` 파서**: 텍스트 대본을 ComfyUI가 읽을 수 있는 매니페스트 데이터로 변환합니다.

### 무슨 일이 일어나는가 (4-Pass)
1. **서사 로드 (Narrative Guide)**: `planning_vault`의 지식 맵을 읽고 기획된 서사 뼈대를 로드합니다.
2. **대본 초안 (Fountain)**: 행동(Action) 지문에는 시각적 비유(Metaphor)를, 대사와 나레이션에는 정확한 **팩트(Fact)**를 담아 정보 전달의 본질을 잃지 않도록 작성합니다.
3. **구조 검증 (Structural Audit)**: 컷 밀도(20+ cuts/min)와 대사/액션의 비율을 검토합니다.
4. **프롬프트 북 변환**: `screenplain` 엔진이 대본을 파싱하여, 각 샷의 카메라, 캐릭터, 프롬프트가 매핑된 최종 `manifest.json`을 출력합니다.


---
### 실행용 대본 파생

`/write-script`가 만든 manifest는 바로 실행용으로 쓰지 않는다. 아래 파생 단계를 거친다.

- writer script: 사람 검토용 원본
- tts script: TTS/보이스 생성용
- subtitle script: 자막 표출용
- visual scene script: 스토리보드/비주얼 생성용
- timing script: 샷 길이/러프 타이밍용

```bash
python3 pipeline/shared/script_artifact_splitter.py --manifest episodes/ep01/manifest.json
```
- 2C: 목차를 씬으로 분해
- 2D: 샷 의도 초안 작성
  - 상황/감정에 따라 기본 `shot_size`, `angle`, `composition` 후보 결정
  - 필요 시 `emotion_shot_matrix.json`, `shot_statistics.json`을 참조해 프레이밍 초안 보강
- 2E: 대사 작성

**대사 작성 시 말투 규칙:**
- **나레이터**: `SHOW_BIBLE.md` 나레이터 톤 섹션 필수 참조
  - 한 문장 = 한 줄. 줄바꿈이 리듬. 설명 안 하고 보여줌.
  - 톤 레퍼런스: Anthony Bourdain(보여주기) + Bill Burr(찌르기)
  - 한 줄에 정보 3개 금지. 숫자 하나만 강조.
- **캐릭터**: Step 2B의 말투 레퍼런스 매핑 따름
  - 자막 DB 작품의 "느낌"을 따라감 (내용이 아니라 리듬, 길이, 끝맺음)

**Pass 3: Claude 리파인**
- 7축 자체 진단 (Hook/비유/팩트/arc/리텐션/장치/Shadow Player)

### 중요 교정: scene는 shot가 아니다

`script.md`의 `### S001` 같은 헤더는 **scene block**이다.  
이걸 바로 manifest shot으로 쓰면 안 된다.

필수 규칙:
- `scene 1개 = shot 1개` 금지
- `scene 1개 = beat 3~6개`를 기본으로 설계
- **길이의 자율성**: 5분, 10분 등 하드코딩된 길이에 얽매이지 않는다. 리서치된 팩트의 깊이와 서사의 완성도가 허락하는 한 길이는 유동적이다.
- 평균 샷 길이 2-3초. 최대 5초 (establishing shot 예외).
- 1 narrative sentence = 2-4 visual cuts (1:1 매핑 금지)

필수 분해 절차:
1. `scene` 작성
2. 각 scene를 `beat`로 분해
3. 각 beat를 `shot/cut`으로 분해
4. 그 shot 목록이 storyboard의 입력이 된다

즉 `manifest.json`의 `shots[]`는 scene 목록이 아니라 **실제 컷 목록**이어야 한다.

---

## Stage 0d/0e: Scene → Beat → Shot 분해 + 재분해

이 단계는 storyboard 전에 반드시 수행한다. Stage 0d/0e에 해당.

### 목표
- 긴 내레이션 단락을 그대로 한 컷에 올리지 않는다
- 컷 전환 리듬과 샷 목적을 먼저 확정한다
- **20+ cuts/min** 밀도를 달성한다

### 산출물
- `episodes/<ep>/storyboard/scene_beat_map.json`
- `episodes/<ep>/storyboard/shot_list.json`

### shot 설계 규칙
- 한 shot의 평균 길이: **2-3초** (최대 5초, establishing shot 예외)
- 한 shot은 한 개의 시각 목적만 가진다
  - establish
  - reveal
  - reaction
  - comparison
  - map insert
  - quote insert
  - text_overlay
  - payoff
- 하나의 shot에 설명 4문장을 몰아넣지 않는다
- 정보 카드/통계판은 컷의 주인공이 아니라 보조 insert로만 쓴다
- **1 narrative sentence = 2-4 visual cuts** (1:1 매핑 금지)

### 샷 타입 비율
| 타입 | 비율 | 설명 |
|------|------|------|
| scene | 65% | 메인 장면 (캐릭터, 배경, 액션) |
| insert | 20% | 지도, 통계, 인포그래픽, 클로즈업 |
| reaction | 8% | 캐릭터 리액션 컷 |
| text_overlay | 7% | 제목, 자막 강조, 핵심 수치 |

### 재분해 (Re-decomposition) 워크플로우

**언제 재분해하는가:**
- cuts/min < 20 일 때 (10분 에피소드에서 120 미만)
- 대본 수정 후 scene 구조가 변경되었을 때
- animatic 리뷰에서 특정 구간이 지루하다고 판정될 때

**재분해 프로세스:**
1. `script.md`에서 내러티브 문장 추출
2. 각 문장을 2-4개 visual cut으로 분해
3. cut type 지정 (scene / insert / reaction / text_overlay)
4. 타이밍 계산 (목표 평균 2-3초)
5. cuts/min 검증 → 미달 시 insert/reaction 추가

```bash
# 초기 분해
python pipeline/shared/scene_beat_shot_planner.py --manifest episodes/ep01/manifest.json

# 재분해 (컷 밀도 미달 시)
python pipeline/shared/scene_beat_shot_planner.py --manifest episodes/ep01/manifest.json --redecompose
```

> 재분해 템플릿: `context/shot_decomposition_v2.md` 참조

### S001 예시 (56→120 재분해 후)
- `world map establish` (scene, 3s)
- `Hormuz zoom-in` (scene, 2s)
- `hallway metaphor insert` (insert, 2s)
- `tanker queue close` (scene, 2.5s)
- `oil price text overlay` (text_overlay, 1.5s)
- `America reaction` (reaction, 2s)
- `door/chokepoint emphasis` (scene, 2s)

---

## Stage 1 (개요): 스토리보드 — `/storyboard`

### 입력
- `scene_beat_map.json`
- `shot_list.json`
- storyboard references

### 출력
- 실제 컷 단위 storyboard
- 각 shot의:
  - shot size
  - angle
  - composition
  - camera intent
  - staging note
  - reference image

### 금지 규칙
- shot 수가 scene 수와 같으면 실패
- 20초 이상 지속되는 shot은 기본적으로 실패
- reference를 blurred texture처럼만 쓰고 템플릿 보드를 덮어쓰면 실패

---

## Stage 1c: Animatic / Story Reel

Storyboard 다음 단계는 바로 final keyframe이 아니라 `animatic`이다.

### 목표
- 컷 수와 컷 길이를 오디오 기준으로 먼저 검증
- 리듬이 죽었는지 final rendering 전에 확인

### 산출물
- `episodes/<ep>/animatic/animatic.mp4`
- `episodes/<ep>/animatic/animatic_timeline.json`

### 규칙
- storyboard panel을 cut 순서대로 컷 편집
- rough voice 또는 scratch narration에 맞춰 길이 조정
- animatic 통과 전 Stage 1 final keyframe 금지

---

## Stage 1 (보충): Layout

Animatic이 통과되면 각 shot의 실제 화면 배치를 확정한다.

### 목표
- 캐릭터 위치
- 카메라 거리
- 시선 방향
- 배경 깊이
- 정보 overlay 위치
를 final keyframe 전에 잠근다

### 산출물
- `episodes/<ep>/layout/layout_manifest.json`

### 규칙
- 레퍼런스는 장면 구도 기준으로 사용
- 정보 panel / stats box / lower-third는 장면을 침범하지 않음
- 레이아웃 없이 Stage 1 keyframe render 금지
- 자동 보강 → 사용자 확인 1회

**Pass 4: 감사**
- 풍자 품질 + 리텐션 구조 + 계층적 역추적 검증

**Pass 5: 팩트 체크**
- 리서치 데이터와 대본 교차 검증

**Pass 6: 매니페스트 JSON 생성**
- 프로덕션 파이프라인용 구조화 데이터

**Pass 7: Exit Gate + Memory**
- 13-Metric 채점 → PASS/CONDITIONAL/FAIL

### 산출물
```
episodes/ep{XX}/
├── script_draft.md    ← Dramatron 초안
├── script.md          ← 최종 스크립트 (EN/KO 이중)
└── manifest.json      ← 프로덕션 매니페스트
```

### 대본 포맷 (v4.0 — SHOT_TAXONOMY 통합)
```markdown
## S001 [SKIT] — Hook: 톤 스위치 (0:00-0:15)
**비주얼**: 장면 설명
Shot: CU | low_angle | two_shot          ← SHOT_TAXONOMY 축 1/2/3
Light: low_key | hard_light | side_light  ← 축 4 (intensity/quality/direction)
Mood: tense                               ← 축 5
Situation: confrontation                  ← 축 6
**카메라**: Track Shot → Long Shot → Zoom Shot
**스테이징**: America=왼쪽, Denmark=오른쪽
**프리셋**: hook_tone_switch

> **America**
> EN: "영어 대사 [uv_break] 계속"
> KO: "한국어 대사 [uv_break] 계속"
> Audio: Soft → sudden yakuza tone
```

> **Shot/Light/Mood/Situation의 모든 값은 `context/SHOT_TAXONOMY.md`에서만 가져온다.**

---

## Stage 1 (상세): 스토리보드 및 레이아웃 — `/storyboard`

### 실행
```
/storyboard ep{XX}
```

### 무슨 일이 일어나는가
1. manifest.json의 각 샷 분석
2. **프리셋 자동 적용** (`shot_presets.json` 14종)
   - camera_sequence → manifest camera_movement
   - staging → layout_blueprint bbox
   - reference_images → PSG/가루파 자동 매칭
3. **FilmAgent 8규칙 자동 검증**
   - Track Shot은 씬 첫 샷만
   - Zoom은 Long 뒤에만
   - Close 3연속 금지 등
4. 레퍼런스 이미지 매칭:
      - **6축 태그 검색**: 244K 스크린샷 태그 DB에서 shot_size+angle+mood+situation 복합 쿼리
      - **CLIP 벡터 검색**: 시맨틱 유사도 (텍스트→이미지)
      - **174장 통합 DB**: PSG+Garupa 수동 큐레이션
5. compact reference bundle 선택 및 semantic read 확장.
6. enriched_visual_prompt 보강.
7. manifest.json 업데이트.
8. **레이아웃 확정**: `animatic_layout_builder.py`를 통해 캐릭터/카메라 배치를 고정.
9. **Storyboarder 연동 (lib_ai/storyboarder)**: `tools/manifest_to_storyboarder.py`를 실행하여 `.storyboarder` 프로젝트를 생성하고 시각적 검토.
10. **Kitsu 상태 업데이트 (lib_ai/gazu)**: 샷 상태를 'Storyboard Approved'로 기록.

### reference bundle sequence

레퍼런스 스크린샷을 볼 때는 먼저 compact bundle로 용도를 고른다.

1. `get_storyboard_reference_bundle(use_case='composition')`
2. `get_storyboard_reference_bundle(use_case='character')`
3. `get_storyboard_reference_bundle(use_case='background')`
4. 필요 시 `get_reference_context`
5. 필요 시 `get_frame_structure`
6. 필요 시 `get_composition_profile`
7. 필요 시 `get_subject_layout`
8. 필요 시 `get_background_layout`
9. `get_frame_image`

판단 기준:
- `composition`: 구도와 시선 흐름만 차용
- `character`: 캐릭터 존재감과 포즈 힌트만 차용
- `background`: 배경 프레이밍과 여백, 분위기만 차용

최종 스토리보드 메모에는 아래 3개를 남긴다.
- `composition_driver`
- `subject_dominance`
- `background_role`

manifest에 자동으로 붙일 때:
```bash
python3 tools/knowledge_stack/cli.py storyboard-ref \
  --manifest /home/hugh/youtube-studio-copy/episodes/ep01/manifest.json \
  --include-modes
```

### 벡터 검색 (선택)
```bash
source ~/venvs/phase3-gpu/bin/activate
cd pipeline/shared
python suggest_visuals.py --text "두 캐릭터가 대립하는 장면" --semantic
```
- 규칙 기반 프리셋 + CLIP 이미지 유사도 + 자막 의미 검색

### 카메라 규칙 검증
```bash
python validate_camera_rules.py episodes/ep{XX}/manifest.json
# 또는 프리셋 전체 검증:
python validate_camera_rules.py --preset-check context/shot_presets.json
```

---

## Stage 2-3: 이미지 생성 — `/generate-visuals`

### 실행
```
/generate-visuals ep{XX}
```

### 사전 조건
- ComfyUI 서버 실행 중 (포트 8188)
- GPU VRAM 6GB+ 여유
- 다른 GPU stage와 겹치지 않아야 함 (`voice`와 동시 실행 금지)

### 무슨 일이 일어나는가
1. manifest의 각 shot → enriched_visual_prompt 추출
2. 현재 canonical path는 `generate_keyframes.py`
3. 렌더링된 키프레임들은 **SnowFS (lib_ai/SnowFS)**를 통해 버전 관리 및 분기(branch)가 추적됩니다.
4. 모든 이미지가 생성되면 **Kitsu (lib_ai/gazu)**에 샷 상태를 'Layout Approved' 및 'Render Complete'로 업데이트합니다.

---

## Stage 4: 립싱크 및 애니메이션 보간 (Animation)

이 단계는 생성된 정지 키프레임을 움직이는 영상 샷으로 변환합니다.

### 실행 (예정)
```
/animate-video ep{XX}
```

### 무슨 일이 일어나는가
1. **LivePortrait (lib_ai/LivePortrait)**: 캐릭터의 얼굴이 크게 나오는 샷(CU/MCU)에 대해, 생성된 TTS 오디오 트랙을 기반으로 입모양(Lip-sync)과 표정 변화 애니메이션을 적용합니다.
2. **Kitsu 상태 업데이트**: 완료된 애니메이션 클립을 Kitsu에 'Animation Complete'로 기록.

### ComfyUI 서버 시작
```bash
cd ~/ComfyUI/app
nohup ../venv/bin/python main.py --listen 0.0.0.0 --port 8188 &
```

### 산출물
```
episodes/ep{XX}/images/
├── keyframe_01.png
├── keyframe_02.png
...
└── keyframe_18.png
```

### 현재 운영 판정
- `ep02` 기준 실제 `visuals-run` 수행됨
- 결과는 `8/9 render`, `3/9 pass`
- 즉 실행은 live지만 품질은 아직 canonical production 수준에 못 미침
- 운영 책임 역할: `comfy_specialist`, `gpu_worker`, `quality_auditor`

---

## Stage 5: 음성 생성 — `/generate-voice`

### 실행
```
/generate-voice ep{XX}
```

### 무슨 일이 일어나는가
1. manifest의 각 dialogue → TTS 생성
   - **EN**: Chatterbox TTS (3.4GB VRAM)
   - **KO**: Edge-TTS (InJoon 음성)
2. BGM 생성: ACE-Step v1.5
3. SFX: "뚜둔!", gavel, 등

### 현재 운영 판정
- `ep02` 기준 실제 `voice-run` 수행됨
- narration `3/3`, dialogue `7/7` 생성 완료
- 현재 voice path는 실제 production-valid 상태
- 운영 책임 역할: `tts_specialist`, `gpu_worker`, `quality_auditor`

### 음성 매핑
| Speaker | 도구 | 레퍼런스 |
|---------|------|----------|
| Narrator (EN) | Chatterbox | `assets/voice_refs/narrator.wav` |
| Narrator (KO) | Edge-TTS | InJoon |
| America | Chatterbox | `assets/voice_refs/america.wav` |
| 기타 캐릭터 | Chatterbox | `assets/voice_refs/character_base.wav` |

### 산출물
```
episodes/ep{XX}/audio/
├── nar_en_s001.wav
├── nar_ko_s001.mp3
├── dialogue/
├── bgm/
└── sfx/
```

---

## Stage 6: 최종 조립 — `/assemble-video`

### 실행
```
/assemble-video ep{XX}
```

운영 책임 역할:
- `assembly_specialist`
- `quality_auditor`

### 무슨 일이 일어나는가
1. 각 shot의 keyframe + audio → 개별 clip (FFmpeg)
2. 클립 concat → 단일 MP4
3. 오디오 믹싱 (나레이션 + BGM + SFX)
4. SRT 자막 생성 (EN/KO)
5. H.264 + AAC, 1920×1080

### 수동 조립 (스크립트 없이)
```bash
# 클립 목록 생성
for f in episodes/ep{XX}/images/clip_*.mp4; do
  echo "file '$(realpath $f)'" >> /tmp/concat.txt
done

# FFmpeg concat
ffmpeg -f concat -safe 0 -i /tmp/concat.txt \
  -c:v libx264 -preset medium -crf 18 \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  episodes/ep{XX}/final/ep{XX}_title.mp4
```

### 산출물
```
episodes/ep{XX}/final/
├── ep{XX}_title.mp4     ← 최종 영상 (1920×1080, H.264)
├── ep{XX}_title.srt      ← 자막
└── ep{XX}_thumbnail.png  ← 썸네일 (선택)
```

---

## 전체 자동 실행 — `/produce-episode`

### 11-Step 파이프라인을 한 번에 (Stage 0-6)
```
/produce-episode "이란 전쟁 28일"
```

자동으로 Stage 0 (intelligence+script+decomposition) → Stage 1 (storyboard+animatic) → Stage 2 (asset design) → Stage 3 (keyframe rendering) → Stage 4 (animation) → Stage 5 (audio) → Stage 6 (assembly+QA) 체이닝. 각 단계 사이에 Quality Gate.

---

## 핵심 파일 경로

### 컨텍스트 (읽기 전용)
| 파일 | 용도 |
|------|------|
| `context/SHOW_BIBLE.md` | 세계관, 캐릭터, 톤, 포맷 |
| `context/CHARACTER_SHEETS.md` | 16캐릭터 시트 + 에셋 현황 |
| `context/SCORING_RUBRICS.md` | 단계별 채점 기준 |
| `context/QUALITY_GATES.md` | 통과 기준 (PASS/CONDITIONAL/FAIL) |
| `context/SHOT_TAXONOMY.md` | **6축 영상 연출 태그 체계 (SSOT)** |
| `context/ANIME_DATA_CAPABILITIES.md` | 244K 스크린샷+68K 자막 활용 리포트 |
| `context/shot_presets.json` | 14종 상황별 구도 프리셋 |
| `context/unified_reference_db.json` | 174장 통합 레퍼런스 DB |
| `context/sentiment_to_visual_matrix.json` | 감정→카메라 매트릭스 |

### 파이프라인 스크립트
| 파일 | 용도 |
|------|------|
| `pipeline/stage0_research/deep_researcher.py` | GPT Researcher wrapper (현재 미사용) |
| `pipeline/stage0_research/storm_perspectives.py` | STORM 다시점 분석 |
| `pipeline/stage0_research/knowledge_graph.py` | Neo4j 지식 그래프 |
| `pipeline/stage0_research/fact_checker.py` | 팩트 검증 (오프라인) |
| `pipeline/shared/suggest_visuals.py` | 연출 조수 (--semantic) |
| `pipeline/shared/validate_camera_rules.py` | FilmAgent 규칙 검증 |
| `pipeline/shared/vector_search.py` | CLIP + 자막 벡터 검색 |
| `pipeline/shared/analyze_reference_patterns.py` | 감정→카메라 매트릭스 생성 |

### 애니메이션 데이터
| 데이터 | 규모 | 위치 |
|--------|------|------|
| 스크린샷 | 244,763장 (11작품 151ep) | `/mnt/e/download/panty/screenshots/{작품명}/{작품명}_{화수}/` |
| 스크린샷 6축 태그 | 작품당 1화수 태깅 완료 | `references/screenshot_tags/{ep}_tags.json` |
| 자막 + 감정 태그 | 68,370씬 (99% 태깅) | `references/vibe-search/total_smart_reference.json` |
| CLIP 이미지 임베딩 | 96,820 × 768dim (297MB) | `embeddings/clip_image_embeddings.npy` |
| 자막 텍스트 임베딩 | 68,370 × 384dim (105MB) | `embeddings/subtitle_embeddings.npy` |
| 임베딩 인덱스 | 경로 매핑 | `embeddings/clip_image_paths.json`, `embeddings/subtitle_metadata.json` |

### 스크린샷 소스 작품 (11작품)
| 작품 | 에피소드 | 장르 | 참고용도 |
|------|---------|------|---------|
| nichijou | 26ep | 코미디/부조리 | 과장 연출, 코미디 비트 |
| psg_new | 13ep | 액션/코미디 | 메인 비주얼 스타일 |
| psg_2010 | 13ep | 액션/코미디 | 오리지널 PSG 연출 |
| bocchi | 12ep | 코미디/음악 | 패닉, 감정 폭발 |
| kyou_kara | 10ep (OVA) | 코미디/불량 | 허세, 깡패 말투 |
| gokushufudou | 10ep | 코미디/일상 | 갭 모에, 데드팬 |
| watamote | 12ep | 코미디/우울 | 사회불안, 내면 독백 |
| bucchigiri | 12ep | 액션/불량 | 싸움, 위협, 긴장 |
| zvezda | 13ep | 코미디/SF | 보스 캐릭터, 작전 |
| kenka_banchou | 12ep | 액션/학원 | 격투, 단호함 |
| jojo3 | 18ep | 액션/모험 | JoJo 스탠드 연출, 극적 포즈 |

### 6축 태그 체계 (SSOT)
모든 시각 연출 용어는 `context/SHOT_TAXONOMY.md` 단일 기준. 태깅, 대본, 콘티, 검색 전부 동일 용어.
- 축 1: Shot Size (ECU~ELS, 9종)
- 축 2: Camera Angle (eye_level~ground_level, 11종)
- 축 3: Composition (single~foreground_framing, 14종)
- 축 4: Lighting (intensity×quality×direction, 3서브축)
- 축 5: Mood (comedy~intimidating, 12종)
- 축 6: Situation (confrontation~idle, 20종)

활용 방안 상세: `context/ANIME_DATA_CAPABILITIES.md`

### 파일 이름 규칙

스크립트 파일: `{회차}_{제목}_{언어}_{버전}_{날짜}.md`

```
ep01_56000_v1_20260329.md              ← EN 최종
ep01_56000_ko_v1_20260329.md           ← KO 최종
ep01_56000_draft_20260329.md           ← 초안
ep02_everybody-thinks-they-won_v2_20260330.md  ← 수정 시 버전 올림
```

- 제목: 짧게, 영어, 하이픈 구분
- 언어: 생략=EN, ko=한국어
- 버전: v1, v2, v3... 리라이트할 때마다
- 날짜: YYYYMMDD

### 에피소드 구조
```
episodes/ep{XX}/
├── research_brief.md              ← /deep-research Step 1
├── reference_analysis.md          ← /deep-research Step 0.5
├── perspectives.md                ← /deep-research Step 2
├── fact_check.md                  ← /deep-research Step 4
├── episode_plan.md                ← /deep-research Step 0.6
├── ep{XX}_{title}_draft_{date}.md ← /write-script 초안
├── ep{XX}_{title}_v{N}_{date}.md  ← /write-script 최종
├── ep{XX}_{title}_ko_v{N}_{date}.md ← 한국어 버전
├── manifest.json                  ← /write-script Pass 6
├── images/              ← /generate-visuals
│   └── keyframe_*.png
├── audio/               ← /generate-voice
│   ├── nar_en_s*.wav
│   ├── nar_ko_s*.mp3
│   ├── dialogue/
│   ├── bgm/
│   └── sfx/
└── final/               ← /assemble-video
    ├── ep{XX}_title.mp4
    └── ep{XX}_title.srt
```

---

## 유용한 커맨드

### 벡터 검색
```bash
source ~/venvs/phase3-gpu/bin/activate
cd pipeline/shared

# 텍스트로 이미지 검색 (CLIP)
python vector_search.py --text "two characters arguing" --top_k 5

# 자막으로 검색 (sentence-transformer)
python vector_search.py --subtitle "안 팔아" --top_k 5

# 연출 조수 (규칙 + 벡터 하이브리드)
python suggest_visuals.py --text "Denmark가 분노하는 장면" --semantic
```

### 카메라 규칙 검증
```bash
python validate_camera_rules.py episodes/ep31/manifest.json
python validate_camera_rules.py --preset-check context/shot_presets.json
```

### Neo4j 지식 그래프
```bash
# 연결 테스트
python pipeline/stage0_research/knowledge_graph.py --test

# 리서치 결과 저장
python pipeline/stage0_research/knowledge_graph.py --ingest episodes/ep31/research_brief.md --episode ep31

# 전체 관계 조회
python pipeline/stage0_research/knowledge_graph.py --summary
```

### 감정→카메라 매트릭스 재생성
```bash
python pipeline/shared/analyze_reference_patterns.py
# → context/sentiment_to_visual_matrix.json 업데이트
```

### CLIP 품질 평가
```bash
python pipeline/shared/eval_clip_quality.py
# → 10쿼리 × Top-5, precision@5 측정
```

---

## 품질 기준 요약

| 단계 | 통과 기준 | 핵심 메트릭 |
|------|-----------|-------------|
| /find-topic | ≥ 7.0 | 13-Metric 가중평균 |
| /write-script | ≥ 7.5 | hook, fact, rhythm, arc, satire, retention, metaphor |
| /storyboard | ≥ 7.0 | layout, camera, reference, prompt, composition |
| /generate-visuals | ≥ 7.0 | consistency, quality, character, composition |
| /generate-voice | ≥ 7.0 | clarity, emotion, sync, mix |
| /assemble-video | ≥ 8.0 | flow, audio, visual, pacing + **사람 리뷰 필수** |

---

## 트러블슈팅

### ComfyUI ControlNet 에러 (mat1/mat2)
- **원인**: Flux 2 VAE(32ch)를 Flux 1 모델+ControlNet에 사용
- **해결**: VAE를 `ae.safetensors` (Flux 1, 16ch)로 교체

### GPU VRAM 부족
- ComfyUI: batch_size 줄이기, float16 사용
- CLIP 벡터화: `--batch-size 64`로 줄이기
- 동시 실행 주의: Ollama + ComfyUI + CLIP 동시 사용 시 VRAM 부족

### langchain 버전 충돌
- `pip install "langchain-core>=0.3,<0.4"`로 핀
- GPT Researcher는 의존성 지옥 — 별도 venv 권장 또는 미사용

### Neo4j 연결 안 됨
```bash
docker start neo4j-research
# 또는 새로 생성:
docker run -d --name neo4j-research -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/research2026 -v ~/neo4j_data:/data neo4j:5-community
```
Production quality gate commands:

```bash
wsl python3 /home/hugh/youtube-studio-copy/tools/youtube_studio_frontdoor.py --episode-id ep02 visuals-prepare
wsl python3 /home/hugh/youtube-studio-copy/tools/youtube_studio_frontdoor.py --episode-id ep02 voice-prepare
wsl python3 /home/hugh/youtube-studio-copy/tools/youtube_studio_frontdoor.py --episode-id ep02 assembly-prepare
wsl python3 /home/hugh/youtube-studio-copy/tools/youtube_studio_frontdoor.py --episode-id ep02 production-status
wsl python3 /home/hugh/youtube-studio-copy/tools/youtube_studio_frontdoor.py --episode-id ep02 production-qc
```

Production run activation commands:

```bash
wsl python3 /home/hugh/youtube-studio-copy/tools/youtube_studio_frontdoor.py --episode-id ep02 bgm-run --dry-run --force-synth
wsl python3 /home/hugh/youtube-studio-copy/tools/youtube_studio_frontdoor.py --episode-id ep02 visuals-run --dry-run
wsl python3 /home/hugh/youtube-studio-copy/tools/youtube_studio_frontdoor.py --episode-id ep02 voice-run --dry-run
wsl python3 /home/hugh/youtube-studio-copy/tools/youtube_studio_frontdoor.py --episode-id ep02 assembly-run --dry-run
```
