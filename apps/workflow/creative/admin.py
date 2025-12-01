# 文件路径: apps/workflow/creative/admin.py
import logging

from django.contrib import admin, messages
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from . import views as creative_views
from .forms import (  # 导入新表单
    BatchCreationForm,
    CreativeProjectForm,
    DubbingConfigurationForm,
    LocalizeConfigurationForm,
    NarrationConfigurationForm,
)
from .jobs import CreativeJob
from .projects import CreativeBatch, CreativeProject
from .services.orchestrator import CreativeOrchestrator  # 导入新服务

# [!!!] 注意：我们不再从这里导入 tasks

logger = logging.getLogger(__name__)


# [!!!] 确保这个函数存在，并被 tabs.py 导入
def get_creative_project_tabs(request: HttpRequest) -> list[dict]:
    resolver = request.resolver_match

    # [关键修复] 1. 防御性检查：确保视图匹配正确的模型
    if not (resolver and resolver.view_name.startswith("admin:workflow_creativeproject_")):
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
                "active": current_view_name
                in ["admin:workflow_creativeproject_tab_1_narration", default_change_view_name],
            },
            {
                "title": "步骤 1.5：多语言分发",  # [新增 Tab]
                "link": reverse("admin:workflow_creativeproject_tab_1_5_localize", args=[object_id]),
                "active": current_view_name == "admin:workflow_creativeproject_tab_1_5_localize",
            },
            {
                "title": "步骤 2：配音推理",
                "link": reverse("admin:workflow_creativeproject_tab_2_audio", args=[object_id]),
                "active": current_view_name == "admin:workflow_creativeproject_tab_2_audio",
            },
            {
                "title": "步骤 3：剪辑脚本推理",
                "link": reverse("admin:workflow_creativeproject_tab_3_edit", args=[object_id]),
                "active": current_view_name == "admin:workflow_creativeproject_tab_3_edit",
            },
            {  # [新增]
                "title": "步骤 4：视频合成",
                "link": reverse("admin:workflow_creativeproject_tab_4_synthesis", args=[object_id]),
                "active": current_view_name == "admin:workflow_creativeproject_tab_4_synthesis",
            },
        ]
    return [{"models": [{"name": "workflow.creativeproject", "detail": True}], "items": tab_items}]


class CreativeJobInline(TabularInline):
    model = CreativeJob
    extra = 0
    can_delete = False

    # [新增配置] 隐藏 Unfold 自动生成的行标题
    hide_title = True

    # [修改 1] 使用自定义方法 'display_id' 代替直接使用 'id'
    # 同时恢复 input_params 为直接显示
    fields = ("display_id", "job_type", "status", "cloud_task_id", "created", "modified", "input_params")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    # [修改 2] 定义一个显示 ID 的方法
    @admin.display(description="ID")
    def display_id(self, obj):
        return obj.id


@admin.register(CreativeProject)
class CreativeProjectAdmin(ModelAdmin):
    form = CreativeProjectForm

    list_display = ("name", "asset", "status", "created", "view_current_project", "go_to_inference")
    search_fields = ("name", "inference_project__name", "asset__title")
    autocomplete_fields = ["inference_project"]

    # 1. 定义公共头部 (Base Layout)
    base_fieldsets = (
        (
            None,
            {
                "fields": (
                    ("name", "status"),  # 第一行
                    ("asset", "inference_project"),  # 第二行
                    "description",  # 第三行 (通栏)
                )
            },
        ),
    )

    # 2. 定义各个 Tab 的 Fieldsets
    # 逻辑：公共头部 + 该步骤特有的 Fieldset

    # 步骤 1
    tab_1_fieldsets = base_fieldsets + (("步骤 1 产出物", {"fields": ("narration_script_file",)}),)

    # 步骤 1.5 (本地化) - [修正后]
    tab_1_5_fieldsets = base_fieldsets + (
        (
            "双语脚本下载与核对",
            {
                "fields": (
                    "narration_script_file",  # 中文母本
                    "localized_script_file",  # 英文译本
                ),
                "description": "请下载上方两个文件进行人工比对。如果进行了修改，请重新上传覆盖，再进行下一步。",
            },
        ),
    )

    # 步骤 2
    tab_2_fieldsets = base_fieldsets + (("步骤 2 产出物", {"fields": ("dubbing_script_file",)}),)

    # 步骤 3
    tab_3_fieldsets = base_fieldsets + (("步骤 3 产出物", {"fields": ("edit_script_file",)}),)

    # 步骤 4
    tab_4_fieldsets = base_fieldsets + (("步骤 4 产出物", {"fields": ("final_video_file",)}),)

    # 3. 只读字段
    readonly_fields = ("asset", "status")

    # [修改] 注释掉 inlines，暂时在 UI 上隐藏子任务列表，但 TODO: 保留代码以便未来调试或加权限
    # inlines = [CreativeJobInline]
    inlines = []

    # [新增] 辅助方法：统一注入工厂入口 URL
    def _inject_factory_context(self, context, object_id):
        if object_id:
            context["launch_factory_url"] = reverse("admin:creative_project_launch_factory", args=[object_id])
        return context

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return ((None, {"fields": ("name", "description", "inference_project")}),)
        view_name = request.resolver_match.view_name

        if view_name == "admin:workflow_creativeproject_tab_1_5_localize":
            return self.tab_1_5_fieldsets
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
            path(
                "<uuid:object_id>/change/tab-1-narration/",
                self.admin_site.admin_view(self.tab_1_narration_view),
                name=get_url_name("tab_1_narration"),
            ),
            # [新增] Tab 1.5 路由
            path(
                "<uuid:object_id>/change/tab-1-5-localize/",
                self.admin_site.admin_view(self.tab_1_5_localize_view),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_tab_1_5_localize",
            ),
            path(
                "<uuid:object_id>/change/tab-2-audio/",
                self.admin_site.admin_view(self.tab_2_audio_view),
                name=get_url_name("tab_2_audio"),
            ),
            path(
                "<uuid:object_id>/change/tab-3-edit/",
                self.admin_site.admin_view(self.tab_3_edit_view),
                name=get_url_name("tab_3_edit"),
            ),
            path(
                "<uuid:object_id>/change/tab-4-synthesis/",
                self.admin_site.admin_view(self.tab_4_synthesis_view),
                # [新增]
                name=get_url_name("tab_4_synthesis"),
            ),
            path(
                "<uuid:project_id>/launch-factory/",
                self.admin_site.admin_view(creative_views.launch_factory_view),
                name="creative_project_launch_factory",
            ),
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            extra_context["launch_factory_url"] = reverse("admin:creative_project_launch_factory", args=[object_id])

        return self.tab_1_narration_view(request, object_id, extra_context)

    # --- Tab 渲染视图 (Renderers) ---

    def tab_1_narration_view(self, request, object_id, extra_context=None):
        context = extra_context or {}
        self._inject_factory_context(context, object_id)

        project = self.get_object(request, object_id)

        # [核心修改] 尝试从 auto_config 读取已保存的参数
        saved_config = {}
        if project.auto_config and isinstance(project.auto_config, dict):
            saved_config = project.auto_config.get("narration", {})

        # 使用 saved_config 作为 initial，如果没有则 Form 会使用定义时的 default
        form = NarrationConfigurationForm(initial=saved_config)

        form_url = reverse("workflow:creative_trigger_narration", args=[project.pk])

        context["trigger_text"] = "▶️ 生成解说词 (步骤 1)"
        context["trigger_disabled"] = project.status == CreativeProject.STATUS.NARRATION_RUNNING
        context["help_text"] = "请配置解说词的叙事方向和风格。"
        context["configuration_form"] = form

        self.change_form_template = "admin/workflow/project/creative/wizard_tab.html"
        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def tab_1_5_localize_view(self, request, object_id, extra_context=None):
        context = extra_context or {}
        self._inject_factory_context(context, object_id)

        project = self.get_object(request, object_id)

        # [核心修改] 读取 localize 配置
        saved_config = {}
        if project.auto_config and isinstance(project.auto_config, dict):
            saved_config = project.auto_config.get("localize", {})

        form = LocalizeConfigurationForm(initial=saved_config)

        form_url = reverse("workflow:creative_trigger_localize", args=[project.pk])

        context["trigger_text"] = "▶️ 启动本地化翻译 (步骤 1.5)"
        context["trigger_disabled"] = project.status == CreativeProject.STATUS.LOCALIZATION_RUNNING or not bool(
            project.narration_script_file
        )

        if not project.narration_script_file:
            context["help_text"] = "请先完成步骤 1 生成中文母本。"
        else:
            context["help_text"] = "基于中文母本，生成目标语言的发行脚本。"

        context["configuration_form"] = form
        self.change_form_template = "admin/workflow/project/creative/wizard_tab.html"
        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def tab_2_audio_view(self, request, object_id, extra_context=None):
        context = extra_context or {}
        self._inject_factory_context(context, object_id)

        project = self.get_object(request, object_id)

        # [核心修改] 读取 audio 配置
        saved_config = {}
        if project.auto_config and isinstance(project.auto_config, dict):
            saved_config = project.auto_config.get("audio", {})

        form = DubbingConfigurationForm(initial=saved_config)

        form_url = reverse("workflow:creative_trigger_audio", args=[project.pk])

        context["trigger_text"] = "▶️ 生成配音 (步骤 2)"
        context["trigger_disabled"] = project.status == CreativeProject.STATUS.AUDIO_RUNNING or not bool(
            project.narration_script_file
        )

        context["help_text"] = "配置配音的音色和语速。风格默认继承自解说词。"
        context["configuration_form"] = form

        self.change_form_template = "admin/workflow/project/creative/wizard_tab.html"
        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def tab_3_edit_view(self, request, object_id, extra_context=None):
        context = extra_context or {}
        # [修改] 调用辅助方法注入 URL
        self._inject_factory_context(context, object_id)
        project = self.get_object(request, object_id)

        form_url = reverse("workflow:creative_trigger_edit", args=[project.pk])
        # form_url = reverse('admin:workflow_creativeproject_tab_3_edit', args=[project.pk])

        context["trigger_text"] = "▶️ 生成剪辑脚本 (步骤 3)"
        # [UI 修复] 禁用条件：正在运行 OR 缺少配音脚本
        context["trigger_disabled"] = project.status == CreativeProject.STATUS.EDIT_RUNNING or not bool(
            project.dubbing_script_file
        )
        context["help_text"] = "当配音生成后，点击此按钮生成剪辑脚本。"

        self.change_form_template = "admin/workflow/project/creative/wizard_tab.html"
        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def tab_4_synthesis_view(self, request, object_id, extra_context=None):  # [新增]
        context = extra_context or {}
        # [修改] 调用辅助方法注入 URL
        self._inject_factory_context(context, object_id)
        project = self.get_object(request, object_id)

        form_url = reverse("workflow:creative_trigger_synthesis", args=[project.pk])

        context["trigger_text"] = "▶️ 开始视频合成 (步骤 4)"
        # [UI 修复] 禁用条件：正在运行 OR 缺少剪辑脚本
        context["trigger_disabled"] = project.status == CreativeProject.STATUS.SYNTHESIS_RUNNING or not bool(
            project.edit_script_file
        )
        context["help_text"] = "当剪辑脚本生成后，点击此按钮调用本地 FFmpeg 进程完成音视频合成。"

        self.change_form_template = "admin/workflow/project/creative/wizard_tab.html"
        return super().changeform_view(request, str(object_id), form_url=form_url, extra_context=context)

    def add_view(self, request, form_url="", extra_context=None):
        # 当在 "add" 页面点击 "Save" (POST) 时
        # 我们必须覆盖 changeform_view
        self.change_form_template = None
        return super().add_view(request, form_url, extra_context)

    def changeform_view(self, request, object_id, form_url, extra_context=None):
        # 这个方法现在处理 "add" (object_id=None) 和 "change" (object_id=UUID)
        if request.method == "POST" and object_id:
            # 这是一个 "change" 视图的 POST
            # 它不是 "Save"，而是我们的自定义按钮
            if "tab-1-narration" in request.path:
                return redirect("workflow:creative_trigger_narration", project_id=object_id)
            if "tab-1-5-localize" in request.path:
                return redirect("workflow:creative_trigger_localize", project_id=object_id)
            if "tab-2-audio" in request.path:
                return redirect("workflow:creative_trigger_audio", project_id=object_id)
            if "tab-3-edit" in request.path:
                return redirect("workflow:creative_trigger_edit", project_id=object_id)
            if "tab-4-synthesis" in request.path:  # [新增]
                return redirect("workflow:creative_trigger_synthesis", project_id=object_id)

        # 否则，让 Django/Unfold 正常处理 (GET 请求或 "Save" POST)
        return super().changeform_view(request, object_id, form_url, extra_context)

    # [新增方法] 提供快速进入当前项目详情页的“操作”按钮
    @admin.display(description="操作")
    def view_current_project(self, obj):
        """
        在 changelist 视图中添加一个“进入项目”的快捷按钮。
        """
        url = reverse("admin:workflow_creativeproject_change", args=[obj.pk])
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
            url = reverse("admin:workflow_inferenceproject_change", args=[inference_proj.pk])
            return format_html('<a href="{}" class="button">返回推理</a>', url)
        except Exception:
            return "N/A"


@admin.register(CreativeBatch)
class CreativeBatchAdmin(ModelAdmin):
    list_display = ("__str__", "inference_project", "total_count", "created", "view_projects")

    # 关闭默认的 Add 按钮，因为我们要用自定义页面
    def has_add_permission(self, request):
        return False

    @admin.display(description="查看详情")
    def view_projects(self, obj):
        url = reverse("admin:workflow_creativeproject_changelist") + f"?batch_id={obj.id}"
        return format_html('<a href="{}" class="button">查看生成结果</a>', url)

    # 注册自定义 URL
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                # "orchestrator/", self.admin_site.admin_view(self.orchestrator_view)
                # , name="creative_batch_orchestrator"
                "factory/",
                self.admin_site.admin_view(self.factory_view),
                name="creative_batch_factory",
            ),
        ]
        return custom_urls + urls

    def factory_view(self, request):
        # 暂时只渲染模板，不处理 POST
        context = {
            **self.admin_site.each_context(request),
            "title": "精细化创作参数工厂 (Pipeline Factory)",
        }
        return render(request, "admin/workflow/creative/factory_mock.html", context)

    # 编排器视图
    def orchestrator_view(self, request):
        if request.method == "POST":
            form = BatchCreationForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                count = data.pop("count")
                inf_proj = data.pop("inference_project")

                # 这里的 data 剩余部分就是 fixed_params
                # 我们需要过滤掉空值，空值代表随机
                fixed_params = {k: v for k, v in data.items() if v}

                try:
                    orchestrator = CreativeOrchestrator(inference_project_id=str(inf_proj.id))
                    batch = orchestrator.create_batch(count, fixed_params)

                    self.message_user(request, f"成功启动批量任务！批次ID: {batch.id}，共 {count} 个项目正在生成中。", messages.SUCCESS)
                    return redirect("admin:workflow_creativebatch_changelist")
                except Exception as e:
                    self.message_user(request, f"启动失败: {e}", messages.ERROR)
        else:
            form = BatchCreationForm()

        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "批量创作编排器 (Orchestrator)",
        }
        return render(request, "admin/workflow/project/creative/orchestrator_form.html", context)
