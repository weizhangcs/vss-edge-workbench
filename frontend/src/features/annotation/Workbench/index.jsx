import React, { useState, useRef, useMemo, useEffect } from 'react';
import { Typography, Space, Button, message, Spin, Slider, Tooltip as AntTooltip } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, SaveOutlined, ArrowLeftOutlined, PlusOutlined, ScissorOutlined, MergeCellsOutlined } from '@ant-design/icons';
import _ from 'lodash';
import VideoPlayer from './components/VideoPlayer';
import SimpleTimeline from './components/SimpleTimeline';
import Inspector from './components/Inspector';
import { parseSRT } from './utils/parsers';
import './style.css';

const { Title } = Typography;

const TEST_VIDEO_URL = "http://localhost:9999/media/transcoding_outputs/5124d170-c299-4d58-8447-abdaac2af5aa/158.mp4";
const TEST_SRT_URL = "http://localhost:9999/media/transcoding_outputs/5124d170-c299-4d58-8447-abdaac2af5aa/158.srt";

const AnnotationWorkbench = () => {
    const [playing, setPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [tracks, setTracks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedActionId, setSelectedActionId] = useState(null);
    const [scale, setScale] = useState(20);

    const videoRef = useRef(null);

    // 初始化加载
    useEffect(() => {
        const loadData = async () => {
            try {
                setLoading(true);
                let subtitleActions = [];
                try {
                    const resp = await fetch(TEST_SRT_URL);
                    if (resp.ok) {
                        const text = await resp.text();
                        subtitleActions = parseSRT(text);
                        message.success(`成功加载 ${subtitleActions.length} 条字幕`);
                    } else {
                        console.warn("SRT file not found.");
                    }
                } catch (e) {
                    console.error(e);
                }

                const newTracks = [
                    { id: 'scenes', name: 'SCENES', color: '#d8b4fe', actions: [] },
                    { id: 'subs', name: 'DIALOG', color: '#bae7ff', actions: subtitleActions }
                ];
                setTracks(newTracks);
            } catch (error) {
                message.error("数据加载失败");
            } finally {
                setLoading(false);
            }
        };
        loadData();
    }, []);

    // 计算当前选中的上下文 (action & track)
    const selectedContext = useMemo(() => {
        if (!selectedActionId) return { action: null, track: null };
        for (const track of tracks) {
            const action = track.actions.find(a => a.id === selectedActionId);
            if (action) return { action, track };
        }
        return { action: null, track: null };
    }, [selectedActionId, tracks]);

    // [新增] 判断当前选中的是否为场景 (用于禁用按钮)
    const isSceneSelected = selectedContext.track?.id === 'scenes';

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

    // --- 业务逻辑修改: 拆分 (Cut) ---
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

        // [规则] Cut时赋值：字幕内容直接复制 (cloneDeep 已包含 data.text 和 data.speaker)
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

    // --- 业务逻辑修改: 合并 (Join) ---
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
            {/* Header */}
            <header className="wb-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => window.history.back()} />
                    <div>
                        <Title level={4} style={{ margin: 0 }}>Big Buck Bunny (Production)</Title>
                        <span style={{ fontSize: '12px', color: '#9ca3af' }}>v2.2 (Rules Enforced)</span>
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
                    <Button type="primary" icon={<SaveOutlined />}>保存进度</Button>
                </Space>
            </header>

            {/* Body */}
            <div className="wb-body">

                {/* Top Pane */}
                <div className="wb-stage-pane">
                    <div className="wb-video-area">
                        <VideoPlayer
                            ref={videoRef}
                            url={TEST_VIDEO_URL}
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

                {/* Bottom Pane: Timeline */}
                <div className="wb-timeline-pane">
                    <div className="wb-timeline-toolbar">
                        <div style={{ display: 'flex', gap: '8px', marginRight: '24px' }}>

                            {/* 拆分按钮: 选中场景时禁用 */}
                            <AntTooltip title={isSceneSelected ? "场景不支持拆分" : "快捷键: S (复制属性)"}>
                                <Button
                                    size="small"
                                    icon={<ScissorOutlined />}
                                    onClick={handleSplitClip}
                                    disabled={!selectedActionId || isSceneSelected}
                                >
                                    拆分
                                </Button>
                            </AntTooltip>

                            {/* 合并按钮: 选中场景时禁用 */}
                            <AntTooltip title={isSceneSelected ? "场景不支持合并" : "快捷键: M (需角色一致)"}>
                                <Button
                                    size="small"
                                    icon={<MergeCellsOutlined />}
                                    onClick={handleMergeClip}
                                    disabled={!selectedActionId || isSceneSelected}
                                >
                                    合并
                                </Button>
                            </AntTooltip>
                        </div>

                        <span style={{ fontSize: '12px', color: '#6b7280', flex: 1 }}>
                        操作: 轨道划词创建 | S键拆分 | M键合并
                    </span>

                        <div style={{ width: 200, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Slider
                                min={1}
                                max={100}
                                value={scale}
                                onChange={setScale}
                                style={{ flex: 1 }}
                                tooltip={{ formatter: (v) => `${v} px/s` }}
                            />
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
                            onSelect={(action) => setSelectedActionId(action.id)}
                            scale={scale}
                            onScaleChange={setScale}
                            videoUrl={TEST_VIDEO_URL}
                            onCreate={handleCreateClip}
                        />
                    </div>
                </div>

            </div>
        </div>
    );
};

export default AnnotationWorkbench;