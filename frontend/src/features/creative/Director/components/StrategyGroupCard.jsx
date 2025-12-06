import React from 'react';
import { Card, Segmented, Space, Tag, Row, Col, Divider, Typography } from 'antd';
import { ConfigRow } from './Widgets';

const { Text } = Typography;

const ModeSwitcher = ({ hasAsset, mode, onChange }) => {
    const options = hasAsset
        ? [
            { label: '锁定', value: 'LOCKED', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">lock</span> },
            { label: '重制', value: 'RECREATE', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">sync</span> }
        ]
        : [
            { label: '跳过', value: 'SKIP', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">skip_next</span> },
            { label: '新建', value: 'NEW', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">add</span> }
        ];

    let bg = mode === 'LOCKED' ? '#fff1f0' : (mode === 'NEW' || mode === 'RECREATE' ? '#e6f7ff' : '#f5f5f5');

    // Antd 的 Segmented 组件不支持直接 style 设置背景色，通常需要包一层 div 或者用 class
    // 这里为了简单复现原逻辑，我们直接返回组件
    return (
        <div style={{ backgroundColor: bg, borderRadius: 6, padding: 2 }}>
            <Segmented options={options} value={mode} onChange={onChange} />
        </div>
    );
};

const StrategyGroupCard = ({ title, groups, domain, badgeColor, strategyData, onUpdate, metaData, onModeChange }) => {
    const { mode } = metaData || {};
    const isLocked = mode === 'LOCKED';
    const isSkipped = mode === 'SKIP';

    const renderFields = (fieldGroup) => {
        return Object.entries(fieldGroup || {}).map(([key, fieldSchema]) => {
            const config = strategyData[key];
            if (!config) return null;

            // 合并静态 Schema 和运行时动态属性 (如 _runtime.hidden, _runtime.options)
            const runtimeField = { ...fieldSchema, ...(config._runtime || {}) };

            if (runtimeField.hidden) return null;

            return (
                <ConfigRow
                    key={key}
                    field={runtimeField}
                    config={config}
                    isLocked={isLocked}
                    onConfigChange={(newConf) => onUpdate(key, newConf)}
                />
            );
        });
    };

    return (
        <Card
            title={
                <Space>
                    <Tag color={isSkipped ? 'default' : badgeColor}>{domain.toUpperCase()}</Tag>
                    <Text strong style={{ color: isSkipped ? '#ccc' : undefined }}>{title}</Text>
                </Space>
            }
            extra={<ModeSwitcher hasAsset={metaData?.has_asset} mode={mode} onChange={onModeChange} />}
            style={{ marginBottom: 24, borderColor: isLocked ? '#ffccc7' : '#f0f0f0' }}
            headStyle={{ background: isLocked ? '#fff2f0' : '#fff' }}
            size="small"
        >
            {!isSkipped && (
                <Row gutter={48}>
                    <Col xs={24} md={12}>
                        <Divider orientation="left" style={{ marginTop: 0, fontSize: 12 }}>Content (内容)</Divider>
                        {renderFields(groups.content)}
                    </Col>
                    <Col xs={24} md={12}>
                        <Divider orientation="left" style={{ marginTop: 0, fontSize: 12 }}>Constraints (约束)</Divider>
                        {renderFields(groups.constraints)}
                    </Col>
                </Row>
            )}
            {isSkipped && <div style={{ padding: 24, textAlign: 'center', color: '#ccc' }}>此模块已跳过，将不执行任何操作。</div>}
        </Card>
    );
};

export default StrategyGroupCard;