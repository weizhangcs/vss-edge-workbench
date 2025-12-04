# 文件路径: apps/workflow/annotation/views.py

import logging

from django.conf import settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from ..models import AnnotationJob, AnnotationProject
from .tasks import (
    calculate_local_metrics_task,
    export_l2_output_task,
    generate_narrative_blueprint_task,
    trigger_character_audit_task,
)

logger = logging.getLogger(__name__)


# --- 辅助函数：构建完整媒体 URL ---
def _build_full_media_url(relative_url):
    """
    将相对路径 (/media/...) 转换为绝对 URL (http://IP:9999/media/...)
    """
    if not relative_url:
        return ""
    if relative_url.startswith("http"):
        return relative_url

    # 获取 .env 中配置的媒体服务基地址 (例如 http://10.0.0.145:9999)
    base_url = settings.LOCAL_MEDIA_URL_BASE.rstrip("/")
    return f"{base_url}{relative_url}"


def start_l1_annotation_view(request, job_id):
    """
    (L1 Tab 按钮触发)
    处理“开始L1字幕标注”按钮点击的视图。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    if job.status == "PENDING":
        job.start_annotation()  # (PENDING -> PROCESSING)
        job.save()
        messages.success(request, f"字幕任务 '{job.media.title}' 状态已更新为“处理中”。")

    # 智能获取视频 URL (CDN 或本地)
    video_url = job.media.get_best_playback_url(encoding_profile=job.project.source_encoding_profile)

    # 2. 获取源字幕绝对路径
    raw_srt_url = job.media.source_subtitle.url if job.media.source_subtitle else ""
    srt_url = _build_full_media_url(raw_srt_url)

    logger.debug(f"DEBUG URL: FINAL URLs prepared for Subeditor: video_url={video_url}, srt_url={srt_url}")

    job_id_param = job.id
    # 构建一个回调 URL，以便 Subeditor 完成后能返回 L1 Tab
    return_url_param = request.build_absolute_uri(
        reverse("admin:workflow_annotationproject_tab_l1", args=[job.project.id])
    )

    # 构建 vss-subeditor 的 URL
    subeditor_url = f"{settings.SUBEDITOR_PUBLIC_URL}?videoUrl={video_url}&srtUrl={srt_url}&jobId={job_id_param}&returnUrl={return_url_param}"  # noqa: E501

    return redirect(subeditor_url)


def revise_l1_annotation_view(request, job_id):
    """
    (L1 Tab 按钮触发)
    处理“修订L1字幕”按钮点击的视图。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    if job.status == "COMPLETED":
        job.revise()  # (COMPLETED -> REVISING, 自动备份在 job.revise() 中处理)
        job.save()
        messages.success(request, f"字幕任务 '{job.media.title}' 已重新打开进行修订。")

    # 智能获取视频 URL (CDN 或本地)
    video_url = job.media.get_best_playback_url(encoding_profile=job.project.source_encoding_profile)

    raw_srt_url = job.l1_output_file.url if job.l1_output_file else ""
    srt_url = _build_full_media_url(raw_srt_url)

    job_id_param = job.id
    return_url_param = request.build_absolute_uri(
        reverse("admin:workflow_annotationproject_tab_l1", args=[job.project.id])
    )

    # 构建 vss-subeditor 的 URL
    subeditor_url = f"{settings.SUBEDITOR_PUBLIC_URL}?videoUrl={video_url}&srtUrl={srt_url}&jobId={job_id_param}&returnUrl={return_url_param}"  # noqa: E501

    return redirect(subeditor_url)


@csrf_exempt
def save_l1_output_view(request, job_id):
    """
    (外部 Webhook)
    接收来自 vss-subeditor 的 POST 回调，保存L1产出物 (.ass 文件)。
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Only POST method is allowed"}, status=405)

    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    try:
        # 1. 从 request.body 获取 .ass 内容
        ass_content = request.body.decode("utf-8")

        if not ass_content:
            return JsonResponse({"status": "error", "message": "No content received"}, status=400)

        # 2. 保存文件到 L1 产出物字段
        file_name = f"{job.media.title}_l1.ass"
        job.l1_output_file.save(file_name, ContentFile(ass_content.encode("utf-8")), save=False)

        # 3. 转换状态为 "COMPLETED"
        job.complete_annotation()
        job.save()

        return JsonResponse({"status": "success", "message": "L1 output saved and job marked as complete."})

    except Exception as e:
        # 4. 如果失败, 转换状态为 "FAILED" (或 "ERROR")
        job.fail()
        job.save()
        logger.error(f"保存L1产出物时出错 (Job ID: {job.id}): {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def start_l2l3_annotation_view(request, job_id):
    """
    (L2 Tab 按钮触发)
    处理“开始L2/L3语义标注”按钮点击的视图。
    1. 将任务状态变更为“处理中”。
    2. 重定向到 Label Studio 的具体任务页面。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L2L3_SEMANTIC)

    if job.status == "PENDING":
        job.start_annotation()  # (PENDING -> PROCESSING)
        job.save()
        messages.success(request, f"语义标注任务 '{job.media.title}' 状态已更新为“处理中”。")

    if not job.project.label_studio_project_id or not job.label_studio_task_id:
        messages.error(request, "错误：项目或任务未成功在 Label Studio 中创建，无法跳转。")
        return redirect(reverse("admin:workflow_annotationproject_tab_l2", args=[job.project.id]))

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
    return redirect(reverse("admin:workflow_annotationproject_tab_l2", args=[project.id]))


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
    return redirect(reverse("admin:workflow_annotationproject_tab_l3", args=[project.id]))


def trigger_character_audit_view(request, project_id):
    """
    (L1 Tab 按钮触发)
    触发 'trigger_character_audit_task' 后台任务。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)
    trigger_character_audit_task.delay(project_id=str(project.id))
    messages.success(request, f"已启动为项目《{project.name}》生成角色审计报告的后台任务。请稍后刷新查看。")

    # 重定向回 L1 Tab
    return redirect(reverse("admin:workflow_annotationproject_tab_l1", args=[project.id]))


def trigger_local_metrics_view(request, project_id):
    """
    (L3 Tab 按钮触发)
    触发 'calculate_local_metrics_task' 后台任务。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)

    if not project.final_blueprint_file:
        messages.error(request, "错误：叙事蓝图 (JSON) 文件不存在，无法计算矩阵。")
        return redirect(reverse("admin:workflow_annotationproject_tab_l3", args=[project.id]))

    calculate_local_metrics_task.delay(project_id=str(project.id))
    messages.success(request, f"已启动为项目《{project.name}》计算本地角色矩阵的任务。请稍后刷新。")

    # 重定向回 L3 Tab
    return redirect(reverse("admin:workflow_annotationproject_tab_l3", args=[project.id]))
