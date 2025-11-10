# 文件路径: apps/workflow/inference/urls.py

from django.urls import path
from . import views as inference_views

# app_name 在主 urls.py 中定义为 'workflow'
# 所以这些 URL name 将会是 'workflow:inference_trigger_...'

urlpatterns = [
    path(
        'project/<uuid:project_id>/trigger-cloud-pipeline/',
        inference_views.trigger_cloud_pipeline_view,
        name='inference_trigger_cloud_pipeline' # (新 URL name)
    ),
    path(
        'project/<uuid:project_id>/trigger-cloud-metrics/',
        inference_views.trigger_cloud_metrics_view,
        name='inference_trigger_cloud_metrics' # (新 URL name)
    ),
    path(
        'project/<uuid:project_id>/trigger-cloud-facts/',
        inference_views.trigger_cloud_facts_view,
        name='inference_trigger_cloud_facts' # (新 URL name)
    ),
]