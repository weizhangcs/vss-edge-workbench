// apps/workflow/static/creative/js/director/cards.js
const { ConfigRow } = window.DirectorWidgets;
const { React } = window;
const { Card, Segmented, Space, Tag, Row, Col, Divider, Typography } = window.antd;
const { Text } = Typography;

const ModeSwitcher = ({ hasAsset, mode, onChange }) => {
    const options = hasAsset
        ? [{ label: '锁定', value: 'LOCKED', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">lock</span> },
           { label: '重制', value: 'RECREATE', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">sync</span> }]
        : [{ label: '跳过', value: 'SKIP', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">skip_next</span> },
           { label: '新建', value: 'NEW', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">add</span> }];

    let bg = mode === 'LOCKED' ? '#fff1f0' : (mode === 'NEW' || mode === 'RECREATE' ? '#e6f7ff' : '#f5f5f5');
    return <Segmented options={options} value={mode} onChange={onChange} style={{ backgroundColor: bg }} />;
};

const StrategyGroupCard = ({ title, groups, domain, badgeColor, strategyData, onUpdate, metaData, onModeChange }) => {
    const { mode, locked_source } = metaData || {};
    const isLocked = mode === 'LOCKED';
    const isSkipped = mode === 'SKIP';

    const renderFields = (fieldGroup) => {
        return Object.entries(fieldGroup || {}).map(([key, fieldSchema]) => {
            const config = strategyData[key];
            if (!config) return null;

            const runtimeField = { ...fieldSchema, ...(config._runtime || {}) };

            // [新增] 如果标记为隐藏，则不渲染
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
            title={<Space><Tag color={isSkipped ? 'default' : badgeColor}>{domain.toUpperCase()}</Tag><Text strong style={{ color: isSkipped ? '#ccc' : undefined }}>{title}</Text></Space>}
            extra={<ModeSwitcher hasAsset={metaData?.has_asset} mode={mode} onChange={onModeChange} />}
            style={{ marginBottom: 24, borderColor: isLocked ? '#ffccc7' : '#f0f0f0' }}
            headStyle={{ background: isLocked ? '#fff2f0' : '#fff' }}
            size="small"
        >
            {!isSkipped && (
                <Row gutter={48}>
                    <Col xs={24} md={12}><Divider orientation="left" style={{marginTop:0, fontSize:12}}>Content</Divider>{renderFields(groups.content)}</Col>
                    <Col xs={24} md={12}><Divider orientation="left" style={{marginTop:0, fontSize:12}}>Constraints</Divider>{renderFields(groups.constraints)}</Col>
                </Row>
            )}
            {isSkipped && <div style={{ padding: 24, textAlign: 'center', color: '#ccc' }}>已跳过</div>}
        </Card>
    );
};

window.DirectorCards = { StrategyGroupCard };