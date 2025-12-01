// apps/workflow/static/creative/js/factory_react.js

const { useState, useMemo, useEffect } = React;
const {
    Card, Segmented, Slider, Select, Input, InputNumber,
    Switch, Tag, Space, Divider, Button, Typography, Badge,
    Tooltip, Row, Col, Statistic, Radio, theme
} = antd;
const { Title, Text } = Typography;
const { CheckableTag } = Tag;

// =============================================================================
// 1. Schema & Defaults
// =============================================================================

const SCHEMA = {
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

const DEFAULTS = {
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

// =============================================================================
// 2. Logic Helpers
// =============================================================================
const Logic = {
    parseEnum: (str) => {
        if (!str) return [];
        if (Array.isArray(str)) return str;
        return str.split(/[,，]/).map(s => s.trim()).filter(s => s);
    },
    calculateRange: (conf) => {
        if (conf.type !== 'range') return [];
        let start = parseFloat(conf.min);
        let end = parseFloat(conf.max);
        let step = parseFloat(conf.step);
        if (isNaN(start) || isNaN(end) || isNaN(step) || step <= 0) return [];
        let res = [];
        let count = 0;
        for (let i = start; i <= end + 0.00001; i += step) {
            res.push(Number(i.toFixed(2)));
            count++;
            if (count > 50) break;
        }
        return res;
    },
    calcCombinations: (domainStrategy) => {
        let total = 1;
        for (let key in domainStrategy) {
            if (key === '_meta') continue;
            let c = domainStrategy[key];
            if (c.type === 'fixed') total *= 1;
            else if (c.type === 'enum') {
                let len = Logic.parseEnum(c.values_str).length;
                total *= (len > 0 ? len : 1);
            } else if (c.type === 'range') {
                let len = Logic.calculateRange(c).length;
                total *= (len > 0 ? len : 1);
            }
        }
        return total;
    },
    transformSavedConfig: (defaultStrategy, savedFlatConfig) => {
        const merged = JSON.parse(JSON.stringify(defaultStrategy));
        if (!savedFlatConfig || Object.keys(savedFlatConfig).length === 0) return merged;
        for (const key in savedFlatConfig) {
            if (Object.prototype.hasOwnProperty.call(merged, key)) {
                merged[key] = { type: 'fixed', value: String(savedFlatConfig[key]) };
            }
        }
        return merged;
    }
};

// =============================================================================
// 3. Initial State Factory (Context Aware)
// =============================================================================
const getInitialState = () => {
    const serverData = window.SERVER_DATA || {};
    console.log("[Factory] Server Context:", serverData); // Debugging

    const assets = serverData.assets || {};
    const savedConfig = serverData.initial_config || {};

    const determineMode = (domain, hasAsset) => {
        if (hasAsset) return 'LOCKED';
        if (domain === 'localize') return 'SKIP';
        return 'NEW';
    };

    const createStrategy = (domain, defaults) => {
        const hasAsset = !!assets[domain]?.exists;
        return {
            ...Logic.transformSavedConfig(defaults, savedConfig[domain]),
            _meta: {
                mode: determineMode(domain, hasAsset),
                locked_source: assets[domain]?.name,
                has_asset: hasAsset
            }
        };
    };

    return {
        narration: createStrategy('narration', DEFAULTS.narration),
        localize: createStrategy('localize', DEFAULTS.localize),
        audio: createStrategy('audio', DEFAULTS.audio),
        edit: { ...Logic.transformSavedConfig(DEFAULTS.edit, savedConfig.edit), _meta: { mode: 'NEW', has_asset: false } }
    };
};

// =============================================================================
// 4. Ant Design Widgets (The Good Stuff)
// =============================================================================

// 策略切换器 (图标按钮)
const StrategyTypeSwitcher = ({ value, onChange, isNumeric, disabled }) => {
    const options = [
        { value: 'fixed', label: '固定', icon: <span className="material-symbols-outlined text-[16px] align-middle">edit</span> },
        { value: 'enum', label: '枚举', icon: <span className="material-symbols-outlined text-[16px] align-middle">format_list_bulleted</span> }
    ];
    if (isNumeric) {
        options.push({ value: 'range', label: '范围', icon: <span className="material-symbols-outlined text-[16px] align-middle">linear_scale</span> });
    }

    return (
        <Segmented
            size="small"
            options={options}
            value={value}
            onChange={onChange}
            disabled={disabled}
            style={{ backgroundColor: '#f5f5f5' }}
        />
    );
};

// 胶囊选择器 (多选 - 使用 Antd CheckableTag)
const WidgetPillsMulti = ({ valueStr, onChange, options = [], disabled, color }) => {
    const selectedValues = new Set(Logic.parseEnum(valueStr));
    const normalizedOptions = options.map(o => (typeof o === 'string' ? {label: o, value: o} : o));

    const toggle = (val, checked) => {
        if (checked) selectedValues.add(val);
        else selectedValues.delete(val);
        onChange(Array.from(selectedValues).join(', '));
    };

    return (
        <div className={`flex flex-wrap gap-2 ${disabled ? 'opacity-60' : ''}`}>
            {normalizedOptions.map(opt => (
                <CheckableTag
                    key={opt.value}
                    checked={selectedValues.has(opt.value)}
                    onChange={checked => !disabled && toggle(opt.value, checked)}
                    style={{
                        border: '1px solid #d9d9d9',
                        padding: '2px 12px',
                        fontSize: '12px',
                        userSelect: 'none'
                    }}
                >
                    {opt.label}
                </CheckableTag>
            ))}
        </div>
    );
};

// 胶囊/分段选择器 (单选 - 使用 Antd Segmented)
const WidgetSegmented = ({ value, onChange, options = [], disabled }) => {
    const normalizedOptions = options.map(o => (typeof o === 'string' ? {label: o, value: o} : o));
    return (
        <Segmented
            block
            options={normalizedOptions}
            value={value}
            onChange={onChange}
            disabled={disabled}
            style={{ backgroundColor: '#f0f0f0' }}
        />
    );
};

// 滑块
const WidgetSlider = ({ value, onChange, min, max, step, unit, disabled }) => {
    return (
        <Row gutter={12} align="middle">
            <Col flex="auto">
                <Slider
                    min={min} max={max} step={step}
                    value={Number(value)}
                    onChange={onChange}
                    disabled={disabled}
                />
            </Col>
            <Col flex="none">
                <InputNumber
                    min={min} max={max} step={step}
                    value={value}
                    onChange={onChange}
                    disabled={disabled}
                    addonAfter={unit}
                    size="small"
                    style={{ width: 90 }}
                />
            </Col>
        </Row>
    );
};

// 范围输入组
const WidgetRangeGroup = ({ config, onChange, color, disabled }) => {
    const handleChange = (field, val) => onChange({ ...config, [field]: val });
    const preview = Logic.calculateRange(config);

    return (
        <div className={`${disabled ? 'opacity-60 pointer-events-none' : ''}`}>
            <Space.Compact block>
                <InputNumber prefix="Min" value={config.min} onChange={v => handleChange('min', v)} style={{ width: '33%' }} />
                <InputNumber prefix="Max" value={config.max} onChange={v => handleChange('max', v)} style={{ width: '33%' }} />
                <InputNumber prefix="Step" value={config.step} onChange={v => handleChange('step', v)} style={{ width: '34%' }} />
            </Space.Compact>
            <div className="mt-2 text-xs text-gray-400 flex flex-wrap gap-1">
                <span>预览 ({preview.length}):</span>
                {preview.slice(0, 8).map((v, i) => (
                    <Tag key={i} bordered={false} style={{marginRight: 0}}>{v}</Tag>
                ))}
                {preview.length > 8 && <span>...</span>}
            </div>
        </div>
    );
};


// =============================================================================
// 5. Config Row Component (Controller)
// =============================================================================

const ConfigRow = ({ fieldKey, field, config, onConfigChange, onTypeChange, isLocked }) => {

    const renderWidget = () => {
        const commonProps = { disabled: isLocked, style: { width: '100%' } };

        // --- A. Range Mode ---
        if (config.type === 'range') {
            return <WidgetRangeGroup config={config} onChange={onConfigChange} disabled={isLocked} />;
        }

        // --- B. Enum Mode (Multiselect) ---
        if (config.type === 'enum') {
            // 使用 CheckableTag (Pills)
            if (field.options) {
                return <WidgetPillsMulti valueStr={config.values_str} options={field.options} onChange={v => onConfigChange({...config, values_str: v})} disabled={isLocked} />;
            }
            // Fallback: Tags Input
            return <Select mode="tags" value={Logic.parseEnum(config.values_str)} onChange={v => onConfigChange({...config, values_str: v.join(', ')})} {...commonProps} />;
        }

        // --- C. Fixed Mode (Single Value) ---
        if (config.type === 'fixed') {
            // 1. Slider
            if (field.widget === 'slider') {
                return <WidgetSlider value={config.value} min={field.min} max={field.max} step={field.step} unit={field.unit} onChange={v => onConfigChange({...config, value: v})} disabled={isLocked} />;
            }
            // 2. Segmented (or Pills in Fixed mode = Single Select)
            if (field.widget === 'segmented' || field.widget === 'pills' || field.widget === 'speed_preset') {
                return <WidgetSegmented value={config.value} options={field.options} onChange={v => onConfigChange({...config, value: v})} disabled={isLocked} />;
            }
            // 3. Default Input
            return <Input value={config.value} onChange={e => onConfigChange({...config, value: e.target.value})} {...commonProps} />;
        }
    };

    return (
        <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Space size={4} align="center">
                    <Text strong style={{ fontSize: 13 }}>{field.label}</Text>
                    {field.is_numeric && <Tag bordered={false} style={{fontSize: 10, lineHeight: '14px', margin: 0}}>NUM</Tag>}
                    <Tooltip title={field.desc}>
                        <span className="material-symbols-outlined text-gray-400 text-sm cursor-help">help</span>
                    </Tooltip>
                </Space>

                <StrategyTypeSwitcher
                    value={config.type}
                    onChange={onTypeChange}
                    isNumeric={field.is_numeric}
                    disabled={isLocked}
                />
            </div>
            {renderWidget()}
        </div>
    );
};

// =============================================================================
// 6. Strategy Group Card (The 4-State Switcher)
// =============================================================================

const ModeSwitcher = ({ hasAsset, mode, onChange }) => {
    const options = hasAsset
        ? [
            { label: '锁定 (复用)', value: 'LOCKED', icon: <span className="material-symbols-outlined text-sm align-middle">lock</span> },
            { label: '二次创作', value: 'RECREATE', icon: <span className="material-symbols-outlined text-sm align-middle">sync</span> }
          ]
        : [
            { label: '跳过', value: 'SKIP', icon: <span className="material-symbols-outlined text-sm align-middle">skip_next</span> },
            { label: '新增', value: 'NEW', icon: <span className="material-symbols-outlined text-sm align-middle">add</span> }
          ];

    // 根据状态显示不同的颜色主题
    const isGreen = mode === 'LOCKED';
    const isBlue = mode === 'NEW';

    return (
        <Segmented
            options={options}
            value={mode}
            onChange={onChange}
            style={{
                backgroundColor: isGreen ? '#f6ffed' : (isBlue ? '#e6f7ff' : '#f5f5f5'),
                border: isGreen ? '1px solid #b7eb8f' : (isBlue ? '1px solid #91caff' : '1px solid #d9d9d9')
            }}
        />
    );
};

const StrategyGroupCard = ({ stepNum, title, groups, domain, badgeColor, strategyData, onUpdate, metaData, onModeChange }) => {
    const { mode, locked_source, has_asset } = metaData || {};
    const isLocked = mode === 'LOCKED';
    const isSkipped = mode === 'SKIP';

    const showForm = mode !== 'SKIP';
    const formDisabled = isLocked;

    return (
        <Card
            title={
                <Space>
                    <span className="material-symbols-outlined" style={{ color: isLocked ? '#52c41a' : '#8c8c8c' }}>
                        {isSkipped ? 'do_not_disturb_on' : (isLocked ? 'lock' : 'edit_square')}
                    </span>
                    <Text strong style={{ color: isSkipped ? '#bfbfbf' : undefined, textDecoration: isSkipped ? 'line-through' : undefined }}>
                        Step {stepNum}: {title}
                    </Text>
                    <Tag color={isSkipped ? 'default' : badgeColor}>{domain.toUpperCase()}</Tag>
                </Space>
            }
            extra={
                <ModeSwitcher hasAsset={has_asset} mode={mode} onChange={onModeChange} />
            }
            style={{ marginBottom: 24, borderColor: isLocked ? '#b7eb8f' : undefined }}
            headStyle={{ background: isLocked ? '#f6ffed' : (isSkipped ? '#fafafa' : '#fff') }}
            bodyStyle={{
                background: isLocked ? '#fcfcfc' : '#fff',
                opacity: isLocked ? 0.8 : 1,
                transition: 'opacity 0.3s'
            }}
            size="small"
        >
            {showForm && (
                <>
                    {isLocked && locked_source && (
                        <div style={{ marginBottom: 24, padding: '8px 12px', background: 'rgba(82, 196, 26, 0.05)', border: '1px dashed #b7eb8f', borderRadius: 6, color: '#389e0d', fontSize: 12, display: 'flex', alignItems: 'center' }}>
                            <span className="material-symbols-outlined text-sm" style={{marginRight: 8}}>verified</span>
                            已锁定母本产出物: <Text code style={{marginLeft: 4}}>{locked_source}</Text>
                        </div>
                    )}

                    <Row gutter={48}>
                        <Col xs={24} md={12}>
                            <Divider orientation="left" style={{marginTop: 0, fontSize: 12, color: '#8c8c8c'}}>内容设定</Divider>
                            {Object.entries(groups.content || {}).map(([key, field]) => (
                                <ConfigRow key={key} fieldKey={key} field={field}
                                    config={strategyData[key] || {type: 'fixed', value: ''}}
                                    isLocked={formDisabled} badgeColor={badgeColor}
                                    onConfigChange={(newConf) => onUpdate(key, newConf)}
                                    onTypeChange={(newType) => onUpdate(key, { ...strategyData[key], type: newType })}
                                />
                            ))}
                        </Col>
                        <Col xs={24} md={12}>
                            <Divider orientation="left" style={{marginTop: 0, fontSize: 12, color: '#8c8c8c'}}>生成限制</Divider>
                            {Object.entries(groups.constraints || {}).map(([key, field]) => (
                                <ConfigRow key={key} fieldKey={key} field={field}
                                    config={strategyData[key] || {type: 'fixed', value: ''}}
                                    isLocked={formDisabled} badgeColor={badgeColor}
                                    onConfigChange={(newConf) => onUpdate(key, newConf)}
                                    onTypeChange={(newType) => onUpdate(key, { ...strategyData[key], type: newType })}
                                />
                            ))}
                        </Col>
                    </Row>
                </>
            )}

            {isSkipped && (
                <div style={{ padding: 24, textAlign: 'center', color: '#bfbfbf' }}>
                    此步骤已跳过，不产生任务。
                </div>
            )}
        </Card>
    );
};

// =============================================================================
// 7. Main App Entry
// =============================================================================
const FactoryApp = () => {
    const [strategy, setStrategy] = useState(getInitialState);

    const updateDomain = (domain, key, newConfig) => {
        setStrategy(prev => ({ ...prev, [domain]: { ...prev[domain], [key]: newConfig } }));
    };

    const changeMode = (domain, newMode) => {
        setStrategy(prev => ({
            ...prev,
            [domain]: { ...prev[domain], _meta: { ...prev[domain]._meta, mode: newMode } }
        }));
    };

    const groupFields = (schemaDomain) => {
        const groups = { content: {}, constraints: {} };
        for (const [key, field] of Object.entries(schemaDomain)) {
            const g = field.group || 'content';
            if (!groups[g]) groups[g] = {};
            groups[g][key] = field;
        }
        return groups;
    };

    const getCount = (domain) => {
        const mode = strategy[domain]?._meta?.mode;
        if (mode === 'LOCKED') return 1;
        if (mode === 'SKIP') return 1;
        return Logic.calcCombinations(strategy[domain]);
    };

    const counts = {
        narration: getCount('narration'),
        localize: getCount('localize'),
        audio: getCount('audio'),
        edit: getCount('edit'),
    };
    const totalCombinations = counts.narration * counts.localize * counts.audio * counts.edit;

    const cleanStrategyJson = useMemo(() => JSON.stringify({
        strategy_version: "3.0",
        source_project_id: window.SERVER_DATA?.project_id,
        config: strategy,
        meta: { total_jobs: totalCombinations }
    }, null, 2), [strategy, totalCombinations]);

    return (
        <Row gutter={24}>
            <Col span={18}>
                <StrategyGroupCard stepNum="1" title="解说词参数" domain="narration" badgeColor="geekblue"
                    groups={groupFields(SCHEMA.narration)}
                    strategyData={strategy.narration}
                    metaData={strategy.narration._meta}
                    onModeChange={(m) => changeMode('narration', m)}
                    onUpdate={(k, v) => updateDomain('narration', k, v)} />

                <StrategyGroupCard stepNum="1.5" title="本地化参数" domain="localize" badgeColor="magenta"
                    groups={groupFields(SCHEMA.localize)}
                    strategyData={strategy.localize}
                    metaData={strategy.localize._meta}
                    onModeChange={(m) => changeMode('localize', m)}
                    onUpdate={(k, v) => updateDomain('localize', k, v)} />

                 <StrategyGroupCard stepNum="2" title="配音参数" domain="audio" badgeColor="purple"
                    groups={groupFields(SCHEMA.audio)}
                    strategyData={strategy.audio}
                    metaData={strategy.audio._meta}
                    onModeChange={(m) => changeMode('audio', m)}
                    onUpdate={(k, v) => updateDomain('audio', k, v)} />
            </Col>
            <Col span={6}>
                 <div className="sticky top-6">
                    <Card title="生产预览" bordered={false} className="shadow-lg">
                        <Statistic title="总生成任务" value={totalCombinations} suffix="个" valueStyle={{ color: '#3f8600', fontWeight: 'bold' }} />
                        <Divider />
                        <Space direction="vertical" size="small" style={{width: '100%'}}>
                            {Object.keys(counts).map(k => (
                                <div key={k} style={{display:'flex', justifyContent:'space-between'}}>
                                    <Text type="secondary">{k}</Text>
                                    <Text strong>{counts[k]}</Text>
                                </div>
                            ))}
                        </Space>
                        <Button type="primary" size="large" block style={{marginTop: 20}} icon={<span className="material-symbols-outlined align-middle" style={{fontSize:18}}>rocket_launch</span>}>
                            生成并入队
                        </Button>
                    </Card>
                    <Card size="small" title="Payload" style={{marginTop: 16}} bodyStyle={{padding: 0}}>
                         <pre className="custom-scrollbar text-[10px] text-green-600 font-mono overflow-auto h-64 p-3 bg-gray-50 m-0">{cleanStrategyJson}</pre>
                    </Card>
                </div>
            </Col>
        </Row>
    );
};

const rootNode = document.getElementById('react-root');
if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(<FactoryApp />);
}