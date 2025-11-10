# 文件路径: apps/workflow/inference/views.py
import json
import logging
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from .projects import InferenceProject
from apps.workflow.annotation.forms import CharacterSelectionForm
from .tasks import (
    start_cloud_pipeline_task,
    start_cloud_metrics_task,
    continue_cloud_facts_task
)

logger = logging.getLogger(__name__)


def trigger_cloud_pipeline_view(request, project_id):
    """
    (从 InferenceProjectAdmin 迁移而来)
    触发云端自动流水线。
    """
    project = get_object_or_404(InferenceProject, id=project_id)
    if not project.annotation_project.final_blueprint_file:
        messages.error(request, "错误：缺少 叙事蓝图(Blueprint) 产出物，无法启动。")
        return redirect(reverse('admin:workflow_inferenceproject_change', args=[project.id]))

    top_n = request.POST.get('top_n', 3)
    try:
        top_n = int(top_n)
    except ValueError:
        top_n = 3

    start_cloud_pipeline_task.delay(project_id=str(project.id))
    messages.success(request, f"成功启动“自动推理流水线 (Top {top_n})”任务。")
    return redirect(reverse('admin:workflow_inferenceproject_change', args=[project.id]))


def trigger_cloud_metrics_view(request, project_id):
    """
    (从 InferenceProjectAdmin 迁移而来)
    触发云端角色矩阵分析。
    """
    project = get_object_or_404(InferenceProject, id=project_id)
    if not project.annotation_project.final_blueprint_file:
        messages.error(request, "错误：缺少 叙事蓝图(Blueprint) 产出物，无法启动。")
        return redirect(reverse('admin:workflow_inferenceproject_change', args=[project.id]))

    start_cloud_metrics_task.delay(project_id=str(project.id))
    messages.success(request, "成功启动“分析角色矩阵”任务，请稍后刷新。")
    return redirect(reverse('admin:workflow_inferenceproject_change', args=[project.id]))


def trigger_cloud_facts_view(request, project_id):
    """
    (从 InferenceProjectAdmin 迁移而来)
    处理角色选择表单提交。
    """
    project = get_object_or_404(InferenceProject, id=project_id)
    if request.method != 'POST':
        messages.error(request, "无效的请求方法。")
        return redirect(reverse('admin:workflow_inferenceproject_change', args=[project.id]))

    metrics_data = None
    try:
        # 仍然从关联的 annotation_project 读取本地文件
        if project.annotation_project.local_metrics_result_file:
            with project.annotation_project.local_metrics_result_file.open('r') as f:
                metrics_data = json.load(f)
        else:
            messages.error(request, "致命错误：找不到用于验证的 (本地) 角色矩阵文件。")
            return redirect(reverse('admin:workflow_inferenceproject_change', args=[project.id]))
    except Exception as e:
        logger.error(f"无法加载或解析 local_metrics_result_file (项目: {project.id}): {e}", exc_info=True)
        messages.error(request, f"无法加载角色矩阵文件: {e}")
        return redirect(reverse('admin:workflow_inferenceproject_change', args=[project.id]))

    form = CharacterSelectionForm(request.POST, metrics_data=metrics_data)
    if form.is_valid():
        selected_characters = form.cleaned_data['characters']
        continue_cloud_facts_task.delay(project_id=str(project.id), characters_to_analyze=selected_characters)
        messages.success(request, f"已为 {len(selected_characters)} 个角色启动“识别角色属性”任务。")
    else:
        messages.error(request, f"表单提交无效: {form.errors.as_text()}")

    return redirect(reverse('admin:workflow_inferenceproject_change', args=[project.id]))