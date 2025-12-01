// [FIXED] 移除 export，挂载到 window
window.FactoryConfig = window.FactoryConfig || {};

window.FactoryConfig.SCHEMA = {
    narration: {
        narrative_focus: {
            label: "叙事焦点", group: "content", widget: "pills",
            options: [
                { label: "情感递进", value: "romantic_progression" },
                { label: "商业成功", value: "business_success" },
                { label: "悬疑揭秘", value: "suspense_reveal" },
                { label: "人物成长", value: "character_growth" },
                { label: "复仇爽文", value: "revenge_plot" }
            ],
            desc: "决定故事的核心走向"
        },
        style: {
            label: "解说风格", group: "content", widget: "pills",
            options: [
                { label: "幽默", value: "humorous" },
                { label: "严肃", value: "serious" },
                { label: "悬疑", value: "suspense" },
                { label: "毒舌", value: "sarcastic" },
                { label: "深情", value: "emotional" },
                { label: "治愈", value: "healing" }
            ],
            desc: "决定文案的情感基调"
        },
        perspective: {
            label: "叙述视角", group: "content", widget: "segmented",
            options: [
                { label: "第一人称", value: "first_person" },
                { label: "第三人称", value: "third_person" }
            ],
            desc: "叙述者的身份"
        },
        target_duration_minutes: {
            label: "目标时长", group: "constraints", widget: "slider", is_numeric: true,
            min: 3, max: 15, step: 1, unit: "分",
            desc: "控制生成的篇幅"
        },
        speaking_rate: {
            label: "文案语速", group: "constraints", widget: "segmented", is_numeric: true,
            options: [
                { label: "慢 (3.5)", value: "3.5" },
                { label: "标准 (4.2)", value: "4.2" },
                { label: "快 (5.0)", value: "5.0" }
            ],
            desc: "LLM估算基准 (字/秒)"
        },
        rag_top_k: {
            label: "RAG 检索量", group: "constraints", widget: "slider", is_numeric: true,
            min: 10, max: 100, step: 10, unit: "条",
            desc: "上下文检索数量"
        }
    },
    localize: {
        target_lang: {
            label: "目标语言", group: "content", widget: "pills",
            options: [
                { label: "英语", value: "en" },
                { label: "法语", value: "fr" },
                { label: "德语", value: "de" },
                { label: "日语", value: "ja" },
                { label: "韩语", value: "ko" }
            ],
            desc: "发行目标区域"
        },
        speaking_rate: { label: "目标语速", group: "constraints", widget: "slider", min: 2.0, max: 5.0, step: 0.1, unit: "wps", is_numeric: true },
        overflow_tolerance: { label: "时长容忍", group: "constraints", widget: "segmented", options: [{label: "宽松 (0.0)", value: "0.0"}, {label: "严格 (-0.15)", value: "-0.15"}], is_numeric: true }
    },
    audio: {
        template_name: {
            label: "配音模板", group: "content", widget: "segmented",
            options: [
                { label: "Gemini (情感)", value: "chinese_gemini_emotional" },
                { label: "CosyVoice (复刻)", value: "chinese_paieas_replication" }
            ]
        },
        voice_name: {
            label: "人设选择", group: "content", widget: "pills",
            options: ["Puck", "Charon", "Kore", "Fenrir", "Aoede"],
            desc: "选择音色"
        },
        speed: {
            label: "朗读倍率", group: "constraints", widget: "slider", is_numeric: true,
            min: 0.8, max: 1.5, step: 0.1, unit: "x"
        }
    },
    edit: {
        lang: { label: "剪辑语言", group: "content", widget: "fixed_input" }
    }
};

window.FactoryConfig.DEFAULTS = {
    narration: {
        narrative_focus: { type: 'enum', values_str: 'romantic_progression, business_success' },
        style: { type: 'enum', values_str: 'humorous, emotional' },
        perspective: { type: 'fixed', value: 'third_person' },
        target_duration_minutes: { type: 'fixed', value: '6' },
        speaking_rate: { type: 'fixed', value: '4.2' },
        rag_top_k: { type: 'range', min: 50, max: 100, step: 10 }
    },
    localize: {
        target_lang: { type: 'enum', values_str: 'en, fr' },
        speaking_rate: { type: 'fixed', value: '2.5' },
        overflow_tolerance: { type: 'fixed', value: '-0.15' }
    },
    audio: {
        template_name: { type: 'fixed', value: 'chinese_gemini_emotional' },
        voice_name: { type: 'enum', values_str: 'Puck, Kore' },
        speed: { type: 'fixed', value: '1.0' }
    },
    edit: {
        lang: { type: 'fixed', value: 'zh' }
    }
};