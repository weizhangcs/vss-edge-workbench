// [FIXED] 移除 import，使用全局变量
const { ConfigRow } = window.FactoryWidgets;
const { React } = window;
const { Card, Segmented, Space, Tag, Row, Col, Divider, Typography } = window.antd;
const { Text } = Typography;

// 1. 模式切换器
// [FIXED] 移除 export
const ModeSwitcher = ({ hasAsset, mode, onChange }) => {
    const options = hasAsset
        ? [
            { label: '锁定 (复用)', value: 'LOCKED', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">lock</span> },
            { label: '二次创作', value: 'RECREATE', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">sync</span> }
          ]
        : [
            { label: '跳过', value: 'SKIP', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">skip_next</span> },
            { label: '新增', value: 'NEW', icon: <span className="material-symbols-outlined text-[14px] align-middle mr-1">add</span> }
          ];

    let bg = '#f5f5f5';
    if (mode === 'LOCKED') bg = '#f6ffed';
    else if (mode === 'RECREATE') bg = '#fff1f0';
    else if (mode === 'NEW') bg = '#e6f7ff';

    return (
        <Segmented
            options={options}
            value={mode}
            onChange={onChange}
            style={{ backgroundColor: bg, transition: 'background-color 0.3s' }}
        />
    );
};

// 2. 策略组卡片
// [FIXED] 移除 export
const StrategyGroupCard = ({ stepNum, title, groups, domain, badgeColor, strategyData, onUpdate, metaData, onModeChange }) => {
    const { mode, locked_source, has_asset } = metaData || {};
    const isLocked = mode === 'LOCKED';
    const isSkipped = mode === 'SKIP';
    const isRecreate = mode === 'RECREATE';

    const showForm = mode !== 'SKIP';
    const formDisabled = isLocked;

    let borderColor = '#f0f0f0';
    if (isLocked) borderColor = '#b7eb8f';
    if (isRecreate) borderColor = '#ffa39e';

    return (
        <Card
            title={
                <Space>
                    <span className="material-symbols-outlined" style={{ color: isLocked ? '#52c41a' : '#8c8c8c', fontSize: 20 }}>
                        {isSkipped ? 'do_not_disturb_on' : (isLocked ? 'lock' : 'edit_square')}
                    </span>
                    <Text strong style={{ color: isSkipped ? '#bfbfbf' : undefined, textDecoration: isSkipped ? 'line-through' : undefined, fontSize: 15 }}>
                        Step {stepNum}: {title}
                    </Text>
                    <Tag color={isSkipped ? 'default' : badgeColor}>{domain.toUpperCase()}</Tag>
                </Space>
            }
            extra={
                <ModeSwitcher hasAsset={has_asset} mode={mode} onChange={onModeChange} />
            }
            style={{ marginBottom: 24, borderColor: borderColor }}
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
                            <span className="material-symbols-outlined text-[16px]" style={{marginRight: 8}}>verified</span>
                            <span>已锁定母本产出物: </span>
                            <Text code style={{marginLeft: 8, fontSize: 12}}>{locked_source}</Text>
                        </div>
                    )}

                    {isRecreate && (
                         <div style={{ marginBottom: 24, padding: '8px 12px', background: '#fff1f0', border: '1px dashed #ffccc7', borderRadius: 6, color: '#cf1322', fontSize: 12, display: 'flex', alignItems: 'center' }}>
                            <span className="material-symbols-outlined text-[16px]" style={{marginRight: 8}}>warning</span>
                            注意：此操作将生成新文件覆盖原有母本。
                        </div>
                    )}

                    <Row gutter={48}>
                        <Col xs={24} md={12}>
                            <Divider orientation="left" style={{marginTop: 0, fontSize: 12, color: '#8c8c8c'}}>内容设定 (Content)</Divider>
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
                            <Divider orientation="left" style={{marginTop: 0, fontSize: 12, color: '#8c8c8c'}}>生成限制 (Constraints)</Divider>
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
                    <span className="material-symbols-outlined" style={{ fontSize: 48, display: 'block', marginBottom: 8 }}>skip_next</span>
                    此步骤已跳过，不产生任务。
                </div>
            )}
        </Card>
    );
};

// [FIXED] 挂载到全局
window.FactoryCards = { StrategyGroupCard };