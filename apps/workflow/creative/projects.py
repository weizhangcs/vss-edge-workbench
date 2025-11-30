# 文件路径: apps/workflow/creative/projects.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_fsm import FSMField
from model_utils import Choices
from model_utils.models import TimeStampedModel

from apps.workflow.common.baseProject import BaseProject
from apps.workflow.inference.projects import InferenceProject


def get_creative_output_upload_path(instance: "CreativeProject", filename: str) -> str:
    """
    [Callback] 为 FileField 生成动态上传路径。
    Format: creative/<project_uuid>/outputs/<filename>
    """
    return f"creative/{instance.id}/outputs/{filename}"


class CreativeBatch(TimeStampedModel):
    """
    [Model] 批量创作批次

    用于管理和监控由编排器 (Orchestrator) 批量生成的创作项目。
    记录了批次的生成策略和总数量。
    """

    inference_project = models.ForeignKey(InferenceProject, on_delete=models.PROTECT, verbose_name=_("源推理项目"))

    total_count = models.PositiveIntegerField(verbose_name=_("计划生成数量"))

    # 存储生成时的配置快照，用于追溯 (e.g. {"style": "random", "count": 10})
    batch_strategy = models.JSONField(default=dict, verbose_name=_("编排策略快照"))

    def __str__(self):
        return f"Batch {self.id} - {self.inference_project.name} ({self.total_count} items)"

    class Meta:
        verbose_name = _("批量创作任务")
        verbose_name_plural = _("批量创作任务")
        ordering = ["-created"]


class CreativeProject(BaseProject):
    """
    [Model] L4 创作工作流项目 (Creative Project)

    管理视频二创的全生命周期，包括解说词生成、配音、脚本剪辑和最终合成。

    State Machine (FSM):
        1. PENDING: 初始状态，等待触发
        2. NARRATION_*: 步骤1 (解说词)
        3. AUDIO_*: 步骤2 (配音)
        4. EDIT_*: 步骤3 (剪辑脚本)
        5. SYNTHESIS_*: 步骤4 (视频合成)
        6. COMPLETED: 全流程结束
    """

    # --- 1. State Definition ---
    # 注意：key (如 'PENDING') 保持英文不变，label 使用 _() 标记翻译
    STATUS = Choices(
        ("PENDING", _("排队待处理")),
        # Step 1: Narration
        ("NARRATION_RUNNING", _("解说词生成中")),
        ("NARRATION_COMPLETED", _("解说词已完成")),
        # Step 2: Localization
        ("LOCALIZATION_RUNNING", _("翻译中")),
        ("LOCALIZATION_COMPLETED", _("翻译已完成")),
        # Step 3: Audio/Dubbing
        ("AUDIO_RUNNING", _("配音生成中")),
        ("AUDIO_COMPLETED", _("配音已完成")),
        # Step 4: Edit Script
        ("EDIT_RUNNING", _("剪辑脚本生成中")),
        ("EDIT_COMPLETED", _("剪辑脚本已完成")),
        # Step 5: Synthesis
        ("SYNTHESIS_RUNNING", _("合成中")),
        # Final States
        ("COMPLETED", _("所有产出物已完成")),
        ("FAILED", _("失败")),
    )

    status = FSMField(max_length=30, choices=STATUS, default=STATUS.PENDING, verbose_name=_("创作项目状态"))

    # --- 2. Relationships ---
    inference_project = models.ForeignKey(
        InferenceProject,
        on_delete=models.PROTECT,
        related_name="creative_projects",
        verbose_name=_("关联的推理项目"),
    )

    batch = models.ForeignKey(
        CreativeBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects", verbose_name=_("所属批次")
    )

    # --- 3. Configuration ---
    # 自动化全流程配置 (Auto-Pilot)
    # 若存在，任务完成后将自动读取此配置触发下一步。
    auto_config = models.JSONField(null=True, blank=True, verbose_name=_("自动化全流程配置 (Auto-Pilot)"))

    # --- 4. Outputs (Artifacts) ---

    # Step 1 Output
    narration_script_file = models.FileField(
        upload_to=get_creative_output_upload_path, blank=True, null=True, verbose_name=_("解说词脚本 (JSON)")
    )

    # Step 1.5 Output (Localization)
    localized_script_file = models.FileField(
        upload_to=get_creative_output_upload_path, blank=True, null=True, verbose_name=_("本地化/翻译脚本 (JSON)")
    )

    # Step 2 Output
    dubbing_script_file = models.FileField(
        upload_to=get_creative_output_upload_path,
        blank=True,
        null=True,
        verbose_name=_("配音脚本 (JSON)"),
    )

    # Step 3 Output
    edit_script_file = models.FileField(
        upload_to=get_creative_output_upload_path, blank=True, null=True, verbose_name=_("剪辑脚本 (JSON/EDL)")
    )

    # Step 4 Output
    final_video_file = models.FileField(
        upload_to=get_creative_output_upload_path, blank=True, null=True, verbose_name=_("最终合成视频 (MP4)")
    )

    def save(self, *args, **kwargs):
        """
        Override: 保存模型。

        Logic:
            自动数据补全：如果未显式指定 `asset`，则从关联的 `inference_project` 继承 `asset_id`。
            这确保了 CreativeProject 总是链接到正确的顶层 Asset。
        """
        # 使用 asset_id (DB字段) 而非 asset (对象) 以避免不必要的查询
        if self.inference_project_id and not self.asset_id:
            # 只有当关联对象已加载或通过ID能查询时才执行
            if hasattr(self, "inference_project"):
                self.asset_id = self.inference_project.asset_id

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("创作项目")
        verbose_name_plural = _("创作项目")
        ordering = ["-modified"]
