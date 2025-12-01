// apps/workflow/static/creative/js/factory/widgets.js

// [Global Deps]
const Logic = window.FactoryLogic;
const { React } = window;
const {
    Segmented, Slider, Select, Input, InputNumber,
    Tag, Space, Row, Col, Typography, Tooltip
} = window.antd;
const { Text } = Typography;
const { CheckableTag } = Tag;
const { TextArea } = Input;

// ... (Widget 组件 1-7 保持不变，直接复用之前的代码) ...
// 1. [增强] 策略切换器
const StrategyTypeSwitcher = ({ value, onChange, options = [], disabled, labels = {} }) => {
    const ICONS = {
        single: <span className="material-symbols-outlined text-[16px] align-middle">check_circle</span>,
        enum: <span className="material-symbols-outlined text-[16px] align-middle">checklist</span>,
        text: <span className="material-symbols-outlined text-[16px] align-middle">edit</span>,
        range: <span className="material-symbols-outlined text-[16px] align-middle">linear_scale</span>
    };
    const DEFAULT_LABELS = { single: '单选', enum: '多选', text: '自定义', range: '范围' };
    const segmentedOptions = options.map(type => ({
        value: type,
        label: labels[type] || DEFAULT_LABELS[type] || type,
        icon: ICONS[type]
    }));
    return <Segmented size="small" options={segmentedOptions} value={value} onChange={onChange} disabled={disabled} style={{ backgroundColor: '#f5f5f5' }} />;
};

const WidgetPillsMulti = ({ valueStr, onChange, options = [], disabled }) => {
    const selectedValues = new Set(Logic.parseEnum(valueStr));
    const normalizedOptions = options.map(o => (typeof o === 'object' ? o : {label: String(o), value: String(o)}));
    const toggle = (val, checked) => {
        if (checked) selectedValues.add(val); else selectedValues.delete(val);
        onChange(Array.from(selectedValues).join(', '));
    };
    return <div className={disabled ? 'opacity-60 pointer-events-none' : ''}><Space size={[8, 8]} wrap>{normalizedOptions.map(opt => (<CheckableTag key={opt.value} checked={selectedValues.has(opt.value)} onChange={checked => !disabled && toggle(opt.value, checked)} style={{ border: '1px solid #d9d9d9', padding: '2px 12px', fontSize: '12px' }}>{opt.label}</CheckableTag>))}</Space></div>;
};

const WidgetPills = ({ valueStr, onChange, options = [], disabled, singleSelect }) => {
    const normalizedOptions = options.map(o => (typeof o === 'object' ? o : {label: String(o), value: String(o)}));
    const handleChange = (val, checked) => {
        if (disabled) return;
        if (singleSelect) { if (checked) onChange(val); }
        else {
            const selectedValues = new Set(Logic.parseEnum(valueStr));
            if (checked) selectedValues.add(val); else selectedValues.delete(val);
            onChange(Array.from(selectedValues).join(', '));
        }
    };
    return <div className={disabled ? 'opacity-60 pointer-events-none' : ''}><Space size={[8, 8]} wrap>{normalizedOptions.map(opt => (<CheckableTag key={opt.value} checked={singleSelect ? opt.value === valueStr : Logic.parseEnum(valueStr).includes(opt.value)} onChange={checked => handleChange(opt.value, checked)} style={{ border: '1px solid #d9d9d9', padding: '2px 12px', fontSize: '12px' }}>{opt.label}</CheckableTag>))}</Space></div>;
};

const WidgetSegmented = ({ value, onChange, options = [], disabled }) => {
    const normalizedOptions = options.map(o => { if (typeof o === 'object') return o; return { label: String(o), value: String(o) }; });
    return <Segmented block options={normalizedOptions} value={String(value)} onChange={onChange} disabled={disabled} />;
};

const WidgetSlider = ({ value, onChange, min, max, step, unit, disabled }) => {
    return <Row gutter={12} align="middle"><Col flex="auto"><Slider min={min} max={max} step={step} value={Number(value)} onChange={onChange} disabled={disabled} /></Col><Col flex="none"><InputNumber min={min} max={max} step={step} value={value} onChange={onChange} disabled={disabled} addonAfter={unit} size="small" style={{ width: 100 }} /></Col></Row>;
};

const WidgetInput = ({ value, onChange, disabled, customConfig = {} }) => {
    const { placeholder = "请输入...", rows = 1 } = customConfig;
    const isTextArea = rows > 1;
    if (isTextArea) { return <TextArea value={value || ''} onChange={e => onChange(e.target.value)} disabled={disabled} placeholder={placeholder} autoSize={{ minRows: rows, maxRows: rows + 4 }} style={{ fontSize: '12px', lineHeight: '1.5' }} />; }
    return <Input value={value || ''} onChange={e => onChange(e.target.value)} disabled={disabled} placeholder={placeholder} prefix={<span className="material-symbols-outlined text-gray-400 text-sm">edit</span>} />;
};

const WidgetRangeGroup = ({ config, onChange, disabled, unit }) => {
    const handleChange = (field, val) => onChange({ ...config, [field]: val });
    const preview = Logic.calculateRange(config);
    return <div className={disabled ? 'opacity-60 pointer-events-none' : ''}><Space.Compact block><InputNumber prefix="Min" value={config.min} onChange={v => handleChange('min', v)} style={{ width: '33%' }} /><InputNumber prefix="Max" value={config.max} onChange={v => handleChange('max', v)} style={{ width: '33%' }} /><InputNumber prefix="Step" value={config.step} onChange={v => handleChange('step', v)} style={{ width: '34%' }} /></Space.Compact><div style={{ marginTop: 8, fontSize: 12, color: '#8c8c8c', display: 'flex', justifyContent: 'space-between' }}><Space size={4} wrap><span>预览 ({preview.length}):</span>{preview.slice(0, 8).map((v, i) => (<Tag key={i} bordered={false} style={{marginRight: 0}}>{v}{unit}</Tag>))}{preview.length > 8 && <span>...</span>}</Space></div></div>;
};

// 8. 配置行 (Controller)
const ConfigRow = ({ fieldKey, field, config, onConfigChange, onTypeChange, isLocked }) => {
    const supportedTypes = field.supported_types || ['single'];

    // [Clean Logic] 仅根据 Config 配置决定数据源
    let unit = field.unit || '';
    let effectiveOptions = field.options;

    if (fieldKey === 'speaking_rate') {
        const assetLang = window.SERVER_DATA?.assets?.source_language || 'zh-CN';
        const isEnglish = String(assetLang).toLowerCase().includes('en');

        if (isEnglish) {
            // 严格读取配置，不使用 Hardcoded Fallback
            if (field.options_en) effectiveOptions = field.options_en;
            if (field.unit_en) unit = field.unit_en;

            // [Auto Correct] 如果 Config 里有英文配置，但当前 Value 仍是中文默认值，则自动修正
            if (field.options_en) {
                const currentVal = String(config.value);
                const isValidOption = effectiveOptions.some(o => String(o.value) === currentVal);

                // 如果当前值无效（例如 4.2 不在 2.2/2.5/3.0 中），则修正为标准值
                if (!isValidOption) {
                    const stdOpt = effectiveOptions[1] || effectiveOptions[0];
                    // 使用 setTimeout 避免 React 渲染周期冲突
                    setTimeout(() => onConfigChange({...config, value: stdOpt.value}), 0);
                }
            }
        }
    }

    const typeAliases = field.type_aliases || {};
    const activeUiType = Object.keys(typeAliases).find(key => typeAliases[key] === config.type) || config.type;

    const handleTypeSwitch = (uiType) => {
        const actualDataType = typeAliases[uiType] || uiType;
        let newConfig = { ...config, type: actualDataType };

        // [自动单选]
        if (uiType === 'single' && effectiveOptions?.length === 1) {
            const opt = effectiveOptions[0];
            newConfig.value = typeof opt === 'object' ? opt.value : String(opt);
        }
        onConfigChange(newConfig);
    };

    const renderWidget = () => {
        if (activeUiType === 'text') {
            return <WidgetInput
                key={`${fieldKey}_text`}
                value={config.value}
                onChange={v => onConfigChange({...config, value: v})}
                disabled={isLocked}
                customConfig={field.customConfig}
            />;
        }

        if (activeUiType === 'range') {
            return <WidgetRangeGroup config={config} onChange={onConfigChange} disabled={isLocked} unit={unit} />;
        }

        if (activeUiType === 'enum') {
            return <WidgetPillsMulti valueStr={config.values_str} options={effectiveOptions} onChange={v => onConfigChange({...config, values_str: v})} disabled={isLocked} />;
        }

        if (activeUiType === 'single') {
            // 使用 effectiveOptions 渲染
            if (field.widget === 'pills') {
                 return <WidgetPills valueStr={config.value} options={effectiveOptions} onChange={v => onConfigChange({...config, value: v})} disabled={isLocked} singleSelect={true} />;
            }
            if (field.widget === 'segmented' || field.widget === 'speed_preset') {
                return <WidgetSegmented value={config.value} options={effectiveOptions} onChange={v => onConfigChange({...config, value: v})} disabled={isLocked} />;
            }
            if (field.widget === 'slider') {
                return <WidgetSlider value={config.value} min={field.min} max={field.max} step={field.step} unit={unit} onChange={v => onConfigChange({...config, value: v})} disabled={isLocked} />;
            }
            return <WidgetPills valueStr={config.value} options={effectiveOptions} onChange={v => onConfigChange({...config, value: v})} disabled={isLocked} singleSelect={true} />;
        }
    };

    return (
        <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Space size={4} align="center">
                    <Text strong style={{ fontSize: 13 }}>{field.label}</Text>
                    <Tooltip title={field.desc}>
                        <span className="material-symbols-outlined text-gray-400 text-sm cursor-help">help</span>
                    </Tooltip>
                </Space>
                <StrategyTypeSwitcher
                    value={activeUiType}
                    onChange={handleTypeSwitch}
                    options={supportedTypes}
                    labels={field.type_labels}
                    isNumeric={field.is_numeric}
                    disabled={isLocked}
                />
            </div>
            {renderWidget()}
        </div>
    );
};

window.FactoryWidgets = {
    ConfigRow,
    WidgetPills,
    WidgetSegmented,
    WidgetSlider,
    WidgetInput,
    WidgetRangeGroup
};