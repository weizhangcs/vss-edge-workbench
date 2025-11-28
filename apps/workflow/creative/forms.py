# 文件路径: apps/workflow/creative/forms.py

from django import forms
from unfold.widgets import UnfoldAdminTextareaWidget, UnfoldAdminTextInputWidget, UnfoldAdminSelectWidget, UnfoldAdminIntegerFieldWidget
from .projects import CreativeProject
from apps.workflow.inference.projects import InferenceProject


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
    步骤 1：解说词生成配置表单 (Narration V3 - v1.2.0-alpha.3+)
    严格对齐 VSS Cloud API 文档。
    """

    # --- 1. 核心选项定义 ---
    NARRATIVE_FOCUS_CHOICES = [
        ('romantic_progression', '感情线 (Romantic Progression)'),
        ('business_success', '事业/复仇线 (Business/Revenge)'),
        ('suspense_reveal', '悬疑解密 (Suspense Reveal)'),
        ('character_growth', '人物成长 (Character Growth)'),
        ('general', '通用剧情概览 (General)'),
        ('custom', '★ 自定义意图 (Custom)'),
    ]

    STYLE_CHOICES = [
        ('humorous', '幽默吐槽 (Humorous)'),
        ('emotional', '深情电台 (Emotional)'),
        ('suspense', '悬疑惊悚 (Suspense)'),
        ('objective', '客观纪录 (Objective)'),
        ('custom', '★ 自定义人设 (Custom)'),
    ]

    PERSPECTIVE_CHOICES = [
        ('third_person', '上帝视角 (Third Person)'),
        ('first_person', '角色第一人称 (First Person)'),
    ]

    # 基于文档 3.1 章节
    TOLERANCE_STRATEGIES = [
        ('-0.15', '强制留白 (Strict -15%) - 适合纯解说'),
        ('0.0', '严格对齐 (Standard) - 默认'),
        ('0.20', '允许溢出 (Loose +20%) - 适合混剪'),
    ]

    # --- 2. 创作控制参数 (Control Params) ---

    narrative_focus = forms.ChoiceField(
        label="叙事焦点",
        choices=NARRATIVE_FOCUS_CHOICES,
        initial='romantic_progression',
        widget=UnfoldAdminSelectWidget,
    )

    custom_narrative_prompt = forms.CharField(
        label="[自定义] 焦点 Prompt",
        required=False,
        widget=UnfoldAdminTextareaWidget(attrs={'rows': 2, 'placeholder': '例：深度挖掘《{asset_name}》中...'}),
        help_text="仅当叙事焦点选择“自定义”时生效。"
    )

    style = forms.ChoiceField(
        label="解说风格",
        choices=STYLE_CHOICES,
        initial='humorous',
        widget=UnfoldAdminSelectWidget,
    )

    custom_style_prompt = forms.CharField(
        label="[自定义] 风格 Prompt",
        required=False,
        widget=UnfoldAdminTextareaWidget(attrs={'rows': 2, 'placeholder': '例：你是一个毒舌影评人...'}),
        help_text="仅当解说风格选择“自定义”时生效。"
    )

    # 视角设定
    perspective = forms.ChoiceField(
        label="叙述视角",
        choices=PERSPECTIVE_CHOICES,
        initial='third_person',
        widget=UnfoldAdminSelectWidget
    )

    perspective_character = forms.CharField(
        label="视角角色名",
        required=False,
        widget=UnfoldAdminTextInputWidget,
        help_text="<span class='text-red-500'>必填：</span> 若选择“角色第一人称”，必须在此指定角色名称（如“车小小”）。"
    )

    # 剧情范围
    scope_start = forms.IntegerField(
        label="起始集数", initial=1, min_value=1, widget=UnfoldAdminIntegerFieldWidget,
    )
    scope_end = forms.IntegerField(
        label="结束集数", initial=5, min_value=1, widget=UnfoldAdminIntegerFieldWidget,
    )

    # 角色聚焦
    character_focus = forms.CharField(
        label="聚焦角色 (逗号分隔)",
        required=False,
        widget=UnfoldAdminTextInputWidget,
        help_text="例：车小小, 楚昊轩。留空则关注所有主要角色。"
    )

    # --- 3. 核心服务参数 (Service Params) ---

    target_duration_minutes = forms.IntegerField(
        label="目标时长 (分钟)",
        initial=3,
        min_value=1,
        max_value=30,
        widget=UnfoldAdminIntegerFieldWidget
    )

    overflow_tolerance = forms.ChoiceField(
        label="时长策略 (Tolerance)",
        choices=TOLERANCE_STRATEGIES,
        initial='0.0',  # 文档默认值
        widget=UnfoldAdminSelectWidget,
        help_text="0.0为严格对齐，负值预留空隙，正值允许溢出。"
    )

    speaking_rate = forms.DecimalField(
        label="语速标准 (字/秒)",
        initial=4.2,  # 文档建议中文默认值
        max_digits=3,
        decimal_places=1,
        widget=UnfoldAdminIntegerFieldWidget,
        help_text="用于估算文案朗读时长。中文建议 4.2。"
    )

    rag_top_k = forms.IntegerField(
        label="RAG 检索数量",
        initial=50,  # 文档默认值
        widget=UnfoldAdminIntegerFieldWidget,
        help_text="建议 50-100。"
    )


class DubbingConfigurationForm(forms.Form):
    """
    步骤 2：配音生成配置表单 (Dubbing V2)
    """
    TEMPLATE_CHOICES = [
        ('chinese_paieas_replication', '标准解说音色 (推荐)'),
        #('male_deep', '深沉男声'),
        #('female_sweet', '甜美得力'),
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

class BatchCreationForm(forms.Form):
    """
    批量创作编排器的配置表单。
    """
    inference_project = forms.ModelChoiceField(
        #queryset=InferenceProject.objects.filter(status='COMPLETED'),  # 必须是已完成推理的项目
        queryset=InferenceProject.objects.all(),
        label="源推理项目 (Source)",
        required=True,
        widget=UnfoldAdminSelectWidget,
        help_text="选择基于哪个推理结果（蓝图/画像）进行二创。"
    )

    count = forms.IntegerField(
        label="生成数量 (Count)",
        initial=5,
        min_value=1,
        max_value=50,
        widget=UnfoldAdminIntegerFieldWidget
    )

    # --- 以下为可选参数，不填则随机 ---

    narrative_focus = forms.ChoiceField(
        label="叙事焦点 (可选)",
        choices=[('', '🎲 [随机] 由系统自动分配')] + NarrationConfigurationForm.NARRATIVE_FOCUS_CHOICES,
        required=False,
        widget=UnfoldAdminSelectWidget
    )

    style = forms.ChoiceField(
        label="解说风格 (可选)",
        choices=[('', '🎲 [随机] 由系统自动分配')] + NarrationConfigurationForm.STYLE_CHOICES,
        required=False,
        widget=UnfoldAdminSelectWidget
    )

    # 配音模板：根据您的要求，这里只显示推荐的一个，且必选（或者默认选中且隐藏其他）
    # 为了简单，我们直接写死默认值，UI上可以显示为 Readonly 或者单选项
    template_name = forms.ChoiceField(
        label="配音模板",
        choices=[('chinese_paieas_replication', '标准解说音色 (推荐)')],
        initial='chinese_paieas_replication',
        widget=UnfoldAdminSelectWidget,
        help_text="当前仅开放推荐音色。"
    )