import React, { useState, useRef, useMemo, useEffect } from 'react';
import { Typography, Space, Button, message, Spin } from 'antd'; // [新增] Spin, message
import { PlayCircleOutlined, PauseCircleOutlined, SaveOutlined, ArrowLeftOutlined, CloudDownloadOutlined } from '@ant-design/icons';
import _ from 'lodash';
import VideoPlayer from './components/VideoPlayer';
import SimpleTimeline from './components/SimpleTimeline';
import Inspector from './components/Inspector';
import { parseSRT } from './utils/parsers'; // [新增] 引入解析器
import './style.css';

const { Title } = Typography;

// [配置] 你的真实测试数据地址
// 请确保这个地址允许跨域 (CORS) 或同域访问
const TEST_VIDEO_URL = "http://localhost:9999/media/source_files/5124d170-c299-4d58-8447-abdaac2af5aa/media/1.mp4";
const TEST_SRT_URL = "http://localhost:9999/media/source_files/5124d170-c299-4d58-8447-abdaac2af5aa/subtitles/1.srt"; // 假设有一个同名的 srt

const AnnotationWorkbench = () => {
    const [playing, setPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);

    // 初始为空轨道，等待加载
    const [tracks, setTracks] = useState([]);
    const [loading, setLoading] = useState(true); // [新增] 加载状态

    const [selectedActionId, setSelectedActionId] = useState(null);
    const videoRef = useRef(null);

    // --- 1. 数据加载 (模拟从后端 Fetch) ---
    useEffect(() => {
        const loadData = async () => {
            try {
                setLoading(true);

                // A. 获取字幕文件
                // 注意：如果你的 SRT 地址是本地文件路径，浏览器无法直接 fetch，必须是 http URL
                // 这里我们先尝试 fetch，如果失败（比如文件不存在），则回退到空数组
                let subtitleActions = [];
                try {
                    const resp = await fetch(TEST_SRT_URL);
                    if (resp.ok) {
                        const text = await resp.text();
                        subtitleActions = parseSRT(text);
                        message.success(`成功加载 ${subtitleActions.length} 条字幕`);
                    } else {
                        console.warn("SRT file not found, loading empty track.");
                    }
                } catch (e) {
                    console.error("Fetch SRT failed:", e);
                    // 仅作演示：如果 fetch 失败，生成一点假数据测试布局
                    subtitleActions = [
                        { id: 'demo1', start: 1, end: 5, data: { text: 'Fetch失败，这是测试数据', speaker: 'System' } }
                    ];
                }

                // B. 组装轨道
                const newTracks = [
                    {
                        id: 'scenes',
                        name: 'SCENES',
                        color: '#d8b4fe',
                        actions: [] // 场景轨初始为空，等待用户添加
                    },
                    {
                        id: 'subs',
                        name: 'DIALOG',
                        color: '#bae7ff',
                        actions: subtitleActions // 填入解析后的字幕
                    }
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

    // ... (selectedContext, handleProgress, handleSeek 等保持不变) ...
    // 为节省篇幅，以下重复代码省略，请保持原样，只修改 return 部分

    const selectedContext = useMemo(() => {
        if (!selectedActionId) return { action: null, track: null };
        for (const track of tracks) {
            const action = track.actions.find(a => a.id === selectedActionId);
            if (action) return { action, track };
        }
        return { action: null, track: null };
    }, [selectedActionId, tracks]);

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
    };

    const togglePlay = () => setPlaying(!playing);

    return (
        <div className="wb-container">
            {/* Header (不变) */}
            <header className="wb-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => window.history.back()} />
                    <div>
                        <Title level={4} style={{ margin: 0 }}>Big Buck Bunny (Real Data)</Title>
                        <span style={{ fontSize: '12px', color: '#9ca3af' }}>SRT 解析演示</span>
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

                {/* Loading 遮罩 */}
                {loading && (
                    <div className="absolute inset-0 bg-white/50 z-50 flex items-center justify-center">
                        <Spin size="large" tip="加载数据中..." />
                    </div>
                )}

                {/* Top Pane: Stage */}
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
                        <span style={{ flex: 1 }}>Tracks: {tracks.length} | Items: {tracks.reduce((acc, t) => acc + t.actions.length, 0)}</span>
                        <span>按住 Ctrl 滚轮缩放</span>
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
                        />
                    </div>
                </div>

            </div>
        </div>
    );
};

export default AnnotationWorkbench;