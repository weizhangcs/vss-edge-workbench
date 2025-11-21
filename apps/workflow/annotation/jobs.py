# 文件路径: apps/workflow/annotation/jobs.py

import logging

from django.db import models
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile

from model_utils import Choices
from django_fsm import FSMField, transition

from ..common.baseJob import BaseJob
from apps.media_assets.models import Media

logger = logging.getLogger(__name__)

# 定义一个临时的存储位置，用于 .ass 文件
# 注意: 这使用了本地文件系统存储，路径在 Docker 容器内部。
fs = FileSystemStorage(location='/app/media_root')


def get_l1_output_upload_path(instance, filename):
  """
  为L1产出物生成动态路径，格式:
  annotation/<project_id>/l1_exports/<job_id>_<filename>
  """
  return f'annotation/{instance.project.id}/l1_exports/{instance.id}_{filename}'

class AnnotationJob(BaseJob):
    """
    标注工作流的“子任务”模型。

    它代表了一个特定“媒体文件”在一个特定“标注项目”中的工作状态。
    主要用作“链接模型”，存储 Media 与外部服务（如Label Studio）中 Task 的关联。
    """
    TYPE = Choices(
        ('L1_SUBEDITING', '第一层-字幕'),    # 用于 L1 字幕标注 (Subeditor)
        ('L2L3_SEMANTIC', '第二三层-语义标注'), # 用于 L2 语义标注 (Label Studio)
    )

    project = models.ForeignKey(
        'AnnotationProject',
        on_delete=models.CASCADE,
        related_name='jobs',
        verbose_name="所属标注项目",
        null=True,
        blank=True
    )

    media = models.ForeignKey(
        Media,
        on_delete=models.CASCADE,
        related_name='annotation_jobs',
        verbose_name="关联媒体文件",
        null=True,
        blank=True
    )

    job_type = models.CharField(
        max_length=20,
        choices=TYPE,
        verbose_name="任务类型"
    )

    # --- 外部服务 ID ---
    label_studio_task_id = models.IntegerField(blank=True, null=True, verbose_name="Label Studio 任务ID")

    # --- L1 产出物字段 ---
    l1_output_file = models.FileField(
        storage=fs,
        upload_to=get_l1_output_upload_path,
        blank=True,
        null=True,
        verbose_name="L1产出物 (.ass)"
    )

    l1_version_backup_file = models.FileField(
        storage=fs,
        upload_to=get_l1_output_upload_path,
        blank=True,
        null=True,
        verbose_name="L1产出物备份"
    )

    # --- 状态机转换 (继承自 BaseJob 的 'status' 字段) ---

    @transition(field='status', source=BaseJob.STATUS.PENDING, target=BaseJob.STATUS.PROCESSING)
    def start_annotation(self):
        """
        开始标注任务 (PENDING -> PROCESSING)。
        由 L1/L2 视图在用户点击“开始”时触发。
        """
        pass

    @transition(
        field='status',
        source=[
            BaseJob.STATUS.PROCESSING,
            BaseJob.STATUS.REVISING,
            BaseJob.STATUS.ERROR,
        ],
        target=BaseJob.STATUS.COMPLETED
    )
    def complete_annotation(self):
        """
        完成标注任务 (PROCESSING/REVISING/ERROR -> COMPLETED)。
        由 L1 回调视图或 L2 导出任务触发。
        """
        pass

    @transition(field='status', source=BaseJob.STATUS.COMPLETED, target=BaseJob.STATUS.REVISING)
    def revise(self):
        """
        (已重写)
        开始“修订”任务 (COMPLETED -> REVISING)。
        在状态转换前，自动备份当前的 L1 产出物文件。
        """
        # 仅在 L1 任务且产出物存在时执行备份
        if self.job_type == self.TYPE.L1_SUBEDITING and self.l1_output_file:
            try:
                self.l1_output_file.open('rb')
                content = self.l1_output_file.read()
                self.l1_output_file.close()

                file_name = self.l1_output_file.name.split('/')[-1]
                # 保存备份文件 (save=False 因为 super().revise() 之后会调用 save())
                self.l1_version_backup_file.save(f"backup_{file_name}", ContentFile(content), save=False)
            except Exception as e:
                logger.error(f"为 Job {self.id} 备份 L1 文件时出错: {e}", exc_info=True)
                # 即使备份失败，也允许状态转换继续

        super().revise() # (调用 BaseJob 中的原始 revise 逻辑)

    def __str__(self):
        if self.media:
            return f"{self.get_job_type_display()} Job for {self.media.title} ({self.get_status_display()})"
        return f"{self.get_job_type_display()} Job for Project {self.project.name} ({self.get_status_display()})"

    class Meta:
        verbose_name = "标注任务"
        verbose_name_plural = verbose_name
        ordering = ['-created']