# 3단계 이미지 생성 파이프라인 — 구현 핸드오프 문서

> 다른 AI가 이 문서를 읽고 구현을 이어갈 수 있도록 정리.
> Windows 경로: `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\`

---

## 현재 상태 요약

**완료된 것:**
- ep01 대본 (12씬, WHY 인과관계 중심, No Metaphor Rule)
- 컷 분해 (12씬 → 207컷, 분당 23.3컷)
- 프롬프트 컴파일 (207컷 × compiled_prompt, qwen3.5 LLM)
- 치비 캐릭터 8개국 골든샷 (2048x2048)
- 3개 워크플로우 JSON 생성 완료

**남은 것:**
- `generate_panels_3stage.py` 작성 (3단계 렌더러)
- scene_cluster 레퍼런스 매칭 개선
- S001 11컷 3단계 테스트
- 207컷 전체 원화 생성

---

## 사전지식 — 반드시 읽을 파일

### 핵심 문서 (순서대로)
1. **CLAUDE.md** — 프로덕션 규칙, 파이프라인 순서
   - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\CLAUDE.md`

2. **SHOW_BIBLE.md** — 콘텐츠 규칙, 톤앤매너, 배경 스타일, 패러디 테이블
   - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\context\SHOW_BIBLE.md`

3. **character_config.py** — SSOT (캐릭터, 스타일, 배경, 카메라 전부 여기)
   - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\pipeline\shared\character_config.py`

4. **마스터 플랜** — 3단계 파이프라인 설계
   - `\\wsl.localhost\Ubuntu-22.04\home\hugh\.claude\plans\dapper-swinging-stream.md`

### 파이프라인 코드
5. **decompose_cuts.py** — 씬→컷 분해기 (메타만, 프롬프트 안 만듦)
   - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\pipeline\stage1_visuals\decompose_cuts.py`

6. **prompt_compiler_llm.py** — LLM 프롬프트 생성기 (유일한 프롬프트 생성기)
   - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\pipeline\shared\prompt_compiler_llm.py`

7. **generate_storyboard_full.py** — 현재 렌더러 (이걸 참고해서 3stage 버전 만들 것)
   - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\pipeline\stage1_visuals\generate_storyboard_full.py`

8. **generate_keyframes.py** — IP-Adapter + ControlNet 로직 참고
   - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\pipeline\stage1_visuals\generate_keyframes.py`

9. **comfyui_client.py** — ComfyUI API 클라이언트 (재사용)
   - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\pipeline\shared\comfyui_client.py`

### 워크플로우 JSON (이미 생성 완료)
10. **stage1_composition.json** — Stage 1 (구도: Depth ControlNet only, 768x768, 15 steps)
    - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\workflows\stage1_composition.json`

11. **stage2_character.json** — Stage 2 (캐릭터: IP-Adapter 0.5 + CN 0.15, 1024x1024, 25 steps)
    - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\workflows\stage2_character.json`

12. **stage3_upscale.json** — Stage 3 (퀄업: AnimeSharp 4x → 1920x1080)
    - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\workflows\stage3_upscale.json`

### 참고 워크플로우 (디테일/리파인 연구용, 지금 당장 파이프라인에 섞지 말 것)
16. **CRT_FLUX SUPER (v4.3).json** — “Controlnet Sampler Injection(업스케일 단계)” + FaceEnhancement 서브그래프 포함 (메타/서브그래프 기반)
    - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\workflows\reference\CRT_FLUX SUPER (v4.3).json`

17. **flux_lots_of_tweaks.json** — 얼굴/눈/손 등 “디테일러(Detector+Detailer)”가 포함된 대형 워크플로우 (실험용)
    - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\workflows\flux_lots_of_tweaks.json`

### 데이터
13. **manifest.json** — 207컷 포함, compiled_prompt 완료
    - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\episodes\ep01\manifest.json`

14. **scene_clusters.json** — 5,518 씬 레퍼런스 DB
    - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\context\scene_clusters.json`

15. **골든샷** — 8개국 캐릭터
    - `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\assets\characters\{국가}\{국가}_golden.png`

---

## 구현할 것: `generate_panels_3stage.py`

### 위치
`pipeline/stage1_visuals/generate_panels_3stage.py`

### 역할
manifest.json의 207컷을 3단계로 렌더링.

### 올바른 파이프라인 순서 (절대 건너뛰지 말 것)

```
manifest.json (207컷, compiled_prompt 있음)
  ↓
Stage 1: 구도 잡기
  - 워크플로우: stage1_composition.json
  - 입력: scene_clusters에서 레퍼런스 스크린샷 + compiled_prompt
  - ControlNet: Depth 0.3 (레퍼런스 구도 전이)
  - IP-Adapter: OFF
  - 해상도: 768x768
  - Steps: 15 (빠르게)
  - 출력: storyboard/stage1_layout/s001_c001_layout.png
  ↓
Stage 2: 캐릭터 입히기
  - 워크플로우: stage2_character.json
  - 입력: Stage 1 결과(ControlNet ref) + 골든샷(IP-Adapter) + compiled_prompt
  - ControlNet: Depth 0.15 (Stage 1 결과의 구도 유지)
    - 구현상: `end_percent=0.2` (짧게만 걸어두는 구성)
  - IP-Adapter: 0.5 (골든샷 캐릭터 전이)
    - 구현상: `end_percent=0.5`
  - 해상도: 1024x1024
  - Steps: 25
  - 출력: storyboard/stage2_character/s001_c001_char.png
  ↓
Stage 3: 퀄업
  - 워크플로우: stage3_upscale.json
  - 입력: Stage 2 결과
  - AnimeSharp 4x 업스케일 → 1920x1080 리사이즈
  - 출력: storyboard/panels/panel_s001_c001.png (최종)
```

### CLI 인터페이스

```bash
# 전체 3단계
python3 generate_panels_3stage.py --manifest episodes/ep01/manifest.json

# 특정 단계만
python3 generate_panels_3stage.py --manifest episodes/ep01/manifest.json --stage 1
python3 generate_panels_3stage.py --manifest episodes/ep01/manifest.json --stage 2
python3 generate_panels_3stage.py --manifest episodes/ep01/manifest.json --stage 3

# 특정 씬만
python3 generate_panels_3stage.py --manifest episodes/ep01/manifest.json --shot s001

# 이어서 (이미 생성된 컷 스킵)
python3 generate_panels_3stage.py --manifest episodes/ep01/manifest.json --resume
```

### 핵심 함수 (기존 코드 재사용)

```python
# comfyui_client.py에서
from comfyui_client import ComfyUIClient
client = ComfyUIClient()  # http://127.0.0.1:8188
client.health_check(min_free_gb=1.0)
ref_upload = client.upload_image(str(ref_path))  # 이미지 업로드
pid = client.queue_workflow(workflow, overrides)  # 워크플로우 실행
result = client.wait_for_completion(pid, timeout=600)  # 완료 대기
img_data = client.get_image(result["images"][0])  # 결과 다운로드

# 워크플로우 오버라이드 방식 (노드 title로 매칭)
overrides = {
    "Load Reference Screenshot": {"image": ref_upload["name"]},
    "Positive Prompt": {"text": compiled_prompt},
    "Random Noise": {"noise_seed": 42069 + hash(cut_id) % 99999},
    "Load Character Golden Shot": {"image": golden_upload["name"]},
}

# Stage 3 오버라이드 타이틀
# - 입력: "Load Stage 2 Result"
# - 출력: "Save Final"
```

### 레퍼런스 스크린샷 찾기

```python
# 기존 scene_cluster.py 재사용
from scene_cluster import search_scenes

results = search_scenes(
    shot_size=cut["shot_size"],  # CU, MS, FS 등
    mood=cut["mood"],            # anger, sadness 등
    scene_type=cut.get("_parent_type", "SKIT"),
    preferred_shows=["psg_2010", "psg_new", "nichijou"],  # 치비 스타일 우선
    limit=3
)
ref_path = SCREENSHOT_ROOT / results[0]["representative_frame"]
```

### 골든샷 찾기

```python
CHAR_DIR = Path("assets/characters")
def find_golden(characters):
    for c in characters:
        g = CHAR_DIR / c / f"{c}_golden.png"
        if g.exists():
            return g
    return Path("assets/system/blank_white.png")  # 폴백
```

---

## 절대 지켜야 할 규칙

1. **프롬프트를 직접 만들지 말 것** — manifest의 `compiled_prompt` 필드를 그대로 사용. prompt_compiler_llm.py가 유일한 프롬프트 생성기.

2. **AnimeSharp 꼭 사용** — Stage 3에서 4x-AnimeSharp.pth 업스케일 필수.

3. **SSOT 참조** — 캐릭터 외형, 배경, 스타일은 `character_config.py`에서만 가져옴.

4. **파이프라인 순서 절대 건너뛰지 말 것**:
   - decompose_cuts (메타만) → prompt_compiler (프롬프트) → generate_panels_3stage (렌더)
   - Stage 1 → Stage 2 → Stage 3 순서

5. **IP-Adapter에 외부 스크린샷 넣지 말 것** — 골든샷만 사용.

6. **배경은 밝은 파스텔** — 어두운 배경 금지 (CONFESSIONAL/INTERVIEW 포함).

---

## 워크플로우 감사(요약)

Stage 1/2는 Union ControlNet 타입을 **depth**로 사용한다.
- 워크플로우 노드 타이틀은 `Set Canny Type`로 남아있지만, 실제 입력은 `"type": "depth"`다.

Stage 1/2는 latent 해상도와 ModelSamplingFlux 해상도가 일치하도록 맞춰져 있다.
- Stage 1: 768x768
- Stage 2: 1024x1024

---

## 예상 시간

| Stage | 컷당 | 207컷 전체 |
|-------|------|-----------|
| Stage 1 (768x768, 15step) | ~15초 | ~50분 |
| Stage 2 (1024x1024, 25step) | ~25초 | ~85분 |
| Stage 3 (업스케일) | ~10초 | ~35분 |
| **총** | | **~170분 (3시간)** |

---

## 테스트 방법

S001 (11컷)만 먼저 돌려서 확인:
```bash
python3 generate_panels_3stage.py --manifest episodes/ep01/manifest.json --shot s001
```

확인할 것:
- Stage 1: 레퍼런스 스크린샷과 비슷한 구도?
- Stage 2: 우리 캐릭터(골든샷)가 올바르게 입혀졌나?
- Stage 3: AnimeSharp로 선명해졌나?
- 11컷 간 구도 다양성 확보됐나?
- 같은 캐릭터가 다른 컷에서 일관된 외형인가?

---

## 환경

| 항목 | 값 |
|------|-----|
| GPU | RTX 5070 Ti 16GB |
| ComfyUI | http://127.0.0.1:8188 |
| Python | 3.10 (WSL Ubuntu) |
| venv | 없음 (시스템 Python) |
| Flux model | flux1-dev-Q5_K_S.gguf |
| LoRA | Juustagram style v1.0-000005.safetensors @ 1.0 |
| ControlNet | flux-controlnet-union-pro.safetensors (depth mode) |
| IP-Adapter | ip-adapter.bin (자동 다운로드) + google/siglip-so400m-patch14-384 |
| Upscaler | 4x-AnimeSharp.pth |
