# 文件路径: apps/workflow/views/annotation_views.py

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.files.base import ContentFile
import logging

from ..models import AnnotationJob

logger = logging.getLogger(__name__)


def start_l1_annotation_view(request, job_id):
    """
    处理“开始L1字幕标注”按钮点击的视图。
    1. 将任务状态变更为“处理中”。
    2. 重定向到 vss-subeditor 外部工具。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    if job.status == 'PENDING':
        job.start()
        job.save()
        messages.success(request, f"字幕任务 '{job.media.title}' 状态已更新为“处理中”。")

    video_url = f"{settings.LOCAL_MEDIA_URL_BASE}{job.media.source_video.url}"

    srt_url = ""
    if job.media.source_subtitle:
        srt_url = f"{settings.LOCAL_MEDIA_URL_BASE}{job.media.source_subtitle.url}"

    job_id_param = job.id
    return_url_param = request.build_absolute_uri(
        reverse('admin:workflow_annotationproject_change', args=[job.project.id]))

    subeditor_url = f"{settings.SUBEDITOR_PUBLIC_URL}?videoUrl={video_url}&srtUrl={srt_url}&jobId={job_id_param}&returnUrl={return_url_param}"

    return redirect(subeditor_url)


@csrf_exempt
def save_l1_output_view(request, job_id):
    """
    接收来自 vss-subeditor 的回调，保存L1产出物 (.ass 文件)。
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)

    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    try:
        ass_content = request.body.decode('utf-8')

        if not ass_content:
            return JsonResponse({'status': 'error', 'message': 'No content received'}, status=400)

        file_name = f"{job.media.title}_l1.ass"
        job.l1_output_file.save(file_name, ContentFile(ass_content.encode('utf-8')), save=False)

        job.complete()
        job.save()

        return JsonResponse({'status': 'success', 'message': 'L1 output saved and job marked as complete.'})

    except Exception as e:
        job.fail()
        job.save()
        logger.error(f"保存L1产出物时出错 (Job ID: {job.id}): {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def revise_l1_annotation_view(request, job_id):
    """
    处理“修订L1字幕”按钮点击的视图。
    1. 调用revise()方法，自动备份产出物并将状态变更为“修订中”。
    2. 重定向到 vss-subeditor 外部工具。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    if job.status == 'COMPLETED':
        job.revise()
        job.save()
        messages.success(request, f"字幕任务 '{job.media.title}' 已重新打开进行修订。")

    video_url = f"{settings.LOCAL_MEDIA_URL_BASE}{job.media.source_video.url}"
    srt_url = ""
    if job.l1_output_file:
        # 【核心修正】手动构建正确的URL，以匹配Nginx配置
        # job.l1_output_file.name 的值是类似: <project_id>/<job_id>_filename.ass
        correct_path = f"/media/annotation/{job.l1_output_file.name}"
        srt_url = f"{settings.LOCAL_MEDIA_URL_BASE}{correct_path}"

    job_id_param = job.id
    return_url_param = request.build_absolute_uri(
        reverse('admin:workflow_annotationproject_change', args=[job.project.id]))

    subeditor_url = f"{settings.SUBEDITOR_PUBLIC_URL}?videoUrl={video_url}&srtUrl={srt_url}&jobId={job_id_param}&returnUrl={return_url_param}"

    return redirect(subeditor_url)