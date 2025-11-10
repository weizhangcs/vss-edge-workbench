# 文件路径: apps/workflow/annotation/views.py

import json
import logging
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.files.base import ContentFile
from django.contrib import admin

from ..models import AnnotationJob, AnnotationProject, TranscodingJob
from .tasks import (
    trigger_character_audit_task,
    generate_narrative_blueprint_task,
    export_l2_output_task,
    start_cloud_pipeline_task,
    start_cloud_metrics_task,
    continue_cloud_facts_task,
    calculate_local_metrics_task
)
from .forms import CharacterSelectionForm  #

logger = logging.getLogger(__name__)


def get_video_url_for_job(job: AnnotationJob) -> str:
    project = job.project
    media_item = job.media

    video_url = None
    if project.source_encoding_profile:
        transcoding_job = TranscodingJob.objects.filter(
            media=media_item,
            profile=project.source_encoding_profile,
            status=TranscodingJob.STATUS.COMPLETED
        ).order_by('-modified').first()

        if transcoding_job and transcoding_job.output_url:
            video_url = transcoding_job.output_url

    if not video_url:
        #
        if media_item.source_video:
            video_url = f"{settings.LOCAL_MEDIA_URL_BASE}{media_item.source_video.url}"
        else:
            #
            video_url = ""

    return video_url


def start_l1_annotation_view(request, job_id):
    """
    处理“开始L1字幕标注”按钮点击的视图。
    1. 将任务状态变更为“处理中”。
    2. 重定向到 vss-subeditor 外部工具。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L1_SUBEDITING)

    if job.status == 'PENDING':
        job.start_annotation()  #
        job.save()
        messages.success(request, f"字幕任务 '{job.media.title}' 状态已更新为“处理中”。")

    # --- 核心修改: 使用辅助函数获取 URL ---
    video_url = get_video_url_for_job(job)

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

        job.complete_annotation()  #
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

    # --- 核心修改: 使用辅助函数获取 URL ---
    video_url = get_video_url_for_job(job)

    srt_url = ""
    if job.l1_output_file:
        #
        correct_path = f"/media/{job.l1_output_file.name}"
        srt_url = f"{settings.LOCAL_MEDIA_URL_BASE}{correct_path}"

    job_id_param = job.id
    return_url_param = request.build_absolute_uri(
        reverse('admin:workflow_annotationproject_change', args=[job.project.id]))

    subeditor_url = f"{settings.SUBEDITOR_PUBLIC_URL}?videoUrl={video_url}&srtUrl={srt_url}&jobId={job_id_param}&returnUrl={return_url_param}"

    return redirect(subeditor_url)


def start_l2l3_annotation_view(request, job_id):
    """
    处理“开始L2/L3语义标注”按钮点击的视图。
    1. 将任务状态变更为“处理中”。
    2. 重定向到 Label Studio 的具体任务页面。
    """
    job = get_object_or_404(AnnotationJob, id=job_id, job_type=AnnotationJob.TYPE.L2L3_SEMANTIC)

    if job.status == 'PENDING':
        job.start_annotation()  #
        job.save()
        messages.success(request, f"语义标注任务 '{job.media.title}' 状态已更新为“处理中”。")

    if not job.project.label_studio_project_id or not job.label_studio_task_id:
        messages.error(request, "错误：项目或任务未成功在 Label Studio 中创建，无法跳转。")
        return redirect(reverse('admin:workflow_annotationproject_change', args=[job.project.id]))

    ls_project_id = job.project.label_studio_project_id
    ls_task_id = job.label_studio_task_id
    label_studio_task_url = f"{settings.LABEL_STUDIO_PUBLIC_URL}/projects/{ls_project_id}/data/?task={ls_task_id}"

    return redirect(label_studio_task_url)


def export_l2_output_view(request, project_id):
    """
    触发一个后台任务，从 Label Studio 导出 L2 产出物。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)

    export_l2_output_task.delay(project_id=str(project.id))

    messages.success(request, f"已启动为项目《{project.name}》导出L2产出物的后台任务。请稍后刷新查看结果。")

    return redirect(reverse('admin:workflow_annotationproject_change', args=[project.id]))


def generate_blueprint_view(request, project_id):
    """
    触发一个后台任务，为项目生成最终的叙事蓝图。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)

    if not project.label_studio_export_file:
        messages.error(request, "错误：缺少L2产出物，无法生成蓝图。请先导出L2产出物。")
    else:
        generate_narrative_blueprint_task.delay(project_id=str(project.id))
        messages.success(request, f"已启动为项目《{project.name}》生成叙事蓝图的后台任务。")

    return redirect(reverse('admin:workflow_annotationproject_change', args=[project.id]))


# =============================================================================
# ---
# =============================================================================

def reasoning_workflow_view(request, project_id):
    """

    """
    project = get_object_or_404(AnnotationProject, pk=project_id)

    context = {
        **admin.site.each_context(request),  #
        "opts": AnnotationProject._meta,
        "original": project,
        "title": f"云端推理工作流: {project.name}",
        "has_view_permission": True,
        "has_change_permission": True,  #
        "character_selection_form": None,
    }

    #
    if project.cloud_reasoning_status == 'WAITING_FOR_SELECTION':
        metrics_data = None
        try:
            if project.local_metrics_result_file and project.local_metrics_result_file.path:
                with project.local_metrics_result_file.open('r') as f:
                    metrics_data = json.load(f)
            else:
                messages.error(request, "状态错误：项目处于等待选择状态，但找不到“角色矩阵”产出文件。")
        except Exception as e:
            logger.error(f"无法加载或解析 metrics_result_file (项目: {project.id}): {e}", exc_info=True)
            messages.error(request, f"无法加载角色矩阵文件: {e}")

        if metrics_data:
            #
            context['character_selection_form'] = CharacterSelectionForm(metrics_data=metrics_data)

    return render(request, 'admin/workflow/project/annotation/reasoning_workflow.html', context)


def trigger_cloud_pipeline_view(request, project_id):
    """

    """
    project = get_object_or_404(AnnotationProject, id=project_id)

    if not project.final_blueprint_file:
        messages.error(request, "错误：缺少 叙事蓝图(Blueprint) 产出物，无法启动。")
        return redirect(reverse('workflow:annotation_project_reasoning_workflow', args=[project.id]))

    #
    top_n = request.POST.get('top_n', 3)
    try:
        top_n = int(top_n)
    except ValueError:
        top_n = 3

    start_cloud_pipeline_task.delay(project_id=str(project.id), top_n=top_n)
    messages.success(request, f"成功启动“自动推理流水线 (Top {top_n})”任务。")

    return redirect(reverse('workflow:annotation_project_reasoning_workflow', args=[project.id]))


def trigger_cloud_metrics_view(request, project_id):
    """

    """
    project = get_object_or_404(AnnotationProject, id=project_id)

    if not project.final_blueprint_file:
        messages.error(request, "错误：缺少 叙事蓝图(Blueprint) 产出物，无法启动。")
        return redirect(reverse('workflow:annotation_project_reasoning_workflow', args=[project.id]))

    start_cloud_metrics_task.delay(project_id=str(project.id))
    messages.success(request, "成功启动“分析角色矩阵”任务，请稍后刷新。")

    return redirect(reverse('workflow:annotation_project_reasoning_workflow', args=[project.id]))


def trigger_cloud_facts_view(request, project_id):
    """
    处理来自 "reasoning_workflow" 页面的角色选择表单提交。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)  #

    if request.method != 'POST':  #
        messages.error(request, "无效的请求方法。")
        return redirect(reverse('workflow:annotation_project_reasoning_workflow', args=[project.id]))

    # --- [!!! 修复开始 !!!] ---

    # 1. 必须在验证表单前加载 metrics_data，以填充 'choices'
    #    这部分逻辑与 reasoning_workflow_view 中的逻辑一致
    metrics_data = None
    try:
        if project.local_metrics_result_file and project.local_metrics_result_file.path:
            with project.local_metrics_result_file.open('r') as f:
                metrics_data = json.load(f)
        else:
            # 如果文件丢失，这是个严重错误
            messages.error(request, "致命错误：找不到用于验证的 角色矩阵(metrics) 文件。")
            return redirect(reverse('workflow:annotation_project_reasoning_workflow', args=[project.id]))
    except Exception as e:
        logger.error(f"无法加载或解析 metrics_result_file (项目: {project.id}): {e}", exc_info=True)
        messages.error(request, f"无法加载角色矩阵文件: {e}")
        return redirect(reverse('workflow:annotation_project_reasoning_workflow', args=[project.id]))

    # 2. 将 metrics_data 和 request.POST 一起传入表单构造函数
    form = CharacterSelectionForm(request.POST, metrics_data=metrics_data)  #

    # --- [!!! 修复结束 !!!] ---

    if form.is_valid():  #
        selected_characters = form.cleaned_data['characters']
        continue_cloud_facts_task.delay(project_id=str(project.id), characters_to_analyze=selected_characters)  #
        messages.success(request, f"已为 {len(selected_characters)} 个角色启动“识别角色属性”任务。")
    else:
        # 这个错误消息现在会正确显示在页面上
        messages.error(request, f"表单提交无效: {form.errors.as_text()}")  #

    return redirect(reverse('workflow:annotation_project_reasoning_workflow', args=[project.id]))

def trigger_character_audit_view(request, project_id):
    """
    (新) 触发 L1 角色名和指标审计的后台任务。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)

    # 启动 Celery 任务
    trigger_character_audit_task.delay(project_id=str(project.id))

    messages.success(request, f"已启动为项目《{project.name}》生成角色审计报告的后台任务。请稍后刷新查看。")

    # 重定向回 L1 Tab
    return redirect(reverse('admin:workflow_annotationproject_tab_l1', args=[project.id]))

def trigger_local_metrics_view(request, project_id):
    """
    (新) 触发本地角色矩阵计算的后台任务。
    """
    project = get_object_or_404(AnnotationProject, id=project_id)

    if not project.final_blueprint_file:
        messages.error(request, "错误：叙事蓝图 (JSON) 文件不存在，无法计算矩阵。")
        return redirect(reverse('admin:workflow_annotationproject_tab_l3', args=[project.id]))

    # 启动 Celery 任务
    calculate_local_metrics_task.delay(project_id=str(project.id))

    messages.success(request, f"已启动为项目《{project.name}》计算本地角色矩阵的任务。请稍后刷新。")

    # 重定向回 L3 Tab
    return redirect(reverse('admin:workflow_annotationproject_tab_l3', args=[project.id]))