# 文件路径: apps/workflow/transcoding/tasks.py

import subprocess
from pathlib import Path
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
import logging
import os

from django.db import transaction

# [修复/新增] 确保导入 TranscodingProject
from ..models import TranscodingJob, DeliveryJob, TranscodingProject
from ..delivery.tasks import run_delivery_job

from apps.media_assets.services.storage import StorageService

logger = logging.getLogger(__name__)


def _check_and_update_project_status(project: TranscodingProject):
    """
    检查给定项目下的所有转码任务状态，并更新项目的聚合状态。
    """
    all_jobs = project.transcoding_jobs.all()
    total_jobs = all_jobs.count()

    if total_jobs == 0:
        return

    completed_jobs = all_jobs.filter(status=TranscodingJob.STATUS.COMPLETED).count()
    error_jobs = all_jobs.filter(status=TranscodingJob.STATUS.ERROR).count()

    new_status = project.status  # 默认保持不变

    if error_jobs > 0:
        # 如果有任何任务失败，项目状态应为 FAILED
        new_status = TranscodingProject.STATUS.FAILED
    elif completed_jobs == total_jobs:
        # 如果所有任务都已完成，项目状态应为 COMPLETED
        new_status = TranscodingProject.STATUS.COMPLETED

    # 只有当新状态不同于当前状态时才进行更新
    if project.status != new_status:
        project.status = new_status
        project.save(update_fields=['status'])
        logger.info(f"Transcoding Project {project.id} status successfully updated to {new_status}")


@shared_task
def run_transcoding_job(job_id):
    """
    (V2.2 健壮命令版)
    执行一个具体的转码任务 (TranscodingJob)。
    """
    job = None
    temp_output_path = None
    try:
        # 优化查询以减少数据库访问
        job = TranscodingJob.objects.select_related('project', 'profile', 'media__asset').get(id=job_id)
    except TranscodingJob.DoesNotExist:
        logger.error(f"找不到 ID 为 {job_id} 的转码任务。")
        return

    # [FIX 3a] 确保我们是从 PENDING 状态开始的
    if job.status == TranscodingJob.STATUS.PENDING:
        job.start()
        job.save()
    elif job.status != TranscodingJob.STATUS.PROCESSING:
        logger.warning(f"任务 {job_id} 状态为 {job.status}，不是 PENDING，跳过 start()")
        # (如果任务是 REVISING 等，也允许继续)
        pass

    media = job.media
    source_video_path = Path(media.source_video.path)

    temp_output_dir = Path(settings.MEDIA_ROOT) / 'temp_transcoding'
    temp_output_dir.mkdir(parents=True, exist_ok=True)
    temp_output_filename = f"{job.id}.{job.profile.container}"
    temp_output_path = temp_output_dir / temp_output_filename

    try:
        # 1. FFmpeg 命令组装
        encoding_params = job.profile.ffmpeg_command.split()
        command = [
            'ffmpeg',
            '-i', str(source_video_path),
            *encoding_params,
            str(temp_output_path),
            '-y'
        ]

        logger.info(f"执行转码命令: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        logger.info(f"FFmpeg 转码成功: {temp_output_path}")

        # ----------------- 修改开始 -----------------
        # 使用原子事务块，确保块内所有数据库操作提交后，才会执行 on_commit
        with transaction.atomic():
            # 1. 先保存文件 (save=False 不操作DB，只是把文件对象挂在内存实例上)
            with open(temp_output_path, 'rb') as f:
                job.output_file.save(temp_output_filename, ContentFile(f.read()), save=False)

            # 2. 更新状态为 QA_PENDING
            job.queue_for_qa()

            # 3. 真正保存到数据库 (状态和文件路径同时落库)
            job.save()
            logger.info(f"已将本地产出物路径保存至 job.output_file，状态已更为 QA_PENDING")

            # 4. 创建分发任务记录
            delivery_job = DeliveryJob.objects.create(source_object=job)

            # 5. 注册回调：只有当这个 with 块成功结束（事务提交）后，才发送 Celery 任务
            transaction.on_commit(lambda: run_delivery_job.delay(delivery_job.id))

            logger.info(f"已为转码任务 {job.id} 创建分发任务 {delivery_job.id} (等待事务提交后触发)")
        # ----------------- 修改结束 -----------------

        # [新增逻辑] 检查并更新父级项目状态
        _check_and_update_project_status(job.project)

    except Exception as e:
        logger.error(f"转码任务 {job_id} 失败: {e}", exc_info=True)
        if isinstance(e, subprocess.CalledProcessError):
            logger.error(f"--- FFmpeg STDERR ---\n{e.stderr}")

        # 任务失败，更新状态
        if job:
            job.fail()
            job.save()

            # [新增逻辑] 检查并更新父级项目状态 (因为有任务失败了)
            _check_and_update_project_status(job.project)

        raise e
    finally:
        if temp_output_path and os.path.exists(temp_output_path):
            os.remove(temp_output_path)
            logger.info(f"已清理临时文件: {temp_output_path}")