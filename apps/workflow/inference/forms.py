# 文件路径: apps/workflow/annotation/forms.py

from django import forms


class CharacterSelectionForm(forms.Form):
    """
    一个动态表单，用于在 Admin 界面中展示从角色矩阵(metrics)
    任务中返回的角色列表，并允许用户多选。
    """
    characters = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        label="请选择要识别属性的角色",
        required=True
    )

    def __init__(self, *args, **kwargs):
        """
        重写构造函数，以动态接收 metrics_data 并设置 choices。
        """
        metrics_data = kwargs.pop('metrics_data', None)
        super().__init__(*args, **kwargs)

        if metrics_data:
            all_characters = metrics_data.get('all_characters_found', [])
            if all_characters:
                choices = [(char, char) for char in all_characters]
                self.fields['characters'].choices = choices

        # 我们不再需要 FormHelper