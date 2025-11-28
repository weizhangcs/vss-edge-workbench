# 文件路径: apps/workflow/creative/views.py

import logging
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from .projects import CreativeProject
from .tasks import start_narration_task, start_audio_task, start_edit_script_task, start_synthesis_task,start_localize_task
from .forms import NarrationConfigurationForm, DubbingConfigurationForm, LocalizeConfigurationForm

logger = logging.getLogger(__name__)


def trigger_narration_view(request, project_id):
    """
    步骤 1：触发“生成解说词”任务 (处理 POST 表单)
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    if request.method == 'POST':
        # 1. 绑定数据
        form = NarrationConfigurationForm(request.POST)

        if project.status != CreativeProject.STATUS.PENDING:
            messages.warning(request, f"项目状态不对，无法启动。")
            return redirect(reverse('admin:workflow_creativeproject_tab_1_narration', args=[project_id]))

        if form.is_valid():
            # 2. 提取清洗后的数据
            config_data = form.cleaned_data
            # 3. 传递给 Task
            start_narration_task.delay(project_id=str(project.id), config=config_data)
            messages.success(request, "已使用新配置启动解说词生成任务。")
        else:
            # 简单处理错误，实际生产中可能需要带错误重定向回页面
            messages.error(request, f"参数配置有误: {form.errors.as_text()}")

    return redirect(reverse('admin:workflow_creativeproject_tab_1_narration', args=[project_id]))


def trigger_localize_view(request, project_id):
    """
    [新增] 步骤 1.5：触发“本地化”任务
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    if request.method == 'POST':
        form = LocalizeConfigurationForm(request.POST)

        # 校验：必须有母本文件
        if not project.narration_script_file:
            messages.error(request, "未找到母本解说词，无法本地化。")
            return redirect(reverse('admin:workflow_creativeproject_tab_1_5_localize', args=[project_id]))

        if form.is_valid():
            config = form.cleaned_data
            start_localize_task.delay(project_id=str(project.id), config=config)
            messages.success(request, f"已启动本地化任务 (目标: {config.get('target_lang')})。")
        else:
            messages.error(request, f"参数错误: {form.errors.as_text()}")

    return redirect(reverse('admin:workflow_creativeproject_tab_1_5_localize', args=[project_id]))

def trigger_audio_view(request, project_id):
    """
    步骤 2：触发“生成配音”任务
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    if request.method == 'POST':
        form = DubbingConfigurationForm(request.POST)

        if project.status != CreativeProject.STATUS.NARRATION_COMPLETED:
            messages.warning(request, "请先完成解说词步骤。")
            return redirect(reverse('admin:workflow_creativeproject_tab_2_audio', args=[project_id]))

        if form.is_valid():
            config_data = form.cleaned_data
            start_audio_task.delay(project_id=str(project.id), config=config_data)
            messages.success(request, "已启动配音生成任务。")
        else:
            messages.error(request, f"参数错误: {form.errors.as_text()}")

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

def trigger_synthesis_view(request, project_id): # [新增]
    """
    (新) 步骤 4：触发“视频合成”任务
    """
    project = get_object_or_404(CreativeProject, id=project_id)
    if project.status == CreativeProject.STATUS.EDIT_COMPLETED:
        # 直接调用 task，在 task 中会执行同步的 SynthesisService.execute()
        start_synthesis_task.delay(project_id=str(project.id))
        messages.success(request, "步骤 4：视频合成任务已启动。")
    else:
        messages.warning(request, "必须先完成剪辑脚本才能进行视频合成。")

    return redirect(reverse('admin:workflow_creativeproject_tab_4_synthesis', args=[project_id]))