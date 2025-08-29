# 文件路径: apps/workflow/jobs/transcodingJob.py

from django.db import models
from model_utils import Choices
from .baseJob import BaseJob  # 从 workflow 的主 models.py 导入 BaseJob

class TranscodingJob(BaseJob):
    """
    (V1.1 数据源修正版)
    一个具体的、原子的转码任务。
    包含了转码规格 (profile) 和输出文件 (output_file) 的定义。
    """
    PROFILE = Choices(
        ('H264_720P_2M', 'H.264 720p (2Mbps)'),
        ('H264_1080P_5M', 'H.264 1080p (5Mbps)'),
        # 未来可以添加更多 profile
    )

    # --- 核心修复：使用字符串 'app_name.ModelName' 来声明外键 ---
    project = models.ForeignKey(
        'workflow.TranscodingProject',
        on_delete=models.CASCADE,
        related_name='transcoding_jobs',
        verbose_name="所属转码项目"
    )
    media = models.ForeignKey(
        'media_assets.Media',
        on_delete=models.CASCADE,
        related_name='transcoding_jobs',
        verbose_name="关联媒体文件"
    )

    profile = models.CharField(
        max_length=20,
        choices=PROFILE,
        verbose_name="转码规格"
    )

    output_file = models.FileField(
        # 我们将让 task 动态生成完整的路径
        upload_to='transcoding_outputs/',
        blank=True, null=True,
        verbose_name="输出文件"
    )

    def __str__(self):
        return f"对 {self.media.title} 进行 {self.get_profile_display()} 转码"

    class Meta:
        verbose_name = "转码任务日志"
        verbose_name_plural = "转码任务日志"