# 文件路径: apps/workflow/transcoding/tasks.py

import subprocess
from pathlib import Path
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
import logging
import os

from ..models import TranscodingJob, DeliveryJob
from ..delivery.tasks import run_delivery_job

from apps.media_assets.services.storage import StorageService

logger = logging.getLogger(__name__)


@shared_task
def run_transcoding_job(job_id):
    """
    (V2.2 健壮命令版)
    执行一个具体的转码任务 (TranscodingJob)。
    """
    try:
        job = TranscodingJob.objects.select_related('profile', 'media__asset').get(id=job_id)
    except TranscodingJob.DoesNotExist:
        logger.error(f"找不到 ID 为 {job_id} 的转码任务。")
        return

    job.start()
    job.save()

    media = job.media
    source_video_path = Path(media.source_video.path)

    temp_output_dir = Path(settings.MEDIA_ROOT) / 'temp_transcoding'
    temp_output_dir.mkdir(parents=True, exist_ok=True)
    temp_output_filename = f"{job.id}.{job.profile.container}"
    temp_output_path = temp_output_dir / temp_output_filename

    try:
        # --- ↓↓↓ 核心修正：采用更健壮的命令组装方式 ↓↓↓ ---

        # 1. 从 profile 获取纯粹的转码参数
        encoding_params = job.profile.ffmpeg_command.split()

        # 2. 按照 ffmpeg 的标准语法，清晰地组装命令
        command = [
            'ffmpeg',
            '-i', str(source_video_path),
            *encoding_params,  # 使用 * 解包，将所有参数平铺到列表中
            str(temp_output_path),  # 明确地在参数之后、-y 之前，添加输出文件路径
            '-y'  # 覆盖输出文件
        ]
        # --- ↑↑↑ 修正结束 ↑↑↑ ---

        logger.info(f"执行转码命令: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        logger.info(f"FFmpeg 转码成功: {temp_output_path}")

        with open(temp_output_path, 'rb') as f:
            job.output_file.save(temp_output_filename, ContentFile(f.read()), save=False)
        logger.info(f"已将本地产出物路径保存至 job.output_file")

        delivery_job = DeliveryJob.objects.create(source_object=job)

        # 2. 触发新的 delivery Celery 任务
        run_delivery_job.delay(delivery_job.id)
        logger.info(f"已为转码任务 {job.id} 创建并触发了分发任务 {delivery_job.id}")

        #job.output_url = s3_url
        job.complete()
        job.save()
        #logger.info(f"转码任务 {job_id} 成功完成！产出物URL: {s3_url}")

    except Exception as e:
        logger.error(f"转码任务 {job_id} 失败: {e}", exc_info=True)
        if isinstance(e, subprocess.CalledProcessError):
            logger.error(f"--- FFmpeg STDERR ---\n{e.stderr}")
        job.fail()
        job.save()
        raise e
    finally:
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
            logger.info(f"已清理临时文件: {temp_output_path}")