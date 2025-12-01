# 文件路径: apps/workflow/creative/views.py

import json
import logging
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
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
    [工具函数] 将配置字典中的 Decimal 对象转换为 float，确保可被 JSON 序列化。
    """
    new_config = config.copy()
    for k, v in new_config.items():
        if isinstance(v, Decimal):
            new_config[k] = float(v)
    return new_config


def _update_project_config(project: CreativeProject, section: str, config: dict):
    """
    [工具函数] 增量更新 project.auto_config 并保存到数据库。
    结构示例:
    {
        "narration": { ... },
        "localize": { ... },
        "audio": { ... }
    }
    """
    # 1. 获取当前配置，如果为 None 则初始化为空字典
    current_config = project.auto_config or {}

    # 2. 防御性检查：确保是字典类型
    if not isinstance(current_config, dict):
        current_config = {}

    # 3. 更新特定 section
    current_config[section] = config

    # 4. 赋值并保存 (仅更新相关字段，避免竞态)
    project.auto_config = current_config
    project.save(update_fields=["auto_config", "modified"])


def launch_factory_view(request, project_id):
    """
    [Factory 入口] 参数工厂启动器
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    # 1. 构建资产清单 (告诉前端哪些步骤已有产出物)
    assets = {
        "narration": {
            "exists": bool(project.narration_script_file),
            "name": project.narration_script_file.name if project.narration_script_file else None,
        },
        "localize": {
            "exists": bool(project.localized_script_file),
            "name": project.localized_script_file.name if project.localized_script_file else None,
        },
        "audio": {
            "exists": bool(project.dubbing_script_file),
            "name": project.dubbing_script_file.name if project.dubbing_script_file else None,
        },
        # edit 步骤通常没有独立的可复用输入源，暂略
    }

    # 2. 获取初始配置 (复用 auto_config)
    initial_config = project.auto_config if project.auto_config else {}

    # 3. 组装上下文
    server_data = {
        "project_id": str(project.id),
        "project_name": project.name,
        "assets": assets,
        "initial_config": initial_config,
    }

    context = {
        # 这里的 admin.site.each_context 需要在 urls.py 或调用处确保 request 正确
        # 为简化，这里假设 request 包含必要信息，或直接使用简单的 context
        "title": f"参数构建工厂 - {project.name}",
        "server_data_json": json.dumps(server_data, ensure_ascii=False),
    }

    # 注意：需要在 admin.py 中正确引用此视图，通常不需要 admin.site.each_context 也能渲染
    return render(request, "admin/workflow/creative/factory_mock.html", context)


def trigger_narration_view(request, project_id):
    """
    步骤 1：触发“生成解说词”任务
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    if request.method == "POST":
        form = NarrationConfigurationForm(request.POST)

        if project.status == CreativeProject.STATUS.NARRATION_RUNNING:
            messages.warning(request, "解说词生成任务正在进行中，请勿重复触发。")
            return redirect(reverse("admin:workflow_creativeproject_tab_1_narration", args=[project_id]))

        inf_proj = project.inference_project
        if not inf_proj or not inf_proj.annotation_project.final_blueprint_file:
            messages.error(request, "缺少前置资产：关联的推理项目未找到“最终叙事蓝图”。")
            return redirect(reverse("admin:workflow_creativeproject_tab_1_narration", args=[project_id]))

        if form.is_valid():
            raw_config = form.cleaned_data
            safe_config = _sanitize_config(raw_config)

            # [核心修改] 持久化保存参数
            _update_project_config(project, "narration", safe_config)

            start_narration_task.delay(project_id=str(project.id), config=safe_config)
            messages.success(request, "已启动解说词生成任务。")
        else:
            messages.error(request, f"参数配置有误: {form.errors.as_text()}")

    return redirect(reverse("admin:workflow_creativeproject_tab_1_narration", args=[project_id]))


def trigger_localize_view(request, project_id):
    """
    步骤 1.5：触发“本地化”任务
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    if request.method == "POST":
        form = LocalizeConfigurationForm(request.POST)

        if project.status == CreativeProject.STATUS.LOCALIZATION_RUNNING:
            messages.warning(request, "本地化翻译任务正在进行中。")
            return redirect(reverse("admin:workflow_creativeproject_tab_1_5_localize", args=[project_id]))

        if not project.narration_script_file:
            messages.error(request, "缺少前置资产：未找到母本解说词，无法本地化。")
            return redirect(reverse("admin:workflow_creativeproject_tab_1_5_localize", args=[project_id]))

        if form.is_valid():
            raw_config = form.cleaned_data
            safe_config = _sanitize_config(raw_config)

            # [核心修改] 持久化保存参数
            _update_project_config(project, "localize", safe_config)

            start_localize_task.delay(project_id=str(project.id), config=safe_config)
            messages.success(request, f"已启动本地化任务 (目标: {safe_config.get('target_lang')})。")
        else:
            messages.error(request, f"参数错误: {form.errors.as_text()}")

    return redirect(reverse("admin:workflow_creativeproject_tab_1_5_localize", args=[project_id]))


def trigger_audio_view(request, project_id):
    """
    步骤 2：触发“生成配音”任务
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    if request.method == "POST":
        form = DubbingConfigurationForm(request.POST)

        if project.status == CreativeProject.STATUS.AUDIO_RUNNING:
            messages.warning(request, "配音生成任务正在进行中。")
            return redirect(reverse("admin:workflow_creativeproject_tab_2_audio", args=[project_id]))

        if not project.narration_script_file:
            messages.error(request, "缺少前置资产：请先生成解说词。")
            return redirect(reverse("admin:workflow_creativeproject_tab_2_audio", args=[project_id]))

        if form.is_valid():
            raw_config = form.cleaned_data
            safe_config = _sanitize_config(raw_config)

            # [核心修改] 持久化保存参数
            _update_project_config(project, "audio", safe_config)

            start_audio_task.delay(project_id=str(project.id), config=safe_config)
            messages.success(request, "已启动配音生成任务。")
        else:
            messages.error(request, f"参数错误: {form.errors.as_text()}")

    return redirect(reverse("admin:workflow_creativeproject_tab_2_audio", args=[project_id]))


def trigger_edit_view(request, project_id):
    """
    步骤 3：触发“生成剪辑脚本”任务
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    if project.status == CreativeProject.STATUS.EDIT_RUNNING:
        messages.warning(request, "剪辑脚本生成任务正在进行中。")
        return redirect(reverse("admin:workflow_creativeproject_tab_3_edit", args=[project_id]))

    if not project.dubbing_script_file:
        messages.error(request, "缺少前置资产：必须先完成配音（生成配音脚本）才能生成剪辑脚本。")
        return redirect(reverse("admin:workflow_creativeproject_tab_3_edit", args=[project_id]))

    start_edit_script_task.delay(project_id=str(project.id))
    messages.success(request, "已启动剪辑脚本生成任务。")

    return redirect(reverse("admin:workflow_creativeproject_tab_3_edit", args=[project_id]))


def trigger_synthesis_view(request, project_id):
    """
    步骤 4：触发“视频合成”任务
    """
    project = get_object_or_404(CreativeProject, id=project_id)

    if project.status == CreativeProject.STATUS.SYNTHESIS_RUNNING:
        messages.warning(request, "视频合成任务正在进行中。")
        return redirect(reverse("admin:workflow_creativeproject_tab_4_synthesis", args=[project_id]))

    if not project.edit_script_file:
        messages.error(request, "缺少前置资产：必须先完成剪辑脚本才能进行视频合成。")
        return redirect(reverse("admin:workflow_creativeproject_tab_4_synthesis", args=[project_id]))

    start_synthesis_task.delay(project_id=str(project.id))
    messages.success(request, "已启动视频合成任务。")

    return redirect(reverse("admin:workflow_creativeproject_tab_4_synthesis", args=[project_id]))
