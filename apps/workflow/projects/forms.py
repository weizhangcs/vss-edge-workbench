# 文件路径: apps/workflow/projects/forms.py

from django import forms
from ..jobs.transcodingJob import TranscodingJob

class StartTranscodingForm(forms.Form):
    profile = forms.ChoiceField(
        choices=TranscodingJob.PROFILE,
        label="选择转码规格",
        required=True,
    )