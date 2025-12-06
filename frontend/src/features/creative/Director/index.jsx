import React, { useState, useMemo } from 'react';
import { Card, Statistic, Button, message, Typography, Row, Col } from 'antd';
import { VideoCameraOutlined, BugOutlined } from '@ant-design/icons';
import StrategyGroupCard from './components/StrategyGroupCard';
import { initializeStrategy, computeDerivedState } from './logic';
import { SCHEMA } from './constants';
import './style.css';

const { Text } = Typography;

const LANG_MAPPING = {
    "en": "en-US", "fr": "fr-FR", "de": "de-DE", "ja": "ja-JP",
    "ko": "ko-KR", "zh": "cmn-CN", "es": "es-ES"
};

// CSRF Helper
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

const DirectorApp = ({ context }) => {
    const { assets, initial_config, project_id } = context;
    const sourceLanguage = assets?.source_language || 'zh-CN';

    // 1. 初始化状态
    const [strategy, setStrategy] = useState(() =>
        initializeStrategy(initial_config || {}, assets || {}, sourceLanguage)
    );
    const [loading, setLoading] = useState(false);
    const [debugLoading, setDebugLoading] = useState(false);

    // 2. 策略更新处理
    const updateStrategy = (domain, key, newConfig) => {
        setStrategy(prev => {
            const next = { ...prev, [domain]: { ...prev[domain], [key]: newConfig } };
            return computeDerivedState(next, sourceLanguage);
        });
    };

    const changeMode = (domain, newMode) => {
        setStrategy(prev => {
            const next = {
                ...prev,
                [domain]: {
                    ...prev[domain],
                    _meta: { ...prev[domain]._meta, mode: newMode }
                }
            };
            return computeDerivedState(next, sourceLanguage);
        });
    };

    // 3. 辅助函数：将字段按 Group 分组
    const groupFields = (schemaDomain) => {
        const groups = { content: {}, constraints: {} };
        for (const [key, field] of Object.entries(schemaDomain)) {
            const g = field.group || 'content';
            if (!groups[g]) groups[g] = {};
            groups[g][key] = field;
        }
        return groups;
    };

    // 4. 核心逻辑：组装最终 Payload JSON
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
                    // 只提取 type 和 value，过滤掉 _runtime 等前端辅助字段
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
            source_project_id: project_id,
            config: finalConfig,
            meta: { total_jobs: 1 }
        }, null, 2);

    }, [strategy, project_id]);

    // 5. 提交逻辑
    const sendRequest = async (url, isLoadingSetter) => {
        isLoadingSetter(true);
        const csrftoken = getCookie('csrftoken'); // Django CSRF
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: cleanStrategyJson
            });
            const data = await response.json();
            if (response.ok && data.status === 'success') {
                message.success(data.message || "操作成功");
                if (data.debug_data) console.log(data.debug_data);
                if (data.redirect_url) {
                    setTimeout(() => window.location.href = data.redirect_url, 1500);
                }
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
        sendRequest(`/workflow/creative/project/${project_id}/pipeline/submit/`, setLoading);
    };

    const handleDebug = () => {
        sendRequest(`/workflow/creative/project/${project_id}/pipeline/debug/`, setDebugLoading);
    };

    return (
        <div className="pt-4">
            <Row gutter={24} align="top">
                {/* 左侧：策略卡片列表 */}
                <Col xs={24} lg={18} className="space-y-6">
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
                </Col>

                {/* 右侧：控制台 (Sticky) */}
                <Col xs={24} lg={6}>
                    <div className="sticky top-6 space-y-4">
                        <Card title="导演控制台" bordered={false} className="shadow-lg">
                            <div style={{ textAlign: 'center', marginBottom: 20 }}>
                                <Text type="secondary">单管道精细化生产</Text>
                                <Statistic value={1} suffix="个任务" valueStyle={{ color: '#1890ff' }} />
                            </div>
                            <Button
                                type="primary"
                                size="large"
                                block
                                icon={<VideoCameraOutlined />}
                                loading={loading}
                                onClick={handleSubmit}
                            >
                                开始制作
                            </Button>
                            <Button
                                type="dashed"
                                size="middle"
                                block
                                style={{marginTop: 10}}
                                icon={<BugOutlined />}
                                loading={debugLoading}
                                onClick={handleDebug}
                            >
                                Debug Pipeline
                            </Button>
                        </Card>

                        <Card size="small" title="Payload Preview" bodyStyle={{padding: 0}}>
                            <pre className="text-[10px] text-green-600 font-mono overflow-auto h-64 p-3 bg-gray-50 m-0 border-none rounded-b">
                                {cleanStrategyJson}
                            </pre>
                        </Card>
                    </div>
                </Col>
            </Row>
        </div>
    );
};

export default DirectorApp;