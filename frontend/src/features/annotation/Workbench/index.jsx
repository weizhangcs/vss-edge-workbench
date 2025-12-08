import React, { useState, useRef, useMemo, useEffect } from 'react';
import { Typography, Space, Button, message, Spin, Slider, Tooltip as AntTooltip } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, SaveOutlined, ArrowLeftOutlined, PlusOutlined, ScissorOutlined, MergeCellsOutlined } from '@ant-design/icons';
import _ from 'lodash';
import VideoPlayer from './components/VideoPlayer';
import SimpleTimeline from './components/SimpleTimeline';
import Inspector from './components/Inspector';
import { parseSRT } from './utils/parsers';
import { transformToTracks, transformFromTracks } from './utils/adapter';
import './style.css';

const { Title } = Typography;

const TEST_VIDEO_URL = "http://localhost:9999/media/transcoding_outputs/5124d170-c299-4d58-8447-abdaac2af5aa/158.mp4";
const TEST_SRT_URL = "http://localhost:9999/media/transcoding_outputs/5124d170-c299-4d58-8447-abdaac2af5aa/158.srt";

const AnnotationWorkbench = () => {
    // --- 状态定义 ---
    const [playing, setPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [tracks, setTracks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedActionId, setSelectedActionId] = useState(null);
    const [scale, setScale] = useState(20);

    // [修复] 补全状态定义
    const [originalMeta, setOriginalMeta] = useState(null);
    const [saving, setSaving] = useState(false);

    const videoRef = useRef(null);

    // --- 初始化加载 ---
    useEffect(() => {
        const initData = async () => {
            setLoading(true);

            // 获取注入的数据
            const serverData = window.SERVER_DATA || null;
            console.log("[Workbench] Init Data:", serverData);

            if (serverData) {
                // 1. 保存元数据 (用于 Save 时回填)
                setOriginalMeta(serverData);

                // 2. 转换数据
                try {
                    const convertedTracks = transformToTracks(serverData);
                    setTracks(convertedTracks);

                    if (serverData.duration) {
                        setDuration(serverData.duration);
                    }
                } catch (e) {
                    console.error("[Workbench] Adapter Error:", e);
                    message.error("数据转换失败");
                }
            } else {
                // Fallback: 如果没有后端数据，加载空轨道
                message.warning("未检测到后端数据，使用空模板");
                setTracks([
                    { id: 'scenes', name: 'SCENES', color: '#d8b4fe', actions: [] },
                    { id: 'dialogues', name: 'DIALOG', color: '#bae7ff', actions: [] }
                ]);
            }

            setLoading(false);
        };

        initData();
    }, []);

    // --- 辅助计算 ---
    const selectedContext = useMemo(() => {
        if (!selectedActionId) return { action: null, track: null };
        for (const track of tracks) {
            const action = track.actions.find(a => a.id === selectedActionId);
            if (action) return { action, track };
        }
        return { action: null, track: null };
    }, [selectedActionId, tracks]);

    const isSceneSelected = selectedContext.track?.id === 'scenes';

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

    const handleCreateClip = (trackId, start, end) => {
        const newTracks = _.cloneDeep(tracks);
        const track = newTracks.find(t => t.id === trackId);
        if (track) {
            const newId = `${trackId}-${Date.now()}`;
            const newAction = {
                id: newId,
                start: start,
                end: end,
                data: trackId === 'scenes' ? { label: '新场景' } : { text: '新字幕', speaker: 'Unknown' }
            };
            track.actions.push(newAction);
            setTracks(newTracks);
            setSelectedActionId(newId);
            if (trackId === 'scenes') message.success('场景创建成功');
        }
    };

    // --- [完整] 拆分逻辑 (Split) ---
    const handleSplitClip = () => {
        if (!selectedActionId) return;

        // 1. 查找对象
        let targetTrack = null;
        let targetAction = null;
        let trackIndex = -1;
        let actionIndex = -1;

        tracks.forEach((t, tIdx) => {
            t.actions.forEach((a, aIdx) => {
                if (a.id === selectedActionId) {
                    targetTrack = t;
                    targetAction = a;
                    trackIndex = tIdx;
                    actionIndex = aIdx;
                }
            });
        });

        if (!targetAction) return;

        // [规则] 场景块不支持拆分
        if (targetTrack.id === 'scenes') {
            message.warning('场景块不支持拆分操作');
            return;
        }

        // 检查游标位置
        if (currentTime <= targetAction.start + 0.1 || currentTime >= targetAction.end - 0.1) {
            message.warning('游标未在片段中间，无法拆分');
            return;
        }

        const newTracks = _.cloneDeep(tracks);
        const track = newTracks[trackIndex];
        const action = track.actions[actionIndex];

        // [规则] Cut时赋值：字幕内容直接复制
        const originalEnd = action.end;
        action.end = currentTime;

        const newId = `${targetTrack.id}-${Date.now()}-split`;
        const newAction = {
            ..._.cloneDeep(action), // 继承角色和文本
            id: newId,
            start: currentTime,
            end: originalEnd
        };

        track.actions.push(newAction);
        setTracks(newTracks);
        setSelectedActionId(newId);
        message.success('拆分成功 (请手动校验文本内容)');
    };

    // --- [完整] 合并逻辑 (Merge) ---
    const handleMergeClip = () => {
        if (!selectedActionId) return;

        // 1. 查找
        let trackIndex = -1;
        let track = null;
        let currentAction = null;

        const newTracks = _.cloneDeep(tracks);

        for (let i = 0; i < newTracks.length; i++) {
            const t = newTracks[i];
            const a = t.actions.find(act => act.id === selectedActionId);
            if (a) {
                trackIndex = i;
                track = t;
                currentAction = a;
                break;
            }
        }

        if (!currentAction) return;

        // [规则] 场景块不支持合并
        if (track.id === 'scenes') {
            message.warning('场景块不支持合并操作');
            return;
        }

        // 2. 排序并找下一个
        track.actions.sort((a, b) => a.start - b.start);
        const currentIndex = track.actions.findIndex(a => a.id === currentAction.id);

        if (currentIndex >= track.actions.length - 1) {
            message.warning('后方无片段，无法合并');
            return;
        }

        const nextAction = track.actions[currentIndex + 1];

        // [规则] 角色一致性校验
        if (currentAction.data.speaker !== nextAction.data.speaker) {
            message.error(`角色不一致 (${currentAction.data.speaker} vs ${nextAction.data.speaker})，禁止合并`);
            return;
        }

        // [规则] 执行合并：更新时间，拼接文本
        currentAction.end = nextAction.end;
        currentAction.data.text = `${currentAction.data.text} ${nextAction.data.text}`;

        // 删除后一个
        track.actions.splice(currentIndex + 1, 1);

        setTracks(newTracks);
        message.success('合并成功 (请手动校验合并后的文本)');
    };

    const togglePlay = () => setPlaying(!playing);

    // --- 保存逻辑 (Save) ---
    const handleSave = async () => {
        if (!originalMeta) {
            message.error("原始数据丢失，无法保存");
            return;
        }

        setSaving(true);
        try {
            // 1. 数据组装：Tracks -> Backend Schema
            const payload = transformFromTracks(tracks, originalMeta);
            console.log("[Workbench] Saving Payload:", payload);

            // 2. 发送请求
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            });

            const resData = await response.json();

            if (response.ok && resData.status === 'success') {
                message.success('保存成功');
            } else {
                message.error(`保存失败: ${resData.message || '未知错误'}`);
            }

        } catch (e) {
            console.error(e);
            message.error("网络请求失败");
        } finally {
            setSaving(false);
        }
    };

    // --- 键盘快捷键 ---
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

            switch(e.code) {
                case 'Space': e.preventDefault(); setPlaying(prev => !prev); break;
                case 'Backspace': case 'Delete': if (selectedActionId) { e.preventDefault(); handleActionDelete(selectedActionId); } break;
                case 'KeyS': e.preventDefault(); handleSplitClip(); break;
                case 'KeyM': e.preventDefault(); handleMergeClip(); break;
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [selectedActionId, currentTime, tracks]);

    return (
        <div className="wb-container">
            {/* Header */}
            <header className="wb-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => window.history.back()} />
                    <div>
                        <Title level={4} style={{ margin: 0 }}>Annotation Workbench</Title>
                        <span style={{ fontSize: '12px', color: '#9ca3af' }}>v3.1 (Full Features)</span>
                    </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', background: '#f3f4f6', padding: '4px 16px', borderRadius: '99px' }}>
                    <Button
                        type="text"
                        shape="circle"
                        icon={playing ? <PauseCircleOutlined style={{ fontSize: 24, color: '#9333ea' }}/> : <PlayCircleOutlined style={{ fontSize: 24 }}/>}
                        onClick={togglePlay}
                    />
                    <span style={{ fontFamily: 'monospace', color: '#4b5563', width: '100px', textAlign: 'center' }}>
                    {currentTime.toFixed(2)}s
                </span>
                </div>

                <Space>
                    {/* 保存按钮 */}
                    <Button
                        type="primary"
                        icon={<SaveOutlined />}
                        onClick={handleSave}
                        loading={saving}
                    >
                        保存
                    </Button>
                </Space>
            </header>

            {/* Body */}
            <div className="wb-body">

                {/* Top Pane */}
                <div className="wb-stage-pane">
                    <div className="wb-video-area">
                        <VideoPlayer
                            ref={videoRef}
                            url={originalMeta?.source_path ? originalMeta.source_path : TEST_VIDEO_URL} // 尝试使用后端返回的路径
                            playing={playing}
                            onProgress={handleProgress}
                            onDuration={setDuration}
                            onPlay={() => setPlaying(true)}
                            onPause={() => setPlaying(false)}
                        />
                    </div>
                    <div className="wb-inspector-area">
                        <Inspector
                            action={selectedContext.action}
                            track={selectedContext.track}
                            onUpdate={handleActionUpdate}
                            onDelete={handleActionDelete}
                        />
                    </div>
                </div>

                {/* Bottom Pane */}
                <div className="wb-timeline-pane">
                    <div className="wb-timeline-toolbar">
                        <div style={{ display: 'flex', gap: '8px', marginRight: '24px' }}>
                            <AntTooltip title={isSceneSelected ? "场景不支持拆分" : "快捷键: S"}>
                                <Button size="small" icon={<ScissorOutlined />} onClick={handleSplitClip} disabled={!selectedActionId || isSceneSelected}>拆分</Button>
                            </AntTooltip>
                            <AntTooltip title={isSceneSelected ? "场景不支持合并" : "快捷键: M"}>
                                <Button size="small" icon={<MergeCellsOutlined />} onClick={handleMergeClip} disabled={!selectedActionId || isSceneSelected}>合并</Button>
                            </AntTooltip>
                        </div>

                        <span style={{ fontSize: '12px', color: '#6b7280', flex: 1 }}>
                        操作: 轨道划词创建 | S键拆分 | M键合并
                    </span>

                        <div style={{ width: 200, display: 'flex', alignItems: 'center', gap: 8 }}>
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
                            onSelect={(action) => setSelectedActionId(action ? action.id : null)} // 增加空值检查：如果是 null，则设为 null，否则取 id
                            scale={scale}
                            onScaleChange={setScale}
                            videoUrl={originalMeta?.source_path ? originalMeta.source_path : TEST_VIDEO_URL}
                            onCreate={handleCreateClip}
                        />
                    </div>
                </div>
            </div>

            <div style={{ display: 'none' }}></div>
        </div>
    );
};

export default AnnotationWorkbench;