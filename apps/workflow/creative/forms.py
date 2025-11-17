# 文件路径: apps/workflow/creative/forms.py

from django import forms
from unfold.widgets import UnfoldAdminTextareaWidget
from .projects import CreativeProject


class CreativeProjectForm(forms.ModelForm):
    class Meta:
        model = CreativeProject
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # [FIX 1] 将 description 字段的行高设置为 2
        if 'description' in self.fields:
            self.fields['description'].widget = UnfoldAdminTextareaWidget(attrs={'rows': 2})