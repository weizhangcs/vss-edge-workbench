# 文件路径: apps/workflow/inference/forms.py

from django import forms
from unfold.widgets import UnfoldAdminTextareaWidget

from .projects import InferenceProject

# [!!! 步骤 1: 创建一个新的 ModelForm (修复 UI 样式) !!!]
class InferenceProjectForm(forms.ModelForm):
    class Meta:
        model = InferenceProject
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # (就像我们在 AnnotationProjectForm 中做的一样)
        if 'description' in self.fields:
            self.fields['description'].widget = UnfoldAdminTextareaWidget(attrs={'rows': 2})


# [!!! 步骤 2: 保持你已有的 CharacterSelectionForm 不变 !!!]
class CharacterSelectionForm(forms.Form):
    """
    (V3 架构)
    一个动态表单，用于在 InferenceProject Admin 中
    从 local_metrics_result_file 中读取角色列表。
    """
    characters = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        label="请选择要识别属性的角色",
        required=True
    )

    def __init__(self, *args, **kwargs):
        metrics_data = kwargs.pop('metrics_data', None)
        super().__init__(*args, **kwargs)

        if metrics_data:
            all_characters = metrics_data.get('all_characters_found', [])
            if all_characters:
                choices = [(char, char) for char in all_characters]
                self.fields['characters'].choices = choices