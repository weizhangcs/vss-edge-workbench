# 文件路径: apps/workflow/inference/urls.py

from django.urls import path

from . import views as inference_views

urlpatterns = [
    # [!!! 步骤 4: 移除过时的 URL !!!]
    # path('.../trigger-cloud-pipeline/', ...), (已删除)
    # path('.../trigger-cloud-metrics/', ...), (已删除)
    # (保持 FACTS URL 不变，它现在创建 Job)
    path(
        "project/<uuid:project_id>/trigger-cloud-facts/",
        inference_views.trigger_cloud_facts_view,
        name="inference_trigger_cloud_facts",
    ),
    # [!!! 步骤 5: 添加新的 RAG URL !!!]
    path(
        "project/<uuid:project_id>/trigger-rag-deployment/",
        inference_views.trigger_rag_deployment_view,
        name="inference_trigger_rag_deployment",
    ),
]
