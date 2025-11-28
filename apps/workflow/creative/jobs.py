# 文件路径: apps/workflow/creative/jobs.py

from django.db import models
from model_utils import Choices
from apps.workflow.common.baseJob import BaseJob
from .projects import CreativeProject


class CreativeJob(BaseJob):
    """
    (新 V2)
    L4 创作子任务。
    对应您计划中的三个独立云端 API 调用。
    """
    TYPE = Choices(
        ('GENERATE_NARRATION', '生成解说词'),  # 您的步骤 1
        ('LOCALIZE_NARRATION', '本地化/翻译'),
        ('GENERATE_AUDIO', '生成配音'),  # 您的步骤 2
        ('GENERATE_EDIT_SCRIPT', '生成剪辑脚本'),  # 您的步骤 3
        ('SYNTHESIS', '视频合成')
    )

    project = models.ForeignKey(
        CreativeProject,
        on_delete=models.CASCADE,
        related_name='jobs',
        verbose_name="所属创作项目"
    )

    job_type = models.CharField(
        max_length=30,
        choices=TYPE,
        verbose_name="任务类型"
    )

    # --- 输入 ---
    input_params = models.JSONField(blank=True, null=True, verbose_name="输入参数")

    # --- 外部跟踪 ---
    cloud_task_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="云端任务 ID")

    # (产出物存储在父级 Project 上)

    class Meta:
        verbose_name = "L4 创作子任务"
        verbose_name_plural = "L4 创作子任务"
        ordering = ['-created']