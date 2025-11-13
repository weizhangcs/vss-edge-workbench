# 文件路径: apps/workflow/creative/views.py

import logging
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from .projects import CreativeProject
from .tasks import start_narration_task, start_audio_task, start_edit_script_task

logger = logging.getLogger(__name__)


def trigger_narration_view(request, project_id):
    """
    (新) 步骤 1：触发“生成解说词”任务
    """
    project = get_object_or_404(CreativeProject, id=project_id)
    # (此处可添加权限和状态检查)
    if project.status == CreativeProject.STATUS.PENDING:
        start_narration_task.delay(project_id=str(project.id))
        messages.success(request, "步骤 1：生成解说词任务已启动。")
    else:
        messages.warning(request, f"项目状态为 {project.get_status_display()}，无法启动解说词任务。")

    return redirect(reverse('admin:workflow_creativeproject_tab_1_narration', args=[project_id]))


def trigger_audio_view(request, project_id):
    """
    (新) 步骤 2：触发“生成配音”任务 (待实现)
    """
    project = get_object_or_404(CreativeProject, id=project_id)
    if project.status == CreativeProject.STATUS.NARRATION_COMPLETED:
        start_audio_task.delay(project_id=str(project.id))  # (您未来的任务)
        messages.success(request, "步骤 2：生成配音任务已启动。")
    else:
        messages.warning(request, "必须先完成解说词才能生成配音。")

    return redirect(reverse('admin:workflow_creativeproject_tab_2_audio', args=[project_id]))


def trigger_edit_view(request, project_id):
    """
    (新) 步骤 3：触发“生成剪辑脚本”任务 (待实现)
    """
    project = get_object_or_404(CreativeProject, id=project_id)
    if project.status == CreativeProject.STATUS.AUDIO_COMPLETED:
        start_edit_script_task.delay(project_id=str(project.id))  # (您未来的任务)
        messages.success(request, "步骤 3：生成剪辑脚本任务已启动。")
    else:
        messages.warning(request, "必须先完成配音才能生成剪辑脚本。")

    return redirect(reverse('admin:workflow_creativeproject_tab_3_edit', args=[project_id]))