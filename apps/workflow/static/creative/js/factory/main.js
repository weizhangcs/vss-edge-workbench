// apps/workflow/static/creative/js/factory/main.js

// 1. 引用配置
const { SCHEMA, DEFAULTS } = window.FactoryConfig;

// [CRITICAL FIX] 修正引用：FactoryLogic 本身就是逻辑对象，不需要解构
const Logic = window.FactoryLogic;

const { StrategyGroupCard } = window.FactoryCards;

const { React, ReactDOM } = window;
const { useState, useMemo } = React;
const { Card, Statistic, Divider, Space, Button, Typography } = window.antd;
const { Text } = Typography;

// --- State Factory ---

const getInitialState = () => {
    const serverData = window.SERVER_DATA || {};
    console.group("[Factory Debug] Initializing State");
    console.log("1. Server Data Received:", serverData);

    const assets = serverData.assets || {};
    const savedConfig = serverData.initial_config || {};

    const determineMode = (domain, hasAsset) => {
        let mode = 'NEW';
        if (hasAsset) mode = 'LOCKED';
        else if (domain === 'localize') mode = 'SKIP';

        // [Debug] 打印模式判断过程
        console.log(`   - Domain: ${domain} | Asset Exists: ${hasAsset} -> Mode: ${mode}`);
        return mode;
    };

    const createStrategy = (domain, defaults) => {
        // 强制转换为布尔值
        const hasAsset = !!(assets[domain] && assets[domain].exists);

        const strategy = {
            ...Logic.transformSavedConfig(defaults, savedConfig[domain]),
            _meta: {
                mode: determineMode(domain, hasAsset),
                locked_source: assets[domain]?.name || null,
                has_asset: hasAsset
            }
        };
        return strategy;
    };

    const initialState = {
        narration: createStrategy('narration', DEFAULTS.narration),
        localize: createStrategy('localize', DEFAULTS.localize),
        audio: createStrategy('audio', DEFAULTS.audio),
        edit: {
            ...Logic.transformSavedConfig(DEFAULTS.edit, savedConfig.edit),
            _meta: { mode: 'NEW', has_asset: false }
        }
    };

    console.log("2. Calculated Initial State:", initialState);
    console.groupEnd();

    return initialState;
};

// --- Main App ---

const FactoryApp = () => {
    const [strategy, setStrategy] = useState(getInitialState);

    const updateDomain = (domain, key, newConfig) => {
        setStrategy(prev => ({ ...prev, [domain]: { ...prev[domain], [key]: newConfig } }));
    };

    const changeMode = (domain, newMode) => {
        console.log(`[Mode Change] ${domain} -> ${newMode}`);
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
        if (mode === 'LOCKED' || mode === 'SKIP') return 1;
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
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            <div className="lg:col-span-9 space-y-8">
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

                 {/* Step 3 Edit */}
                 <StrategyGroupCard stepNum="3" title="剪辑参数" domain="edit" badgeColor="cyan"
                    groups={groupFields(SCHEMA.edit)}
                    strategyData={strategy.edit}
                    metaData={strategy.edit._meta}
                    onModeChange={(m) => changeMode('edit', m)}
                    onUpdate={(k, v) => updateDomain('edit', k, v)} />
            </div>

            <div className="lg:col-span-3 relative">
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
            </div>
        </div>
    );
};

const rootNode = document.getElementById('react-root');
if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(<FactoryApp />);
}