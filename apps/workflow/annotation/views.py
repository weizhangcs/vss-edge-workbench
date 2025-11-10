# 文件路径: apps/workflow/annotation/views.py

import logging
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.files.base import ContentFile

from ..models import AnnotationJob, AnnotationProject, TranscodingJob
from .tasks import (
    trigger_character_audit_task,
    generate_narrative_blueprint_task,
    export_l2_output_task,
    calculate_local_metrics_task
)

logger = logging.getLogger(__name__)


def get_video_url_for_job(job: AnnotationJob) -> str:
    """
    (V5.0 CDN 加速版)
    为 L1 标注任务智能查找最佳的视频 URL。

    1. 优先尝试查找与项目 'source_encoding_profile' 匹配的 CDN (TranscodingJob) URL。
    2. 如果找不到，回退到使用本地存储的 'source_video' URL。
    """
    project = job.project
    media_item = job.media

    video_url = None
    if project.source_encoding_profile:
        # 1. 优先查找已完成的转码任务
        transcoding_job = TranscodingJob.objects.filter(
            media=media_item,
            profile=project.source_encoding_profile,
            status=TranscodingJob.STATUS.COMPLETED
        ).order_by('-modified').first()

        if transcoding_job and transcoding_job.output_url:
            video_url = transcoding_job.output_url

    if not video_url:
        # 2. 回退到使用本地源文件
        if media_item.source_video:
            video_url = f"{settings.LOCAL_MEDIA_URL_BASE}{media_item.source_video.url}"
        else:
            logger.warning(f"Job {job.id} 既没有转码文件，也没有源文件，视频 URL 将为空。")
            video_url = ""

    return video_url


def start_l1_annotation_view(request, job_id):
    """
    (L1 Tab 按钮触发)
    处理“开始L1字幕标注”按钮点击的视图。
    1. 将 Job 状态变更为“处理中”。
    2. 重定向到 vss-subeditor 外部工具。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    if job.status == 'PENDING':
        job.start_annotation()  # (PENDING -> PROCESSING)
        job.save()
        messages.success(request, f"字幕任务 '{job.media.title}' 状态已更新为“处理中”。")

    # 智能获取视频 URL (CDN 或本地)
    video_url = get_video_url_for_job(job)

    # 获取源字幕文件 URL (如果有)
    srt_url = ""
    if job.media.source_subtitle:
        srt_url = f"{settings.LOCAL_MEDIA_URL_BASE}{job.media.source_subtitle.url}"

    job_id_param = job.id
    # 构建一个回调 URL，以便 Subeditor 完成后能返回 L1 Tab
    return_url_param = request.build_absolute_uri(
        reverse('admin:workflow_annotationproject_tab_l1', args=[job.project.id]))

    # 构建 vss-subeditor 的 URL
    subeditor_url = f"{settings.SUBEDITOR_PUBLIC_URL}?videoUrl={video_url}&srtUrl={srt_url}&jobId={job_id_param}&returnUrl={return_url_param}"

    return redirect(subeditor_url)


@csrf_exempt
def save_l1_output_view(request, job_id):
    """
    (外部 Webhook)
    接收来自 vss-subeditor 的 POST 回调，保存L1产出物 (.ass 文件)。
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)

    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    try:
        # 1. 从 request.body 获取 .ass 内容
        ass_content = request.body.decode('utf-8')

        if not ass_content:
            return JsonResponse({'status': 'error', 'message': 'No content received'}, status=400)

        # 2. 保存文件到 L1 产出物字段
        file_name = f"{job.media.title}_l1.ass"
        job.l1_output_file.save(file_name, ContentFile(ass_content.encode('utf-8')), save=False)

        # 3. 转换状态为 "COMPLETED"
        job.complete_annotation()
        job.save()

        return JsonResponse({'status': 'success', 'message': 'L1 output saved and job marked as complete.'})

    except Exception as e:
        # 4. 如果失败, 转换状态为 "FAILED" (或 "ERROR")
        job.fail()
        job.save()
        logger.error(f"保存L1产出物时出错 (Job ID: {job.id}): {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def revise_l1_annotation_view(request, job_id):
    """
    (L1 Tab 按钮触发)
    处理“修订L1字幕”按钮点击的视图。
    1. 调用 job.revise()，自动备份产出物并将状态变更为“修订中”。
    2. 重定向到 vss-subeditor 外部工具。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    if job.status == 'COMPLETED':
        job.revise()  # (COMPLETED -> REVISING, 自动备份在 job.revise() 中处理)
        job.save()
        messages.success(request, f"字幕任务 '{job.media.title}' 已重新打开进行修订。")

    # 智能获取视频 URL (CDN 或本地)
    video_url = get_video_url_for_job(job)

    # 加载*已有的* L1 .ass 文件作为源字幕
    srt_url = ""
    if job.l1_output_file:
        # 注意: .name 包含了 'upload_to' 定义的完整相对路径
        correct_path = f"/media/{job.l1_output_file.name}"
        srt_url = f"{settings.LOCAL_MEDIA_URL_BASE}{correct_path}"

    job_id_param = job.id
    return_url_param = request.build_absolute_uri(
        reverse('admin:workflow_annotationproject_tab_l1', args=[job.project.id]))

    # 构建 vss-subeditor 的 URL
    subeditor_url = f"{settings.SUBEDITOR_PUBLIC_URL}?videoUrl={video_url}&srtUrl={srt_url}&jobId={job_id_param}&returnUrl={return_url_param}"

    return redirect(subeditor_url)


def start_l2l3_annotation_view(request, job_id):
    """
    (L2 Tab 按钮触发)
    处理“开始L2/L3语义标注”按钮点击的视图。
    1. 将任务状态变更为“处理中”。
    2. 重定向到 Label Studio 的具体任务页面。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L2L3_SEMANTIC)

    if job.status == 'PENDING':
        job.start_annotation()  # (PENDING -> PROCESSING)
        job.save()
        messages.success(request, f"语义标注任务 '{job.media.title}' 状态已更新为“处理中”。")

    if not job.project.label_studio_project_id or not job.label_studio_task_id:
        messages.error(request, "错误：项目或任务未成功在 Label Studio 中创建，无法跳转。")
        return redirect(reverse('admin:workflow_annotationproject_tab_l2', args=[job.project.id]))

    # 构建 Label Studio 任务 URL
    ls_project_id = job.project.label_studio_project_id
    ls_task_id = job.label_studio_task_id
    label_studio_task_url = f"{settings.LABEL_STUDIO_PUBLIC_URL}/projects/{ls_project_id}/data/?task={ls_task_id}"

    return redirect(label_studio_task_url)


# --- Project-Level Action Views ---
# 这些视图都是“触发器”，它们启动一个 Celery 异步任务
# 并立即重定向回 Admin 界面，同时显示一条成功消息。

def export_l2_output_view(request, project_id):
    """
    (L2 Tab 按钮触发)
    触发 'export_l2_output_task' 后台任务。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)
    export_l2_output_task.delay(project_id=str(project.id))
    messages.success(request, f"已启动为项目《{project.name}》导出L2产出物的后台任务。请稍后刷新查看结果。")
    return redirect(reverse('admin:workflow_annotationproject_tab_l2', args=[project.id]))


def generate_blueprint_view(request, project_id):
    """
    (L3 Tab 按钮触发)
    触发 'generate_narrative_blueprint_task' 后台任务。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)

    if not project.label_studio_export_file:
        messages.error(request, "错误：缺少L2产出物，无法生成蓝图。请先导出L2产出物。")
    else:
        generate_narrative_blueprint_task.delay(project_id=str(project.id))
        messages.success(request, f"已启动为项目《{project.name}》生成叙事蓝图的后台任务。")

    # (重定向到 L3 Tab)
    return redirect(reverse('admin:workflow_annotationproject_tab_l3', args=[project.id]))


def trigger_character_audit_view(request, project_id):
    """
    (L1 Tab 按钮触发)
    触发 'trigger_character_audit_task' 后台任务。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)
    trigger_character_audit_task.delay(project_id=str(project.id))
    messages.success(request, f"已启动为项目《{project.name}》生成角色审计报告的后台任务。请稍后刷新查看。")

    # 重定向回 L1 Tab
    return redirect(reverse('admin:workflow_annotationproject_tab_l1', args=[project.id]))


def trigger_local_metrics_view(request, project_id):
    """
    (L3 Tab 按钮触发)
    触发 'calculate_local_metrics_task' 后台任务。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)

    if not project.final_blueprint_file:
        messages.error(request, "错误：叙事蓝图 (JSON) 文件不存在，无法计算矩阵。")
        return redirect(reverse('admin:workflow_annotationproject_tab_l3', args=[project.id]))

    calculate_local_metrics_task.delay(project_id=str(project.id))
    messages.success(request, f"已启动为项目《{project.name}》计算本地角色矩阵的任务。请稍后刷新。")

    # 重定向回 L3 Tab
    return redirect(reverse('admin:workflow_annotationproject_tab_l3', args=[project.id]))