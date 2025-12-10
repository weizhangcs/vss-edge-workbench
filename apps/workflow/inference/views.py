# 文件路径: apps/workflow/inference/views.py
import json
import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from ..common.baseJob import BaseJob
from .forms import CharacterSelectionForm
from .projects import InferenceJob, InferenceProject
from .tasks import start_cloud_facts_task, start_rag_deployment_task

logger = logging.getLogger(__name__)


def trigger_cloud_facts_view(request, project_id):
    """
    (V3.2 适配 Audit Report)
    处理 "第一步：识别" 表单提交。
    """
    project = get_object_or_404(InferenceProject, id=project_id)
    if request.method != "POST":
        messages.error(request, "无效的请求方法。")
        return redirect(reverse("admin:workflow_inferenceproject_tab_1_facts", args=[project.id]))

    # --- 1. 读取上游数据 (Audit Report) ---
    audit_data = None
    annotation_proj = project.annotation_project

    try:
        # [适配] 改为读取 annotation_audit_report
        if annotation_proj and annotation_proj.annotation_audit_report:
            # 必须重新打开文件读取，因为是在 view 请求中
            with annotation_proj.annotation_audit_report.open("r") as f:
                audit_data = json.load(f)
        else:
            raise Exception("未找到审计报告 (Audit Report)。请先在标注项目中运行‘产出物审计’。")
    except Exception as e:
        logger.error(f"无法加载 Audit Report (项目: {project.id}): {e}", exc_info=True)
        messages.error(request, f"数据加载失败: {e}")
        return redirect(reverse("admin:workflow_inferenceproject_tab_1_facts", args=[project.id]))

    # --- 2. 验证表单 ---
    # 将加载好的 audit_data 传给 Form 做校验
    form = CharacterSelectionForm(request.POST, metrics_data=audit_data)

    if form.is_valid():
        selected_characters = form.cleaned_data["characters"]

        try:
            # 创建 Job
            new_job = InferenceJob.objects.create(
                project=project,
                job_type=InferenceJob.TYPE.FACTS,
                status=BaseJob.STATUS.PENDING,
                input_params={"characters": selected_characters},
            )

            # 触发 Task
            start_cloud_facts_task.delay(job_id=new_job.id)

            messages.success(request, f"已为 {len(selected_characters)} 个角色启动“角色属性识别”任务。")
        except Exception as e:
            logger.error(f"创建 FACTS Job 时失败: {e}", exc_info=True)
            messages.error(request, f"创建任务时出错: {e}")
    else:
        messages.error(request, f"表单提交无效: {form.errors.as_text()}")

    return redirect(reverse("admin:workflow_inferenceproject_tab_1_facts", args=[project.id]))


def trigger_rag_deployment_view(request, project_id):
    """
    (保持不变) 处理 "第二步：更新知识图谱" 按钮点击。
    """
    # ... (此函数逻辑无需修改，原样保留即可) ...
    project = get_object_or_404(InferenceProject, id=project_id)
    if request.method != "POST":
        messages.error(request, "无效的请求方法。")
        return redirect(reverse("admin:workflow_inferenceproject_tab_2_rag", args=[project.id]))

    latest_facts_job = (
        InferenceJob.objects.filter(
            project=project,
            job_type=InferenceJob.TYPE.FACTS,
            status=BaseJob.STATUS.COMPLETED,
            output_facts_file__isnull=False,
        )
        .order_by("-modified")
        .first()
    )

    if not latest_facts_job:
        messages.error(request, "找不到已完成的“角色属性识别”任务。请先在第一步中成功运行一个任务。")
        return redirect(reverse("admin:workflow_inferenceproject_tab_2_rag", args=[project.id]))

    try:
        new_job = InferenceJob.objects.create(
            project=project,
            job_type=InferenceJob.TYPE.RAG_DEPLOYMENT,
            status=BaseJob.STATUS.PENDING,
            input_params={"source_facts_job_id": latest_facts_job.id},
        )
        start_rag_deployment_task.delay(job_id=new_job.id)
        messages.success(request, "已创建“知识图谱部署”任务。")
    except Exception as e:
        logger.error(f"创建 RAG_DEPLOYMENT Job 时失败: {e}", exc_info=True)
        messages.error(request, f"创建任务时出错: {e}")

    return redirect(reverse("admin:workflow_inferenceproject_tab_2_rag", args=[project.id]))
