# 文件路径: apps/workflow/creative/urls.py

from django.urls import path
from . import views as creative_views

# app_name = 'workflow' 已经在父级定义
# URL names here will be 'workflow:creative_...'

urlpatterns = [
    # 对应 步骤 1
    path(
        'project/<uuid:project_id>/trigger-narration/',
        creative_views.trigger_narration_view,
        name='creative_trigger_narration'
    ),
    path(
        'project/<uuid:project_id>/trigger-localize/',
        creative_views.trigger_localize_view,
        name='creative_trigger_localize'
    ),
    # 对应 步骤 2
    path(
        'project/<uuid:project_id>/trigger-audio/',
        creative_views.trigger_audio_view,
        name='creative_trigger_audio'
    ),
    # 对应 步骤 3
    path(
        'project/<uuid:project_id>/trigger-edit/',
        creative_views.trigger_edit_view,
        name='creative_trigger_edit'
    ),
    path(
        'project/<uuid:project_id>/trigger-synthesis/',
        creative_views.trigger_synthesis_view,
        name='creative_trigger_synthesis'
    ),
]