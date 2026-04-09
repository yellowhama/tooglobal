#!/usr/bin/env python3
"""Scene clustering pipeline for the youtube-studio storyboard system.

Groups consecutive frames from the same show+episode into scenes,
computes aggregate tags, selects representative frames, and provides
scene-level search.

Usage:
    python scene_cluster.py --build          # build clusters from merged_screenshot_tags.json
    python scene_cluster.py --stats          # print cluster statistics
    python scene_cluster.py --search --shot-size ms --mood comedy --limit 5
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

SHARED_DIR = Path(__file__).resolve().parent
shared_str = str(SHARED_DIR)
if shared_str not in sys.path:
    sys.path.insert(0, shared_str)

from project_paths import find_project_root

PROJECT_ROOT = find_project_root(Path(__file__).resolve())
MERGED_TAGS_PATH = PROJECT_ROOT / "context" / "merged_screenshot_tags.json"
SCENE_CLUSTERS_PATH = PROJECT_ROOT / "context" / "scene_clusters.json"
DB_PATH = PROJECT_ROOT / "references" / "vibe-search" / "scene_metadata.db"

# Clustering parameter: max gap between consecutive frame numbers in a scene
SCENE_GAP_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_frame_number(file_path: str) -> int | None:
    """Extract numeric frame number from a path like 'bocchi/bocchi_01/frame_0042.jpg'."""
    m = re.search(r"frame_(\d+)", file_path)
    return int(m.group(1)) if m else None


def _extract_show_episode(file_path: str) -> tuple[str, str]:
    """Extract (show, episode) from path like 'bocchi/bocchi_01/frame_0042.jpg'."""
    parts = file_path.replace("\\", "/").split("/")
    if len(parts) >= 2:
        return parts[0], parts[1]
    return parts[0] if parts else "unknown", "unknown"


def _most_common(values: list[str | None]) -> str | None:
    """Return the most common non-None value, or None."""
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return Counter(filtered).most_common(1)[0][0]


def _union_list(lists: list[list[str]]) -> list[str]:
    """Return sorted union of all values across lists."""
    result: set[str] = set()
    for lst in lists:
        if isinstance(lst, list):
            result.update(lst)
        elif isinstance(lst, str):
            result.add(lst)
    return sorted(result)


# ---------------------------------------------------------------------------
# 1. Load input data
# ---------------------------------------------------------------------------

def load_merged_tags() -> list[dict[str, Any]]:
    """Load frames from merged_screenshot_tags.json."""
    if not MERGED_TAGS_PATH.exists():
        raise FileNotFoundError(f"Merged tags not found at {MERGED_TAGS_PATH}")
    data = json.loads(MERGED_TAGS_PATH.read_text(encoding="utf-8"))
    return data["frames"]


# ---------------------------------------------------------------------------
# 2. Scene Detection — cluster consecutive frames
# ---------------------------------------------------------------------------

def cluster_frames_into_scenes(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group consecutive frames from the same show+episode into scenes.

    Rule: frames within SCENE_GAP_THRESHOLD frame_numbers of each other = same scene.
    A gap larger than that starts a new scene.

    Returns a list of scene dicts, each containing metadata and a list of member frames.
    """
    # Annotate each frame with parsed show, episode, frame_number
    annotated: list[dict[str, Any]] = []
    for frame in frames:
        file_path = frame.get("file", "")
        fnum = _extract_frame_number(file_path)
        if fnum is None:
            continue
        show, episode = _extract_show_episode(file_path)
        annotated.append({
            **frame,
            "_show": show,
            "_episode": episode,
            "_frame_number": fnum,
        })

    # Sort by show, episode, frame_number
    annotated.sort(key=lambda f: (f["_show"], f["_episode"], f["_frame_number"]))

    # Cluster using two signals:
    #   1. Frame number gap > SCENE_GAP_THRESHOLD = new scene (works for offset-tagged episodes)
    #   2. Tag fingerprint change = new scene (works for dense 1fps episodes)
    # The tag-change rule uses a 3-axis fingerprint (shot_size, angle, mood).
    # A change in any 2+ axes triggers a scene break for dense episodes.
    scenes: list[dict[str, Any]] = []
    current_group: list[dict[str, Any]] = []

    def _fingerprint(f: dict) -> tuple:
        return (f.get("shot_size"), f.get("angle"), f.get("mood"))

    def _fingerprint_diff(a: dict, b: dict) -> int:
        """Count how many of the 3 tag axes differ between two frames."""
        fa, fb = _fingerprint(a), _fingerprint(b)
        return sum(1 for x, y in zip(fa, fb) if x != y)

    for frame in annotated:
        if not current_group:
            current_group.append(frame)
            continue

        prev = current_group[-1]
        same_show = frame["_show"] == prev["_show"]
        same_episode = frame["_episode"] == prev["_episode"]
        gap = frame["_frame_number"] - prev["_frame_number"]

        if not same_show or not same_episode or gap > SCENE_GAP_THRESHOLD:
            # Different show/episode or big gap — always new scene
            scenes.append(_build_scene(current_group, len(scenes)))
            current_group = [frame]
        elif gap <= 1 and _fingerprint_diff(prev, frame) >= 2:
            # Dense episode (gap=1): split when 2+ tag axes change
            scenes.append(_build_scene(current_group, len(scenes)))
            current_group = [frame]
        else:
            current_group.append(frame)

    if current_group:
        scenes.append(_build_scene(current_group, len(scenes)))

    # Re-number scenes per episode
    scenes = _renumber_scenes_per_episode(scenes)
    return scenes


def _renumber_scenes_per_episode(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign scene_ids like 'nichijou_01_scene_042' per episode."""
    counters: dict[str, int] = {}
    for scene in scenes:
        ep = scene["episode"]
        counters[ep] = counters.get(ep, 0) + 1
        scene["scene_id"] = f"{ep}_scene_{counters[ep]:03d}"
    return scenes


# ---------------------------------------------------------------------------
# 3. Scene-Level Tagging
# ---------------------------------------------------------------------------

def _build_scene(group: list[dict[str, Any]], global_idx: int) -> dict[str, Any]:
    """Build a scene dict from a group of consecutive frames."""
    show = group[0]["_show"]
    episode = group[0]["_episode"]
    frame_numbers = [f["_frame_number"] for f in group]
    start_frame = min(frame_numbers)
    end_frame = max(frame_numbers)
    frame_count = len(group)

    # Aggregate tags
    shot_sizes = [f.get("shot_size") for f in group]
    angles = [f.get("angle") for f in group]
    moods = [f.get("mood") for f in group]

    compositions_raw = [f.get("composition", []) for f in group]
    situations_raw = [f.get("situation", []) for f in group]

    # Descriptions — concatenate unique
    descriptions = []
    seen_descs: set[str] = set()
    for f in group:
        desc = f.get("description", "")
        if desc and desc not in seen_descs:
            descriptions.append(desc)
            seen_descs.add(desc)

    # Representative frame
    rep_frame = _select_representative_frame(group, {
        "dominant_shot_size": _most_common(shot_sizes),
        "dominant_angle": _most_common(angles),
        "dominant_mood": _most_common(moods),
    })

    return {
        "scene_id": "",  # placeholder, renumbered later
        "show": show,
        "episode": episode,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "frame_count": frame_count,
        "duration_sec": frame_count,  # 1fps extraction
        "dominant_shot_size": _most_common(shot_sizes),
        "dominant_angle": _most_common(angles),
        "dominant_mood": _most_common(moods),
        "compositions": _union_list(compositions_raw),
        "situations": _union_list(situations_raw),
        "description": " | ".join(descriptions[:5]),  # cap at 5 for readability
        "representative_frame": rep_frame["file"],
        "all_frames": [f["file"] for f in group],
        "_frames_data": group,  # internal, stripped before output
    }


# ---------------------------------------------------------------------------
# 4. Representative Frame Selection
# ---------------------------------------------------------------------------

def _select_representative_frame(
    group: list[dict[str, Any]],
    dominant_tags: dict[str, str | None],
) -> dict[str, Any]:
    """Pick the best representative frame from a scene cluster.

    Scoring:
      - +2 for matching dominant_shot_size
      - +2 for matching dominant_angle
      - +2 for matching dominant_mood
      - +1 for longer description (more detail = more interesting)
      - -1 if first or last frame in the scene (transition avoidance)
    """
    if len(group) == 1:
        return group[0]

    scored: list[tuple[float, int, dict[str, Any]]] = []
    max_desc_len = max(len(f.get("description", "")) for f in group) or 1

    for idx, frame in enumerate(group):
        score = 0.0

        # Tag match bonuses
        if frame.get("shot_size") == dominant_tags.get("dominant_shot_size"):
            score += 2.0
        if frame.get("angle") == dominant_tags.get("dominant_angle"):
            score += 2.0
        if frame.get("mood") == dominant_tags.get("dominant_mood"):
            score += 2.0

        # Description length bonus (normalized 0-1)
        desc_len = len(frame.get("description", ""))
        score += desc_len / max_desc_len

        # Penalize first/last frame (transition avoidance)
        if idx == 0 or idx == len(group) - 1:
            score -= 1.0

        scored.append((score, idx, frame))

    # Sort by score descending, break ties by preferring middle frames
    scored.sort(key=lambda x: (-x[0], abs(x[1] - len(group) // 2)))
    return scored[0][2]


# ---------------------------------------------------------------------------
# 5. Output — JSON + SQLite
# ---------------------------------------------------------------------------

def save_scene_clusters(scenes: list[dict[str, Any]], total_frames: int) -> Path:
    """Save scene clusters to context/scene_clusters.json."""
    shows = set(s["show"] for s in scenes)

    # Strip internal _frames_data before output
    output_scenes = []
    for s in scenes:
        out = {k: v for k, v in s.items() if not k.startswith("_")}
        # Simplify all_frames to just filenames
        out["all_frames"] = [Path(f).name for f in out["all_frames"]]
        output_scenes.append(out)

    payload = {
        "_meta": {
            "total_scenes": len(scenes),
            "total_frames": total_frames,
            "shows": len(shows),
            "show_list": sorted(shows),
            "gap_threshold": SCENE_GAP_THRESHOLD,
            "created": datetime.now(timezone.utc).isoformat(),
        },
        "scenes": output_scenes,
    }

    SCENE_CLUSTERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCENE_CLUSTERS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return SCENE_CLUSTERS_PATH


def update_sqlite_db(scenes: list[dict[str, Any]]) -> None:
    """Add scene_clusters table and scene_id column to screenshot_frames in SQLite DB."""
    if not DB_PATH.exists():
        print(f"  [warn] SQLite DB not found at {DB_PATH}, skipping DB update")
        return

    conn = sqlite3.connect(str(DB_PATH))
    try:
        # 1. Create scene_clusters table
        conn.execute("DROP TABLE IF EXISTS scene_clusters")
        conn.execute("""
            CREATE TABLE scene_clusters (
                scene_id TEXT PRIMARY KEY,
                show TEXT NOT NULL,
                episode TEXT NOT NULL,
                start_frame INTEGER NOT NULL,
                end_frame INTEGER NOT NULL,
                frame_count INTEGER NOT NULL,
                duration_sec INTEGER NOT NULL,
                dominant_shot_size TEXT,
                dominant_angle TEXT,
                dominant_mood TEXT,
                compositions_json TEXT,
                situations_json TEXT,
                description TEXT,
                representative_frame TEXT
            )
        """)

        # 2. Insert scene data
        for scene in scenes:
            conn.execute("""
                INSERT INTO scene_clusters (
                    scene_id, show, episode, start_frame, end_frame,
                    frame_count, duration_sec, dominant_shot_size, dominant_angle,
                    dominant_mood, compositions_json, situations_json,
                    description, representative_frame
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scene["scene_id"],
                scene["show"],
                scene["episode"],
                scene["start_frame"],
                scene["end_frame"],
                scene["frame_count"],
                scene["duration_sec"],
                scene["dominant_shot_size"],
                scene["dominant_angle"],
                scene["dominant_mood"],
                json.dumps(scene["compositions"]),
                json.dumps(scene["situations"]),
                scene["description"],
                scene["representative_frame"],
            ))

        # 3. Add scene_id column to screenshot_frames if not exists
        columns = [
            row[1] for row in conn.execute("PRAGMA table_info(screenshot_frames)").fetchall()
        ]
        if "scene_id" not in columns:
            conn.execute("ALTER TABLE screenshot_frames ADD COLUMN scene_id TEXT")

        # 4. Update screenshot_frames with scene_id
        for scene in scenes:
            for frame_file in scene["all_frames"]:
                conn.execute(
                    "UPDATE screenshot_frames SET scene_id = ? WHERE file = ?",
                    (scene["scene_id"], frame_file),
                )

        conn.commit()
        row_count = conn.execute("SELECT COUNT(*) FROM scene_clusters").fetchone()[0]
        updated = conn.execute(
            "SELECT COUNT(*) FROM screenshot_frames WHERE scene_id IS NOT NULL"
        ).fetchone()[0]
        print(f"  SQLite: {row_count} scenes in scene_clusters, {updated} frames linked")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 6. Search function
# ---------------------------------------------------------------------------

def _load_show_profiles() -> dict[str, Any]:
    """Load show style profiles for scene-type-aware scoring."""
    profiles_path = SHARED_DIR.parents[1] / "context" / "show_profiles.json"
    if not profiles_path.exists():
        return {}
    return json.loads(profiles_path.read_text(encoding="utf-8")).get("shows", {})


# Scene type → keyword mapping for show profile matching
_SCENE_TYPE_KEYWORDS = {
    "SKIT": ["confrontation", "comedy", "reaction", "slapstick", "delinquent", "faction",
             "school daily life", "absurdist", "sketch-comedy", "buddy comedy"],
    "DOCU": ["text overlays", "fact cards", "infographic", "establishing shots",
             "narration", "exposition", "global context", "pop-art", "graphic overlays"],
    "CONFESSIONAL": ["CONFESSIONAL", "talking head", "internal monologue", "isolated",
                     "anxiety", "cringe", "alone", "embarrassment"],
}


def search_scenes(
    *,
    shot_size: str | None = None,
    mood: str | None = None,
    situation: str | None = None,
    composition: str | None = None,
    angle: str | None = None,
    show: str | None = None,
    scene_type: str | None = None,
    preferred_shows: list[str] | None = None,
    min_duration: int | None = None,
    max_duration: int | None = None,
    limit: int = 10,
    diversify_shows: bool = True,
    max_per_show: int = 3,
) -> dict[str, Any]:
    """Search scene clusters by tags. Returns scene-level results with representative frames.

    Parameters:
        shot_size: Filter by dominant shot size (e.g. "ms", "cu")
        mood: Filter by dominant mood (e.g. "comedy", "tense")
        situation: Filter by situation tag (substring match)
        composition: Filter by composition tag (substring match)
        angle: Filter by dominant angle
        show: Filter by show name (hard filter)
        scene_type: SKIT/DOCU/CONFESSIONAL — gives bonus to shows best suited for this type
        preferred_shows: List of show names to boost (e.g. ["jojo3", "psg_2010"])
        min_duration: Minimum scene duration in seconds
        max_duration: Maximum scene duration in seconds
        limit: Max results to return
        diversify_shows: If True, cap results per show for variety
        max_per_show: Max scenes from a single show when diversify_shows is True

    Returns:
        Dict with 'results' list and 'meta' info.
    """
    if not SCENE_CLUSTERS_PATH.exists():
        return {
            "results": [],
            "meta": {"error": "Scene clusters not built yet. Run --build first."},
        }

    data = json.loads(SCENE_CLUSTERS_PATH.read_text(encoding="utf-8"))
    scenes = data["scenes"]

    # Load show profiles for style-aware scoring
    show_profiles = _load_show_profiles()

    # Build show affinity scores based on scene_type
    show_bonus: dict[str, float] = {}
    if scene_type and scene_type.upper() in _SCENE_TYPE_KEYWORDS:
        keywords = _SCENE_TYPE_KEYWORDS[scene_type.upper()]
        for show_name, profile in show_profiles.items():
            best_for = " ".join(profile.get("best_for_our_show", []))
            hits = sum(1 for kw in keywords if kw.lower() in best_for.lower())
            if hits > 0:
                show_bonus[show_name] = hits * 1.5  # 1.5 points per keyword hit

    # Explicit preferred shows bonus
    if preferred_shows:
        for s in preferred_shows:
            show_bonus[s] = show_bonus.get(s, 0) + 3.0

    # Scoring weights
    weights = {
        "shot_size": 3,
        "angle": 2,
        "mood": 3,
        "situation": 2,
        "composition": 2,
    }

    scored: list[tuple[float, dict[str, Any]]] = []

    for scene in scenes:
        # Hard filters
        if show and scene["show"] != show:
            continue
        if min_duration and scene["duration_sec"] < min_duration:
            continue
        if max_duration and scene["duration_sec"] > max_duration:
            continue

        # Score
        score = 0.0
        match_reasons: list[str] = []

        if shot_size:
            if scene.get("dominant_shot_size", "").lower() == shot_size.lower():
                score += weights["shot_size"]
                match_reasons.append(f"shot_size={shot_size}")

        if angle:
            if scene.get("dominant_angle", "").lower() == angle.lower():
                score += weights["angle"]
                match_reasons.append(f"angle={angle}")

        if mood:
            if scene.get("dominant_mood", "").lower() == mood.lower():
                score += weights["mood"]
                match_reasons.append(f"mood={mood}")

        if situation:
            sit_lower = situation.lower()
            if any(sit_lower in s.lower() for s in scene.get("situations", [])):
                score += weights["situation"]
                match_reasons.append(f"situation={situation}")

        if composition:
            comp_lower = composition.lower()
            if any(comp_lower in c.lower() for c in scene.get("compositions", [])):
                score += weights["composition"]
                match_reasons.append(f"composition={composition}")

        # Show style bonus
        bonus = show_bonus.get(scene["show"], 0)
        if bonus > 0:
            score += bonus
            match_reasons.append(f"show_style_bonus={bonus:.1f}")

        if score > 0:
            scene_result = {
                **scene,
                "_score": score,
                "_match_reasons": match_reasons,
            }
            scored.append((score, scene_result))

    # Sort by score descending
    scored.sort(key=lambda x: -x[0])

    # Diversify by show
    results: list[dict[str, Any]] = []
    if diversify_shows:
        show_counts: dict[str, int] = {}
        for _, scene in scored:
            s = scene["show"]
            if show_counts.get(s, 0) >= max_per_show:
                continue
            show_counts[s] = show_counts.get(s, 0) + 1
            results.append(scene)
            if len(results) >= limit:
                break
    else:
        results = [s for _, s in scored[:limit]]

    return {
        "results": results,
        "meta": {
            "total_candidates": len(scored),
            "returned": len(results),
            "filters": {
                k: v for k, v in {
                    "shot_size": shot_size,
                    "mood": mood,
                    "situation": situation,
                    "composition": composition,
                    "angle": angle,
                    "show": show,
                }.items() if v is not None
            },
        },
    }


# ---------------------------------------------------------------------------
# 7. Statistics
# ---------------------------------------------------------------------------

def print_stats() -> None:
    """Print cluster statistics from the saved JSON."""
    if not SCENE_CLUSTERS_PATH.exists():
        print("No scene_clusters.json found. Run --build first.")
        return

    data = json.loads(SCENE_CLUSTERS_PATH.read_text(encoding="utf-8"))
    meta = data["_meta"]
    scenes = data["scenes"]

    print("=" * 60)
    print("Scene Cluster Statistics")
    print("=" * 60)
    print(f"Total scenes:  {meta['total_scenes']}")
    print(f"Total frames:  {meta['total_frames']}")
    print(f"Shows:         {meta['shows']} ({', '.join(meta['show_list'])})")
    print(f"Gap threshold: {meta['gap_threshold']} frames")
    print(f"Created:       {meta['created']}")
    print()

    # Duration distribution
    durations = [s["duration_sec"] for s in scenes]
    print("Duration distribution:")
    print(f"  Mean:   {sum(durations) / len(durations):.1f}s")
    print(f"  Median: {sorted(durations)[len(durations) // 2]}s")
    print(f"  Min:    {min(durations)}s")
    print(f"  Max:    {max(durations)}s")
    print(f"  1-frame scenes: {sum(1 for d in durations if d == 1)}")
    print(f"  2-5 frame:      {sum(1 for d in durations if 2 <= d <= 5)}")
    print(f"  6-15 frame:     {sum(1 for d in durations if 6 <= d <= 15)}")
    print(f"  16+ frame:      {sum(1 for d in durations if d >= 16)}")
    print()

    # Per-show breakdown
    show_scenes: dict[str, list[dict]] = {}
    for s in scenes:
        show_scenes.setdefault(s["show"], []).append(s)

    print("Per-show breakdown:")
    print(f"  {'Show':<20} {'Scenes':>7} {'Frames':>7} {'Avg dur':>8}")
    print(f"  {'-'*20} {'-'*7} {'-'*7} {'-'*8}")
    for show in sorted(show_scenes.keys()):
        ss = show_scenes[show]
        total_frames = sum(s["frame_count"] for s in ss)
        avg_dur = total_frames / len(ss) if ss else 0
        print(f"  {show:<20} {len(ss):>7} {total_frames:>7} {avg_dur:>7.1f}s")
    print()

    # Top moods
    mood_counter: Counter = Counter()
    for s in scenes:
        m = s.get("dominant_mood")
        if m:
            mood_counter[m] += 1
    print("Top moods:")
    for mood, count in mood_counter.most_common(10):
        print(f"  {mood:<20} {count:>5} scenes")
    print()

    # Top shot sizes
    ss_counter: Counter = Counter()
    for s in scenes:
        v = s.get("dominant_shot_size")
        if v:
            ss_counter[v] += 1
    print("Top shot sizes:")
    for val, count in ss_counter.most_common(10):
        print(f"  {val:<20} {count:>5} scenes")


# ---------------------------------------------------------------------------
# 8. Build pipeline
# ---------------------------------------------------------------------------

def build() -> None:
    """Full build pipeline: load → cluster → save → update DB."""
    print("Loading merged_screenshot_tags.json ...")
    frames = load_merged_tags()
    print(f"  Loaded {len(frames)} frames")

    print("Clustering frames into scenes ...")
    scenes = cluster_frames_into_scenes(frames)
    print(f"  Created {len(scenes)} scenes")

    print("Saving scene_clusters.json ...")
    out_path = save_scene_clusters(scenes, total_frames=len(frames))
    print(f"  Saved to {out_path}")

    print("Updating SQLite DB ...")
    update_sqlite_db(scenes)

    print("Done.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scene clustering pipeline for youtube-studio storyboard system"
    )
    parser.add_argument("--build", action="store_true", help="Build clusters from merged_screenshot_tags.json")
    parser.add_argument("--stats", action="store_true", help="Print cluster statistics")
    parser.add_argument("--search", action="store_true", help="Search scene clusters")
    parser.add_argument("--shot-size", type=str, default=None, help="Filter by shot size")
    parser.add_argument("--angle", type=str, default=None, help="Filter by camera angle")
    parser.add_argument("--mood", type=str, default=None, help="Filter by mood")
    parser.add_argument("--situation", type=str, default=None, help="Filter by situation")
    parser.add_argument("--composition", type=str, default=None, help="Filter by composition")
    parser.add_argument("--show", type=str, default=None, help="Filter by show name")
    parser.add_argument("--scene-type", type=str, default=None, choices=["SKIT", "DOCU", "CONFESSIONAL"], help="Boost shows suited for this scene type")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument("--no-diversify", action="store_true", help="Disable show diversity")

    args = parser.parse_args()

    if args.build:
        build()
        if args.stats:
            print()
            print_stats()
        return

    if args.stats:
        print_stats()
        return

    if args.search:
        if not any([args.shot_size, args.angle, args.mood, args.situation, args.composition, args.show]):
            parser.error("--search requires at least one filter (--shot-size, --mood, etc.)")

        result = search_scenes(
            shot_size=args.shot_size,
            angle=args.angle,
            mood=args.mood,
            situation=args.situation,
            composition=args.composition,
            show=args.show,
            scene_type=args.scene_type,
            limit=args.limit,
            diversify_shows=not args.no_diversify,
        )

        meta = result["meta"]
        scenes = result["results"]
        print(f"Found {meta['total_candidates']} matching scenes, returning {meta['returned']}")
        print(f"Filters: {meta['filters']}")
        print()

        for i, scene in enumerate(scenes, 1):
            print(f"  [{i}] {scene['scene_id']}")
            print(f"      Show: {scene['show']}  Duration: {scene['duration_sec']}s  Frames: {scene['frame_count']}")
            print(f"      Shot: {scene['dominant_shot_size']}  Angle: {scene['dominant_angle']}  Mood: {scene['dominant_mood']}")
            print(f"      Compositions: {', '.join(scene.get('compositions', []))}")
            print(f"      Situations: {', '.join(scene.get('situations', []))}")
            print(f"      Rep frame: {scene['representative_frame']}")
            print(f"      Score: {scene.get('_score', 'n/a')}  Reasons: {', '.join(scene.get('_match_reasons', []))}")
            desc = scene.get("description", "")
            if desc:
                print(f"      Desc: {desc[:120]}{'...' if len(desc) > 120 else ''}")
            print()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
