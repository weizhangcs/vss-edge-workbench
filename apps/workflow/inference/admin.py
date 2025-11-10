# 文件路径: apps/workflow/inference/admin.py

import json
import logging
from django.contrib import admin, messages
from unfold.admin import ModelAdmin

from .projects import InferenceProject
from apps.workflow.annotation.forms import CharacterSelectionForm

logger = logging.getLogger(__name__)


@admin.register(InferenceProject)
class InferenceProjectAdmin(ModelAdmin):
    """
    (新) L3 推理项目的 Admin 界面。
    """

    # [!!! 修复 1: 重命名这个变量 !!!]
    # (这只在 change_view 中使用)
    change_form_template_for_reasoning = 'admin/workflow/project/inference/reasoning_workflow.html'

    list_display = ('name', 'annotation_project', 'cloud_reasoning_status', 'modified')
    list_display_links = ('name',)

    # [!!! 修复 2: 为 'add' 视图定义一个单独的 fieldset !!!]
    add_fieldsets = (
        (None, {'fields': ('name', 'description', 'annotation_project')}),
    )

    # (change_view 使用的 fieldsets 保持不变)
    fieldsets = (
        (None, {'fields': ('name', 'description', 'annotation_project')}),
        ('云端状态', {'fields': ('cloud_reasoning_status', 'cloud_reasoning_error')}),
        ('云端产出物', {'fields': ('cloud_facts_result_file', 'cloud_rag_report_file')}),
        ('云端路径 (隐藏)', {'fields': ('cloud_blueprint_path', 'cloud_facts_path')}),
    )

    readonly_fields = (
        'cloud_reasoning_status', 'cloud_reasoning_error',
        'cloud_facts_result_file', 'cloud_rag_report_file',
        'cloud_blueprint_path', 'cloud_facts_path'
    )

    def save_model(self, request, obj, form, change):
        """
        在 'add' 视图中保存模型时被调用。
        我们在此处自动设置 'asset' 字段。
        """
        if not change:  # 'change' is False, meaning this is a new object (add_view)
            # 1. 从表单中获取已选择的 'annotation_project'
            annotation_project = form.cleaned_data['annotation_project']

            # 2. 将 'asset' 从 'annotation_project' 复制到 'inference_project'
            obj.asset = annotation_project.asset

        # 3. 调用超类的方法，正常保存对象
        super().save_model(request, obj, form, change)

    # [!!! 步骤 2: 添加 get_readonly_fields 方法 !!!]
    def get_readonly_fields(self, request, obj=None):
        """
        动态设置只读字段。
        - 'add' 视图 (obj is None): 允许编辑 'annotation_project'
        - 'change' 视图 (obj is not None): 'annotation_project' 变为只读
        """
        if obj:  # 'obj' is not None, 所以这是一个 'change' 视图
            # 返回所有基础只读字段，*并动态添加* 'annotation_project'
            return ('annotation_project',) + self.readonly_fields

        # 'obj' is None, 所以这是一个 'add' 视图
        # 只返回基础只读字段 (不包含 'annotation_project')
        return self.readonly_fields

    def get_fieldsets(self, request, obj=None):
        """
        根据是 'add' 还是 'change' 视图返回不同的 fieldsets。
        """
        if obj is None:
            return self.add_fieldsets
        return self.fieldsets

    def add_view(self, request, form_url="", extra_context=None):
        """
        'add' 视图使用 *默认* admin 模板。
        """
        self.change_form_template = None  # (使用 Unfold 默认模板)
        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """
        'change' 视图使用我们 *自定义* 的工作流模板。
        """
        self.change_form_template = self.change_form_template_for_reasoning
        return super().change_view(request, object_id, form_url, extra_context)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        """
        (逻辑保持不变)
        在渲染 change_form 时，注入角色选择表单所需的数据。
        """
        if obj and obj.cloud_reasoning_status == 'WAITING_FOR_SELECTION':
            # ... (你的 'character_selection_form' 逻辑保持不变) ...
            metrics_data = None
            try:
                if obj.annotation_project.local_metrics_result_file:
                    with obj.annotation_project.local_metrics_result_file.open('r') as f:
                        metrics_data = json.load(f)
                else:
                    messages.error(request, "状态错误：找不到 (本地) 角色矩阵产出文件。")
            except Exception as e:
                logger.error(f"无法加载或解析 local_metrics_result_file (项目: {obj.id}): {e}", exc_info=True)
                messages.error(request, f"无法加载角色矩阵文件: {e}")

            if metrics_data:
                context['character_selection_form'] = CharacterSelectionForm(metrics_data=metrics_data)

        context['original'] = obj

        return super().render_change_form(request, context, add, change, form_url, obj)