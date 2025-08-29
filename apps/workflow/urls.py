# 文件路径: apps/workflow/urls.py

from django.urls import path
from .views import annotation_views

app_name = 'workflow'

urlpatterns = [
    path(
        'annotation/job/<int:job_id>/start-l1/',
        annotation_views.start_l1_annotation_view,
        name='annotation_job_start_l1'
    ),
    path(
        'annotation/job/<int:job_id>/save-l1-output/',
        annotation_views.save_l1_output_view,
        name='save_l1_output'
    ),
    path(
        'annotation/job/<int:job_id>/revise-l1/',
        annotation_views.revise_l1_annotation_view,
        name='annotation_job_revise_l1'
    ),
]