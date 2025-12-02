# 文件路径: apps/workflow/creative/jobs.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from apps.workflow.common.baseJob import BaseJob

from .models import CreativeProject


class CreativeJob(BaseJob):
    """
    [Model] 创作子任务 (Creative Job)

    代表创作工作流中的一个原子操作步骤。
    通常对应一次异步的云端 API 调用或本地的合成任务。
    """

    # --- 1. Choices Definition ---
    TYPE = Choices(
        ("GENERATE_NARRATION", _("生成解说词")),
        ("LOCALIZE_NARRATION", _("本地化/翻译")),
        ("GENERATE_AUDIO", _("生成配音")),
        ("GENERATE_EDIT_SCRIPT", _("生成剪辑脚本")),
        ("SYNTHESIS", _("视频合成")),
    )

    # --- 2. Relationships ---
    project = models.ForeignKey(
        CreativeProject,
        on_delete=models.CASCADE,
        related_name="jobs",
        verbose_name=_("所属创作项目"),
    )

    # --- 3. Job Attributes ---
    job_type = models.CharField(
        max_length=30,
        choices=TYPE,
        verbose_name=_("任务类型"),
    )

    # --- 4. Inputs & Metadata ---
    input_params = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("输入参数"),
    )

    # --- 5. External Tracking ---
    cloud_task_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("云端任务 ID"),
    )

    # Note: 具体的产出物文件 (Artifacts) 通常存储在父级 Project 模型上，
    # Job 模型主要负责追踪执行过程和状态。

    class Meta:
        verbose_name = _("子任务状态列表")
        verbose_name_plural = _("子任务状态列表")
        ordering = ["-created"]
