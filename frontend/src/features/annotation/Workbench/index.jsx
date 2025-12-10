import React, { useState, useRef, useMemo, useEffect } from 'react';
import { Typography, Space, Button, message, Spin, Slider, Tooltip as AntTooltip } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, SaveOutlined, ArrowLeftOutlined, PlusOutlined, ScissorOutlined, MergeCellsOutlined, FileTextOutlined } from '@ant-design/icons';
import _ from 'lodash';
import VideoPlayer from './components/VideoPlayer';
import SimpleTimeline from './components/SimpleTimeline';
import Inspector from './components/Inspector';
import { transformToTracks, transformFromTracks } from './utils/adapter';
import { generateVTT } from './utils/vtt';
// [核心修复] 重新引入配置定义
import { TRACK_DEFINITIONS, canTrackDo, getTrackConfig } from './config/tracks';
import './style.css';

const { Title } = Typography;

const AnnotationWorkbench = () => {
    // --- 状态定义 ---
    const [playing, setPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [tracks, setTracks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedActionId, setSelectedActionId] = useState(null);
    const [scale, setScale] = useState(20);

    const [originalMeta, setOriginalMeta] = useState(null);
    const [saving, setSaving] = useState(false);
    const [showSubtitle, setShowSubtitle] = useState(false); // VTT 开关

    const videoRef = useRef(null);

    // --- 初始化加载 ---
    useEffect(() => {
        const initData = async () => {
            setLoading(true);
            const serverData = window.SERVER_DATA || null;
            console.log("[Workbench] Init Data:", serverData);

            if (serverData) {
                setOriginalMeta(serverData);
                try {
                    const convertedTracks = transformToTracks(serverData);
                    setTracks(convertedTracks);
                    if (serverData.duration) setDuration(serverData.duration);
                } catch (e) {
                    console.error("[Workbench] Adapter Error:", e);
                    message.error("数据转换失败");
                }
            } else {
                // [修复] Fallback 使用配置生成，不再硬编码
                message.warning("未检测到后端数据，使用空模板");
                const emptyTracks = Object.values(TRACK_DEFINITIONS).map(def => ({
                    id: def.id,
                    name: def.label,
                    color: def.color,
                    actions: []
                }));
                setTracks(emptyTracks);
            }
            setLoading(false);
        };
        initData();
    }, []);

    // VTT URL 计算
    const subtitleUrl = useMemo(() => {
        if (!showSubtitle) return null;
        return generateVTT(tracks);
    }, [tracks, showSubtitle]);

    // --- 辅助计算 ---
    const selectedContext = useMemo(() => {
        if (!selectedActionId) return { action: null, track: null };
        for (const track of tracks) {
            const action = track.actions.find(a => a.id === selectedActionId);
            if (action) return { action, track };
        }
        return { action: null, track: null };
    }, [selectedActionId, tracks]);

    // [核心修复] 动态能力检查 (替代 isComplexType)
    const currentTrackId = selectedContext.track?.id;
    const canSplit = currentTrackId && canTrackDo(currentTrackId, 'split');
    const canMerge = currentTrackId && canTrackDo(currentTrackId, 'merge');

    // --- 基础交互 ---
    const handleProgress = (state) => setCurrentTime(state.playedSeconds);

    const handleSeek = (time) => {
        setCurrentTime(time);
        if (playing) setPlaying(false);
        if (videoRef.current) videoRef.current.seekTo(time);
    };

    const handleTrackUpdate = (newTracks) => setTracks(newTracks);

    const handleActionUpdate = (updatedAction) => {
        const newTracks = _.cloneDeep(tracks);
        for (const track of newTracks) {
            const idx = track.actions.findIndex(a => a.id === updatedAction.id);
            if (idx !== -1) {
                track.actions[idx] = updatedAction;
                break;
            }
        }
        setTracks(newTracks);
    };

    const handleActionDelete = (actionId) => {
        const newTracks = _.cloneDeep(tracks);
        for (const track of newTracks) {
            track.actions = track.actions.filter(a => a.id !== actionId);
        }
        setTracks(newTracks);
        setSelectedActionId(null);
        message.info('片段已删除');
    };

    // --- [修复] 恢复基于配置的创建逻辑 ---
    const handleCreateClip = (trackId, start, end) => {
        // 检查权限
        if (!canTrackDo(trackId, 'create')) return;

        const newTracks = _.cloneDeep(tracks);
        const track = newTracks.find(t => t.id === trackId);

        if (track) {
            const trackConfig = getTrackConfig(trackId);
            const newId = `${trackId}-${Date.now()}`;

            // [核心修复] 使用 factory 生成默认数据
            const newData = trackConfig && trackConfig.factory
                ? trackConfig.factory()
                : { label: 'New Clip' };

            const newAction = {
                id: newId,
                start: start,
                end: end,
                data: newData
            };

            track.actions.push(newAction);
            setTracks(newTracks);
            setSelectedActionId(newId);

            if (trackId === 'scenes') message.success('场景创建成功');
        }
    };

    // --- [修复] 恢复基于配置的拆分逻辑 ---
    const handleSplitClip = () => {
        if (!selectedActionId) return;

        let targetTrack = null, targetAction = null, trackIndex = -1, actionIndex = -1;
        tracks.forEach((t, tIdx) => {
            t.actions.forEach((a, aIdx) => {
                if (a.id === selectedActionId) {
                    targetTrack = t; targetAction = a; trackIndex = tIdx; actionIndex = aIdx;
                }
            });
        });

        if (!targetAction) return;

        // [核心修复] 使用 canTrackDo
        if (!canTrackDo(targetTrack.id, 'split')) {
            message.warning('该轨道不支持拆分操作');
            return;
        }

        if (currentTime <= targetAction.start + 0.1 || currentTime >= targetAction.end - 0.1) {
            message.warning('游标未在片段中间，无法拆分');
            return;
        }

        const newTracks = _.cloneDeep(tracks);
        const track = newTracks[trackIndex];
        const action = track.actions[actionIndex];

        const originalEnd = action.end;
        action.end = currentTime;

        const newId = `${targetTrack.id}-${Date.now()}-split`;
        const newAction = {
            ..._.cloneDeep(action),
            id: newId,
            start: currentTime,
            end: originalEnd
        };

        track.actions.push(newAction);
        setTracks(newTracks);
        setSelectedActionId(newId);
        message.success('拆分成功');
    };

    // --- [修复] 恢复基于配置的合并逻辑 ---
    const handleMergeClip = () => {
        if (!selectedActionId) return;

        let trackIndex = -1, track = null, currentAction = null;
        const newTracks = _.cloneDeep(tracks);

        for (let i = 0; i < newTracks.length; i++) {
            const t = newTracks[i];
            const a = t.actions.find(act => act.id === selectedActionId);
            if (a) {
                trackIndex = i; track = t; currentAction = a; break;
            }
        }

        if (!currentAction) return;

        // [核心修复] 使用 canTrackDo
        if (!canTrackDo(track.id, 'merge')) {
            message.warning('该轨道不支持合并操作');
            return;
        }

        track.actions.sort((a, b) => a.start - b.start);
        const currentIndex = track.actions.findIndex(a => a.id === currentAction.id);

        if (currentIndex >= track.actions.length - 1) {
            message.warning('后方无片段，无法合并');
            return;
        }

        const nextAction = track.actions[currentIndex + 1];

        // 角色校验
        if (track.id === 'dialogues' && currentAction.data.speaker !== nextAction.data.speaker) {
            message.error(`角色不一致，禁止合并`);
            return;
        }

        currentAction.end = nextAction.end;
        // 文本拼接 (Dialogues / Captions)
        if (['dialogues', 'captions'].includes(track.id)) {
            currentAction.data.text = `${currentAction.data.text} ${nextAction.data.text}`;
        }

        track.actions.splice(currentIndex + 1, 1);
        setTracks(newTracks);
        message.success('合并成功');
    };

    const togglePlay = () => setPlaying(!playing);

    // --- 保存逻辑 ---
    const handleSave = async () => {
        if (!originalMeta) {
            message.error("原始数据丢失，无法保存");
            return;
        }

        setSaving(true);
        try {
            const payload = transformFromTracks(tracks, originalMeta);
            console.log("[Workbench] Saving Payload:", payload);

            // [核心修复] 获取 CSRF Token
            // 优先从 window.CONTEXT 获取 (我们在 workbench.html 里注入了)
            // 如果没有，再尝试从 DOM 获取
            const csrfToken = window.CONTEXT?.csrfToken || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

            // [核心修复] 使用后端注入的专用 API 地址
            // 之前的 window.location.href 会请求到 HTML 页面，导致 "Unexpected token <" 错误
            const saveUrl = window.CONTEXT?.saveEndpoint;

            if (!saveUrl) {
                throw new Error("Save endpoint not found in window.CONTEXT");
            }

            const response = await fetch(saveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            });

            // 检查 HTTP 状态码，防止 404/500 返回 HTML 导致的解析错误
            if (!response.ok) {
                const text = await response.text();
                throw new Error(`Server Error (${response.status}): ${text.substring(0, 100)}...`);
            }

            const resData = await response.json();

            if (resData.status === 'success') {
                message.success('保存成功');
                // 可选：更新本地 originalMeta，防止重复保存
                setOriginalMeta(payload);
            } else {
                message.error(`保存失败: ${resData.message || '未知错误'}`);
            }

        } catch (e) {
            console.error(e);
            message.error(`保存请求异常: ${e.message}`);
        } finally {
            setSaving(false);
        }
    };

    // [新增] 处理返回逻辑
    const handleGoBack = () => {
        // 优先使用后端注入的精确路径
        const returnUrl = window.CONTEXT?.returnUrl;

        if (returnUrl) {
            window.location.href = returnUrl;
        } else {
            // 兜底：如果没有路径，才尝试浏览器回退
            window.history.back();
        }
    };

    // --- 键盘快捷键 ---
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

            switch(e.code) {
                case 'Space':
                    e.preventDefault();
                    setPlaying(prev => !prev);
                    break;
                case 'Backspace':
                case 'Delete':
                    if (selectedActionId) {
                        e.preventDefault();
                        handleActionDelete(selectedActionId);
                    }
                    break;
                case 'KeyS':
                    e.preventDefault();
                    handleSplitClip();
                    break;
                case 'KeyM':
                    e.preventDefault();
                    handleMergeClip();
                    break;
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [selectedActionId, currentTime, tracks]);

    return (
        <div className="wb-container">
            <header className="wb-header">
                {/* 左侧：返回与标题 */}
                <div className="wb-header-left">
                    <Button
                        icon={<ArrowLeftOutlined />}
                        type="text"
                        onClick={handleGoBack} // 假设逻辑代码里有这个
                        title="返回项目列表"
                    />
                    <div>
                        <Title level={4} style={{ margin: 0 }}>Annotation Workbench</Title>
                        <span className="wb-version-tag">v1.3.0</span>
                    </div>
                </div>

                {/* 中间：播放控制 */}
                <div className="wb-player-controls">
                    <div className="wb-control-group">
                        <Button
                            type="text"
                            shape="circle"
                            icon={playing ? <PauseCircleOutlined style={{ fontSize: 24, color: '#9333ea' }}/> : <PlayCircleOutlined style={{ fontSize: 24 }}/>}
                            onClick={togglePlay} // 假设逻辑代码里有这个
                        />

                        <AntTooltip title={showSubtitle ? "隐藏原片字幕" : "显示原片字幕 (CC)"}>
                            <Button
                                type={showSubtitle ? "primary" : "text"}
                                shape="circle"
                                size="small"
                                icon={<FileTextOutlined style={{ fontSize: 16 }} />}
                                onClick={() => setShowSubtitle(!showSubtitle)} // 假设逻辑代码里有这个
                                style={showSubtitle ? { backgroundColor: '#9333ea' } : { color: '#6b7280' }}
                            />
                        </AntTooltip>

                        <span className="wb-time-display">
                            {currentTime.toFixed(2)}s
                        </span>
                    </div>
                </div>

                {/* 右侧：保存提交 */}
                <Space size="middle">
                    <span className="wb-save-hint">
                        暂存后请记得点击此处提交 👉
                    </span>

                    <Button
                        type="primary"
                        icon={<SaveOutlined />}
                        onClick={handleSave} // 假设逻辑代码里有这个
                        loading={saving} // 假设逻辑代码里有这个
                        title="将当前所有暂存的修改写入后端存储"
                    >
                        提交本次标注成果
                    </Button>
                </Space>
            </header>

            <div className="wb-body">
                <div className="wb-stage-pane">
                    <div className="wb-video-area">
                        <VideoPlayer
                            ref={videoRef}
                            url={originalMeta?.source_path}
                            playing={playing}
                            onProgress={handleProgress}
                            onDuration={setDuration}
                            onPlay={() => setPlaying(true)}
                            onPause={() => setPlaying(false)}
                            subtitleUrl={subtitleUrl}
                        />
                    </div>
                    {/* 这里的 .wb-inspector-area 样式已在 CSS 中去除了多余 padding */}
                    <div className="wb-inspector-area">
                        <Inspector
                            action={selectedContext?.action}
                            track={selectedContext?.track}
                            onUpdate={handleActionUpdate}
                            onDelete={handleActionDelete}
                        />
                    </div>
                </div>

                <div className="wb-timeline-pane">
                    <div className="wb-timeline-toolbar">
                        <div className="wb-toolbar-actions">
                            <AntTooltip title={!canSplit ? "此轨道不支持拆分" : "快捷键: S"}>
                                <Button size="small" icon={<ScissorOutlined />} onClick={handleSplitClip} disabled={!selectedActionId || !canSplit}>拆分</Button>
                            </AntTooltip>
                            <AntTooltip title={!canMerge ? "此轨道不支持合并" : "快捷键: M"}>
                                <Button size="small" icon={<MergeCellsOutlined />} onClick={handleMergeClip} disabled={!selectedActionId || !canMerge}>合并</Button>
                            </AntTooltip>
                        </div>

                        <span className="wb-toolbar-hint">
                            操作: 轨道划词创建 | 拖拽调整 | S键拆分 | M键合并
                        </span>

                        <div className="wb-toolbar-slider">
                            <Slider min={1} max={100} value={scale} onChange={setScale} style={{ flex: 1 }} tooltip={{ formatter: (v) => `${v} px/s` }} />
                        </div>
                    </div>

                    <div className="wb-timeline-body">
                        <SimpleTimeline
                            tracks={tracks}
                            currentTime={currentTime}
                            duration={duration || 60}
                            onSeek={handleSeek}
                            onUpdate={handleTrackUpdate}
                            selectedActionId={selectedActionId}
                            onSelect={(action) => setSelectedActionId(action ? action.id : null)}
                            scale={scale}
                            onScaleChange={setScale}
                            videoUrl={originalMeta?.source_path}
                            onCreate={handleCreateClip}
                            waveformUrl={originalMeta?.waveform_url}
                        />
                    </div>
                </div>
            </div>

            <div style={{ display: 'none' }}></div>
        </div>
    );
};

export default AnnotationWorkbench;