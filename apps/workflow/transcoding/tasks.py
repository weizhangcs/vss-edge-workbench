# apps/workflow/transcoding/tasks.py

import json  # [新增] 用于解析 ffprobe 的 JSON 输出
import logging
import os
import subprocess
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from apps.media_assets.models import Media
from apps.workflow.models import DeliveryJob, TranscodingJob, TranscodingProject

from ..delivery.tasks import run_delivery_job
from .utils import generate_peaks_from_video

logger = logging.getLogger(__name__)


def _check_and_update_project_status(project: TranscodingProject):
    """
    检查给定项目下的所有转码任务状态，并更新项目的聚合状态。
    """
    project.refresh_from_db()
    all_jobs = project.transcoding_jobs.all()

    if all_jobs.count() == 0:
        return

    failed_exists = all_jobs.filter(status="ERROR").exists()
    running_exists = all_jobs.filter(status__in=["PENDING", "PROCESSING", "CREATED"]).exists()

    new_status = project.status

    if failed_exists:
        new_status = "FAILED"
    elif not running_exists:
        new_status = "COMPLETED"
    else:
        return

    if project.status != new_status:
        project.status = new_status
        project.save(update_fields=["status"])
        logger.info(f"Project {project.id} status updated to {new_status}")


@shared_task(name="apps.workflow.transcoding.tasks.generate_waveform")
def generate_waveform_task(media_id):
    """
    独立任务：为指定 Media 生成波形数据
    """
    # ... (保持原样，未修改) ...
    logger.info(f"Starting waveform generation for Media {media_id}")
    try:
        media = Media.objects.get(id=media_id)
        if not media.source_video:
            logger.warning(f"Media {media_id} has no source video, skipping waveform.")
            return

        temp_dir = Path(settings.MEDIA_ROOT) / "temp_waveforms"
        temp_dir.mkdir(parents=True, exist_ok=True)

        json_filename = f"waveform_{media.id}.json"
        temp_json_path = temp_dir / json_filename

        success = generate_peaks_from_video(media.source_video.path, temp_json_path)

        if success and temp_json_path.exists():
            with open(temp_json_path, "rb") as f:
                media.waveform_data.save(json_filename, ContentFile(f.read()), save=True)
            logger.info(f"Waveform generated and saved for Media {media_id}")
            os.remove(temp_json_path)
        else:
            logger.error(f"Failed to generate waveform for Media {media_id}")
    except Exception as e:
        logger.error(f"Error in generate_waveform_task: {e}", exc_info=True)


@shared_task(name="apps.workflow.transcoding.tasks.run_transcoding_job")
def run_transcoding_job(job_id):
    """
    (V2.5 Duration Fix)
    执行转码 -> [新增] 提取并更新时长 -> 保存文件 -> 触发分发 -> 更新项目状态
    """
    try:
        job = TranscodingJob.objects.select_related("project", "profile", "media__asset").get(id=job_id)
    except TranscodingJob.DoesNotExist:
        logger.error(f"Job {job_id} not found.")
        return

    if job.status == "PENDING":
        job.start()
        job.save()
    elif job.status != "PROCESSING":
        logger.warning(f"Job {job_id} is {job.status}, skipping start.")

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
        # 1. FFmpeg 执行转码
        encoding_params = job.profile.ffmpeg_command.split()
        command = ["ffmpeg", "-i", str(source_video_path), *encoding_params, str(temp_output_path), "-y"]

        logger.info(f"FFmpeg cmd: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")

        # === [核心新增] 2. FFprobe 提取精确时长并回写 Media ===
        try:
            probe_cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(temp_output_path),
            ]
            result = subprocess.run(probe_cmd, check=True, capture_output=True, text=True)
            metadata = json.loads(result.stdout)

            # 优先尝试从 format 中获取
            duration_str = metadata.get("format", {}).get("duration")

            # 如果 format 里没有，尝试从第一个 stream 获取
            if not duration_str:
                streams = metadata.get("streams", [])
                if streams:
                    duration_str = streams[0].get("duration")

            if duration_str:
                exact_duration = float(duration_str)

                # 仅当数据库里的时长无效 (0 或 None) 或者你想强制以转码后文件为准时更新
                # 这里我们强制更新，保证转码后文件与数据库一致
                if abs(media.duration - exact_duration) > 0.1:  # 只有差异超过0.1秒才更新，减少DB写操作
                    media.duration = exact_duration
                    media.save(update_fields=["duration"])
                    logger.info(f"Updated Media {media.id} duration to {exact_duration}s based on transcoding output.")
            else:
                logger.warning(f"Could not extract duration from ffprobe output for Job {job_id}")

        except Exception as probe_error:
            # 探测失败不应阻断流程，记录日志即可
            logger.error(f"Failed to probe duration for Job {job_id}: {probe_error}")

        # === [核心新增结束] ===

        # 3. 原子化：保存 + 触发分发
        with transaction.atomic():
            with open(temp_output_path, "rb") as f:
                job.output_file.save(temp_output_filename, ContentFile(f.read()), save=False)

            job.queue_for_qa()
            job.save()

            delivery_job = DeliveryJob.objects.create(source_object=job)
            transaction.on_commit(lambda: run_delivery_job.delay(delivery_job.id))

            if not job.media.waveform_data:
                transaction.on_commit(lambda: generate_waveform_task.delay(job.media.id))

        logger.info(f"Job {job_id} finished transcoding, triggering delivery {delivery_job.id}")
        _check_and_update_project_status(job.project)

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        if job:
            job.fail()
            job.save()
            _check_and_update_project_status(job.project)
        raise e

    finally:
        if temp_output_path and temp_output_path.exists():
            os.remove(temp_output_path)
