# 文件路径: apps/workflow/common/base_project.py

import uuid

from django.db import models
from model_utils.models import TimeStampedModel


class BaseProject(TimeStampedModel):
    """
    所有具体工作项目（如标注、转碼）的抽象基类。
    包含了所有项目的通用字段。
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # 使用字符串引用，避免循环导入
    asset = models.ForeignKey(
        "media_assets.Asset",
        on_delete=models.CASCADE,
        related_name="%(class)s_projects",  # 使用 %(class)s 动态生成 related_name
        verbose_name="关联资产",
    )
    name = models.CharField(max_length=255, verbose_name="项目名称")
    description = models.TextField(blank=True, null=True, verbose_name="项目描述")

    STATUS_CHOICES = (
        ("PENDING", "待处理"),
        ("PROCESSING", "处理中"),
        ("COMPLETED", "已完成"),
        ("FAILED", "失败"),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING", verbose_name="项目状态")

    def __str__(self):
        return self.name

    class Meta:
        abstract = True  # 声明这是一个抽象模型，Django 不会为它创建数据库表
