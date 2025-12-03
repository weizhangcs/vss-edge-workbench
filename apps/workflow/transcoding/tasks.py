# apps/workflow/transcoding/tasks.py

import logging
import os
import subprocess
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from apps.workflow.models import DeliveryJob, TranscodingJob, TranscodingProject

from ..delivery.tasks import run_delivery_job

logger = logging.getLogger(__name__)


def _check_and_update_project_status(project: TranscodingProject):
    """
    检查给定项目下的所有转码任务状态，并更新项目的聚合状态。
    """
    # 刷新对象以获取最新状态
    project.refresh_from_db()

    all_jobs = project.transcoding_jobs.all()
    total_jobs = all_jobs.count()

    if total_jobs == 0:
        return

    # [核心修复] 使用字符串字面量，避开 STATUS vs Status 的属性引用坑
    # 同时也为了兼容 model_utils Choices 的取值方式

    # 检查是否有失败的任务
    # 注意：这里假设数据库里存的就是 "ERROR" 或 "FAILED" 这样的字符串
    # 根据日志报错，之前的 STATUS.CREATED 说明定义可能是 Choices

    # 我们直接查数据库字段的值，这是最安全的
    failed_exists = all_jobs.filter(status="ERROR").exists()

    # 检查是否还有未完成的任务
    running_exists = all_jobs.filter(status__in=["PENDING", "PROCESSING", "CREATED"]).exists()

    new_status = project.status

    if failed_exists:
        new_status = "FAILED"
    elif not running_exists:
        # 没有正在跑的，也没有失败的，说明全成功了
        new_status = "COMPLETED"
    else:
        # 还有在跑的，保持 PROCESSING (或不做改变)
        return

    if project.status != new_status:
        project.status = new_status
        project.save(update_fields=["status"])
        logger.info(f"Project {project.id} status updated to {new_status}")


@shared_task(name="apps.workflow.transcoding.tasks.run_transcoding_job")
def run_transcoding_job(job_id):
    """
    (V2.4 Status 修复版)
    执行转码 -> 保存文件 -> 触发分发 -> 更新项目状态
    """
    try:
        job = TranscodingJob.objects.select_related("project", "profile", "media__asset").get(id=job_id)
    except TranscodingJob.DoesNotExist:
        logger.error(f"Job {job_id} not found.")
        return

    # [修复] 统一使用字符串字面量或确保 Status 属性正确
    # 这里我们直接用字符串，这是 Django Choices 的通用做法
    if job.status == "PENDING":
        job.start()  # start() 方法内部应该会设为 PROCESSING
        job.save()
    elif job.status != "PROCESSING":
        logger.warning(f"Job {job_id} is {job.status}, skipping start.")

    # 准备路径
    media = job.media
    if not media.source_video:
        logger.error(f"Job {job_id}: Media has no source video.")
        job.fail()
        job.save()
        _check_and_update_project_status(job.project)
        return

    source_video_path = Path(media.source_video.path)
    temp_output_dir = Path(settings.MEDIA_ROOT) / "temp_transcoding"
    temp_output_dir.mkdir(parents=True, exist_ok=True)

    ext = job.profile.container if job.profile.container else "mp4"
    temp_output_filename = f"{job.id}.{ext}"
    temp_output_path = temp_output_dir / temp_output_filename

    try:
        # FFmpeg 执行
        encoding_params = job.profile.ffmpeg_command.split()
        command = ["ffmpeg", "-i", str(source_video_path), *encoding_params, str(temp_output_path), "-y"]

        logger.info(f"FFmpeg cmd: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")

        # 原子化：保存 + 触发分发
        with transaction.atomic():
            with open(temp_output_path, "rb") as f:
                job.output_file.save(temp_output_filename, ContentFile(f.read()), save=False)

            job.queue_for_qa()  # 状态变为 QA_PENDING
            job.save()

            delivery_job = DeliveryJob.objects.create(source_object=job)

            transaction.on_commit(lambda: run_delivery_job.delay(delivery_job.id))

        logger.info(f"Job {job_id} finished transcoding, triggering delivery {delivery_job.id}")

        # [关键] 更新项目状态
        _check_and_update_project_status(job.project)

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        if job:
            job.fail()  # 状态变为 ERROR
            job.save()
            _check_and_update_project_status(job.project)
        raise e

    finally:
        if temp_output_path and temp_output_path.exists():
            os.remove(temp_output_path)
