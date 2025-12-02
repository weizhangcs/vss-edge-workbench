# apps/workflow/creative/urls.py
from django.urls import path

from . import views as creative_views

urlpatterns = [
    # 导演模式配置页 (页面入口)
    path("project/<uuid:project_id>/director/", creative_views.launch_director_view, name="creative_director"),
    # API 接口 (Renamed: factory -> pipeline)
    path(
        "project/<uuid:project_id>/pipeline/submit/",
        creative_views.submit_pipeline_view,
        name="creative_pipeline_submit",
    ),
    path(
        "project/<uuid:project_id>/pipeline/debug/", creative_views.debug_pipeline_view, name="creative_pipeline_debug"
    ),
]
