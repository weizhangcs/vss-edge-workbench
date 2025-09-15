# 文件路径: apps/workflow/transcoding/jobs.py

from django.db import models
from ..common.baseJob import BaseJob

class TranscodingJob(BaseJob):
    """
    (V2.1 最终版 - 解耦转码与上传)
    一个具体的、原子的转码任务。
    关联一个可配置的 EncodingProfile，并分别记录转码产出物和最终分发URL。
    """
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

    profile = models.ForeignKey(
        'configuration.EncodingProfile',
        on_delete=models.PROTECT,
        verbose_name="转码规格"
    )

    # 这个字段记录了转码操作成功后，在服务器上生成的物理文件路径。
    output_file = models.FileField(
        upload_to='transcoding_outputs/', # 路径将由后台任务动态生成
        blank=True, null=True,
        verbose_name="输出文件"
    )

    # 这个字段记录了文件上传到 S3 或其他 CDN 之后的可访问 URL。
    output_url = models.URLField(
        max_length=1024,
        blank=True, null=True,
        verbose_name="输出文件URL (CDN)"
    )

    def __str__(self):
        return f"对 {self.media.title} 进行 {self.profile.name} 转码"

    class Meta:
        verbose_name = "转码任务日志"
        verbose_name_plural = "转码任务日志"