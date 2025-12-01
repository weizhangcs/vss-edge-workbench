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
const { TextArea } = Input; // [新增] 引入 TextArea

// 1. 策略切换器
const StrategyTypeSwitcher = ({ value, onChange, isNumeric, disabled }) => {
    const options = [
        { value: 'custom', label: '自定义', icon: <span className="material-symbols-outlined text-[16px] align-middle">edit</span> }, // [恢复] 笔 = Custom
        { value: 'fixed', label: '单选', icon: <span className="material-symbols-outlined text-[16px] align-middle">check_circle</span> },
        { value: 'enum', label: '多选', icon: <span className="material-symbols-outlined text-[16px] align-middle">checklist</span> }
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

// 2. 胶囊选择器 (多选)
const WidgetPillsMulti = ({ valueStr, onChange, options = [], disabled }) => {
    const selectedValues = new Set(Logic.parseEnum(valueStr));
    const normalizedOptions = options.map(o => (typeof o === 'string' ? {label: o, value: o} : o));

    const toggle = (val, checked) => {
        if (checked) selectedValues.add(val);
        else selectedValues.delete(val);
        onChange(Array.from(selectedValues).join(', '));
    };

    return (
        <div className={disabled ? 'opacity-60 pointer-events-none' : ''}>
            <Space size={[8, 8]} wrap>
                {normalizedOptions.map(opt => (
                    <CheckableTag
                        key={opt.value}
                        checked={selectedValues.has(opt.value)}
                        onChange={checked => !disabled && toggle(opt.value, checked)}
                        style={{ border: '1px solid #d9d9d9', padding: '2px 12px', fontSize: '12px' }}
                    >
                        {opt.label}
                    </CheckableTag>
                ))}
            </Space>
        </div>
    );
};

// 3. 普通胶囊 (单选)
const WidgetPills = ({ valueStr, onChange, options = [], disabled, singleSelect }) => {
    const normalizedOptions = options.map(o => (typeof o === 'string' ? {label: o, value: o} : o));

    const handleChange = (val, checked) => {
        if (disabled) return;
        if (singleSelect) {
            if (checked) onChange(val);
        } else {
            const selectedValues = new Set(Logic.parseEnum(valueStr));
            if (checked) selectedValues.add(val);
            else selectedValues.delete(val);
            onChange(Array.from(selectedValues).join(', '));
        }
    };

    return (
        <div className={disabled ? 'opacity-60 pointer-events-none' : ''}>
            <Space size={[8, 8]} wrap>
                {normalizedOptions.map(opt => (
                    <CheckableTag
                        key={opt.value}
                        checked={singleSelect ? opt.value === valueStr : Logic.parseEnum(valueStr).includes(opt.value)}
                        onChange={checked => handleChange(opt.value, checked)}
                        style={{ border: '1px solid #d9d9d9', padding: '2px 12px', fontSize: '12px' }}
                    >
                        {opt.label}
                    </CheckableTag>
                ))}
                 {!singleSelect && (
                    <Input
                        size="small"
                        placeholder="+ 自定义"
                        style={{ width: 80, fontSize: 12 }}
                        onPressEnter={(e) => {
                            const val = e.target.value;
                            if(val) {
                                handleChange(val, true);
                                e.target.value = '';
                            }
                        }}
                        disabled={disabled}
                    />
                )}
            </Space>
        </div>
    );
};

// 4. 分段控制器
const WidgetSegmented = ({ value, onChange, options = [], disabled }) => {
    const normalizedOptions = options.map(o => (typeof o === 'string' ? {label: o, value: o} : o));
    return (
        <Segmented
            block
            options={normalizedOptions}
            value={value}
            onChange={onChange}
            disabled={disabled}
        />
    );
};

// 5. 滑块
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
                    style={{ width: 100 }}
                />
            </Col>
        </Row>
    );
};

// 6. [核心修复] 普通输入 (支持 TextArea)
const WidgetInput = ({ value, onChange, disabled, placeholder, isTextArea }) => {
    if (isTextArea) {
        return (
            <TextArea
                value={value || ''}
                onChange={e => onChange(e.target.value)}
                disabled={disabled}
                placeholder={placeholder}
                rows={3} // [需求] 3行高度
            />
        );
    }
    return (
        <Input
            value={value || ''}
            onChange={e => onChange(e.target.value)}
            disabled={disabled}
            placeholder={placeholder || "请输入自定义值..."}
            prefix={<span className="material-symbols-outlined text-gray-400 text-sm">edit</span>}
        />
    );
};

// 7. 范围输入组
const WidgetRangeGroup = ({ config, onChange, disabled }) => {
    const handleChange = (field, val) => onChange({ ...config, [field]: val });
    const preview = Logic.calculateRange(config);

    return (
        <div className={disabled ? 'opacity-60 pointer-events-none' : ''}>
            <Space.Compact block>
                <InputNumber prefix="Min" value={config.min} onChange={v => handleChange('min', v)} style={{ width: '33%' }} />
                <InputNumber prefix="Max" value={config.max} onChange={v => handleChange('max', v)} style={{ width: '33%' }} />
                <InputNumber prefix="Step" value={config.step} onChange={v => handleChange('step', v)} style={{ width: '34%' }} />
            </Space.Compact>
            <div style={{ marginTop: 8, fontSize: 12, color: '#8c8c8c' }}>
                <Space size={4} wrap>
                    <span>预览 ({preview.length}):</span>
                    {preview.slice(0, 8).map((v, i) => (
                        <Tag key={i} bordered={false} style={{marginRight: 0}}>{v}</Tag>
                    ))}
                    {preview.length > 8 && <span>...</span>}
                </Space>
            </div>
        </div>
    );
};

// 8. 配置行 (Controller)
const ConfigRow = ({ fieldKey, field, config, onConfigChange, onTypeChange, isLocked }) => {
    const commonProps = { disabled: isLocked, style: { width: '100%' } };

    // [核心修复] 自定义占位符映射 (您指定的文案)
    const CUSTOM_PLACEHOLDERS = {
        narrative_focus: "请描写自定义的创作思路，格式如下： 剧集“{asset_name}”中主角个人的成长弧光，性格转变的关键节点。请保留 剧集“{asset_name}”",
        style: "请描述自定义的创作的风格，格式如下： 你是一位客观冷静的纪录片解说员，语调平实，注重事实陈述。"
    };

    const renderWidget = () => {
        // A. [核心修复] Custom Mode -> TextArea
        if (config.type === 'custom') {
            const isTextArea = ['narrative_focus', 'style'].includes(fieldKey);
            const placeholder = CUSTOM_PLACEHOLDERS[fieldKey] || "请输入自定义值...";

            return <WidgetInput
                value={config.value}
                onChange={v => onConfigChange({...config, value: v})}
                disabled={isLocked}
                isTextArea={isTextArea}
                placeholder={placeholder}
            />;
        }

        // B. Range Mode
        if (config.type === 'range') return <WidgetRangeGroup config={config} onChange={onConfigChange} disabled={isLocked} />;

        // C. Enum Mode
        if (config.type === 'enum') {
            if (field.options) {
                return <WidgetPillsMulti valueStr={config.values_str} options={field.options} onChange={v => onConfigChange({...config, values_str: v})} disabled={isLocked} />;
            }
            return <Select mode="tags" value={Logic.parseEnum(config.values_str)} onChange={v => onConfigChange({...config, values_str: v.join(', ')})} {...commonProps} />;
        }

        // D. Fixed Mode
        if (config.type === 'fixed') {
            if (field.widget === 'segmented' || field.widget === 'speed_preset') {
                const opts = field.options?.map(o => (typeof o === 'string' ? {label: o, value: o} : o)) || [];
                return <WidgetSegmented value={config.value} options={opts} onChange={v => onConfigChange({...config, value: v})} disabled={isLocked} />;
            }
            if (field.widget === 'slider') {
                return <WidgetSlider value={config.value} min={field.min} max={field.max} step={field.step} unit={field.unit} onChange={v => onConfigChange({...config, value: v})} disabled={isLocked} />;
            }
            if (field.widget === 'pills') {
                 const opts = field.options?.map(o => (typeof o === 'string' ? {label: o, value: o} : o)) || [];
                 return <WidgetPills valueStr={config.value} options={opts} onChange={v => onConfigChange({...config, value: v})} disabled={isLocked} singleSelect={true} />;
            }
            return <WidgetInput value={config.value} onChange={v => onConfigChange({...config, value: v})} disabled={isLocked} />;
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
                    // [新增] 如果有 options (且不是custom/range)，才允许切固定/枚举。
                    // 这里简单处理：Custom总是可用。
                    disabled={isLocked}
                />
            </div>
            {renderWidget()}
        </div>
    );
};

// [Global Mount]
window.FactoryWidgets = {
    ConfigRow,
    WidgetPills,
    WidgetSegmented,
    WidgetSlider,
    WidgetInput,
    WidgetRangeGroup
};