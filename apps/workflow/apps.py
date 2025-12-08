# 文件路径: apps/workflow/apps.py

from django.apps import AppConfig


class WorkflowConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.workflow"
    verbose_name = "工作流管理"
