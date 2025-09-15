# 文件路径: apps/configuration/admin.py

from django.contrib import admin
from solo.admin import SingletonModelAdmin
from unfold.admin import ModelAdmin # <-- 核心修正：导入 Unfold 的 ModelAdmin
from .models import IntegrationSettings, EncodingProfile


@admin.register(IntegrationSettings)
class IntegrationSettingsAdmin(ModelAdmin, SingletonModelAdmin): # <-- 核心修正：多重继承
    fieldsets = (
        ("权限管理 (Authorization)", {
            'fields': ('superuser_emails',)
        }),
    )

@admin.register(EncodingProfile)
class EncodingProfileAdmin(ModelAdmin):
    list_display = ('name', 'is_default', 'container', 'modified')
    list_filter = ('is_default',) # 顺便也加一个过滤器
    search_fields = ('name', 'description')