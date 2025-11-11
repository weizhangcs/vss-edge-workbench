# 文件路径: apps/workflow/inference/views.py
import json
import logging
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from .projects import InferenceProject, InferenceJob
from .forms import CharacterSelectionForm
# [!!! 步骤 1: 导入正确的 BaseJob 和 Tasks !!!]
from ..common.baseJob import BaseJob
from .tasks import (
    start_cloud_facts_task,
    start_rag_deployment_task
    # (移除了不再需要的 pipeline 和 metrics 任务)
)

logger = logging.getLogger(__name__)


def trigger_cloud_facts_view(request, project_id):
    """
    (已重构 V3.1)
    处理 "第一步：识别" 表单提交。

    职责：
    1. 验证 'CharacterSelectionForm'。
    2. 创建一个 'FACTS' 类型的 InferenceJob (状态: PENDING)。
    3. [!!! 修复 !!!] 立即触发 'start_cloud_facts_task'。
    4. 重定向回 Tab 1。
    """
    project = get_object_or_404(InferenceProject, id=project_id)
    if request.method != 'POST':
        messages.error(request, "无效的请求方法。")
        return redirect(reverse('admin:workflow_inferenceproject_tab_1_facts', args=[project.id]))

    # --- 验证表单 (保持不变) ---
    metrics_data = None
    try:
        if project.annotation_project.local_metrics_result_file:
            with project.annotation_project.local_metrics_result_file.open('r') as f:
                metrics_data = json.load(f)
        else:
            raise Exception("找不到 (本地) 角色矩阵文件。")
    except Exception as e:
        logger.error(f"无法加载 local_metrics_result_file (项目: {project.id}): {e}", exc_info=True)
        messages.error(request, f"无法加载角色矩阵文件: {e}")
        return redirect(reverse('admin:workflow_inferenceproject_tab_1_facts', args=[project.id]))

    form = CharacterSelectionForm(request.POST, metrics_data=metrics_data)

    if form.is_valid():
        selected_characters = form.cleaned_data['characters']

        try:
            # [!!! 步骤 2: 创建 Job !!!]
            new_job = InferenceJob.objects.create(
                project=project,
                job_type=InferenceJob.TYPE.FACTS,
                status=BaseJob.STATUS.PENDING,  # (任务将立即将其变为 PROCESSING)
                input_params={"characters": selected_characters}
            )

            # [!!! 步骤 3: 立即触发 Task !!!]
            start_cloud_facts_task.delay(job_id=new_job.id)

            messages.success(request, f"已为 {len(selected_characters)} 个角色启动“角色属性识别”任务。")
        except Exception as e:
            logger.error(f"创建 FACTS Job 时失败: {e}", exc_info=True)
            messages.error(request, f"创建任务时出错: {e}")
    else:
        messages.error(request, f"表单提交无效: {form.errors.as_text()}")

    return redirect(reverse('admin:workflow_inferenceproject_tab_1_facts', args=[project.id]))


def trigger_rag_deployment_view(request, project_id):
    """
    (已重构 V3.1)
    处理 "第二步：更新知识图谱" 按钮点击。
    """
    project = get_object_or_404(InferenceProject, id=project_id)
    if request.method != 'POST':
        messages.error(request, "无效的请求方法。")
        return redirect(reverse('admin:workflow_inferenceproject_tab_2_rag', args=[project.id]))

    # 1. 查找最新的、已完成的 FACTS 任务
    latest_facts_job = InferenceJob.objects.filter(
        project=project,
        job_type=InferenceJob.TYPE.FACTS,
        status=BaseJob.STATUS.COMPLETED,
        output_facts_file__isnull=False
    ).order_by('-modified').first()

    if not latest_facts_job:
        messages.error(request, "找不到已完成的“角色属性识别”任务。请先在第一步中成功运行一个任务。")
        return redirect(reverse('admin:workflow_inferenceproject_tab_2_rag', args=[project.id]))

    # 2. 创建 RAG Job 并立即触发
    try:
        new_job = InferenceJob.objects.create(
            project=project,
            job_type=InferenceJob.TYPE.RAG_DEPLOYMENT,
            status=BaseJob.STATUS.PENDING,
            input_params={"source_facts_job_id": latest_facts_job.id}
        )

        # [!!! 步骤 3: 立即触发 Task !!!]
        start_rag_deployment_task.delay(job_id=new_job.id)

        messages.success(request, "已创建“知识图谱部署”任务。")
    except Exception as e:
        logger.error(f"创建 RAG_DEPLOYMENT Job 时失败: {e}", exc_info=True)
        messages.error(request, f"创建任务时出错: {e}")

    return redirect(reverse('admin:workflow_inferenceproject_tab_2_rag', args=[project.id]))