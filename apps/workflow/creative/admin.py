# apps/workflow/creative/admin.py

import json
import logging

from django.conf import settings
from django.contrib import admin
from django.http import HttpRequest
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .forms import CreativeProjectForm
from .models import CreativeProject

logger = logging.getLogger(__name__)


# --- 1. Tab 导航定义 ---
def get_creative_project_tabs(request: HttpRequest) -> list[dict]:
    resolver = request.resolver_match
    if not (resolver and resolver.view_name.startswith("admin:workflow_creativeproject_")):
        return []

    object_id = resolver.kwargs.get("object_id")
    if not object_id:
        return []

    current_view = resolver.view_name

    return [
        {
            "models": [{"name": "workflow.creativeproject", "detail": True}],
            "items": [
                {
                    "title": "🎬 导演驾驶舱 (Config)",
                    "link": reverse("admin:workflow_creativeproject_change", args=[object_id]),
                    "active": current_view == "admin:workflow_creativeproject_change",
                },
                {
                    "title": "📺 进度监视器 (Monitor)",
                    "link": reverse("admin:workflow_creativeproject_tab_monitor", args=[object_id]),
                    "active": current_view == "admin:workflow_creativeproject_tab_monitor",
                },
            ],
        }
    ]


@admin.register(CreativeProject)
class CreativeProjectAdmin(ModelAdmin):
    form = CreativeProjectForm
    list_display = ("name", "asset", "status_badge", "created", "action_open_monitor")
    search_fields = ("name", "inference_project__name", "asset__title")
    autocomplete_fields = ["inference_project"]

    readonly_fields = ("status",)
    fieldsets = ((None, {"fields": ()}),)

    def status_badge(self, obj):
        return obj.status

    status_badge.short_description = "状态"

    # --- URL 路由 ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<uuid:object_id>/change/tab-monitor/",
                self.admin_site.admin_view(self.render_monitor_tab),
                name="workflow_creativeproject_tab_monitor",
            ),
        ]
        return custom_urls + urls

    # --- 视图 1: 导演驾驶舱 ---
    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}

        # 隐藏多余按钮
        extra_context["show_save"] = False
        extra_context["show_save_and_continue"] = False
        extra_context["show_save_and_add_another"] = False

        if object_id:
            project = self.get_object(request, object_id)

            assets = {
                "source_language": project.asset.language if project.asset else "zh-CN",
                "narration": {
                    "exists": bool(project.narration_script_file),
                    "name": str(project.narration_script_file),
                },
                "localize": {"exists": bool(project.localized_script_file), "name": str(project.localized_script_file)},
                "audio": {"exists": bool(project.dubbing_script_file), "name": str(project.dubbing_script_file)},
            }

            extra_context["server_data_json"] = json.dumps(
                {
                    "project_id": str(project.id),
                    "project_name": project.name,
                    "assets": assets,
                    "initial_config": project.auto_config or {},
                },
                ensure_ascii=False,
            )

            self.change_form_template = "admin/workflow/project/creative/director_tab.html"

        return super().change_view(request, object_id, form_url, extra_context)

    # --- 视图 2: 进度监视器 ---
    def render_monitor_tab(self, request, object_id, extra_context=None):
        context = extra_context or {}
        project = self.get_object(request, object_id)

        context["show_save"] = False
        context["show_save_and_continue"] = False
        context["show_save_and_add_another"] = False

        # 1. 注入进度 (保持不变)
        status_weights = {
            "CREATED": 5,
            "NARRATION_RUNNING": 15,
            "NARRATION_COMPLETED": 30,
            "LOCALIZATION_RUNNING": 40,
            "LOCALIZATION_COMPLETED": 50,
            "AUDIO_RUNNING": 60,
            "AUDIO_COMPLETED": 75,
            "EDIT_RUNNING": 85,
            "EDIT_COMPLETED": 95,
            "SYNTHESIS_RUNNING": 98,
            "COMPLETED": 100,
            "FAILED": 100,
        }
        context["progress_percent"] = status_weights.get(project.status, 5)
        context["project"] = project
        context["is_running"] = project.status not in ["COMPLETED", "FAILED"]

        # 2. 解说词解析 (保持不变)
        script_data = []
        has_translation = False
        target_file = project.localized_script_file if project.localized_script_file else project.narration_script_file

        if target_file:
            try:
                with target_file.open("r") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # 兼容 narration_script 或 narration 键
                        raw_list = data.get("narration_script") or data.get("narration") or []
                    else:
                        raw_list = data if isinstance(data, list) else []

                    for item in raw_list:
                        # 鲁棒性提取
                        main_text = (item.get("narration") or "").strip()
                        source_text = (item.get("narration_source") or "").strip()

                        if project.localized_script_file and source_text:
                            script_data.append({"source": source_text, "target": main_text})
                            has_translation = True
                        else:
                            script_data.append({"source": main_text, "target": ""})
            except Exception as e:
                logger.error(f"Script Parse Error: {e}")
                script_data = [{"source": f"数据异常: {str(e)}", "target": ""}]
        else:
            status_hint = "⏳ 等待生成..." if context["is_running"] else "❌ 未找到脚本文件"
            script_data = [{"source": status_hint, "target": ""}]

        context["script_lines"] = script_data
        context["has_translation"] = has_translation

        # 3. [重构] 配音解析 (直接读取 local_audio_path)
        audio_list = []
        if project.dubbing_script_file:
            try:
                with project.dubbing_script_file.open("r") as f:
                    data = json.load(f)
                    # 兼容 dubbing_script 或 dubbing 键
                    segments = data.get("dubbing_script") or data.get("dubbing") or []
                    if not isinstance(segments, list):
                        segments = []

                    for seg in segments:
                        # [核心修复] 优先读取 rewrite 后的本地路径
                        # local_audio_path: "creative/uuid/outputs/audio_16/narration_000.mp3"
                        local_path = seg.get("local_audio_path")

                        # 兜底：如果还没 rewrite (比如任务刚开始)，尝试用 audio_file_path (Cloud Path)
                        # 但 Cloud Path 通常无法直接访问，所以这里主要依赖 local_path

                        text_preview = (seg.get("narration") or "")[:20] + "..."

                        if local_path:
                            # 直接拼接 MEDIA_URL
                            full_url = f"{settings.MEDIA_URL}{local_path}"
                            audio_list.append({"name": text_preview, "url": full_url})

            except Exception as e:
                logger.error(f"Audio Parse Error: {e}")

        context["audio_list"] = audio_list

        self.change_form_template = "admin/workflow/project/creative/monitor.html"
        return super().changeform_view(request, str(object_id), extra_context=context)

    # --- 辅助方法 ---
    @admin.display(description="监视器")
    def action_open_monitor(self, obj):
        url = reverse("admin:workflow_creativeproject_tab_monitor", args=[obj.pk])
        return format_html('<a href="{}" class="button">查看进度</a>', url)

    def add_view(self, request, form_url="", extra_context=None):
        self.change_form_template = None
        return super().add_view(request, form_url, extra_context)
