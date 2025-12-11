from django.urls import path

from . import views

# namespace: workflow:annotation
app_name = "annotation"

urlpatterns = [
    # 1. 进入 React 工作台 (Standalone Page)
    path("workbench/<int:job_id>/", views.annotation_workbench_entry, name="annotation_workbench"),
    # 2. 保存标注数据 (API)
    path("workbench/<int:job_id>/save/", views.annotation_save_api, name="annotation_save"),
    # 新增：审计接口
    # 路径示例: /annotation/projects/101/audit/
    path("audit/<uuid:project_id>/audit/", views.trigger_audit, name="trigger-project-audit"),
    # [新增] 导出接口
    path("project/<uuid:project_id>/export/", views.export_project_view, name="export-project"),
    # [新增] 导入接口 (用于前端 React 上传)
    path("import/handle/", views.handle_import_project, name="handle-import-project"),
]
