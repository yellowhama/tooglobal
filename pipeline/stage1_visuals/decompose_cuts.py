#!/usr/bin/env python3
"""decompose_cuts.py — 씬을 컷 단위로 분해.

12씬 manifest → 200+ 컷 manifest.
각 씬의 대사/나레이션을 문장 단위로 쪼개고,
문장마다 주요 컷 + 리액션/인서트 컷을 생성.

Usage:
    python decompose_cuts.py --manifest episodes/ep01/manifest.json
    python decompose_cuts.py --manifest episodes/ep01/manifest.json --dry-run
    python decompose_cuts.py --manifest episodes/ep01/manifest.json --target-cpm 20
"""
import json
import math
import re
import argparse
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT / "pipeline" / "shared"))

from character_config import CHARACTER_VISUAL_DESC, STYLE_ANCHOR, BG_PROMPTS, BG_MOOD_COLORS

# ─── 컷 밀도 설정 ───
DEFAULT_CUTS_PER_MINUTE = 20
CUT_TYPES = ["scene", "reaction", "insert", "text_overlay"]
CUT_RATIO = {"scene": 0.65, "reaction": 0.15, "insert": 0.12, "text_overlay": 0.08}

# ─── 샷 사이즈 패턴 (씬 타입별) ───
SHOT_PATTERNS = {
    "SKIT": ["CU", "MS", "CU", "MS", "CU"],  # 대화는 CU↔MS 교차
    "DOCU": ["LS", "MS", "CU", "MS", "LS"],  # 다큐는 넓게→좁게→넓게
    "CONFESSIONAL": ["MS", "CU", "MS", "CU"],  # 인터뷰는 MS↔CU
    "INTERVIEW": ["MS", "CU", "MS", "CU"],
    "REENACT": ["LS", "MS", "CU", "LS"],
}

# ─── 배경 추론 ───
def _infer_bg_for_cut(scene_type, mood="neutral"):
    if scene_type in ("CONFESSIONAL", "INTERVIEW"):
        return BG_PROMPTS["interview"]
    color = BG_MOOD_COLORS.get(mood, "white")
    return BG_PROMPTS["pastel"].format(color=color)


def _split_sentences(text):
    """텍스트를 문장 단위로 분리."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    parts = re.split(r'(?<=[.!?"])\s+', cleaned)
    return [p.strip() for p in parts if p.strip()]


def _estimate_duration(text, wpm=150):
    """텍스트 길이로 초 수 추정 (WPM 기준)."""
    words = len((text or "").split())
    return max(1.5, round(words / wpm * 60, 1))


def _infer_mood(scene_type, dialogue_text=""):
    """대사/씬타입에서 감정 추론."""
    text = dialogue_text.lower()
    if any(w in text for w in ["angry", "furious", "bomb", "kill", "attack", "war"]):
        return "anger"
    if any(w in text for w in ["cry", "tear", "die", "dead", "suffer"]):
        return "sadness"
    if any(w in text for w in ["laugh", "joke", "funny"]):
        return "comedy"
    if any(w in text for w in ["fear", "panic", "terrif", "scare"]):
        return "fear"
    if scene_type in ("CONFESSIONAL", "INTERVIEW"):
        return "neutral"
    return "tension"


def decompose_scene(scene, scene_idx, target_cpm=DEFAULT_CUTS_PER_MINUTE):
    """하나의 씬을 컷 리스트로 분해."""
    dialogues = scene.get("dialogue", [])
    scene_type = scene.get("type", "SKIT")
    shot_pattern = SHOT_PATTERNS.get(scene_type, SHOT_PATTERNS["SKIT"])

    # 대사를 문장 단위로 분해
    all_sentences = []
    for d in dialogues:
        speaker = d.get("speaker", "narrator")
        text = d.get("text_en", "")
        audio = d.get("audio_instruction", "")
        for sent in _split_sentences(text):
            all_sentences.append({
                "speaker": speaker,
                "text": sent,
                "audio": audio,
            })

    if not all_sentences:
        # VIS 블록만 있는 씬 → 최소 2컷
        vis = scene.get("visual_prompt", "")
        return [{
            "cut_id": f"{scene['shot_id']}_c001",
            "cut_type": "scene",
            "visual_prompt": vis,
            "shot_size": "MS",
            "duration_sec": 3.0,
            "speaker": None,
            "dialogue_text": None,
            "camera": "static",
        }]

    # 부모 씬의 enriched_visual_prompt 상속
    parent_enriched = scene.get("enriched_visual_prompt", scene.get("visual_prompt", ""))

    cuts = []
    cut_idx = 0

    for i, sent in enumerate(all_sentences):
        speaker = sent["speaker"]
        text = sent["text"]
        mood = _infer_mood(scene_type, text)
        duration = _estimate_duration(text)
        shot_size = shot_pattern[i % len(shot_pattern)]

        # ── 메인 컷 (scene) — 메타데이터만, 프롬프트는 prompt_compiler가 생성 ──
        cut_idx += 1
        cuts.append({
            "cut_id": f"{scene['shot_id']}_c{cut_idx:03d}",
            "cut_type": "scene",
            "enriched_visual_prompt": parent_enriched,  # 부모 씬에서 상속
            "shot_size": shot_size,
            "duration_sec": duration,
            "speaker": speaker,
            "dialogue_text": text,
            "mood": mood,
            "camera": "static",
            "characters": [speaker] if speaker != "narrator" else scene.get("characters", []),
        })

        # ── 리액션 컷 (상대방이 있을 때) ──
        if scene_type == "SKIT" and i + 1 < len(all_sentences):
            next_speaker = all_sentences[i + 1]["speaker"]
            if next_speaker != speaker and next_speaker != "narrator" and speaker != "narrator":
                cut_idx += 1
                cuts.append({
                    "cut_id": f"{scene['shot_id']}_c{cut_idx:03d}",
                    "cut_type": "reaction",
                    "enriched_visual_prompt": parent_enriched,
                    "shot_size": "CU",
                    "duration_sec": 1.0,
                    "speaker": next_speaker,
                    "dialogue_text": None,
                    "mood": mood,
                    "camera": "static",
                    "characters": [next_speaker],
                })

        # ── 인서트 컷 (숫자/팩트 언급 시) ──
        has_number = bool(re.search(r'\d+', text))
        if has_number and scene_type == "DOCU":
            cut_idx += 1
            cuts.append({
                "cut_id": f"{scene['shot_id']}_c{cut_idx:03d}",
                "cut_type": "insert",
                "enriched_visual_prompt": f"data visualization related to: {text[:80]}",
                "shot_size": "FS",
                "duration_sec": 1.5,
                "speaker": None,
                "dialogue_text": None,
                "camera": "static",
            })

    return cuts


def decompose_manifest(manifest_path, target_cpm=DEFAULT_CUTS_PER_MINUTE, dry_run=False):
    """manifest.json의 모든 씬을 컷으로 분해."""
    path = Path(manifest_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    total_cuts = 0
    type_counts = {"scene": 0, "reaction": 0, "insert": 0, "text_overlay": 0}

    for i, shot in enumerate(data["shots"]):
        cuts = decompose_scene(shot, i, target_cpm)
        shot["cuts"] = cuts
        total_cuts += len(cuts)
        for c in cuts:
            ct = c.get("cut_type", "scene")
            type_counts[ct] = type_counts.get(ct, 0) + 1

    # 총 시간 계산
    total_duration = sum(
        c["duration_sec"]
        for s in data["shots"]
        for c in s.get("cuts", [])
    )

    data["total_cuts"] = total_cuts
    data["total_duration_sec"] = round(total_duration, 1)
    data["cuts_per_minute"] = round(total_cuts / (total_duration / 60), 1) if total_duration > 0 else 0

    print(f"📊 컷 분해 완료")
    print(f"   씬: {len(data['shots'])}개")
    print(f"   총 컷: {total_cuts}개")
    print(f"   타입: {', '.join(f'{k}:{v}' for k, v in sorted(type_counts.items()))}")
    print(f"   총 시간: {total_duration:.0f}초 ({total_duration/60:.1f}분)")
    print(f"   분당 컷: {data['cuts_per_minute']}개")

    if not dry_run:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ → {path}")

    return data


def main():
    parser = argparse.ArgumentParser(description="씬 → 컷 분해기")
    parser.add_argument("--manifest", required=True, help="manifest.json 경로")
    parser.add_argument("--target-cpm", type=int, default=DEFAULT_CUTS_PER_MINUTE, help="목표 분당 컷 수")
    parser.add_argument("--dry-run", action="store_true", help="통계만 출력")
    args = parser.parse_args()
    decompose_manifest(args.manifest, args.target_cpm, args.dry_run)


if __name__ == "__main__":
    main()
