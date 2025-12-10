# 文件路径: apps/workflow/inference/forms.py

from django import forms
from unfold.widgets import UnfoldAdminTextareaWidget

from .projects import InferenceProject


class InferenceProjectForm(forms.ModelForm):
    class Meta:
        model = InferenceProject
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "description" in self.fields:
            self.fields["description"].widget = UnfoldAdminTextareaWidget(attrs={"rows": 2})


class CharacterSelectionForm(forms.Form):
    """
    (V3.1 适配 Audit Report)
    动态表单：从 annotation_audit_report 中读取角色列表。
    """

    # 这里的 choices 会在 __init__ 中动态填充
    characters = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, label="请选择要识别属性的角色", required=True)

    def __init__(self, *args, **kwargs):
        # view 层传入的应该是完整的 audit_report_json
        audit_data = kwargs.pop("metrics_data", None)
        super().__init__(*args, **kwargs)

        choices = []
        if audit_data:
            # [适配] 新的数据结构路径
            # semantic_audit -> character_roster -> [ { "name": "..." }, ... ]
            roster = audit_data.get("semantic_audit", {}).get("character_roster", [])

            if roster:
                # 列表生成式提取名字
                # value 和 label 都设为 name
                choices = [(item.get("name"), item.get("name")) for item in roster if item.get("name")]

        self.fields["characters"].choices = choices
