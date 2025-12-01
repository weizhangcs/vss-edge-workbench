// apps/workflow/static/creative/js/factory/config.js

window.FactoryConfig = window.FactoryConfig || {};

const TYPES = {
    SINGLE: 'single',
    ENUM: 'enum',
    TEXT: 'text',
    RANGE: 'range'
};

window.FactoryConfig.SCHEMA = {
    // --- Step 1: Narration (已调优，保持不变) ---
    narration: {
        narrative_focus: {
            label: "叙事焦点", group: "content", widget: "pills",
            desc: "决定故事的核心走向",
            supported_types: [TYPES.SINGLE, TYPES.ENUM, TYPES.TEXT],
            customConfig: {
                placeholder: "请描写自定义的创作思路，格式如下： 剧集“{asset_name}”中主角个人的成长弧光，性格转变的关键节点。请保留 剧集“{asset_name}”",
                rows: 4
            },
            options: [
                { label: "情感递进", value: "romantic_progression" },
                { label: "商业成功", value: "business_success" },
                { label: "悬疑揭秘", value: "suspense_reveal" },
                { label: "人物成长", value: "character_growth" },
                { label: "复仇爽文", value: "revenge_plot" }
            ]
        },
        style: {
            label: "解说风格", group: "content", widget: "pills",
            desc: "决定文案的情感基调",
            supported_types: [TYPES.SINGLE, TYPES.ENUM, TYPES.TEXT],
            customConfig: {
                placeholder: "请描述自定义的创作的风格，格式如下： 你是一位客观冷静的纪录片解说员，语调平实，注重事实陈述。",
                rows: 4
            },
            options: [
                { label: "幽默", value: "humorous" },
                { label: "严肃", value: "serious" },
                { label: "悬疑", value: "suspense" },
                { label: "毒舌", value: "sarcastic" },
                { label: "深情", value: "emotional" },
                { label: "治愈", value: "healing" }
            ]
        },
        perspective: {
            label: "叙述视角", group: "content", widget: "segmented",
            desc: "叙述者的身份",
            supported_types: [TYPES.SINGLE, TYPES.TEXT],
            type_labels: { single: "第三人称", text: "第一人称 (指定角色)" },
            type_aliases: { text: "first_person" },
            customConfig: { placeholder: "请输入第一人称角色的名称 (支持多个，逗号分隔)...", rows: 2 },
            options: [{ label: "默认 (上帝视角)", value: "third_person" }]
        },
        scope: {
            label: "剧情范围", group: "content", widget: "range_group",
            desc: "选择使用的剧集范围",
            supported_types: [TYPES.SINGLE, TYPES.RANGE],
            type_labels: { single: "全剧模式", range: "指定集数" },
            type_aliases: { single: "full", range: "episode_range" },
            unit: "集", min: 1, max: 100, step: 1,
            options: [{ label: "全剧 (所有素材)", value: "full" }]
        },
        target_duration_minutes: {
            label: "解说词生成目标时长", group: "constraints", widget: "pills",
            is_numeric: true, unit: "分", desc: "控制生成的篇幅",
            supported_types: [TYPES.SINGLE, TYPES.ENUM, TYPES.TEXT],
            customConfig: { placeholder: "输入分钟数", rows: 1 },
            options: [3, 5, 10, 15, 20, 30]
        },
        speaking_rate: {
            label: "文案语速", group: "constraints", widget: "speed_preset",
            is_numeric: true, desc: "LLM估算基准",
            supported_types: [TYPES.SINGLE, TYPES.ENUM, TYPES.TEXT],
            customConfig: { placeholder: "输入语速数值", rows: 1 },
            options: [
                { label: "慢", value: "3.5" },
                { label: "标准", value: "4.2" },
                { label: "快", value: "5.0" }
            ]
        },
        rag_top_k: {
            label: "RAG 检索量", group: "constraints", widget: "pills",
            is_numeric: true, unit: "条", desc: "上下文检索数量",
            supported_types: [TYPES.SINGLE, TYPES.ENUM, TYPES.TEXT],
            customConfig: { placeholder: "输入检索条数 (10-200)", rows: 1 },
            options: [50, 70, 90]
        },
        overflow_tolerance: {
            label: "解说词预测时长与源素材时长对比", group: "constraints", widget: "pills",
            is_numeric: true, desc: "允许生成内容超出目标时长的比例",
            supported_types: [TYPES.SINGLE, TYPES.ENUM],
            options: [
                {label: "对齐 (0.0)", value: "0.0"},
                {label: "留白支持缩剪 (-0.15)", value: "-0.15"},
                {label: "超长支持补画面 (+0.15)", value: "0.15"}
            ]
        }
    },

    // --- Step 1.5: Localize (规范化) ---
    localize: {
        target_lang: {
            label: "目标语言", group: "content",
            widget: "pills", // 统一 UI
            desc: "发行目标区域",
            supported_types: [TYPES.SINGLE, TYPES.ENUM],
            customConfig: { placeholder: "暂不支持自定义语言", rows: 1 },
            options: [
                { label: "英语", value: "en" },
                { label: "法语", value: "fr" },
                { label: "德语", value: "de" },
                { label: "日语", value: "ja" },
                { label: "韩语", value: "ko" }
            ]
        },
        speaking_rate: {
            label: "文案语速",
            group: "constraints",
            widget: "speed_preset",
            is_numeric: true,
            desc: "LLM估算基准",
            supported_types: [TYPES.SINGLE, TYPES.ENUM, TYPES.TEXT],
            customConfig: { placeholder: "输入语速数值", rows: 1 },

            // 1. 默认/中文配置 (Char/s)
            unit: "字/秒",
            options: [
                { label: "慢 (3.5)", value: "3.5" },
                { label: "标准 (4.2)", value: "4.2" },
                { label: "快 (5.0)", value: "5.0" }
            ],

            // 2. 英文配置 (Word/s)
            unit_en: "词/秒",
            options_en: [
                { label: "慢 (2.2)", value: "2.2" },
                { label: "标准 (2.5)", value: "2.5" },
                { label: "快 (3.0)", value: "3.0" }
            ]
        },
        overflow_tolerance: {
            label: "解说词预测时长与源素材时长对比", group: "constraints", widget: "pills",
            is_numeric: true, desc: "允许生成内容超出目标时长的比例",
            supported_types: [TYPES.SINGLE, TYPES.ENUM],
            options: [
                {label: "对齐 (0.0)", value: "0.0"},
                {label: "留白支持缩剪 (-0.15)", value: "-0.15"},
                {label: "超长支持补画面 (+0.15)", value: "0.15"}
            ]
        }
    },

    // --- Step 2: Audio (规范化) ---
    audio: {
        template_name: {
            label: "配音模块", group: "content",
            widget: "pills",
            supported_types: [TYPES.SINGLE],
            customConfig: { placeholder: "选择模板", rows: 1 },
            // [修改] 仅保留 Gemini
            options: [
                { label: "Gemini (情感)", value: "chinese_gemini_emotional" }
            ]
        },
        voice_name: {
            label: "人设选择", group: "content",
            widget: "pills",
            desc: "选择音色",
            supported_types: [TYPES.SINGLE, TYPES.ENUM],
            customConfig: { placeholder: "输入自定义音色ID", rows: 1 },
            // [修改] 真实的 Gemini 音色列表
            options: [
                { label: "Puck (乐观男)", value: "Puck" },
                { label: "Charon (沉稳男)", value: "Charon" },
                { label: "Kore (干练女)", value: "Kore" },
                { label: "Fenrir (激昂男)", value: "Fenrir" },
                { label: "Aoede (轻快女)", value: "Aoede" },
                { label: "Zephyr (明快女)", value: "Zephyr" },
                { label: "Orus (坚定男)", value: "Orus" },
                { label: "Leda (少女音)", value: "Leda" },
                { label: "Enceladus (柔和男)", value: "Enceladus" }
            ]
        },
        speed: {
            label: "朗读语速", group: "constraints",
            widget: "slider",
            is_numeric: true, min: 0.8, max: 1.5, step: 0.1, unit: "x",
            supported_types: [TYPES.SINGLE, TYPES.RANGE],
            customConfig: { placeholder: "输入倍率", rows: 1 }
        }
    },

    // --- Step 3: Edit (规范化) ---
    edit: {
        lang: {
            label: "剪辑语言", group: "content",
            widget: "pills", // 统一 UI，替换 fixed_input
            supported_types: [TYPES.SINGLE],
            customConfig: { placeholder: "输入语言代码", rows: 1 },
            options: [
                { label: "中文 (默认)", value: "zh" },
                { label: "英语", value: "en" }
            ]
        }
    }
};

// [Defaults Update] 保持类型一致
window.FactoryConfig.DEFAULTS = {
    narration: {
        narrative_focus: { type: 'enum', values_str: 'romantic_progression, business_success' },
        style: { type: 'enum', values_str: 'humorous, emotional' },
        perspective: { type: 'single', value: 'third_person' },
        scope: { type: 'single', value: 'full' },
        target_duration_minutes: { type: 'single', value: '6' },
        speaking_rate: { type: 'single', value: '4.2' },
        rag_top_k: { type: 'range', min: 50, max: 100, step: 10 },
        overflow_tolerance: { type: 'single', value: '0.0' }
    },
    localize: {
        target_lang: { type: 'enum', values_str: 'en, fr' },
        speaking_rate: { type: 'single', value: '2.5' },
        overflow_tolerance: { type: 'single', value: '-0.15' }
    },
    audio: {
        template_name: { type: 'single', value: 'chinese_gemini_emotional' },
        voice_name: { type: 'enum', values_str: 'Puck, Kore' },
        speed: { type: 'single', value: '1.0' }
    },
    edit: {
        lang: { type: 'single', value: 'zh' }
    }
};