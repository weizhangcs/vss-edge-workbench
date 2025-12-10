# apps/workflow/annotation/views.py

import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.workflow.transcoding.jobs import TranscodingJob

from .jobs import AnnotationJob
from .services.annotation_service import AnnotationService

logger = logging.getLogger(__name__)


def _build_full_url(url_path):
    if not url_path:
        return ""
    if url_path.startswith("http"):
        return url_path

    base = getattr(settings, "LOCAL_MEDIA_URL_BASE", "").rstrip("/")
    path = url_path.lstrip("/")
    return f"{base}/{path}"


@login_required
def annotation_workbench_entry(request, job_id):
    job = get_object_or_404(AnnotationJob, pk=job_id)

    if job.status == "PENDING":
        job.start_annotation()
        job.save()

    # [核心修复] 变量初始化前置，防止 UnboundLocalError
    video_url = ""
    server_data_json = "{}"  # 默认空对象

    # 1. 计算最佳视频播放地址
    try:
        transcoding_job = (
            TranscodingJob.objects.filter(media=job.media, status="COMPLETED").order_by("-modified").first()
        )

        if transcoding_job and transcoding_job.output_url:
            video_url = _build_full_url(transcoding_job.output_url)
        elif job.media.source_video:
            video_url = _build_full_url(job.media.source_video.url)

        logger.info(f"Resolved Video URL for Job {job_id}: {video_url}")
    except Exception as e:
        logger.error(f"Video URL Resolution Error: {e}")
        # 兜底
        if hasattr(job.media, "source_video") and job.media.source_video:
            video_url = job.media.source_video.url

    # 2. 加载数据并注入
    try:
        media_annotation = AnnotationService.load_annotation(job)

        # 注入计算好的 video_url
        if video_url:
            media_annotation.source_path = video_url

        server_data_json = media_annotation.model_dump_json()
    except Exception as e:
        logger.error(f"Data Load Error for Job {job.id}: {e}", exc_info=True)
        server_data_json = json.dumps({"error": str(e)})

    # 3. 获取波形图
    waveform_url = None
    if job.media.waveform_data:
        waveform_url = _build_full_url(job.media.waveform_data.url)

    # [核心新增] 计算精确的返回路径 (Back to Project)
    # 跳转到 AnnotationProject 的 Admin 详情页 (Tab 1)
    try:
        return_url = reverse("admin:workflow_annotationproject_change", args=[job.project.id])
    except Exception:
        # 兜底：如果反向解析失败，回退到 admin 首页
        return_url = "/admin/"

    context = {
        "job_id": job.id,
        "project_id": job.project.id,
        "media_url": video_url,
        "waveform_url": waveform_url,
        "return_url": return_url,
        "server_data_json": server_data_json,
    }

    return render(request, "admin/workflow/project/annotation/workbench.html", context)


@require_POST
def annotation_save_api(request, job_id):
    try:
        job = get_object_or_404(AnnotationJob, pk=job_id)
        payload = json.loads(request.body)

        AnnotationService.save_annotation(job, payload)

        return JsonResponse({"status": "success", "message": "Saved successfully"})
    except Exception as e:
        logger.error(f"Save failed for Job {job_id}: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
