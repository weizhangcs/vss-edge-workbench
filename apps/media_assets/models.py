# 文件路径: apps/media_assets/models.py

import uuid
from django.db import models
from model_utils.models import TimeStampedModel

# --- 核心新增：定义动态路径函数 ---
def get_media_upload_path(instance, filename):
    """为上传的媒体文件（视频）生成动态路径"""
    return f'source_files/{instance.asset.id}/media/{filename}'

def get_subtitle_upload_path(instance, filename):
    """为上传的字幕文件生成动态路径"""
    return f'source_files/{instance.asset.id}/subtitles/{filename}'

# --- 核心修改：让 Asset 继承 TimeStampedModel ---
class Asset(TimeStampedModel):
    """
    (V4.2 终极纯净版)
    顶层媒资实体，代表一个完整的逻辑作品 (Asset)。
    """
    ASSET_TYPE_CHOICES = (('short_drama', '短剧'), ('movie', '电影'))
    COPYRIGHT_STATUS_CHOICES = (('pending', '待定'), ('cleared', '已授权'), ('owned', '自有版权'),
                                ('restricted', '受限'))
    LANGUAGE_CHOICES = (('zh-CN', '中文 (简体)'), ('en-US', '英语 (美国)'))
    UPLOAD_STATUS_CHOICES = (('pending', '等待文件上传'), ('uploading', '上传中'), ('completed', '上传完成'),
                             ('failed', '上传失败'))


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name="资产标题 (Title)")
    description = models.TextField(blank=True, null=True, verbose_name="描述")
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES, default='short_drama',
                                  verbose_name="资产类型")
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='zh-CN', verbose_name="语言")
    copyright_status = models.CharField(max_length=20, choices=COPYRIGHT_STATUS_CHOICES, default='pending',
                                        verbose_name="版权状态")
    upload_status = models.CharField(max_length=20, choices=UPLOAD_STATUS_CHOICES, default='pending',
                                     verbose_name="文件上传状态")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "内容资产 (Asset)"
        verbose_name_plural = "内容资产 (Asset)"
        ordering = ['-created']


# --- 核心修改：让 Media 继承 TimeStampedModel ---
class Media(TimeStampedModel):
    """
    (V4.2 终极纯净版)
    媒体文件实体，代表组成 Asset 的具体物理文件 (Media)。
    这是一个纯粹的静态模型。
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='medias', verbose_name="所属资产 (Asset)")
    title = models.CharField(max_length=255, verbose_name="媒体标题")
    sequence_number = models.PositiveIntegerField(default=1, verbose_name="序号")

    source_video = models.FileField(
        upload_to=get_media_upload_path,
        blank=True, null=True, verbose_name="源视频文件"
    )
    source_subtitle = models.FileField(
        upload_to=get_subtitle_upload_path,
        blank=True, null=True, verbose_name="源字幕文件 (SRT)"
    )

    processed_video_url = models.URLField(max_length=1024, blank=True, null=True, verbose_name="处理后视频URL (CDN)")
    source_subtitle_url = models.URLField(max_length=1024, blank=True, null=True,
                                          verbose_name="源字幕文件URL (CDN/Public)")


    def __str__(self):
        return f"{self.asset.title} - {self.sequence_number:02d} - {self.title}"

    class Meta:
        verbose_name = "媒体文件 (Media)"
        verbose_name_plural = "媒体文件 (Media)"
        ordering = ['asset', 'sequence_number']