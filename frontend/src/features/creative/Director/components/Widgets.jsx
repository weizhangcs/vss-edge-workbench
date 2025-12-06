import React from 'react';
import { Segmented, Slider, Input, InputNumber, Space, Row, Col, Typography, Tooltip } from 'antd';
import { TYPES } from '../constants';

const { Text } = Typography;

// 子组件：普通输入框
const WidgetInput = ({ value, onChange, disabled, placeholder }) => (
    <Input value={value} onChange={e => onChange(e.target.value)} disabled={disabled} placeholder={placeholder} />
);

// 子组件：分段选择器
const WidgetSegmented = ({ value, onChange, options = [], disabled }) => (
    <Segmented block options={options} value={value} onChange={onChange} disabled={disabled} />
);

// 子组件：带数字输入的滑块
const WidgetSlider = ({ value, onChange, min, max, step, unit, disabled }) => (
    <Row gutter={12} align="middle">
        <Col flex="auto">
            <Slider min={min} max={max} step={step} value={Number(value)} onChange={onChange} disabled={disabled} />
        </Col>
        <Col flex="none">
            <InputNumber
                min={min} max={max} step={step}
                value={value} onChange={onChange}
                disabled={disabled}
                addonAfter={unit}
                size="small"
                style={{ width: 100 }}
            />
        </Col>
    </Row>
);

// 子组件：只读常量显示
const WidgetConstDisplay = ({ value, options }) => {
    const label = options?.find(o => String(o.value) === String(value))?.label || value;
    return <Text type="secondary" code>{label}</Text>;
};

// 子组件：数字输入框
const WidgetInputNumber = ({ value, onChange, disabled, min, max, step }) => (
    <InputNumber
        style={{ width: '100%' }}
        value={value}
        onChange={onChange}
        min={min} max={max} step={step}
        disabled={disabled}
    />
);

// 核心：配置行组件
export const ConfigRow = ({ field, config, onConfigChange, isLocked }) => {
    const renderWidget = () => {
        const commonProps = { disabled: isLocked };

        if (field.type === TYPES.CONST || field.widget === 'const_display') {
            return <WidgetConstDisplay value={config.value} options={field.options} />;
        }

        if (config.type === TYPES.VALUE) {
            const val = config.value;
            const handleChange = (v) => onConfigChange({ ...config, value: v });

            if (field.widget === 'slider') {
                return <WidgetSlider value={val} onChange={handleChange} min={field.min} max={field.max} step={field.step} unit={field.unit} {...commonProps} />;
            }

            // pills, segmented, speed_preset 统一用 Segmented 渲染
            if (['segmented', 'pills', 'speed_preset'].includes(field.widget)) {
                return <WidgetSegmented value={val} onChange={handleChange} options={field.options} {...commonProps} />;
            }

            if (field.widget === 'number') {
                return <WidgetInputNumber
                    value={val} onChange={handleChange}
                    min={field.min} max={field.max} step={field.step}
                    {...commonProps}
                />;
            }

            return <WidgetInput value={val} onChange={handleChange} placeholder={field.desc} {...commonProps} />;
        }
        return <div style={{ color: 'red' }}>Err: Unknown Type</div>;
    };

    return (
        <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Space size={4} align="center">
                    <Text strong style={{ fontSize: 13 }}>{field.label}</Text>
                    {field.desc && (
                        <Tooltip title={field.desc}>
                            <span className="material-symbols-outlined text-gray-400 text-sm cursor-help" style={{ fontSize: '16px' }}>help</span>
                        </Tooltip>
                    )}
                </Space>
            </div>
            {renderWidget()}
        </div>
    );
};