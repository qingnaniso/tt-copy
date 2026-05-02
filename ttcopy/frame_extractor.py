"""视频关键帧提取器 —— 基于 ffmpeg，纯工具模块，不依赖 AI。"""

import subprocess
from pathlib import Path


def extract_frames(video_path: str, num_frames: int = 3, output_dir: str = None) -> list[str]:
    """
    从视频中提取 num_frames 张关键帧，均匀分布在视频中段（跳过首尾）。

    Args:
        video_path: 视频文件路径。
        num_frames: 提取帧数，默认 3 张（前中后各一帧）。
        output_dir: 帧输出目录，默认保存到视频同目录的 frames/ 文件夹下。

    Returns:
        提取成功的帧文件绝对路径列表。

    Raises:
        FileNotFoundError: 视频文件不存在。
        RuntimeError: ffmpeg/ffprobe 执行失败。
    """
    video = Path(video_path).resolve()
    if not video.exists():
        raise FileNotFoundError(f"视频不存在: {video}")

    out = Path(output_dir) if output_dir else video.parent / "frames"
    out.mkdir(parents=True, exist_ok=True)

    # 获取视频时长（秒）
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        capture_output=True, text=True, check=True,
    )
    duration = float(probe.stdout.strip())

    frames: list[str] = []
    stem = video.stem

    for i in range(1, num_frames + 1):
        # 均匀分布，跳过开头和结尾（避免黑屏、片头片尾、转场）
        timestamp = (duration * i) / (num_frames + 1)
        frame_file = out / f"{stem}_frame{i:02d}.jpg"

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(timestamp),
                "-i", str(video),
                "-vframes", "1",
                "-q:v", "2",
                str(frame_file),
            ],
            capture_output=True,
        )

        if frame_file.exists() and frame_file.stat().st_size > 0:
            frames.append(str(frame_file))

    return frames
