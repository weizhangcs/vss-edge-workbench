# 文件路径: apps/media_assets/admin.py

from django.db import models
from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from unfold.admin import ModelAdmin
from unfold.decorators import display
from unfold.contrib.forms.widgets import WysiwygWidget
from .models import Media, Asset
from . import views

@admin.register(Asset)
class AssetAdmin(ModelAdmin):
    formfield_overrides = {
        models.TextField: {"widget": WysiwygWidget},
    }

    list_display = (
        'title', 'asset_type', 'language', 'copyright_status',
        'upload_status',  'created', 'modified',
        'batch_upload_action',
        #'processing_status',
        # 'manage_projects_action', # 您已注释掉，保持不变
    )
    list_filter = ('asset_type', 'language', 'copyright_status', 'upload_status' ) #'processing_status'
    search_fields = ('title',)
    inlines = []
    actions = []

    @display(header=True, description="文件上传状态与操作", label="文件上传")
    def batch_upload_action(self, obj):
        # --- 核心修复：使用正确的 URL 名称 ---
        url_name = f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_batch_upload'
        batch_upload_url = reverse(url_name, args=[obj.pk])

        if obj.upload_status == 'pending':
            return format_html('<a href="{}" class="button">上传文件</a>', batch_upload_url)
        elif obj.upload_status == 'uploading':
            return "上传中..."
        elif obj.upload_status == 'failed':
            return "上传失败"
        return "✓ 上传完成"

    def get_urls(self):
        """

        :return:
        """
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        custom_urls = [
            path('<path:asset_id>/batch-upload/', self.admin_site.admin_view(views.batch_upload_page_view),
                 name='%s_%s_batch_upload' % info),
            path('<path:asset_id>/api/upload/', self.admin_site.admin_view(views.batch_file_upload_view),
                 name='%s_%s_batch_upload_api' % info),
            path('<path:asset_id>/trigger-ingest/', self.admin_site.admin_view(views.trigger_ingest_task),
                 name='%s_%s_trigger_ingest' % info),
        ]
        return custom_urls + urls

@admin.register(Media)
class MediaAdmin(ModelAdmin):
    """
        (V3 重构版)
        资产条目管理页。现在只负责展示资产的基本信息和物理文件处理状态。
    """
    # --- 核心修改：大幅简化 list_display ---
    list_display = (
        '__str__',
        'asset',  # 显示其所属的媒资
        # 'processing_status' 这个字段在您的旧代码中不存在于 AssetAdmin, 我们遵循原样
        'modified',
    )
    list_filter = ('asset',)  # 按媒资筛选
    search_fields = ('title', 'asset__title')

    # --- 核心修改：简化 fieldsets，移除所有标注相关字段和按钮 ---
    fieldsets = (
        ('基本信息', {'fields': ('asset', 'title', 'sequence_number')}),
        ('输入与输出文件', {
            'classes': ('collapse',),
            'fields': ('source_video', 'source_subtitle', 'processed_video_url'
                       )
        }),
    )
    readonly_fields = ('processed_video_url', 'source_subtitle_url')

    # 移除所有自定义的 get_urls 和 action 方法


