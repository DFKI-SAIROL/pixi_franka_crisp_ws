#!/usr/bin/env python3
"""Cut the end of recorded episodes at the last teleoperation command.

After a demonstration the operator sends the arm home with a button. That motion is
still recorded (the robot follows `safe_target_pose` with teleop disabled), but it is
not part of the demonstration. This script finds the last moment `movement_enabled`
was true in `/franka_<arm>/mq_debug` and cuts the episode there:

- every video in `videos/` keeps exactly the frames whose stamp is <= the cut time
  (stream copy, no re-encoding; the decoded frames are checked against the originals);
- `videos/timestamps.npy` is cut to the same frames;
- the mcap keeps the messages received up to the cut time (all topics, incl. /tf_static);
- `calibration/` is copied unchanged.

Frame i of every video still has stamp timestamps[i], so actions and camera frames stay
aligned. The originals are not modified: the output goes to a separate folder.

Usage (from the workspace root):

    pixi run -e humble bash -c "source install/setup.bash && python scripts/python/clip_episodes.py \
        /mnt/data/xiaoqi/single_arm/put_banana_on_box/episode_2026* \
        --output-dir /mnt/data/xiaoqi/single_arm/put_banana_on_box_clipped"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np


def last_teleop_time(mcap_dir: Path) -> tuple[float | None, list[str]]:
    """Latest header stamp [s] with movement_enabled == True over all arms."""
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(mcap_dir), storage_id="mcap"), rosbag2_py.ConverterOptions("", ""))
    topics = {t.name: t.type for t in reader.get_all_topics_and_types() if t.name.endswith("/mq_debug")}
    if not topics:
        return None, []
    reader.set_filter(rosbag2_py.StorageFilter(topics=list(topics)))
    classes = {name: get_message(kind) for name, kind in topics.items()}
    last, arms = None, set()
    while reader.has_next():
        topic, data, _ = reader.read_next()
        msg = deserialize_message(data, classes[topic])
        if msg.movement_enabled:
            stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            last = stamp if last is None else max(last, stamp)
            arms.add(topic.split("/")[1])
    return last, sorted(arms)


def clip_mcap(src_dir: Path, dst_dir: Path, cut_ns: int) -> tuple[int, int]:
    import rosbag2_py

    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(src_dir), storage_id="mcap"), rosbag2_py.ConverterOptions("", ""))
    writer = rosbag2_py.SequentialWriter()
    writer.open(rosbag2_py.StorageOptions(uri=str(dst_dir), storage_id="mcap"), rosbag2_py.ConverterOptions("", ""))
    for topic in reader.get_all_topics_and_types():
        writer.create_topic(topic)
    kept = dropped = 0
    while reader.has_next():
        topic, data, t_ns = reader.read_next()
        if t_ns <= cut_ns or topic == "/tf_static":
            writer.write(topic, data, t_ns)
            kept += 1
        else:
            dropped += 1
    del writer  # closes the bag and writes metadata.yaml
    return kept, dropped


def _frame_hashes(path: Path, frames: int | None = None) -> list[str]:
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0"]
    if frames is not None:
        cmd += ["-frames:v", str(frames)]
    cmd += ["-f", "framemd5", "-"]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    return [line.split(",")[-1].strip() for line in out.splitlines() if line and not line.startswith("#")]


def exact_cut_points(path: Path) -> set[int]:
    """Frame counts n where a stream copy of the first n packets gives exactly frames 0..n-1.

    With B-frames, packets come in decode order (e.g. P3 B1 B0 B2), so cutting inside such a
    group leaves frames that reference a dropped packet. A cut is exact where the first n
    packets in decode order are the n earliest frames in display order.
    """
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    pts = [int(x) for x in out.split() if x.strip() and x.strip() != "N/A"]
    order = {p: i for i, p in enumerate(sorted(pts))}  # display index of each packet
    points, seen_max = set(), -1
    for n, p in enumerate(pts, start=1):
        seen_max = max(seen_max, order[p])
        if seen_max == n - 1:
            points.add(n)
    return points


def clip_video(src: Path, dst: Path, frames: int) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0", "-c", "copy", "-frames:v", str(frames), str(dst)],
        check=True,
    )
    got = _frame_hashes(dst)
    want = _frame_hashes(src, frames)
    if got != want:
        raise RuntimeError(f"{dst}: decoded frames differ from the first {frames} frames of {src} "
                           f"({len(got)} vs {len(want)} frames)")


MAX_FRAMES_LOST = 3  # frames we accept to drop at the end to avoid re-encoding
REENCODE_CRF = 16  # recordings use crf 23; 16 keeps re-encoded frames visually identical
MIN_PSNR_DB = 40.0


def reencode_video(src: Path, dst: Path, frames: int) -> float:
    """Re-encode the first ``frames`` frames (H.264, high quality). Returns the mean PSNR vs. the source."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:v:0", "-frames:v", str(frames),
         "-fps_mode", "passthrough", "-c:v", "libx264", "-preset", "slow", "-crf", str(REENCODE_CRF),
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)],
        check=True,
    )
    count = len(_frame_hashes(dst))
    if count != frames:
        raise RuntimeError(f"{dst}: re-encoded {count} frames, expected {frames}")
    out = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(dst), "-i", str(src), "-lavfi",
         f"[1:v]trim=end_frame={frames},setpts=PTS-STARTPTS[ref];[0:v]setpts=PTS-STARTPTS[dst];[dst][ref]psnr",
         "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    ).stderr
    psnr = float(out.rsplit("average:", 1)[1].split()[0])
    if psnr < MIN_PSNR_DB:
        raise RuntimeError(f"{dst}: PSNR {psnr:.1f} dB vs. source is below {MIN_PSNR_DB} dB")
    return psnr


def clip_episode(src: Path, dst: Path, margin_s: float, dry_run: bool) -> dict:
    stamps = np.load(src / "videos" / "timestamps.npy")
    last_on, arms = last_teleop_time(src / "mcap")
    if last_on is None:
        raise RuntimeError(f"{src.name}: teleop was never enabled (no movement_enabled in mq_debug)")
    teleop_end_ns = int(round((last_on + margin_s) * 1e9))
    wanted = int((stamps <= teleop_end_ns).sum())
    # Largest frame count <= wanted at which every video can be cut exactly without re-encoding.
    videos = sorted(v for v in (src / "videos").iterdir() if v.suffix in (".mp4", ".mkv"))
    points = {video: exact_cut_points(video) for video in videos}
    common = set.intersection(*points.values())
    candidates = [n for n in common if wanted - MAX_FRAMES_LOST <= n <= wanted]
    if candidates:
        frames = max(candidates)
    else:
        # The cameras' B-frame groups are out of phase: pick the cut (at most MAX_FRAMES_LOST early)
        # that most videos can take as a stream copy; the others get re-encoded.
        window = range(max(1, wanted - MAX_FRAMES_LOST), wanted + 1)
        frames = max(window, key=lambda n: (sum(n in p for p in points.values()), n))
    reencode = [v.name for v in videos if frames not in points[v]]
    # Robot data runs until the next (removed) frame, so the last kept frame keeps its full interval.
    cut_ns = int(stamps[frames]) - 1 if frames < len(stamps) else int(stamps[-1])
    info = {
        "episode": src.name,
        "arms": arms,
        "frames_before": len(stamps),
        "frames_after": frames,
        "frames_lost_to_gop": wanted - frames,
        "reencoded": reencode,
        "teleop_end_s_from_start": round((teleop_end_ns - stamps[0]) * 1e-9, 2),
        "removed_s": round((stamps[-1] - stamps[frames - 1]) * 1e-9, 2),
    }
    if dry_run:
        return info
    if dst.exists():
        raise RuntimeError(f"{dst} exists; remove it first")
    (dst / "videos").mkdir(parents=True)
    shutil.copytree(src / "calibration", dst / "calibration")
    np.save(dst / "videos" / "timestamps.npy", stamps[:frames])
    psnr = {}
    for video in videos:
        if video.name in reencode:
            psnr[video.name] = round(reencode_video(video, dst / "videos" / video.name, frames), 1)
        else:
            clip_video(video, dst / "videos" / video.name, frames)
    if psnr:
        info["reencode_psnr_db"] = psnr
    kept, dropped = clip_mcap(src / "mcap", dst / "mcap", cut_ns)
    info.update(mcap_messages_kept=kept, mcap_messages_dropped=dropped)
    (dst / "clip_info.json").write_text(json.dumps({**info, "source": str(src), "cut_ns": cut_ns}, indent=1))
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("episodes", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--margin-s", type=float, default=0.0,
                        help="keep this much extra time after the last teleop command")
    parser.add_argument("--min-removed-s", type=float, default=0.0,
                        help="copy episodes unchanged when less than this would be removed")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    failures = 0
    for src in args.episodes:
        src = src.resolve()
        try:
            info = clip_episode(src, args.output_dir / src.name, args.margin_s, dry_run=True)
            if not args.dry_run:
                if info["removed_s"] < args.min_removed_s:
                    shutil.copytree(src, args.output_dir / src.name)
                    info["copied_unchanged"] = True
                else:
                    info = clip_episode(src, args.output_dir / src.name, args.margin_s, dry_run=False)
            print(json.dumps(info))
        except Exception as exc:  # keep going, report at the end
            failures += 1
            print(f"[ERROR] {src.name}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
