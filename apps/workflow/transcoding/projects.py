# 文件路径: apps/workflow/transcoding/projects.py

from django.db import models
from django_fsm import FSMField
from model_utils import Choices

from ..common.baseProject import BaseProject


class TranscodingProject(BaseProject):
    STATUS = Choices(("PENDING", "等待开始"), ("PROCESSING", "处理中"), ("COMPLETED", "已完成"), ("FAILED", "失败"))

    asset = models.ForeignKey(
        "media_assets.Asset", on_delete=models.CASCADE, related_name="transcoding_projects", verbose_name="关联资产"
    )
    name = models.CharField(max_length=255, verbose_name="项目名称")
    description = models.TextField(blank=True, null=True, verbose_name="项目描述")

    # --- 核心新增：添加项目级别的状态字段 ---
    status = FSMField(
        default=STATUS.PENDING,
        # choices=STATUS.choices,
        verbose_name="项目状态",
    )

    encoding_profile = models.ForeignKey(
        "configuration.EncodingProfile",
        on_delete=models.PROTECT,
        null=True,  # 允许为空，但我们会在 admin 中设为必填
        blank=False,
        verbose_name="编码配置",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "转码项目"
        verbose_name_plural = "转码项目"
