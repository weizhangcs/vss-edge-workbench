# 文件路径: apps/workflow/projects/transcodingProject.py

from django.db import models
from .baseProject import BaseProject # <-- 导入 BaseProject
from model_utils import Choices
from django_fsm import FSMField

class TranscodingProject(BaseProject):
    STATUS = Choices(('PENDING', '等待开始'), ('PROCESSING', '处理中'), ('COMPLETED', '已完成'))

    asset = models.ForeignKey(
        'media_assets.Asset',
        on_delete=models.CASCADE,
        related_name='transcoding_projects',
        verbose_name="关联资产"
    )
    name = models.CharField(max_length=255, verbose_name="项目名称")
    description = models.TextField(blank=True, null=True, verbose_name="项目描述")

    # --- 核心新增：添加项目级别的状态字段 ---
    status = FSMField(
        default=STATUS.PENDING,
        #choices=STATUS.choices,
        verbose_name="项目状态"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "转码项目"
        verbose_name_plural = "转码项目"