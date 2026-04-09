# QUICKSTART — 5분 안에 작업 시작하기

> 이 문서는 새 작업자가 즉시 첫 작업을 실행할 수 있도록 최소한의 정보만 담는다.
> 전체 파이프라인 이해가 필요하면 `ONBOARDING.md`를 읽을 것.

---

## 1. 환경 확인

```bash
# GPU 확인 (RTX 5070 Ti 16GB 필요)
nvidia-smi

# Python venv 확인
source ~/venvs/phase3-gpu/bin/activate
python -c "import torch; print(torch.cuda.get_device_name(0))"

# ComfyUI 실행 확인 (포트 8188)
curl -s http://localhost:8188/system_stats | python -m json.tool | head -5

# ComfyUI가 안 뜨면:
cd ~/ComfyUI/app && python main.py --listen 0.0.0.0 --port 8188 &
```

### 필수 경로 확인
```bash
ls ~/youtube-studio-copy/pipeline/shared/scene_cluster.py    # 씬 클러스터
ls ~/youtube-studio-copy/context/SHOW_BIBLE.md               # 세계관
ls ~/youtube-studio-copy/context/CHARACTER_SHEETS.md          # 캐릭터
```

---

## 2. 첫 스토리보드 테스트

manifest.json이 있는 에피소드가 필요하다. 없으면 3단계(대본)부터 시작.

```bash
cd ~/youtube-studio-copy

# 1) 씬 클러스터 검색 테스트 — 코미디 미디엄 샷 5개 검색
source ~/venvs/phase3-gpu/bin/activate
python pipeline/shared/scene_cluster.py --search --shot-size ms --mood comedy --limit 5

# 2) 카메라 결정 dry-run (LLM 호출 없이 프롬프트만 확인)
python pipeline/shared/filmagent_camera.py \
  --manifest episodes/ep01/manifest.json --dry-run

# 3) 스토리보드 패널 생성 (ComfyUI 필요)
python pipeline/stage1_visuals/generate_storyboard_panels.py \
  --manifest episodes/ep01/manifest.json --limit 3
```

---

## 3. 첫 키프레임 테스트

스토리보드 패널이 있어야 한다 (Stage 1 완료 후).

```bash
cd ~/youtube-studio-copy
source ~/venvs/phase3-gpu/bin/activate

# 1) 키프레임 생성 (3장만 테스트)
python pipeline/stage1_visuals/generate_keyframes.py \
  --manifest episodes/ep01/manifest.json --limit 3

# 2) QC 채점
python pipeline/shared/qc_tagger.py \
  --input episodes/ep01/images/ --output episodes/ep01/qc_results.json

# 3) 결과 확인
ls -la episodes/ep01/images/
```

### Stage 1 vs Stage 2 핵심 차이

| | Stage 1 (스토리보드) | Stage 2 (키프레임) |
|---|---|---|
| 목적 | 구도 확인 (러프) | 최종 영상용 (고품질) |
| 레퍼런스 | 외부 작품 씬 | Stage 1 스토리보드 패널 |
| CN Canny | 0.4/0.7 (구조선만) | 0.2/0.4 (윤곽선도) |
| CN end | 0.4 | 0.6 |
| Steps | 20 | 25 |

---

## 4. 대본 작성 (`/write-script`)

Claude Code에서 실행:

```
/write-script 미-이란 호르무즈 해협 봉쇄
```

### 자동 진행 순서
1. WebSearch로 팩트 수집
2. Dramatron 계층 생성 (Title → Characters → Scenes → Places → Dialogue)
3. Claude 자체 보강 + 7축 자체 진단
4. 풍자/리텐션 감사
5. 팩트 체크
6. manifest.json 자동 생성
7. Exit Gate + Memory Writeback

### 산출물
- `episodes/ep{XX}/script.md` — 풀 스크립트 (EN/KO)
- `episodes/ep{XX}/manifest.json` — 다음 단계 입력

### 사용자 승인: 1회만
Dramatron 초안 + Claude 보강 후 최종 확인 1회.

---

## 5. 문제 해결

### ComfyUI 연결 실패
```
Error: Connection refused (localhost:8188)
```
**해결**: ComfyUI 프로세스 확인 후 재시작
```bash
ps aux | grep main.py
cd ~/ComfyUI/app && python main.py --listen 0.0.0.0 --port 8188 &
```

### VRAM 부족 (OOM)
```
RuntimeError: CUDA out of memory
```
**해결**: 좀비 프로세스 정리
```bash
nvidia-smi
# PID 확인 후
kill -9 <PID>
# 또는 전체 정리
pkill -f "python.*comfy"
```

### scene_cluster.py 검색 결과 0건
```
No scenes found matching criteria
```
**해결**: 태그 DB가 로드되었는지 확인
```bash
python pipeline/shared/scene_cluster.py --stats
# total_scenes: 5518 이어야 정상
```

### manifest.json 없음
```
FileNotFoundError: manifest.json
```
**해결**: `/write-script`를 먼저 실행하여 manifest 생성

### TTS Chatterbox 실패
```
Error: chatterbox model not found
```
**해결**: Chatterbox 경로 확인
```bash
ls ~/chatterbox/
# voice_refs 심링크 확인
ls -la ~/youtube-studio-copy/assets/voice_refs/
```

### 생성 이미지 품질 낮음
**체크리스트**:
1. LoRA 강도 확인 (키프레임 = 0.8, 캐릭터 = 0.6, 배경 = 0.4)
2. ControlNet 설정이 Stage에 맞는지 확인 (Stage 1 vs 2)
3. 골든샷이 IP-Adapter에 제대로 연결되었는지 확인
4. 프롬프트에 금지어 (`realistic`, `3d render` 등) 없는지 확인

### 작업 중 막혔을 때
```
/check-progress ep01
```
현재 상태 + 블로커 + 다음 액션을 알려준다.

---

## 핵심 파일 3개 (반드시 읽을 것)

1. **`CLAUDE.md`** — 회사 규칙, 파이프라인 11단계, 기술 환경
2. **`context/SHOW_BIBLE.md`** — 세계관, 캐릭터, 톤, Moe-Fact Hybrid Rule
3. **`context/SHOT_TAXONOMY.md`** — 6축 영상 연출 태그 (모든 시각 용어의 SSOT)
