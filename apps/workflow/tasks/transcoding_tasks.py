# 文件路径: apps/workflow/tasks/transcoding_tasks.py

import subprocess
from pathlib import Path
from celery import shared_task
from django.conf import settings
import logging

from ..jobs.transcodingJob import TranscodingJob

logger = logging.getLogger(__name__)


def get_ffmpeg_command(profile, source_path, output_path):
    """根据不同的 profile 生成对应的 FFmpeg 命令"""
    if profile == TranscodingJob.PROFILE.H264_720P_2M:
        return [
            'ffmpeg', '-i', str(source_path),
            '-c:v', 'libx264', '-b:v', '2M',
            '-vf', 'scale=-2:720',  # 缩放到 720p
            '-preset', 'fast', '-y', str(output_path)
        ]
    elif profile == TranscodingJob.PROFILE.H264_1080P_5M:
        return [
            'ffmpeg', '-i', str(source_path),
            '-c:v', 'libx264', '-b:v', '5M',
            '-vf', 'scale=-2:1080',  # 缩放到 1080p
            '-preset', 'fast', '-y', str(output_path)
        ]
    # 未来可以在这里添加更多 profile 的处理逻辑
    raise ValueError(f"不支持的转码规格: {profile}")


@shared_task
def run_transcoding_job(job_id):
    """
    执行一个具体的转码任务 (TranscodingJob)。
    """
    try:
        job = TranscodingJob.objects.get(id=job_id)
    except TranscodingJob.DoesNotExist:
        logger.error(f"找不到 ID 为 {job_id} 的转码任务。")
        return

    # 1. 更新任务状态为“处理中”
    job.start()
    job.save()

    media = job.media
    source_video_path = Path(media.source_video.path)

    # 2. 准备输出路径
    # 遵循您的设计：transcoding_outputs/{asset_id}/{job_id}.mp4
    output_dir = Path(settings.MEDIA_ROOT) / 'transcoding_outputs' / str(media.asset.id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{job.id}.mp4"

    try:
        # 3. 生成并执行 FFmpeg 命令
        command = get_ffmpeg_command(job.profile, source_video_path, output_path)
        logger.info(f"执行转码命令: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')

        # 4. 成功后，将输出文件路径保存回 Job 模型
        # 'transcoding_outputs/' 后面的部分
        relative_path = output_path.relative_to(Path(settings.MEDIA_ROOT))
        job.output_file.name = str(relative_path)

        job.complete()
        job.save()
        logger.info(f"转码任务 {job_id} 成功完成！")

    except Exception as e:
        # 5. 失败后，更新任务状态为“错误”
        logger.error(f"转码任务 {job_id} 失败: {e}", exc_info=True)
        job.fail()
        job.save()
        raise e