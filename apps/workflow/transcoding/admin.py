# 文件路径: apps/workflow/transcoding/admin.py

from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html

from unfold.admin import ModelAdmin

from ..models import TranscodingProject, TranscodingJob
from .views import trigger_transcoding_view  # 导入我们新的视图


@admin.register(TranscodingProject)
class TranscodingProjectAdmin(ModelAdmin):
    # --- 核心修改 1: 在列表页增加“操作”列 ---
    list_display = ('name', 'asset', 'status', 'encoding_profile', 'project_actions')
    list_display_links = ('name',)

    # 详情页字段，现在也包含了编码配置的选择
    fields = ('name', 'asset', 'description', 'encoding_profile', 'status')
    readonly_fields = ('status',)

    # --- 核心修改 2: 定义“操作”列的内容 ---
    @admin.display(description="操作")
    def project_actions(self, obj):
        # 只在项目处于 PENDING 状态时显示“启动”按钮
        if obj.status == 'PENDING':
            trigger_url = reverse('admin:workflow_transcodingproject_trigger', args=[obj.pk])
            return format_html('<a href="{}" class="button variant-primary">▶️ 启动任务</a>', trigger_url)
        return "—"  # 其他状态下不显示按钮

    # --- 核心修改 3: 添加新的 URL 路由 ---
    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        custom_urls = [
            path(
                '<path:project_id>/trigger/',
                self.admin_site.admin_view(trigger_transcoding_view),
                name='%s_%s_trigger' % info
            ),
        ]
        return custom_urls + urls


@admin.register(TranscodingJob)
class TranscodingJobAdmin(ModelAdmin):
    # TranscodingJobAdmin 的代码保持不变
    list_display = ('media', 'project', 'status', 'profile', 'output_url', 'modified')
    list_filter = ('status', 'project', 'profile')
    list_display_links = ('media',)
    readonly_fields = ('project', 'media', 'profile', 'output_file', 'output_url')
    search_fields = ('media__title', 'project__name')