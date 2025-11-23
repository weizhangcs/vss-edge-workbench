# 文件路径: apps/workflow/creative/forms.py

from django import forms
from unfold.widgets import UnfoldAdminTextareaWidget, UnfoldAdminTextInputWidget, UnfoldAdminSelectWidget, UnfoldAdminIntegerFieldWidget
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


class NarrationConfigurationForm(forms.Form):
    """
    步骤 1：解说词生成配置表单 (Narration V2)
    """
    NARRATIVE_FOCUS_CHOICES = [
        ('romantic_progression', '情感推进 (Romantic)'),
        ('career_growth', '搞事业/成长 (Career)'),
        ('suspense_thriller', '悬疑/反转 (Suspense)'),
        ('dramatic_conflict', '强冲突/撕逼 (Conflict)'),
    ]

    STYLE_CHOICES = [
        ('humorous', '幽默搞笑 (Humorous)'),
        ('emotional', '深情治愈 (Emotional)'),
        ('suspense', '悬疑紧张 (Suspense)'),
        ('straight', '直白叙述 (Straight)'),
    ]

    PERSPECTIVE_CHOICES = [
        ('third_person', '上帝视角 (第三人称)'),
        ('first_person', '角色沉浸 (第一人称)'),
    ]

    narrative_focus = forms.ChoiceField(
        label="叙事焦点",
        choices=NARRATIVE_FOCUS_CHOICES,
        initial='romantic_progression',
        widget=UnfoldAdminSelectWidget,
        help_text="决定解说词的侧重点。"
    )

    # 这是一个简化的范围输入，实际可能需要更复杂的组件
    scope_start = forms.IntegerField(
        label="起始集数",
        initial=1,
        min_value=1,
        widget=UnfoldAdminIntegerFieldWidget,
        help_text="剧情范围开始"
    )
    scope_end = forms.IntegerField(
        label="结束集数",
        initial=5,
        min_value=1,
        widget=UnfoldAdminIntegerFieldWidget,
        help_text="剧情范围结束"
    )

    style = forms.ChoiceField(
        label="解说风格",
        choices=STYLE_CHOICES,
        initial='humorous',
        widget=UnfoldAdminSelectWidget,
        help_text="此风格将传递给后续的配音环节。"
    )

    perspective = forms.ChoiceField(
        label="叙述视角",
        choices=PERSPECTIVE_CHOICES,
        initial='third_person',
        widget=UnfoldAdminSelectWidget
    )

    target_duration_minutes = forms.IntegerField(
        label="目标时长 (分钟)",
        initial=5,
        min_value=1,
        max_value=20,
        widget=UnfoldAdminIntegerFieldWidget,
        help_text="AI 将尝试控制在这个时长附近，过长会自动触发缩写。"
    )


class DubbingConfigurationForm(forms.Form):
    """
    步骤 2：配音生成配置表单 (Dubbing V2)
    """
    TEMPLATE_CHOICES = [
        ('chinese_paieas_replication', '标准解说音色 (推荐)'),
        ('male_deep', '深沉男声'),
        ('female_sweet', '甜美得力'),
    ]

    # 这里的 Style 可以留空，留空则继承 Narration
    STYLE_CHOICES = [
        ('', '--- 继承解说词风格 ---'),
        ('humorous', '幽默搞笑'),
        ('emotional', '深情治愈'),
        ('suspense', '悬疑紧张'),
    ]

    template_name = forms.ChoiceField(
        label="配音模板",
        choices=TEMPLATE_CHOICES,
        initial='chinese_paieas_replication',
        widget=UnfoldAdminSelectWidget,
        required=True
    )

    style = forms.ChoiceField(
        label="强制风格 (可选)",
        choices=STYLE_CHOICES,
        required=False,
        widget=UnfoldAdminSelectWidget,
        help_text="如果不选，将自动使用步骤 1 中设定的风格。"
    )

    speed = forms.FloatField(
        label="语速",
        initial=1.0,
        min_value=0.5,
        max_value=2.0,
        step_size=0.1,
        widget=UnfoldAdminIntegerFieldWidget,  # 复用 Integer Widget 样式
        help_text="1.0 为标准语速，1.2 为快，0.8 为慢。"
    )

    instruct = forms.CharField(
        label="高级指令 (Instruct)",
        required=False,
        widget=UnfoldAdminTextInputWidget,
        help_text="高级用户专用，例如：'用极度夸张的语气说<|endofprompt|>'"
    )