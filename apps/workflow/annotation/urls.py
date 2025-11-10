# 文件路径: apps/workflow/annotation/urls.py

from django.urls import path
from . import views as annotation_views

# app_name 在主 urls.py 中定义，这里不需要

urlpatterns = [
    path(
        'job/<int:job_id>/start-l1/',
        annotation_views.start_l1_annotation_view,
        name='annotation_job_start_l1'
    ),
    path(
        'job/<int:job_id>/save-l1-output/',
        annotation_views.save_l1_output_view,
        name='save_l1_output'
    ),
    path(
        'job/<int:job_id>/revise-l1/',
        annotation_views.revise_l1_annotation_view,
        name='annotation_job_revise_l1'
    ),
    path(
        'job/<int:job_id>/start-l2l3/',
        annotation_views.start_l2l3_annotation_view,
        name='annotation_job_start_l2l3'
    ),
    path(
        'project/<uuid:project_id>/export-l2-output/',
        annotation_views.export_l2_output_view,
        name='annotation_project_export_l2'
    ),
    path(
        'project/<uuid:project_id>/generate-blueprint/',
        annotation_views.generate_blueprint_view,
        name='annotation_project_generate_blueprint'
    ),

    # ---
    #
    path(
        'project/<uuid:project_id>/reasoning-workflow/',
        annotation_views.reasoning_workflow_view,
        name='annotation_project_reasoning_workflow'
    ),
    # ---

    path(
        'project/<uuid:project_id>/trigger-cloud-pipeline/',
        annotation_views.trigger_cloud_pipeline_view,
        name='annotation_project_trigger_cloud_pipeline'
    ),
    path(
        'project/<uuid:project_id>/trigger-cloud-metrics/',
        annotation_views.trigger_cloud_metrics_view,
        name='annotation_project_trigger_cloud_metrics'
    ),
    path(
        'project/<uuid:project_id>/trigger-cloud-facts/',
        annotation_views.trigger_cloud_facts_view,
        name='annotation_project_trigger_cloud_facts'
    ),

    path(
        'project/<uuid:project_id>/trigger-character-audit/',
        annotation_views.trigger_character_audit_view,
        name='annotation_project_trigger_character_audit'
    ),
    path(
        'project/<uuid:project_id>/trigger-local-metrics/',
        annotation_views.trigger_local_metrics_view,
        name='annotation_project_trigger_local_metrics'
    ),
]