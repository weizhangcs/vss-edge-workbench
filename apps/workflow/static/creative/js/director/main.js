// apps/workflow/static/creative/js/director/main.js

const { SCHEMA } = window.DirectorConfig;
const Logic = window.DirectorLogic;
const { StrategyGroupCard } = window.DirectorCards;

const { React, ReactDOM } = window;
const { useState, useMemo } = React;
const { Card, Statistic, Divider, Space, Button, message, Typography } = window.antd;
const { Text } = Typography;

const LANG_MAPPING = { "en": "en-US", "fr": "fr-FR", "de": "de-DE", "ja": "ja-JP", "ko": "ko-KR", "zh": "cmn-CN", "es": "es-ES" };

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

const DirectorApp = () => {
    const serverData = window.SERVER_DATA || {};
    const sourceLanguage = serverData.assets?.source_language || 'zh-CN';

    const [strategy, setStrategy] = useState(() => Logic.initializeStrategy(serverData.initial_config || {}, serverData.assets || {}, sourceLanguage));
    const [loading, setLoading] = useState(false);
    const [debugLoading, setDebugLoading] = useState(false);

    const updateStrategy = (domain, key, newConfig) => {
        setStrategy(prev => {
            const next = { ...prev, [domain]: { ...prev[domain], [key]: newConfig } };
            return Logic.computeDerivedState(next, sourceLanguage);
        });
    };

    const changeMode = (domain, newMode) => {
        setStrategy(prev => {
            const next = { ...prev, [domain]: { ...prev[domain], _meta: { ...prev[domain]._meta, mode: newMode } } };
            return Logic.computeDerivedState(next, sourceLanguage);
        });
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

    const cleanStrategyJson = useMemo(() => {
        const finalConfig = {};

        Object.keys(strategy).forEach(domain => {
            const { _meta, ...restConfig } = strategy[domain];
            const mode = _meta?.mode || 'NEW';
            const payloadItem = { mode: mode, config: null };

            if (mode === 'NEW' || mode === 'RECREATE') {
                const cleanConfig = {};
                Object.keys(restConfig).forEach(k => {
                    const item = restConfig[k];
                    cleanConfig[k] = { type: item.type, value: item.value };
                });
                payloadItem.config = cleanConfig;
            }
            finalConfig[domain] = payloadItem;
        });

        // 智能补全 Audio 语言 (前端只做显式选择的补全，兜底交给后端)
        const locMode = finalConfig.localize?.mode;
        const locConfig = finalConfig.localize?.config;

        if (finalConfig.audio?.mode === 'NEW' || finalConfig.audio?.mode === 'RECREATE') {
            const audioConfig = { ...finalConfig.audio.config };
            if ((locMode === 'NEW' || locMode === 'RECREATE') && locConfig?.target_lang?.value) {
                const lang = locConfig.target_lang.value;
                audioConfig.source_script_type = { type: 'value', value: 'localized' };
                audioConfig.language_code = { type: 'value', value: LANG_MAPPING[lang] || 'cmn-CN' };
            } else if (locMode === 'SKIP') {
                audioConfig.source_script_type = { type: 'value', value: 'master' };
                audioConfig.language_code = { type: 'value', value: 'cmn-CN' };
            }
            finalConfig.audio.config = audioConfig;
        }

        return JSON.stringify({
            strategy_version: "3.0",
            source_project_id: window.SERVER_DATA?.project_id,
            config: finalConfig,
            meta: { total_jobs: 1 }
        }, null, 2);

    }, [strategy]);

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
                if (data.debug_data) console.log(data.debug_data);
                if (data.redirect_url) setTimeout(() => window.location.href = data.redirect_url, 1500);
            } else {
                message.error("失败: " + (data.message || "未知错误"));
            }
        } catch (error) {
            console.error(error);
            message.error("网络错误");
        } finally {
            isLoadingSetter(false);
        }
    };

    const handleSubmit = () => {
        const projectId = window.SERVER_DATA?.project_id;
        // [Renamed] pipeline/submit
        sendRequest(`/workflow/creative/project/${projectId}/pipeline/submit/`, setLoading);
    };

    const handleDebug = () => {
        const projectId = window.SERVER_DATA?.project_id;
        // [Renamed] pipeline/debug
        sendRequest(`/workflow/creative/project/${projectId}/pipeline/debug/`, setDebugLoading);
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            <div className="lg:col-span-9 space-y-8">
                {['narration', 'localize', 'audio', 'edit'].map((domain, idx) => (
                    <StrategyGroupCard
                        key={domain}
                        title={domain.charAt(0).toUpperCase() + domain.slice(1)}
                        domain={domain}
                        badgeColor={['geekblue', 'magenta', 'purple', 'cyan'][idx]}
                        groups={groupFields(SCHEMA[domain])}
                        strategyData={strategy[domain]}
                        metaData={strategy[domain]._meta}
                        onModeChange={(m) => changeMode(domain, m)}
                        onUpdate={(k, v) => updateStrategy(domain, k, v)}
                    />
                ))}
            </div>

            <div className="lg:col-span-3 relative">
               <div className="sticky top-6">
                   <Card title="导演控制台" bordered={false} className="shadow-lg">
                       <div style={{ textAlign: 'center', marginBottom: 20 }}>
                           <Text type="secondary">单管道精细化生产</Text>
                           <Statistic value={1} suffix="个任务" valueStyle={{ color: '#1890ff' }} />
                       </div>
                       <Button type="primary" size="large" block icon={<span className="material-symbols-outlined align-middle" style={{fontSize:18}}>movie_filter</span>} loading={loading} onClick={handleSubmit}>
                           开始制作
                       </Button>
                       <Button type="dashed" size="middle" block style={{marginTop: 10}} icon={<span className="material-symbols-outlined align-middle" style={{fontSize:16}}>bug_report</span>} loading={debugLoading} onClick={handleDebug}>
                           Debug Pipeline
                       </Button>
                   </Card>
                   <Card size="small" title="Payload Preview" style={{marginTop: 16}} bodyStyle={{padding: 0}}>
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
    root.render(<DirectorApp />);
}