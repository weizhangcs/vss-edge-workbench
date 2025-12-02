// apps/workflow/static/creative/js/director/widgets.js

const { TYPES } = window.DirectorConfig;
const { React } = window;
const { Segmented, Slider, Input, InputNumber, Space, Row, Col, Typography, Tooltip } = window.antd;
const { Text } = Typography;

const WidgetInput = ({ value, onChange, disabled, placeholder }) => (
    <Input value={value} onChange={e => onChange(e.target.value)} disabled={disabled} placeholder={placeholder} />
);

const WidgetSegmented = ({ value, onChange, options = [], disabled }) => (
    <Segmented block options={options} value={value} onChange={onChange} disabled={disabled} />
);

const WidgetSlider = ({ value, onChange, min, max, step, unit, disabled }) => (
    <Row gutter={12} align="middle">
        <Col flex="auto">
            <Slider min={min} max={max} step={step} value={Number(value)} onChange={onChange} disabled={disabled} />
        </Col>
        <Col flex="none">
            <InputNumber min={min} max={max} step={step} value={value} onChange={onChange} disabled={disabled} addonAfter={unit} size="small" style={{ width: 100 }} />
        </Col>
    </Row>
);

const WidgetConstDisplay = ({ value, options }) => {
    const label = options?.find(o => String(o.value) === String(value))?.label || value;
    return <Text type="secondary" code>{label}</Text>;
};

const ConfigRow = ({ field, config, onConfigChange, isLocked }) => {
    const renderWidget = () => {
        const commonProps = { disabled: isLocked };

        if (field.type === TYPES.CONST || field.widget === 'const_display') {
            return <WidgetConstDisplay value={config.value} options={field.options} />;
        }

        if (config.type === TYPES.VALUE) {
            const val = config.value;
            const handleChange = (v) => onConfigChange({...config, value: v});

            if (field.widget === 'slider') {
                return <WidgetSlider value={val} onChange={handleChange} min={field.min} max={field.max} step={field.step} unit={field.unit} {...commonProps} />;
            }
            // Director 模式下 pills 也当 segmented 用 (单选)
            if (field.widget === 'segmented' || field.widget === 'pills' || field.widget === 'speed_preset') {
                return <WidgetSegmented value={val} onChange={handleChange} options={field.options} {...commonProps} />;
            }
            return <WidgetInput value={val} onChange={handleChange} placeholder={field.desc} {...commonProps} />;
        }
        return <div style={{color:'red'}}>Err</div>;
    };

    return (
        <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Space size={4} align="center">
                    <Text strong style={{ fontSize: 13 }}>{field.label}</Text>
                    <Tooltip title={field.desc}><span className="material-symbols-outlined text-gray-400 text-sm cursor-help">help</span></Tooltip>
                </Space>
            </div>
            {renderWidget()}
        </div>
    );
};

window.DirectorWidgets = { ConfigRow };