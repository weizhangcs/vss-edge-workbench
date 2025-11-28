# 文件路径: apps/workflow/delivery/admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin

from ..models import DeliveryJob


@admin.register(DeliveryJob)
class DeliveryJobAdmin(ModelAdmin):
    list_display = ("__str__", "status", "delivery_url", "modified")
    list_filter = ("status", "source_content_type")
    readonly_fields = ("source_object", "delivery_url")
    search_fields = ("source_object_id",)
