# CLAUDE.md — "지구촌 반상회" AI 프로덕션 회사

> **채널명**: TOO GLOBAL TO HANDLE (지구촌 반상회)
> **컨셉**: 미소녀 캐릭터 × 리얼리티TV 연출 × 팩트 기반 국제정치 풍자
> **위치**: `/home/hugh/youtube-studio-copy/` (= `E:\youtube-studio\`)

---

## 회사 규칙

### 1. 파이프라인 순서 (11단계 Stage 0-6 + 오케스트레이터 + 기획/진행)
```
/plan-episode                        ← 기획PD (시즌 기획, 트렌드, 경쟁분석, 콘텐츠 캘린더)
  ↓ 주제 후보 + 로드맵
/produce-episode {주제 or epXX}      ← 총괄PD (11단계 자동 오케스트레이션)
  └─ Stage 0: /find-topic → /deep-research → /write-script → scene/beat/shot 분해 → 컷 재분해(20+/min)
     Stage 1: 스토리보드 패널(ComfyUI) → 컨택트시트 → 러프 애니매틱 → 비주얼 게이트
     Stage 2: 캐릭터/배경/소품 에셋 → (Character LoRA 트레이닝)
     Stage 3: ComfyUI 키프레임 렌더 → 품질 채점 → MD5 고유성 검증
     Stage 4: WAN 2.2 애니메이션 → 카메라 이펙트
     Stage 5: TTS(Chatterbox EN) → BGM(ACE-Step) → SFX → 믹싱
     Stage 6: /assemble-video → 자막 → publishability audit → Shorts
       ↑ /check-progress             ← 진행PD (상태 추적, QA 라우팅, 블로커 감지)
```
각 단계는 독립 스킬로 실행. **manifest.json이 공유 데이터 계약** — 모든 단계가 읽고 쓰는 작업 지시서.
`/plan-episode`는 "뭘 만들까" 전략, `/produce-episode`는 "어떻게 만들까" 실행, `/check-progress`는 "지금 어디까지 됐나" 추적.
현재 정렬 상태, 코드 현실, 구현 우선순위는 `work/pipeline_rebuild_plan/MASTER_PLAN.md`를 기준으로 관리한다.

**컷 밀도 규칙** (2026-04-06 확정):
- 목표: **20+ cuts/min**, 평균 2-3초/shot, 최대 5초
- 1 나레이션 문장 = 2-4 비주얼 컷 (1:1 금지)
- 컷 비율: scene 65% + insert 20% + reaction 8% + text_overlay 7%
- PIL 렌더링은 publishable 경로에서 **완전 제거** — ComfyUI only

### 2. 에피소드 산출물 구조
```
episodes/ep{XX}/
├── manifest.json                ← 파이프라인 공유 지시서 (120+ shots)
├── script.md                    ← 풀 스크립트 (EN/KO 이중)
├── shot_decomposition_v2.md     ← 컷 분해 명세 (scene별 shot 정의)
├── storyboard/
│   ├── panels/                  ← ComfyUI 960×540 스토리보드 패널
│   ├── contact_sheet.png        ← 전체 패널 그리드
│   ├── scene_beat_map.json      ← 씬→비트→샷 매핑
│   └── shot_list.json           ← 전체 샷 목록
├── animatic/
│   └── rough_animatic.mp4       ← 러프 애니매틱 (패널+TTS)
├── images/                      ← ComfyUI 1920×1080 키프레임
├── clips/                       ← WAN 2.2 애니메이션 클립
├── audio/                       ← TTS, BGM, SFX
├── script_artifacts/            ← timing, TTS, subtitle 스크립트
└── final/                       ← 최종 MP4, SRT, 썸네일, Shorts
```

### 3. 콘텐츠 원칙
- **팩트 우선**: 코미디가 아닌 팩트 기반 풍자. 유머는 이중 레이어 톤(진지 나레이션 × 유치한 캐릭터)의 갭에서 자연스럽게.
- **이중 언어**: 모든 대사 EN + KO. 나레이터는 EN/KO 별도 speaker.
- **교차편집**: [SKIT] 40% + [DOCU] 45% + [CONFESSIONAL] 15% 리듬 유지.
- **금지**: 특정 국가 혐오, 인종차별, 성적 대상화, 실제 정치인 얼굴.
- **팩트 밀도**: 에피소드당 핵심 팩트 5-7개. 리텐션 피크 25/50/75%.

### 4. 기술 환경
| 항목 | 값 |
|------|-----|
| GPU | RTX 5070 Ti 16GB |
| torch | 2.10+cu128 (sm_120 Blackwell) |
| Python venvs | `ace-step-gpu` (BGM), `phase3-gpu` (diffusers+ML) |
| TTS 1순위 | Chatterbox (`~/chatterbox/`, 3.4GB VRAM, **EN only**) |
| TTS 폴백 | Edge-TTS (KO InJoon) — EN Guy는 미사용, Chatterbox가 EN 전담 |
| TTS 금지 | Fish Speech S2 Pro (16GB VRAM 초과, 사용 불가) |
| voice_refs | `assets/voice_refs/` (심링크 → `~/youtube/ch2-geopolitics-moe/audio/voice_refs/`) |
| voice 매핑 | `pipeline/shared/manifest_loader.py` (`VOICE_REF_MAP`, `SPEAKER_EXAGGERATION`) |
| ComfyUI | Flux 1 Dev GGUF (Q5_K_S) + **Juustagram Chibi LoRA @ 1.0**, 트리거: `juustagram style, chibi` |
| ComfyUI 스타일 | **azur lane slow ahead style** 앵커 + flat color cel shading |
| ComfyUI 렌더 | CFG 3.5, Steps 30, 시드 65700, **AnimeSharp 4x → 2048x2048** |
| IP-Adapter | 골든샷 생성: OFF / 스토리보드: 0.4 (스타일 전이용) |
| ControlNet | 스토리보드: 꺼짐 / 키프레임: Depth (우리 스토리보드 기반만) |
| 프롬프트 변환 | prompt_compiler_llm.py (qwen3.5 → tags + natural, 10-15태그/40단어) |
| **이미지 제약** | **`context/IMAGE_GENERATION_CONSTRAINTS.md` 필독** — 1캐릭터, 심플배경, 정적포즈만 |
| BGM | ACE-Step v1.5 (`~/ACE-Step/`) |
| 애니메이션 | MimicMotion (`~/MimicMotion/`), AnimateDiff |
| 레퍼런스 DB | scene_clusters.json (5,518 씬, 17K 프레임, 11 작품) + show_profiles.json (작품별 스타일) |
| 카메라 선택 | filmagent_camera.py (Debate-Judge LLM 카메라 결정) |
| 스크린샷 원본 | `/mnt/e/download/panty/screenshots/` (12 작품) |

### 5. 경로 규약
| 용도 | 경로 |
|------|------|
| 프로덕션 루트 | `/home/hugh/youtube-studio-copy/` |
| 파이프라인 스크립트 | `pipeline/stage{0-4}_*/` |
| 공유 에셋 | `assets/` |
| 보이스 레퍼런스 | `assets/voice_refs/` (narrator.wav, america.wav, anime_db/) |
| 에피소드 산출물 | `episodes/ep{XX}/` |
| 지식 베이스 | `context/` |
| 프로덕션 메모리 | `memory/` |
| 레퍼런스 이미지 | `references/` |
| ComfyUI 워크플로우 | `workflows/` |
| 기존 소스 (읽기 전용) | `~/youtube/ch2-geopolitics-moe/` |

### 6. manifest.json 규약
- 위치: `episodes/ep{XX}/manifest.json`
- 스키마: `context/PRODUCTION_MANUAL.md` 참조
- 모든 파이프라인 단계가 manifest를 읽고 → 보강하여 → 다시 씀
- shot_id: `s001`, `s002`, ... (3자리 패딩)
- type: `SKIT` | `DOCU` | `CONFESSIONAL`
- `stage_scores`: 각 단계 품질 점수 (SCORING_RUBRICS.md 기준)

### 6.5. 품질 시스템
- **스코어링**: `context/SCORING_RUBRICS.md` — 6단계 메트릭, 가중치, 통과 기준
- **게이트**: `context/QUALITY_GATES.md` — PASS/CONDITIONAL/FAIL 전환 규칙
- **실험 (intra)**: `context/EXPERIMENT_LOOPS.md` — 변형 생성 + 승자 선택 프로토콜
- **실험 (inter)**: `context/AUTORESEARCH.md` — 에피소드 간 자율 파라미터 최적화 (Karpathy autoresearch)
- 모든 스킬이 Exit Gate에서 manifest `stage_scores`에 점수 기록
- 모든 스킬이 Memory Writeback으로 학습 기록
- `/autoresearch` 스킬 = 에피소드 간 실험 루프 (LOOP FOREVER, 7개 파라미터 좌표 하강)
- `memory/research_state.md` = 현재 최적 파라미터, `memory/experiment_results.tsv` = 실험 로그

### 7. 에이전트 부서
자세한 역할·도구·권한은 `AGENTS.md` 참조.
| 부서 | 스킬 | 역할 |
|------|------|------|
| **프로듀서** | `/produce-episode` | **7단계 오케스트레이션 + 품질 게이트 + 회고** |
| **기획PD** | `/plan-episode` | **시즌 기획 + 트렌드 + 경쟁분석 + 콘텐츠 캘린더** |
| 리서처 | `/find-topic` | 주제 발굴 + 팩트 수집 |
| 리서처(심화) | `/deep-research` | 심층 조사 + 다시점 분석 + 팩트 검증 + 에피소드 앵글 설계 |
| 대본가 | `/write-script` | 6-pass 대본 + 매니페스트 + Hook 3변형 + Outline 2변형 |
| 콘티감독 | `/storyboard` | 샷별 카메라·레퍼런스·레이아웃 |
| 아트디렉터 | `/generate-visuals` | 캐릭터·배경·키프레임 + Hero Shot 2변형 |
| 음성PD | `/generate-voice` | TTS + BGM + SFX + Narrator 2변형 |
| 편집감독 | `/assemble-video` | 최종 영상 조립 + QA + Release Gate |
| **진행PD** | `/check-progress` | **단계별 상태 추적 + QA 라우팅 + 블로커 감지 + 핸드오프** |
