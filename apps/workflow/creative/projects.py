# 文件路径: apps/workflow/creative/projects.py

from django.db import models
from django_fsm import FSMField, transition
from model_utils import Choices

from apps.workflow.common.baseProject import BaseProject
from apps.workflow.inference.projects import InferenceProject


def get_creative_output_upload_path(instance, filename):
    """为创作产出物生成动态路径"""
    # instance 是 CreativeProject
    return f'creative/{instance.id}/outputs/{filename}'


class CreativeProject(BaseProject):
    """
    (新 V2 - 遵从您的三步计划)
    L4 创作工作流项目。

    状态机：
    1. PENDING: 等待触发“生成解说词”
    2. NARRATION_RUNNING: “解说词”任务已发送到云端
    3. NARRATION_COMPLETED: “解说词”已下载，等待触发“生成配音”
    4. AUDIO_RUNNING: “配音”任务已发送到云端
    5. AUDIO_COMPLETED: “配音”文件已下载，等待触发“生成剪辑脚本”
    6. EDIT_RUNNING: “剪辑脚本”任务已发送到云端
    7. COMPLETED: “所有产出物已完成”
    8. FAILED: 任何一步失败
    """
    STATUS = Choices(
        ('PENDING', '待处理'),
        ('NARRATION_RUNNING', '解说词生成中'),
        ('NARRATION_COMPLETED', '解说词已完成'),
        ('AUDIO_RUNNING', '配音生成中'),
        ('AUDIO_COMPLETED', '配音已完成'),
        ('EDIT_RUNNING', '剪辑脚本生成中'),
        ('COMPLETED', '所有产出物已完成'),
        ('FAILED', '失败')
    )

    # 覆盖 BaseProject 的 status
    status = FSMField(
        max_length=30,
        choices=STATUS,
        default=STATUS.PENDING,
        verbose_name="创作项目状态"
    )

    inference_project = models.ForeignKey(
        InferenceProject,
        on_delete=models.PROTECT,  # 必须有推理项目才能创作
        related_name='creative_projects',
        verbose_name="关联的推理项目"
    )

    # --- 步骤 1 产出物 ---
    narration_script_file = models.FileField(
        upload_to=get_creative_output_upload_path,
        blank=True, null=True, verbose_name="解说词脚本 (JSON)"
    )

    # [!!!] --- 核心修正 --- [!!!]
    # --- 步骤 2 产出物 ---
    dubbing_script_file = models.FileField(
        upload_to=get_creative_output_upload_path,
        blank=True, null=True,
        verbose_name="配音脚本 (JSON)"  # <--- 修正了 verbose_name
    )

    # --- 步骤 3 产出物 ---
    edit_script_file = models.FileField(
        upload_to=get_creative_output_upload_path,
        blank=True, null=True, verbose_name="剪辑脚本 (JSON/EDL)"
    )

    # (省略 FSM transition 方法，它们将在 tasks.py 中被调用)

    def save(self, *args, **kwargs):
        """
        (修正版)
        重写 save 方法，自动从 InferenceProject 复制 asset。
        """

        # 检查 self.asset_id (ID字段) 而不是 self.asset (对象关系)
        if self.inference_project and not self.asset_id:
            # 直接从 self.inference_project (已由表单填充) 中获取 asset_id
            self.asset_id = self.inference_project.asset_id

        # 现在可以安全地调用父类的 save 方法
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "L4 创作项目"
        verbose_name_plural = "L4 创作项目"
        ordering = ['-modified']