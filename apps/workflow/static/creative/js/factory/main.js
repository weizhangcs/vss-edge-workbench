// apps/workflow/static/creative/js/factory/main.js

const { SCHEMA, DEFAULTS } = window.FactoryConfig;
const Logic = window.FactoryLogic;
const { StrategyGroupCard } = window.FactoryCards;

const { React, ReactDOM } = window;
const { useState, useMemo } = React;
const { Card, Statistic, Divider, Space, Button, Typography, message } = window.antd;
const { Text } = Typography;

// --- Helpers ---
const getCookie = (name) => {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
};

// --- State Factory ---
const getInitialState = () => {
    const serverData = window.SERVER_DATA || {};
    const assets = serverData.assets || {};
    const savedConfig = serverData.initial_config || {};

    const determineMode = (domain, hasAsset) => {
        let mode = 'NEW';
        if (hasAsset) mode = 'LOCKED';
        else if (domain === 'localize') mode = 'SKIP';
        return mode;
    };

    const createStrategy = (domain, defaults) => {
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

    return {
        narration: createStrategy('narration', DEFAULTS.narration),
        localize: createStrategy('localize', DEFAULTS.localize),
        audio: createStrategy('audio', DEFAULTS.audio),
        edit: {
            ...Logic.transformSavedConfig(DEFAULTS.edit, savedConfig.edit),
            _meta: { mode: 'NEW', has_asset: false }
        }
    };
};

// --- Main App ---
const FactoryApp = () => {
    const [strategy, setStrategy] = useState(getInitialState);
    const [loading, setLoading] = useState(false);
    const [debugLoading, setDebugLoading] = useState(false);
    const sourceLanguage = window.SERVER_DATA?.assets?.source_language || 'zh-CN';

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

// [通用请求函数]
    const sendRequest = async (url, isLoadingSetter) => {
        isLoadingSetter(true);
        const csrftoken = getCookie('csrftoken');
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                body: cleanStrategyJson
            });
            const data = await response.json();
            if (response.ok && data.status === 'success') {
                message.success(data.message || "操作成功");
                if (data.debug_data) {
                    console.group("🏭 Factory Debug Output");
                    console.log(data.debug_data);
                    console.groupEnd();
                }
                if (data.redirect_url) {
                    setTimeout(() => window.location.href = data.redirect_url, 1000);
                }
            } else {
                message.error("失败: " + (data.message || "未知错误"));
            }
        } catch (error) {
            console.error('Request Error:', error);
            message.error("网络错误");
        } finally {
            isLoadingSetter(false);
        }
    };

    const handleSubmit = () => {
        if (totalCombinations > 50 && !confirm(`即将生成 ${totalCombinations} 个任务，确定要继续吗？`)) return;
        const projectId = window.SERVER_DATA?.project_id;
        const url = `/workflow/creative/project/${projectId}/factory/submit/`;
        sendRequest(url, setLoading);
    };

    // [核心新增] Debug 处理
    const handleDebug = () => {
        const projectId = window.SERVER_DATA?.project_id;
        const url = `/workflow/creative/project/${projectId}/factory/debug/`;
        sendRequest(url, setDebugLoading);
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            <div className="lg:col-span-9 space-y-8">
                <StrategyGroupCard stepNum="1" title="解说词参数" domain="narration" badgeColor="geekblue"
                    groups={groupFields(SCHEMA.narration)}
                    strategyData={strategy.narration}
                    metaData={strategy.narration._meta}
                    sourceLanguage={sourceLanguage}
                    onModeChange={(m) => changeMode('narration', m)}
                    onUpdate={(k, v) => updateDomain('narration', k, v)} />

                <StrategyGroupCard stepNum="1.5" title="本地化参数" domain="localize" badgeColor="magenta"
                    groups={groupFields(SCHEMA.localize)}
                    strategyData={strategy.localize}
                    metaData={strategy.localize._meta}
                    sourceLanguage={sourceLanguage}
                    onModeChange={(m) => changeMode('localize', m)}
                    onUpdate={(k, v) => updateDomain('localize', k, v)} />

                 <StrategyGroupCard stepNum="2" title="配音参数" domain="audio" badgeColor="purple"
                    groups={groupFields(SCHEMA.audio)}
                    strategyData={strategy.audio}
                    metaData={strategy.audio._meta}
                    sourceLanguage={sourceLanguage}
                    onModeChange={(m) => changeMode('audio', m)}
                    onUpdate={(k, v) => updateDomain('audio', k, v)} />

                 <StrategyGroupCard stepNum="3" title="剪辑参数" domain="edit" badgeColor="cyan"
                    groups={groupFields(SCHEMA.edit)}
                    strategyData={strategy.edit}
                    metaData={strategy.edit._meta}
                    sourceLanguage={sourceLanguage}
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

                       {/* [核心新增] 按钮组 */}
                       <div style={{ marginTop: 20, display: 'flex', gap: '10px' }}>
                           <Button
                               size="large"
                               icon={<span className="material-symbols-outlined align-middle" style={{fontSize:18}}>bug_report</span>}
                               loading={debugLoading}
                               onClick={handleDebug}
                               style={{ flex: 1 }}
                           >
                               Debug
                           </Button>
                           <Button
                               type="primary"
                               size="large"
                               icon={<span className="material-symbols-outlined align-middle" style={{fontSize:18}}>rocket_launch</span>}
                               loading={loading}
                               onClick={handleSubmit}
                               style={{ flex: 1.5 }}
                           >
                               生成
                           </Button>
                       </div>

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