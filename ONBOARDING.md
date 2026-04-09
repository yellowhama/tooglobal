# ONBOARDING — 지구촌 반상회 프로덕션 파이프라인

> **최종 갱신**: 2026-04-07
> **대상**: 새 AI 에이전트 또는 인간 작업자

---

## 1. 프로젝트 개요

**TOO GLOBAL TO HANDLE (지구촌 반상회)** 은 국제정치를 미소녀 캐릭터 리얼리티TV로 풍자하는 유튜브 채널이다. 세계관은 "지구촌 학원"이라는 명문 국제 고등학교이며, 각 국가가 한 명의 미소녀 학생으로 의인화된다. 대본부터 최종 MP4까지 전 공정을 AI 에이전트 파이프라인으로 자동화한다. 타겟: 국제정치에 관심 있는 한/영 이중 언어 시청자. 에피소드 길이 5-10분, 주 1회 목표.

---

## 2. 아키텍처 다이어그램

```
┌─────────────────── PRODUCTION PIPELINE ───────────────────┐
│                                                           │
│  /plan-episode          시즌 기획 + 트렌드 + 캘린더       │
│       │                                                   │
│       ▼                                                   │
│  /find-topic ──► /deep-research ──► /write-script         │
│  (뉴스 스캔)     (STORM+팩트검증)    (7-pass 대본)        │
│                                      │                    │
│                               manifest.json (공유 계약)   │
│                                      │                    │
│                                      ▼                    │
│                              /storyboard                  │
│                    (카메라 결정 + 레퍼런스 매칭)           │
│                          │                │               │
│                 Stage 1: 스토리보드       FilmAgent        │
│                 (960×540 러프 패널)   (Debate-Judge)       │
│                          │                                │
│                          ▼                                │
│                 Stage 2: 키프레임                          │
│                 (1920×1080 원화)                           │
│                          │                                │
│                          ▼                                │
│              ┌───────────┴───────────┐                    │
│         WAN 2.2 I2V              /generate-voice          │
│        (애니메이션)         (Chatterbox+BGM+SFX)          │
│              └───────────┬───────────┘                    │
│                          ▼                                │
│                   /assemble-video                         │
│              (FFmpeg 조립 + 자막 + QA)                    │
│                          │                                │
│                          ▼                                │
│                   final/ep{XX}.mp4                        │
│                                                           │
│  /check-progress ← 전 단계 상태 추적 + 블로커 감지       │
│  /autoresearch   ← 에피소드 간 파라미터 자동 최적화       │
└───────────────────────────────────────────────────────────┘
```

---

## 3. 디렉토리 맵

```
youtube-studio-copy/
├── CLAUDE.md                    # 회사 규칙 (이 파일부터 읽을 것)
├── AGENTS.md                    # 에이전트 부서 명세
├── WORKFLOW_GUIDE.md            # 단계별 실행 가이드
├── context/                     # 지식 베이스 (SSOT)
│   ├── SHOW_BIBLE.md            #   세계관, 톤, 캐릭터 매핑
│   ├── CHARACTER_SHEETS.md      #   16캐릭터 시트
│   ├── STYLE_GUIDE.md           #   비주얼 스타일 규칙
│   ├── SHOT_TAXONOMY.md         #   6축 영상 연출 태그 (SSOT)
│   ├── SCORING_RUBRICS.md       #   단계별 채점 기준
│   ├── QUALITY_GATES.md         #   PASS/CONDITIONAL/FAIL 규칙
│   ├── show_profiles.json       #   11작품 스타일 프로필
│   └── shot_presets.json        #   14종 카메라 프리셋
├── episodes/ep{XX}/             # 에피소드 산출물
│   ├── manifest.json            #   파이프라인 공유 지시서
│   ├── script.md                #   풀 스크립트 (EN/KO)
│   ├── storyboard/panels/       #   960×540 러프 패널
│   ├── images/                  #   1920×1080 키프레임
│   ├── clips/                   #   애니메이션 클립
│   ├── audio/                   #   TTS + BGM + SFX
│   └── final/                   #   MP4, SRT, 썸네일
├── pipeline/                    # Python 파이프라인 스크립트
│   ├── shared/                  #   공유 도구 (scene_cluster, filmagent 등)
│   ├── stage0_research/         #   리서치 도구
│   ├── stage1_visuals/          #   이미지 생성
│   ├── stage2_animation/        #   애니메이션
│   ├── stage3_audio/            #   음성/BGM
│   └── stage4_assembly/         #   최종 조립
├── assets/                      # 공유 에셋 (캐릭터 골든샷, voice_refs)
├── references/                  # 레퍼런스 이미지 DB
├── workflows/                   # ComfyUI 워크플로우 JSON
├── memory/                      # 프로덕션 메모리
└── work/                        # 진행 중 작업 계획
```

---

## 4. 워크플로우 요약

| 단계 | 스킬 | 하는 일 |
|------|------|---------|
| 기획 | `/plan-episode` | 시즌 기획, 트렌드 분석, 콘텐츠 캘린더 작성 |
| 주제 발굴 | `/find-topic` | 최신 국제뉴스 스캔 → 13-Metric 드라마 스코어로 채점 → 상위 3-5개 후보 |
| 딥 리서치 | `/deep-research` | 팩트 딥다이브 + STORM 다시점 분석 + Neo4j 지식 그래프 + 팩트 검증 |
| 대본 작성 | `/write-script` | 7-pass: 리서치 → Dramatron 초안 → Claude 보강 → 감사 → 팩트체크 → manifest.json |
| 콘티 | `/storyboard` | 샷별 카메라 결정 (FilmAgent) + 씬 클러스터 레퍼런스 매칭 + 레이아웃 |
| 비주얼 | `/generate-visuals` | ComfyUI로 스토리보드 패널 → 키프레임 생성. ControlNet + IP-Adapter |
| 음성 | `/generate-voice` | Chatterbox TTS (EN) + Edge-TTS (KO) + ACE-Step BGM + Freesound SFX |
| 조립 | `/assemble-video` | FFmpeg으로 최종 MP4 + SRT 자막 + 썸네일 + Shorts 컷 |
| 진행 추적 | `/check-progress` | 단계별 상태 확인, QA 라우팅, 블로커 감지 |
| 자율 최적화 | `/autoresearch` | 에피소드 간 7개 파라미터 좌표 하강 실험 루프 |

---

## 5. 기술 스택

| 항목 | 값 |
|------|-----|
| GPU | RTX 5070 Ti 16GB |
| PyTorch | 2.10+cu128 (sm_120 Blackwell) |
| Python venvs | `phase3-gpu` (ML), `ace-step-gpu` (BGM) |
| Image Gen | ComfyUI + Flux 1 Dev GGUF (Q5_K_S) |
| Style LoRA | Flat_Anime_Style @ 0.8 (키프레임) / 0.6 (캐릭터) / 0.4 (배경) |
| ControlNet | Union Pro + Canny |
| IP-Adapter | SigLIP (weight 0.4, 0-40% steps) |
| Sampler | Euler, CFG 3.5, Steps 25 |
| Upscaler | 4x-AnimeSharp.pth |
| TTS (1순위) | Chatterbox (EN only, 3.4GB VRAM) |
| TTS (KO 폴백) | Edge-TTS (InJoon) |
| TTS (금지) | Fish Speech S2 Pro (16GB VRAM 초과) |
| BGM | ACE-Step v1.5 |
| Animation | WAN 2.2 I2V, MimicMotion, AnimateDiff |
| Knowledge Graph | Neo4j (Docker, port 7474/7687) |
| Reference DB | scene_clusters.json (5,518 scenes, 17K frames, 11 shows) |
| Camera AI | FilmAgent Debate-Judge (LLM) |
| Render | 1344x768 → 4x AnimeSharp → 1920x1080 |

---

## 6. 캐릭터 시스템

### 16캐릭터
America, Korea, China, EU, Russia, Japan, Denmark, Greenland, France, Germany, UK, Norway + 4 추가 예정.
각 캐릭터는 국가를 의인화한 미소녀이며, 고유 컬러/실루엣/모에 속성/말투/소품을 갖는다.

### 프롬프트 구조
```
[STYLE_PREFIX] flat anime, anime screencap, masterpiece, clean lineart
+ [CHARACTER] CHARACTER_VISUAL_DESC (보루태그: 머리색, 의상, 체형, 소품)
+ [SCENE] enriched_visual_prompt (대본 기반 장면 묘사)
+ [CAMERA] shot_size + angle (6축 태그)
+ [BACKGROUND] 씬별 배경
```

### 골든샷
각 캐릭터의 공인 디자인. `assets/characters/{country}/` 에 저장.
- `{country}_psg_golden.png` — 사장 승인 원본
- `{country}_nichijou_golden.png` — 일상 스타일 프로덕션 에셋
- IP-Adapter에 골든샷을 넣어 캐릭터 일관성 유지

### 금지 프롬프트
`realistic`, `photorealistic`, `3d render`, `chibi`, `nsfw` 등 금지.

---

## 7. 레퍼런스 시스템

### 씬 클러스터 DB
- **5,518 씬**, 17K+ 프레임, **11 작품** 태깅 완료
- 도구: `pipeline/shared/scene_cluster.py`
- 검색: shot_size, mood, situation, scene_type으로 최적 레퍼런스 씬 검색
- 각 씬에 대표 프레임(representative_frame) 지정

### 11 작품 스타일 프로필
`context/show_profiles.json`에 작품별 art_style, camera_tendencies, best_for_our_show 등 기록.

| 작품 | 용도 |
|------|------|
| Nichijou (일상) | **기본 스타일**. 구도, 배경, 일상 분위기 |
| Bocchi the Rock | 불안/긴장, 리액션 |
| JoJo Part 3 | 대비 구도, 극화, epic |
| PSG 2010 | 코미디 폭발, 개그 |
| Watamote | 멜랑콜리, 사회불안 |
| Zvezda | 권력/야심, epic |
| 기타 5작품 | 상황별 보조 레퍼런스 |

### 레퍼런스에서 빌려오는 것 / 빌려오지 않는 것
- OK: 구도, 카메라 앵글, 조명 방향, 감정 연출 방식
- NO: 캐릭터 디자인 (우리 캐릭터로 교체), 배경 디테일 (학원 세계관에 맞게 변형)

### 검색 방법
```bash
# CLI 검색
python pipeline/shared/scene_cluster.py --search --shot-size ms --mood comedy --limit 5

# Python API
from pipeline.shared.scene_cluster import search_scenes
results = search_scenes(shot_size="ms", mood="comedy", limit=5)
```

---

## 8. 2단계 스토리보드 → 키프레임

### Current Canonical Storyboard Pipeline
- `Stage 1`: `workflows/stage1_composition.json`
- `Stage 2`: `workflows/stage2_character.json`
- `Stage 2.5` optional: `workflows/stage2_5_kontext.json`
- `Stage 3`: `workflows/stage3_upscale.json`

운영 규칙:
- 병렬 실행 금지
- Stage 1 pass 전체 완료 후 Stage 2
- Kontext를 쓸 경우 Stage 2.5 뒤에 Stage 3
- 최종 출력은 크롭 없이 `1920x1080`

Legacy/archival workflows:
- `workflows/legacy/storyboard_quick.json`
- `workflows/legacy/nichijou_ipadapter_keyframe.json`

### 8.5 <<VIS>> 마커 + 프롬프트 컴파일

대본에서 이미지까지 3단계 변환:

```
script.fountain (<<VIS>> 자연어 묘사)
    ↓ fountain_to_manifest.py
manifest.json (enriched_visual_prompt — 자연어 시각 묘사)
    ↓ prompt_compiler.py
manifest.json (compiled_prompt — booru 태그 200~350자)
    ↓ generate_storyboard_full.py
ComfyUI → 이미지
```

**<<VIS>> 블록 형식** (대본에서):
```fountain
.INT. APARTMENT HALLWAY - NIGHT

<<VIS>>
A narrow, dimly lit hallway. AMERICA stands at the door,
cowboy hat tilted back, holding dynamite, confident grin.
Camera: medium shot, eye level, dramatic side lighting.
<</VIS>>
```

**prompt_compiler 변환 결과**:
```
flat anime, anime screencap, masterpiece, best quality,
medium shot, waist up, cowboy shot,
1girl, 20 years old, tall sexy body, large breasts, slim waist,
standing, confident, holding,
hallway, corridor, indoor, dark atmosphere, night,
dramatic side lighting
```

**2캐릭터 처리**: 주인공 풀태그 5개 + 서브캐릭터 구분자 2태그 (머리색+옷)

**명령어**:
```bash
python pipeline/shared/prompt_compiler.py --manifest episodes/ep01/manifest.json          # 저장
python pipeline/shared/prompt_compiler.py --manifest episodes/ep01/manifest.json --preview  # 미리보기
```

---

## 9. 카메라 결정 — FilmAgent Debate-Judge

`pipeline/shared/filmagent_camera.py`

### 프로세스
1. **Cinematographer A**: LLM이 대본+씬 정보 기반 카메라 플랜 A 생성
2. **Cinematographer B**: 독립적으로 카메라 플랜 B 생성
3. **Cross-Review**: A가 B의 플랜 리뷰, B가 A의 플랜 리뷰 (N라운드)
4. **Director Judge**: 심사위원 LLM이 샷별 승자 선택
5. **Manifest 기록**: 승리한 카메라 결정이 manifest `shot_taxonomy`에 반영

### 6축 태그 체계 (SHOT_TAXONOMY.md)
shot_size, angle, composition, lighting, mood, situation

### 실행
```bash
# Dry-run (프롬프트만 확인)
python pipeline/shared/filmagent_camera.py --manifest episodes/ep01/manifest.json --dry-run

# 실행 (LLM 호출)
python pipeline/shared/filmagent_camera.py --manifest episodes/ep01/manifest.json --provider anthropic
```

---

## 10. 품질 게이트

모든 단계는 Exit Gate에서 manifest `stage_scores`에 점수를 기록한다.

| 단계 | PASS 기준 | FAIL 시 |
|------|-----------|---------|
| /find-topic | composite >= 7.0 | 재검색 |
| /deep-research | 팩트 10개+, LIKELY_TRUE 비율 >= 70% | 재조사 |
| /write-script | 7축 자체 진단 통과 + 풍자/리텐션/팩트 기준 충족 | 재작성 |
| /storyboard | 카메라 프리셋 100% 적용, 레퍼런스 매칭 완료 | 재보강 |
| /generate-visuals | QC tagger PASS, MD5 고유성 검증 | 재생성 |
| /generate-voice | 오디오 파일 존재 + 길이 매칭 | 재생성 |
| /assemble-video | 1920x1080, H.264+AAC, 동기화 검증 | 재조립 |

**3단계 판정**: PASS (진행) / CONDITIONAL (선택) / FAIL (재작업)

### 컷 밀도 규칙
- 목표: **20+ cuts/min**, 평균 2-3초/shot, 최대 5초
- 1 나레이션 문장 = 2-4 비주얼 컷 (1:1 금지)
- 컷 비율: scene 65% + insert 20% + reaction 8% + text_overlay 7%

---

## 11. 에이전트 팀

| # | 부서 | 스킬 | 페르소나 | 하트비트 |
|---|------|------|----------|----------|
| 0 | Studio CEO | (수동) | Paperclip식 회사 운영자 | issue lineage + approval + budget |
| 1 | 지식뱅크 | `/find-topic` | 전직 CIA 정보분석관 뉴스 큐레이터 | SHOW_BIBLE + 기존 에피소드 중복 체크 |
| 2 | 대본가 | `/write-script` | 존 올리버 구성작가 + 슈카 리서처 | SHOW_BIBLE + QUALITY_STANDARDS + 기존 ep 확인 |
| 3 | 콘티감독 | `/storyboard` | E-konte 감독 | manifest + SHOT_TAXONOMY + CHARACTER_SHEETS |
| 4 | 아트디렉터 | `/art-direction` | 비주얼 정체성 크리에이티브 수장 | SHOW_BIBLE + CHARACTER_SHEETS + assets 인벤토리 |
| 5 | 원화감독 | `/key-animation` | 결정적 순간의 퀄리티 책임자 | manifest + 원화/작화 2-stage 전략 |
| 6 | 동화촬영감독 | `/filming` | 움직임과 카메라 연출자 | manifest + 동화/촬영 2-stage 전략 |
| 7 | 제작진행 | `/production-runner` | 파이프라인 현장 요원 | GPU 상태 + 산출물 모니터링 |
| 8 | 음성PD | `/generate-voice` | 오디오 엔지니어 + 성우 캐스팅 디렉터 | manifest + CHARACTER_SHEETS + voice_refs |
| 9 | 편집감독 | `/assemble-video` | 베테랑 ffmpeg 마스터 | manifest + QUALITY_STANDARDS + 에셋 인벤토리 |
| 10 | DB 관리자 | `/db-admin` | 데이터 파이프라인 운영자 | SHOT_TAXONOMY + tags + embeddings |

### Service Specialist Layer
- `comfy_specialist` — ComfyUI, workflow JSON, 모델/LoRA, queue health
- `tts_specialist` — Chatterbox TTS, voice refs, subtitle/timing 정합
- `assembly_specialist` — clips/audio/subtitle/final mp4 수렴
- `quality_auditor` — preflight vs actual output QC

---

## 12. 자주 쓰는 명령어

| 명령어 | 설명 |
|--------|------|
| `/plan-episode` | 시즌 기획 + 콘텐츠 캘린더 |
| `/find-topic` | 주제 발굴 (키워드 옵션) |
| `/find-topic Iran war` | 키워드 지정 주제 발굴 |
| `/deep-research {주제}` | 딥 리서치 5-step |
| `/write-script {주제}` | 7-pass 대본 + manifest 생성 |
| `/storyboard ep01` | 콘티 보강 (카메라+레퍼런스+레이아웃) |
| `/generate-visuals ep01` | 키프레임 이미지 생성 |
| `/generate-voice ep01` | TTS + BGM + SFX |
| `/assemble-video ep01` | 최종 MP4 조립 |
| `/check-progress ep01` | 진행 상황 확인 |
| `/produce-episode {주제}` | 전체 파이프라인 자동 체이닝 |
| `/autoresearch` | 에피소드 간 자율 파라미터 최적화 |

### 파이프라인 유틸리티

| 명령어 | 설명 |
|--------|------|
| `python pipeline/shared/scene_cluster.py --search --shot-size ms --mood comedy` | 씬 검색 |
| `python pipeline/shared/filmagent_camera.py --manifest ... --dry-run` | 카메라 결정 미리보기 |
| `python pipeline/shared/rebuild_data_pipeline.py` | 태깅 후 데이터 체인 자동 재구축 (2초) |
| `python pipeline/shared/qc_tagger.py` | 생성 이미지 QC (PASS/PARTIAL/FAIL) |
| `python pipeline/shared/suggest_visuals.py --semantic` | 대사 기반 연출 제안 |

---

## 부록: manifest.json 계약

모든 파이프라인 단계가 읽고 쓰는 공유 지시서. `episodes/ep{XX}/manifest.json`에 위치.

- `shot_id`: `s001`, `s002`, ... (3자리 패딩)
- `type`: `SKIT` | `DOCU` | `CONFESSIONAL`
- `stage_scores`: 각 단계 품질 점수
- 포맷 비율: SKIT 40% + DOCU 45% + CONFESSIONAL 15%

## 부록: 콘텐츠 원칙

- **팩트 우선**: 코미디가 아닌 팩트 기반 풍자. 유머는 학원 비유에서 자연스럽게
- **이중 언어**: 모든 대사 EN + KO
- **금지**: 특정 국가 혐오, 인종차별, 성적 대상화, 실제 정치인 얼굴
- **Moe-Fact Hybrid Rule**: 대사의 내용은 현실 팩트, 말투는 캐릭터 성격 유지
