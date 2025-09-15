# 文件路径: apps/workflow/delivery/jobs.py

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from ..common.baseJob import BaseJob

class DeliveryJob(BaseJob):
    """
    一个通用的、原子的分发任务。
    它负责将一个源产出物（如转码文件）交付到一个目标位置（如S3）。
    """
    # --- 核心设计：使用通用外键关联任何源对象 ---
    source_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    source_object_id = models.PositiveIntegerField()
    source_object = GenericForeignKey('source_content_type', 'source_object_id')

    # 记录最终分发到的 URL
    delivery_url = models.URLField(
        max_length=1024,
        blank=True, null=True,
        verbose_name="分发后URL (CDN)"
    )

    def __str__(self):
        return f"分发 {self.source_content_type.model} (ID: {self.source_object_id})"

    class Meta:
        verbose_name = "分发任务"
        verbose_name_plural = "分发任务"