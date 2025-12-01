// [FIXED] 移除 import/export，使用全局变量
const Logic = window.FactoryLogic;
const { React } = window;
const {
    Segmented, Slider, Select, Input, InputNumber,
    Tag, Space, Row, Col, Typography, Tooltip
} = window.antd;
const { Text } = Typography;
const { CheckableTag } = Tag;

// 1. 策略切换器 (图标按钮)
// [FIXED] 移除 export
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

// 2. 胶囊选择器 (多选)
// [FIXED] 移除 export
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
// [FIXED] 移除 export
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
// [FIXED] 移除 export
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
// [FIXED] 移除 export
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

// 6. 普通输入
// [FIXED] 移除 export
const WidgetInput = ({ value, onChange, disabled }) => (
    <Input value={value || ''} onChange={e => onChange(e.target.value)} disabled={disabled} />
);

// 7. 范围输入组
// [FIXED] 移除 export
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
// [FIXED] 移除 export
const ConfigRow = ({ field, config, onConfigChange, onTypeChange, isLocked, badgeColor }) => {
    const commonProps = { disabled: isLocked, style: { width: '100%' } };

    const renderWidget = () => {
        // Range Mode
        if (config.type === 'range') return <WidgetRangeGroup config={config} onChange={onConfigChange} disabled={isLocked} />;

        // Enum Mode
        if (config.type === 'enum') {
            if (field.options) {
                return <WidgetPillsMulti valueStr={config.values_str} options={field.options} onChange={v => onConfigChange({...config, values_str: v})} disabled={isLocked} />;
            }
            return <Select mode="tags" value={Logic.parseEnum(config.values_str)} onChange={v => onConfigChange({...config, values_str: v.join(', ')})} {...commonProps} />;
        }

        // Fixed Mode
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
                <StrategyTypeSwitcher value={config.type} onChange={onTypeChange} isNumeric={field.is_numeric} disabled={isLocked} />
            </div>
            {renderWidget()}
        </div>
    );
};

// [FIXED] 挂载到 window 对象
window.FactoryWidgets = {
    ConfigRow,
    WidgetPills,
    WidgetSegmented,
    WidgetSlider,
    WidgetInput,
    WidgetRangeGroup
};