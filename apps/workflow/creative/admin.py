# 文件路径: apps/workflow/creative/admin.py

import logging
from django.contrib import admin, messages
from django.http import HttpRequest
from django.urls import path, reverse
from django.shortcuts import redirect
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .forms import CreativeProjectForm, NarrationConfigurationForm, DubbingConfigurationForm # 导入新表单
from .projects import CreativeProject
from .jobs import CreativeJob

# [!!!] 注意：我们不再从这里导入 tasks

logger = logging.getLogger(__name__)


# [!!!] 确保这个函数存在，并被 tabs.py 导入
def get_creative_project_tabs(request: HttpRequest) -> list[dict]:
    resolver = request.resolver_match

    # [关键修复] 1. 防御性检查：确保视图匹配正确的模型
    if not (resolver and
            resolver.view_name.startswith("admin:workflow_creativeproject_")):
        return []

    # 2. 检查是否有 object_id (确认是 detail view)
    object_id = resolver.kwargs.get("object_id")
    if not object_id:
        return []

    # 此时 object_id 保证为 UUID 字符串，且视图匹配 CreativeProject
    current_view_name = resolver.view_name
    default_change_view_name = "admin:workflow_creativeproject_change"

    tab_items = []
    if object_id:
        tab_items = [
            {
                "title": "步骤 1：解说词推理",
                "link": reverse("admin:workflow_creativeproject_tab_1_narration", args=[object_id]),
                "active": current_view_name in [
                    "admin:workflow_creativeproject_tab_1_narration",
                    default_change_view_name
                ]
            },
            {
                "title": "步骤 2：配音推理",
                "link": reverse("admin:workflow_creativeproject_tab_2_audio", args=[object_id]),
                "active": current_view_name == "admin:workflow_creativeproject_tab_2_audio"
            },
            {
                "title": "步骤 3：剪辑脚本推理",
                "link": reverse("admin:workflow_creativeproject_tab_3_edit", args=[object_id]),
                "active": current_view_name == "admin:workflow_creativeproject_tab_3_edit"
            },
            {  # [新增]
                "title": "步骤 4：视频合成",
                "link": reverse("admin:workflow_creativeproject_tab_4_synthesis", args=[object_id]),
                "active": current_view_name == "admin:workflow_creativeproject_tab_4_synthesis"
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
    form = CreativeProjectForm

    list_display = ('name', 'asset', 'status', 'created', 'view_current_project', 'go_to_inference')
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
    tab_4_fieldsets = base_fieldsets + (
        ('步骤 4 产出物', {'fields': ('final_video_file',)}),
    )

    # [!!! 核心修正] 确保新的状态字段被添加
    readonly_fields = ('asset', 'status')  # [新增]

    inlines = [CreativeJobInline]

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return ((None, {'fields': ('name', 'description', 'inference_project')}),)
        view_name = request.resolver_match.view_name
        if view_name == "admin:workflow_creativeproject_tab_2_audio":
            return self.tab_2_fieldsets
        if view_name == "admin:workflow_creativeproject_tab_3_edit":
            return self.tab_3_fieldsets
        if view_name == "admin:workflow_creativeproject_tab_4_synthesis":  # [新增]
            return self.tab_4_fieldsets
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
            path('<uuid:object_id>/change/tab-4-synthesis/', self.admin_site.admin_view(self.tab_4_synthesis_view),
                 # [新增]
                 name=get_url_name('tab_4_synthesis')),
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

        # 1. 实例化表单 (如果是 POST，视图层会处理，这里主要负责初始渲染)
        # 我们不需要在这里绑定 POST 数据，因为 POST 请求会直接打到 trigger_narration_view
        form = NarrationConfigurationForm()

        form_url = reverse('workflow:creative_trigger_narration', args=[project.pk])

        context['trigger_text'] = "▶️ 生成解说词 (步骤 1)"
        context['trigger_disabled'] = project.status != CreativeProject.STATUS.PENDING
        context['help_text'] = "请配置解说词的叙事方向和风格。"
        context['configuration_form'] = form  # [关键] 将表单注入上下文

        self.change_form_template = "admin/workflow/project/creative/wizard_tab.html"
        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def tab_2_audio_view(self, request, object_id, extra_context=None):
        context = extra_context or {}
        project = self.get_object(request, object_id)

        form = DubbingConfigurationForm() # 默认值即可

        form_url = reverse('workflow:creative_trigger_audio', args=[project.pk])

        context['trigger_text'] = "▶️ 生成配音 (步骤 2)"
        context['trigger_disabled'] = project.status != CreativeProject.STATUS.NARRATION_COMPLETED
        context['help_text'] = "配置配音的音色和语速。风格默认继承自解说词。"
        context['configuration_form'] = form # [关键] 将表单注入上下文

        self.change_form_template = "admin/workflow/project/creative/wizard_tab.html"
        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def tab_3_edit_view(self, request, object_id, extra_context=None):
        context = extra_context or {}
        project = self.get_object(request, object_id)

        form_url = reverse('workflow:creative_trigger_edit', args=[project.pk])
        #form_url = reverse('admin:workflow_creativeproject_tab_3_edit', args=[project.pk])

        context['trigger_text'] = "▶️ 生成剪辑脚本 (步骤 3)"
        context['trigger_disabled'] = project.status != CreativeProject.STATUS.AUDIO_COMPLETED
        context['help_text'] = "当配音生成后，点击此按钮生成剪辑脚本。"

        self.change_form_template = "admin/workflow/project/creative/wizard_tab.html"
        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def tab_4_synthesis_view(self, request, object_id, extra_context=None):  # [新增]
        context = extra_context or {}
        project = self.get_object(request, object_id)

        form_url = reverse('workflow:creative_trigger_synthesis', args=[project.pk])

        context['trigger_text'] = "▶️ 开始视频合成 (步骤 4)"
        context['trigger_disabled'] = project.status != CreativeProject.STATUS.EDIT_COMPLETED
        context['help_text'] = "当剪辑脚本生成后，点击此按钮调用本地 FFmpeg 进程完成音视频合成。"

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
            if 'tab-4-synthesis' in request.path:  # [新增]
                return redirect('workflow:creative_trigger_synthesis', project_id=object_id)

        # 否则，让 Django/Unfold 正常处理 (GET 请求或 "Save" POST)
        return super().changeform_view(request, object_id, form_url, extra_context)

# [新增方法] 提供快速进入当前项目详情页的“操作”按钮
    @admin.display(description="操作")
    def view_current_project(self, obj):
        """
        在 changelist 视图中添加一个“进入项目”的快捷按钮。
        """
        url = reverse('admin:workflow_creativeproject_change', args=[obj.pk])
        return format_html('<a href="{}" class="button">进入项目</a>', url)

    # [新增方法] 提供跳转到关联推理项目的导航按钮
    @admin.display(description="关联推理项目")
    def go_to_inference(self, obj):
        """
        跳转到关联的 Inference Project 详情页。
        """
        try:
            inference_proj = obj.inference_project
            # 使用 'workflow' app_label 进行跨项目导航
            url = reverse('admin:workflow_inferenceproject_change', args=[inference_proj.pk])
            return format_html('<a href="{}" class="button">返回推理</a>', url)
        except Exception:
            return "N/A"
