# 文件路径: apps/workflow/jobs/annotationJob.py

from django.db import models
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile

from model_utils import Choices
from django_fsm import FSMField, transition

from ..common.baseJob import BaseJob
from apps.media_assets.models import Media
from unfold.admin import StackedInline

# 定义一个临时的存储位置，如果需要更复杂的权限控制可以替换
fs = FileSystemStorage(location='/app/media_root')

def get_l1_output_upload_path(instance, filename):
  """
  为L1产出物生成动态路径，并包含'annotation/l1_exports'前缀。
  """
  return f'annotation/{instance.project.id}/l1_exports/{instance.id}_{filename}'

class AnnotationJob(BaseJob):
    """
    (V4.3 新架构)
    一个用于管理 L1/L2/L3 标注工作流的模型。
    同时，它也作为“链接模型”，存储 Media 与外部服务（如Label Studio）中Task的关联。
    """
    TYPE = Choices(
        ('L1_SUBEDITING', '第一层-字幕'),
        ('L2L3_SEMANTIC', '第二三层-语义标注'),
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

    label_studio_task_id = models.IntegerField(blank=True, null=True, verbose_name="Label Studio 任务ID")


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

    @transition(field='status', source=BaseJob.STATUS.PENDING, target=BaseJob.STATUS.PROCESSING)
    def start_annotation(self):
        """
        开始标注任务。
        这个转换可以由用户点击 Admin 里的按钮触发。
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
        完成标注任务。
        当收到外部工具（如 Label Studio）的回调或执行完数据同步任务后调用。
        """
        pass

    @transition(field='status', source=BaseJob.STATUS.COMPLETED, target=BaseJob.STATUS.REVISING)
    def revise(self):
        """
        重写 revise 方法以实现L1字幕文件的备份逻辑。
        """
        if self.job_type == self.TYPE.L1_SUBEDITING and self.l1_output_file:
            self.l1_output_file.open('rb')
            content = self.l1_output_file.read()
            self.l1_output_file.close()

            file_name = self.l1_output_file.name.split('/')[-1]
            self.l1_version_backup_file.save(f"backup_{file_name}", ContentFile(content), save=False)

        super().revise()

    def __str__(self):
        if self.media:
            return f"{self.get_job_type_display()} Job for {self.media.title} ({self.get_status_display()})"
        return f"{self.get_job_type_display()} Job for Project {self.project.name} ({self.get_status_display()})"

    class Meta:
        verbose_name = "标注任务"
        verbose_name_plural = verbose_name
        ordering = ['-created']


