# 文件路径: apps/workflow/annotation/urls.py

from django.urls import path

from . import views as annotation_views

# Note: app_name = 'workflow' is defined in the parent urls.py
# URL names here will be accessed like 'workflow:annotation_job_start_l1'

urlpatterns = [
    # --- L1 Job (Sub-task) Actions ---
    # Triggered from the L1 Tab's "Assets" list
    path("job/<int:job_id>/start-l1/", annotation_views.start_l1_annotation_view, name="annotation_job_start_l1"),
    path("job/<int:job_id>/save-l1-output/", annotation_views.save_l1_output_view, name="save_l1_output"),
    path("job/<int:job_id>/revise-l1/", annotation_views.revise_l1_annotation_view, name="annotation_job_revise_l1"),
    # --- L2 Job (Sub-task) Action ---
    # Triggered from the L2 Tab's "Assets" list
    path("job/<int:job_id>/start-l2l3/", annotation_views.start_l2l3_annotation_view, name="annotation_job_start_l2l3"),
    # --- Project-Level Actions (Triggered by Admin Buttons) ---
    # L2 Project Action
    path(
        "project/<uuid:project_id>/export-l2-output/",
        annotation_views.export_l2_output_view,
        name="annotation_project_export_l2",
    ),
    # L3 Project Actions
    path(
        "project/<uuid:project_id>/generate-blueprint/",
        annotation_views.generate_blueprint_view,
        name="annotation_project_generate_blueprint",
    ),
    path(
        "project/<uuid:project_id>/trigger-local-metrics/",
        annotation_views.trigger_local_metrics_view,
        name="annotation_project_trigger_local_metrics",
    ),
    # L1 Project Action
    path(
        "project/<uuid:project_id>/trigger-character-audit/",
        annotation_views.trigger_character_audit_view,
        name="annotation_project_trigger_character_audit",
    ),
]
