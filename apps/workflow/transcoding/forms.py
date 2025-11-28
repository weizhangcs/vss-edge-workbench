# 文件路径: apps/workflow/transcoding/forms.py

from django import forms

from apps.configuration.models import EncodingProfile


class StartTranscodingForm(forms.Form):
    profile = forms.ModelChoiceField(
        queryset=EncodingProfile.objects.none(),  # 初始时给一个空的 queryset，防止缓存问题
        label="选择转码规格",
        required=True,
        empty_label="-- 请选择一个转码配置 --",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # --- 核心修正 3: 在 __init__ 方法中动态地设置 queryset ---
        self.fields["profile"].queryset = EncodingProfile.objects.all()

        # 查找并设置默认值的逻辑
        default_profile = self.fields["profile"].queryset.filter(is_default=True).first()
        if default_profile:
            self.fields["profile"].initial = default_profile
