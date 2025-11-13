# 文件路径: apps/workflow/creative/admin.py

import logging
from django.contrib import admin, messages
from django.http import HttpRequest
from django.urls import path, reverse
from django.shortcuts import redirect
from unfold.admin import ModelAdmin, TabularInline

from .projects import CreativeProject
from .jobs import CreativeJob

# [!!!] 注意：我们不再从这里导入 tasks

logger = logging.getLogger(__name__)


# [!!!] 确保这个函数存在，并被 tabs.py 导入
def get_creative_project_tabs(request: HttpRequest) -> list[dict]:
    object_id = None
    if request.resolver_match and "object_id" in request.resolver_match.kwargs:
        object_id = request.resolver_match.kwargs.get("object_id")
    current_view_name = request.resolver_match.view_name
    default_change_view_name = "admin:workflow_creativeproject_change"

    tab_items = []
    if object_id:
        tab_items = [
            {
                "title": "步骤 1：解说词",
                "link": reverse("admin:workflow_creativeproject_tab_1_narration", args=[object_id]),
                "active": current_view_name in [
                    "admin:workflow_creativeproject_tab_1_narration",
                    default_change_view_name
                ]
            },
            {
                "title": "步骤 2：配音",
                "link": reverse("admin:workflow_creativeproject_tab_2_audio", args=[object_id]),
                "active": current_view_name == "admin:workflow_creativeproject_tab_2_audio"
            },
            {
                "title": "步骤 3：剪辑合成",
                "link": reverse("admin:workflow_creativeproject_tab_3_edit", args=[object_id]),
                "active": current_view_name == "admin:workflow_creativeproject_tab_3_edit"
            },
        ]
    return [{"models": [{"name": "workflow.creativeproject", "detail": True}], "items": tab_items}]


class CreativeJobInline(TabularInline):
    model = CreativeJob
    extra = 0
    can_delete = False
    list_display = ('job_type', 'status', 'cloud_task_id', 'created', 'modified')
    readonly_fields = list_display + ('input_params',)

    def has_add_permission(self, request, obj=None): return False


@admin.register(CreativeProject)
class CreativeProjectAdmin(ModelAdmin):
    list_display = ('name', 'inference_project', 'asset', 'status', 'created')
    search_fields = ('name', 'inference_project__name', 'asset__title')
    autocomplete_fields = ['inference_project']

    base_fieldsets = (
        (None, {'fields': ('name', 'description', 'status', 'inference_project', 'asset')}),
    )
    tab_1_fieldsets = base_fieldsets + (
        ('步骤 1 产出物', {'fields': ('narration_script_file',)}),
    )
    # [!!!] --- 核心修正 --- [!!!]
    tab_2_fieldsets = base_fieldsets + (
        ('步骤 2 产出物', {'fields': ('dubbing_script_file',)}),  # <--- 字段重命名
    )
    tab_3_fieldsets = base_fieldsets + (
        ('步骤 3 产出物', {'fields': ('edit_script_file',)}),
    )

    # [!!!] --- 核心修正 --- [!!!]
    readonly_fields = ('asset', 'status', 'narration_script_file',
                       'dubbing_script_file', 'edit_script_file')  # <--- 字段重命名

    inlines = [CreativeJobInline]

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return ((None, {'fields': ('name', 'description', 'inference_project')}),)
        view_name = request.resolver_match.view_name
        if view_name == "admin:workflow_creativeproject_tab_2_audio":
            return self.tab_2_fieldsets
        if view_name == "admin:workflow_creativeproject_tab_3_edit":
            return self.tab_3_fieldsets
        return self.tab_1_fieldsets

    # [!!! 修正 !!!]
    # get_urls 现在只定义 Tab 视图。触发器视图已移至 urls.py
    def get_urls(self):
        urls = super().get_urls()

        def get_url_name(view_name):
            return f"{self.model._meta.app_label}_{self.model._meta.model_name}_{view_name}"

        custom_urls = [
            path('<uuid:object_id>/change/tab-1-narration/', self.admin_site.admin_view(self.tab_1_narration_view),
                 name=get_url_name('tab_1_narration')),
            path('<uuid:object_id>/change/tab-2-audio/', self.admin_site.admin_view(self.tab_2_audio_view),
                 name=get_url_name('tab_2_audio')),
            path('<uuid:object_id>/change/tab-3-edit/', self.admin_site.admin_view(self.tab_3_edit_view),
                 name=get_url_name('tab_3_edit')),
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        return self.tab_1_narration_view(request, object_id, extra_context)

    # [!!! 修正 !!!]
    # 触发器视图 (Triggers) 已被移除，逻辑已移至 views.py

    # --- Tab 渲染视图 (Renderers) ---

    def tab_1_narration_view(self, request, object_id, extra_context=None):
        context = extra_context or {}
        project = self.get_object(request, object_id)

        # [!!! 修正 !!!]
        # form_url 现在指向我们新创建的、在 'workflow' 命名空间下的 URL
        form_url = reverse('workflow:creative_trigger_narration', args=[project.pk])

        context['trigger_text'] = "▶️ 生成解说词 (步骤 1)"
        context['trigger_disabled'] = project.status != CreativeProject.STATUS.PENDING
        context['help_text'] = "点击按钮将调用云端 API 生成解说词。"

        self.change_form_template = "admin/workflow/project/creative/wizard_tab.html"
        # [!!! 修正 !!!] 我们需要将 form_url 传递给 changeform_view
        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def tab_2_audio_view(self, request, object_id, extra_context=None):
        context = extra_context or {}
        project = self.get_object(request, object_id)

        form_url = reverse('workflow:creative_trigger_audio', args=[project.pk])

        context['trigger_text'] = "▶️ 生成配音 (步骤 2)"
        context['trigger_disabled'] = project.status != CreativeProject.STATUS.NARRATION_COMPLETED
        context['help_text'] = "当解说词生成后，点击此按钮开始配音。（此功能待您在云端实现）"

        self.change_form_template = "admin/workflow/project/creative/wizard_tab.html"
        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def tab_3_edit_view(self, request, object_id, extra_context=None):
        context = extra_context or {}
        project = self.get_object(request, object_id)

        form_url = reverse('workflow:creative_trigger_edit', args=[project.pk])

        context['trigger_text'] = "▶️ 生成剪辑脚本 (步骤 3)"
        context['trigger_disabled'] = project.status != CreativeProject.STATUS.AUDIO_COMPLETED
        context['help_text'] = "当配音生成后，点击此按钮生成剪辑脚本。（此功能待您在云端实现）"

        self.change_form_template = "admin/workflow/project/creative/wizard_tab.html"
        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def add_view(self, request, form_url="", extra_context=None):
        # 当在 "add" 页面点击 "Save" (POST) 时
        # 我们必须覆盖 changeform_view
        self.change_form_template = None
        return super().add_view(request, form_url, extra_context)

    def changeform_view(self, request, object_id, form_url, extra_context=None):
        # 这个方法现在处理 "add" (object_id=None) 和 "change" (object_id=UUID)
        if request.method == 'POST' and object_id:
            # 这是一个 "change" 视图的 POST
            # 它不是 "Save"，而是我们的自定义按钮
            if 'tab-1-narration' in request.path:
                return redirect('workflow:creative_trigger_narration', project_id=object_id)
            if 'tab-2-audio' in request.path:
                return redirect('workflow:creative_trigger_audio', project_id=object_id)
            if 'tab-3-edit' in request.path:
                return redirect('workflow:creative_trigger_edit', project_id=object_id)

        # 否则，让 Django/Unfold 正常处理 (GET 请求或 "Save" POST)
        return super().changeform_view(request, object_id, form_url, extra_context)

