# 文件路径: apps/workflow/creative/views.py

import logging
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from .forms import DubbingConfigurationForm, LocalizeConfigurationForm, NarrationConfigurationForm
from .projects import CreativeProject
from .tasks import (
    start_audio_task,
    start_edit_script_task,
    start_localize_task,
    start_narration_task,
    start_synthesis_task,
)

logger = logging.getLogger(__name__)


def _sanitize_config(config: dict) -> dict:
    """
    将配置字典中的 Decimal 对象转换为 float，确保可被 JSON 序列化。
    用于处理 Django Form cleaned_data 中的 DecimalField。
    """
    new_config = config.copy()
    for k, v in new_config.items():
        if isinstance(v, Decimal):
            new_config[k] = float(v)
    return new_config


def trigger_narration_view(request, project_id):
    """
    步骤 1：触发“生成解说词”任务
    依赖：推理项目的蓝图文件
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    if request.method == "POST":
        # 1. 绑定数据
        form = NarrationConfigurationForm(request.POST)

        # [修改 1] 状态门禁：只拦截“正在运行”的状态，允许 PENDING/FAILED/COMPLETED(重跑)
        if project.status == CreativeProject.STATUS.NARRATION_RUNNING:
            messages.warning(request, "解说词生成任务正在进行中，请勿重复触发。")
            return redirect(reverse("admin:workflow_creativeproject_tab_1_narration", args=[project_id]))

        # [修改 2] 资产门禁：检查蓝图是否存在
        inf_proj = project.inference_project
        if not inf_proj or not inf_proj.annotation_project.final_blueprint_file:
            messages.error(request, "缺少前置资产：关联的推理项目未找到“最终叙事蓝图”。")
            return redirect(reverse("admin:workflow_creativeproject_tab_1_narration", args=[project_id]))

        if form.is_valid():
            # 2. 提取清洗后的数据
            raw_config = form.cleaned_data
            safe_config = _sanitize_config(raw_config)

            # 3. 传递给 Task
            start_narration_task.delay(project_id=str(project.id), config=safe_config)
            messages.success(request, "已使用新配置启动解说词生成任务。")
        else:
            # 简单处理错误，实际生产中可能需要带错误重定向回页面
            messages.error(request, f"参数配置有误: {form.errors.as_text()}")

    return redirect(reverse("admin:workflow_creativeproject_tab_1_narration", args=[project_id]))


def trigger_localize_view(request, project_id):
    """
    步骤 1.5：触发“本地化”任务
    依赖：解说词脚本 (narration_script_file)
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    if request.method == "POST":
        form = LocalizeConfigurationForm(request.POST)

        # [修改 1] 状态门禁
        if project.status == CreativeProject.STATUS.LOCALIZATION_RUNNING:
            messages.warning(request, "本地化翻译任务正在进行中。")
            return redirect(reverse("admin:workflow_creativeproject_tab_1_5_localize", args=[project_id]))

        # [修改 2] 资产门禁
        if not project.narration_script_file:
            messages.error(request, "缺少前置资产：未找到母本解说词，无法本地化。")
            return redirect(reverse("admin:workflow_creativeproject_tab_1_5_localize", args=[project_id]))

        if form.is_valid():
            raw_config = form.cleaned_data
            safe_config = _sanitize_config(raw_config)

            start_localize_task.delay(project_id=str(project.id), config=safe_config)
            messages.success(request, f"已启动本地化任务 (目标: {safe_config.get('target_lang')})。")
        else:
            messages.error(request, f"参数错误: {form.errors.as_text()}")

    return redirect(reverse("admin:workflow_creativeproject_tab_1_5_localize", args=[project_id]))


def trigger_audio_view(request, project_id):
    """
    步骤 2：触发“生成配音”任务
    依赖：解说词脚本 (narration_script_file) 或 译本 (localized_script_file)
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    if request.method == "POST":
        form = DubbingConfigurationForm(request.POST)

        # [修改 1] 状态门禁
        if project.status == CreativeProject.STATUS.AUDIO_RUNNING:
            messages.warning(request, "配音生成任务正在进行中。")
            return redirect(reverse("admin:workflow_creativeproject_tab_2_audio", args=[project_id]))

        # [修改 2] 资产门禁：只要有母本就可以进，具体是用母本还是译本，由 Task 内部检查 TODO: 这个逻辑要再次校验一下
        if not project.narration_script_file:
            messages.error(request, "缺少前置资产：请先生成解说词。")
            return redirect(reverse("admin:workflow_creativeproject_tab_2_audio", args=[project_id]))

        if form.is_valid():
            # [修复点] 使用 _sanitize_config 清洗数据
            raw_config = form.cleaned_data
            safe_config = _sanitize_config(raw_config)

            start_audio_task.delay(project_id=str(project.id), config=safe_config)
            messages.success(request, "已启动配音生成任务。")
        else:
            messages.error(request, f"参数错误: {form.errors.as_text()}")

    return redirect(reverse("admin:workflow_creativeproject_tab_2_audio", args=[project_id]))


def trigger_edit_view(request, project_id):
    """
    步骤 3：触发“生成剪辑脚本”任务
    依赖：配音脚本 (dubbing_script_file)
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    # [修改 1] 状态门禁
    if project.status == CreativeProject.STATUS.EDIT_RUNNING:
        messages.warning(request, "剪辑脚本生成任务正在进行中。")
        return redirect(reverse("admin:workflow_creativeproject_tab_3_edit", args=[project_id]))

    # [修改 2] 资产门禁
    if not project.dubbing_script_file:
        messages.error(request, "缺少前置资产：必须先完成配音（生成配音脚本）才能生成剪辑脚本。")
        return redirect(reverse("admin:workflow_creativeproject_tab_3_edit", args=[project_id]))

    start_edit_script_task.delay(project_id=str(project.id))
    messages.success(request, "已启动剪辑脚本生成任务。")

    return redirect(reverse("admin:workflow_creativeproject_tab_3_edit", args=[project_id]))


def trigger_synthesis_view(request, project_id):  # [新增]
    """
    步骤 4：触发“视频合成”任务
    依赖：剪辑脚本 (edit_script_file)
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    # [修改 1] 状态门禁
    if project.status == CreativeProject.STATUS.SYNTHESIS_RUNNING:
        messages.warning(request, "视频合成任务正在进行中。")
        return redirect(reverse("admin:workflow_creativeproject_tab_4_synthesis", args=[project_id]))

    # [修改 2] 资产门禁
    if not project.edit_script_file:
        messages.error(request, "缺少前置资产：必须先完成剪辑脚本才能进行视频合成。")
        return redirect(reverse("admin:workflow_creativeproject_tab_4_synthesis", args=[project_id]))

    # 直接调用 task，在 task 中会执行同步的 SynthesisService.execute()
    start_synthesis_task.delay(project_id=str(project.id))
    messages.success(request, "已启动视频合成任务。")

    return redirect(reverse("admin:workflow_creativeproject_tab_4_synthesis", args=[project_id]))
