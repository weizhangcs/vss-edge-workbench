# 文件路径: apps/workflow/creative/forms.py

from django import forms
from unfold.widgets import (
    UnfoldAdminIntegerFieldWidget,
    UnfoldAdminSelectWidget,
    UnfoldAdminTextareaWidget,
    UnfoldAdminTextInputWidget,
)

from apps.workflow.inference.projects import InferenceProject

from .projects import CreativeProject


class CreativeProjectForm(forms.ModelForm):
    class Meta:
        model = CreativeProject
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # [FIX 1] 将 description 字段的行高设置为 2
        if "description" in self.fields:
            self.fields["description"].widget = UnfoldAdminTextareaWidget(attrs={"rows": 2})


class NarrationConfigurationForm(forms.Form):
    """
    步骤 1：解说词生成配置表单 (Narration V3 - v1.2.0-alpha.3+)
    严格对齐 VSS Cloud API 文档。
    """

    # --- 1. 核心选项定义 ---
    NARRATIVE_FOCUS_CHOICES = [
        ("romantic_progression", "感情线 (Romantic Progression)"),
        ("business_success", "事业/复仇线 (Business/Revenge)"),
        ("suspense_reveal", "悬疑解密 (Suspense Reveal)"),
        ("character_growth", "人物成长 (Character Growth)"),
        ("general", "通用剧情概览 (General)"),
        ("custom", "★ 自定义意图 (Custom)"),
    ]

    STYLE_CHOICES = [
        ("humorous", "幽默吐槽 (Humorous)"),
        ("emotional", "深情电台 (Emotional)"),
        ("suspense", "悬疑惊悚 (Suspense)"),
        ("objective", "客观纪录 (Objective)"),
        ("custom", "★ 自定义人设 (Custom)"),
    ]

    PERSPECTIVE_CHOICES = [
        ("third_person", "上帝视角 (Third Person)"),
        ("first_person", "角色第一人称 (First Person)"),
    ]

    # 基于文档 3.1 章节
    TOLERANCE_STRATEGIES = [
        ("-0.15", "强制留白 (Strict -15%) - 适合纯解说"),
        ("0.0", "严格对齐 (Standard) - 默认"),
        ("0.20", "允许溢出 (Loose +20%) - 适合混剪"),
    ]

    # --- 2. 创作控制参数 (Control Params) ---

    narrative_focus = forms.ChoiceField(
        label="叙事焦点",
        choices=NARRATIVE_FOCUS_CHOICES,
        initial="romantic_progression",
        widget=UnfoldAdminSelectWidget,
    )

    custom_narrative_prompt = forms.CharField(
        label="[自定义] 焦点 Prompt",
        required=False,
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 2, "placeholder": "例：深度挖掘《{asset_name}》中..."}),
        help_text="仅当叙事焦点选择“自定义”时生效。",
    )

    style = forms.ChoiceField(
        label="解说风格",
        choices=STYLE_CHOICES,
        initial="humorous",
        widget=UnfoldAdminSelectWidget,
    )

    custom_style_prompt = forms.CharField(
        label="[自定义] 风格 Prompt",
        required=False,
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 2, "placeholder": "例：你是一个毒舌影评人..."}),
        help_text="仅当解说风格选择“自定义”时生效。",
    )

    # 视角设定
    perspective = forms.ChoiceField(
        label="叙述视角", choices=PERSPECTIVE_CHOICES, initial="third_person", widget=UnfoldAdminSelectWidget
    )

    perspective_character = forms.CharField(
        label="视角角色名",
        required=False,
        widget=UnfoldAdminTextInputWidget,
        help_text="<span class='text-red-500'>必填：</span> 若选择“角色第一人称”，必须在此指定角色名称（如“车小小”）。",
    )

    # 剧情范围
    scope_start = forms.IntegerField(
        label="起始集数",
        initial=1,
        min_value=1,
        widget=UnfoldAdminIntegerFieldWidget,
    )
    scope_end = forms.IntegerField(
        label="结束集数",
        initial=5,
        min_value=1,
        widget=UnfoldAdminIntegerFieldWidget,
    )

    # 角色聚焦
    character_focus = forms.CharField(
        label="聚焦角色 (逗号分隔)", required=False, widget=UnfoldAdminTextInputWidget, help_text="例：车小小, 楚昊轩。留空则关注所有主要角色。"
    )

    # --- 3. 核心服务参数 (Service Params) ---

    target_duration_minutes = forms.IntegerField(
        label="目标时长 (分钟)", initial=3, min_value=1, max_value=30, widget=UnfoldAdminIntegerFieldWidget
    )

    overflow_tolerance = forms.ChoiceField(
        label="时长策略 (Tolerance)",
        choices=TOLERANCE_STRATEGIES,
        initial="0.0",  # 文档默认值
        widget=UnfoldAdminSelectWidget,
        help_text="0.0为严格对齐，负值预留空隙，正值允许溢出。",
    )

    speaking_rate = forms.DecimalField(
        label="语速标准 (字/秒)",
        initial=4.2,  # 文档建议中文默认值
        max_digits=3,
        decimal_places=1,
        widget=UnfoldAdminIntegerFieldWidget,
        help_text="用于估算文案朗读时长。中文建议 4.2。",
    )

    rag_top_k = forms.IntegerField(
        label="RAG 检索数量", initial=50, widget=UnfoldAdminIntegerFieldWidget, help_text="建议 50-100。"  # 文档默认值
    )


class DubbingConfigurationForm(forms.Form):
    """
    步骤 2：配音生成配置表单 (Dubbing V2)
    """

    # [新增] 脚本源选择
    SOURCE_SCRIPT_CHOICES = [
        ("master", "🎙️ 中文母本 (Narration Script)"),
        ("localized", "🌍 本地化/译本 (Localized Script)"),
    ]

    source_script_type = forms.ChoiceField(
        label="配音脚本源",
        choices=SOURCE_SCRIPT_CHOICES,
        initial="master",
        widget=UnfoldAdminSelectWidget,
        help_text="选择要对哪个脚本进行配音。若选择译本，请确保已完成“多语言分发”步骤。",
    )

    # 策略模板选择
    TEMPLATE_CHOICES = [
        ("chinese_gemini_emotional", "Google Gemini (情感/多语言/推荐)"),
        ("chinese_paieas_replication", "Aliyun CosyVoice (复刻/中文传统)"),
    ]

    # Google Gemini 人设
    VOICE_CHOICES = [
        ("Puck", "Puck (幽默/男)"),
        ("Charon", "Charon (深沉/男)"),
        ("Kore", "Kore (冷静/女)"),
        ("Fenrir", "Fenrir (激动/男)"),
        ("Aoede", "Aoede (明快/女)"),
    ]

    # 标准语言代码
    LANG_CHOICES = [
        ("cmn-CN", "中文 (Mandarin)"),
        ("en-US", "英语 (English US)"),
        ("fr-FR", "法语 (French)"),
    ]

    template_name = forms.ChoiceField(
        label="配音策略 (Template)",
        choices=TEMPLATE_CHOICES,
        initial="chinese_gemini_emotional",
        widget=UnfoldAdminSelectWidget,
        help_text="Google 策略支持情感指令和多语言；Aliyun 策略主要用于中文声音克隆。",
    )

    # --- Google 策略专用参数 ---
    voice_name = forms.ChoiceField(
        label="人设 (Google Only)",
        choices=VOICE_CHOICES,
        initial="Puck",
        required=False,
        widget=UnfoldAdminSelectWidget,
    )

    language_code = forms.ChoiceField(
        label="语言 (Google Only)",
        choices=LANG_CHOICES,
        initial="cmn-CN",
        required=False,
        widget=UnfoldAdminSelectWidget,
    )

    # --- 通用参数 ---
    speed = forms.DecimalField(
        label="语速 (Speed/Rate)",
        initial=1.0,
        min_value=0.5,
        max_value=2.0,
        step_size=0.1,
        widget=UnfoldAdminIntegerFieldWidget,
        help_text="标准为 1.0。对应 Google 的 speaking_rate 或 Aliyun 的 speed。",
    )

    # 这里的 Style 可以留空，留空则继承 Narration
    # STYLE_CHOICES = [
    #    ('', '--- 继承解说词风格 ---'),
    #    ('humorous', '幽默搞笑'),
    #    ('emotional', '深情治愈'),
    #    ('suspense', '悬疑紧张'),
    # ]


class LocalizeConfigurationForm(forms.Form):
    """
    [V1.2.1 新增] 本地化任务配置表单
    """

    LANG_CHOICES = [
        ("en", "英语 (English)"),
        ("zh", "中文 (Chinese)"),
        ("fr", "法语 (French)"),
    ]

    TOLERANCE_STRATEGIES = [
        ("-0.15", "强制留白 (Strict -15%)"),
        ("0.0", "严格对齐 (Standard)"),
    ]

    target_lang = forms.ChoiceField(label="目标发行语言", choices=LANG_CHOICES, initial="en", widget=UnfoldAdminSelectWidget)

    speaking_rate = forms.DecimalField(
        label="目标语言语速标准",
        initial=2.5,
        widget=UnfoldAdminIntegerFieldWidget,
        help_text="用于时长校验。建议：英文 2.5 (词/秒)，中文 4.2 (字/秒)。",
    )

    overflow_tolerance = forms.ChoiceField(
        label="时长容忍度",
        choices=TOLERANCE_STRATEGIES,
        initial="-0.15",
        widget=UnfoldAdminSelectWidget,
        help_text="翻译后的文本往往比原文长，建议预留空隙。",
    )


class BatchCreationForm(forms.Form):
    """
    批量创作编排器的配置表单。
    """

    inference_project = forms.ModelChoiceField(
        # queryset=InferenceProject.objects.filter(status='COMPLETED'),  # 必须是已完成推理的项目
        queryset=InferenceProject.objects.all(),
        label="源推理项目 (Source)",
        required=True,
        widget=UnfoldAdminSelectWidget,
        help_text="选择基于哪个推理结果（蓝图/画像）进行二创。",
    )

    count = forms.IntegerField(
        label="生成数量 (Count)", initial=5, min_value=1, max_value=50, widget=UnfoldAdminIntegerFieldWidget
    )

    # --- 以下为可选参数，不填则随机 ---

    narrative_focus = forms.ChoiceField(
        label="叙事焦点 (可选)",
        choices=[("", "🎲 [随机] 由系统自动分配")] + NarrationConfigurationForm.NARRATIVE_FOCUS_CHOICES,
        required=False,
        widget=UnfoldAdminSelectWidget,
    )

    style = forms.ChoiceField(
        label="解说风格 (可选)",
        choices=[("", "🎲 [随机] 由系统自动分配")] + NarrationConfigurationForm.STYLE_CHOICES,
        required=False,
        widget=UnfoldAdminSelectWidget,
    )

    # 配音模板：根据您的要求，这里只显示推荐的一个，且必选（或者默认选中且隐藏其他）
    # 为了简单，我们直接写死默认值，UI上可以显示为 Readonly 或者单选项
    template_name = forms.ChoiceField(
        label="配音模板",
        choices=[("chinese_paieas_replication", "标准解说音色 (推荐)")],
        initial="chinese_paieas_replication",
        widget=UnfoldAdminSelectWidget,
        help_text="当前仅开放推荐音色。",
    )
