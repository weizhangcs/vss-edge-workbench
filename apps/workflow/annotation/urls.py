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
]