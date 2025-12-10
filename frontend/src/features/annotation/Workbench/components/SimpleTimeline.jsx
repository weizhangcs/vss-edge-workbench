import React, { useRef, useState, useEffect } from 'react';
import { Tooltip } from 'antd';
import _ from 'lodash';
import Waveform from './Waveform';
import '../style.css';
import { canTrackDo } from '../config/tracks';

const TRACK_HEIGHT = 60;
const HEADER_HEIGHT = 30;
const WAVEFORM_HEIGHT = 60;

const getRulerStep = (scale) => {
    const minSpacing = 60;
    const steps = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 300, 600];
    for (const step of steps) {
        if (step * scale >= minSpacing) return step;
    }
    return 600;
};

const SimpleTimeline = ({
                            currentTime = 0,
                            duration = 600,
                            tracks = [],
                            scale = 20,
                            onSeek,
                            onUpdate,
                            onScaleChange,
                            selectedActionId,
                            onSelect,
                            onCreate, // [新增] 创建回调
                            videoUrl,
                            waveformUrl // [新增] 接收 prop
                        }) => {
    const containerRef = useRef(null);
    const totalWidth = Math.max(duration * scale, 1000);

    const [draggingAction, setDraggingAction] = useState(null);
    // [新增] 创建状态: { trackId, startX, currentX }
    const [creatingAction, setCreatingAction] = useState(null);

    // --- 1. 标尺点击 (Seek) ---
    const handleRulerClick = (e) => {
        if (!containerRef.current) return;
        const rect = containerRef.current.getBoundingClientRect();
        const scrollLeft = containerRef.current.scrollLeft;
        const clickX = e.clientX - rect.left + scrollLeft;
        const validX = Math.max(0, clickX);
        const newTime = validX / scale;
        if (onSeek) onSeek(newTime);
    };

    // --- 2. 滚轮缩放 ---
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;
        const onWheel = (e) => {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                const zoomSensitivity = 0.001;
                const newScale = Math.max(1, Math.min(200, scale * (1 - e.deltaY * zoomSensitivity)));
                if (onScaleChange) onScaleChange(newScale);
            }
        };
        container.addEventListener('wheel', onWheel, { passive: false });
        return () => container.removeEventListener('wheel', onWheel);
    }, [scale, onScaleChange]);

    const renderRuler = () => {
        const step = getRulerStep(scale);
        const count = Math.ceil(duration / step);
        return Array.from({ length: count + 1 }).map((_, i) => {
            const time = i * step;
            const left = time * scale;
            return (
                <div key={i} className="timeline-tick" style={{ left }}>
                    {step < 1 ? time.toFixed(1) : time}s
                </div>
            );
        });
    };

    // --- 3. 交互逻辑 (拖拽 Move/Resize & 画框 Create) ---

    // A. 点击已有片段 -> 准备移动/调整
    const handleClipMouseDown = (e, trackId, action, type) => {
        e.stopPropagation(); // 阻止冒泡，防止触发轨道点击
        e.preventDefault();

        // [新增] 校验权限
        if (type !== 'move' && !canTrackDo(trackId, 'resize')) {
            return; // 如果该轨道不支持 resize，忽略边缘点击
        }
        if (type === 'move' && !canTrackDo(trackId, 'move')) {
            return;
        }

        setDraggingAction({
            trackId,
            actionId: action.id,
            startX: e.clientX,
            originalStart: action.start,
            originalEnd: action.end,
            type
        });
        if (type === 'move' && onSelect) onSelect(action);
    };

    // B. 点击轨道空白处 -> 准备创建
    const handleTrackMouseDown = (e, trackId) => {

        // 如果点的是轨道背景
        const rect = containerRef.current.getBoundingClientRect();
        const scrollLeft = containerRef.current.scrollLeft;
        // 记录相对于 Timeline 内容区域的 X 坐标
        const absoluteX = e.clientX - rect.left + scrollLeft;

        setCreatingAction({
            trackId,
            startX: e.clientX, // 屏幕坐标用于计算位移
            startAbsoluteX: absoluteX, // 绝对坐标用于确定起始点
            currentX: e.clientX
        });

        // 点击空白处，取消选中
        if (onSelect) onSelect(null);
    };

    // C. 全局移动处理
    useEffect(() => {
        const handleMouseMove = (e) => {
            // Case 1: 正在调整已有片段
            if (draggingAction) {
                const deltaX = e.clientX - draggingAction.startX;
                const deltaTime = deltaX / scale;
                const MIN_DURATION = 0.2;

                let newStart = draggingAction.originalStart;
                let newEnd = draggingAction.originalEnd;

                if (draggingAction.type === 'move') {
                    const dur = draggingAction.originalEnd - draggingAction.originalStart;
                    newStart = Math.max(0, draggingAction.originalStart + deltaTime);
                    newEnd = newStart + dur;
                } else if (draggingAction.type === 'left') {
                    // 左侧调整：改变 start，保持 end 不变 (除非碰到 min duration)
                    newStart = Math.min(
                        Math.max(0, draggingAction.originalStart + deltaTime),
                        draggingAction.originalEnd - MIN_DURATION
                    );
                } else if (draggingAction.type === 'right') {
                    // 右侧调整：改变 end，保持 start 不变
                    newEnd = Math.max(
                        draggingAction.originalStart + MIN_DURATION,
                        draggingAction.originalEnd + deltaTime
                    );
                }

                const newTracks = _.cloneDeep(tracks);
                const track = newTracks.find(t => t.id === draggingAction.trackId);
                if (track) {
                    const action = track.actions.find(a => a.id === draggingAction.actionId);
                    if (action) {
                        // 实时更新本地状态，实现流畅拖拽
                        action.start = newStart;
                        action.end = newEnd;
                        // 标记为已人工修改
                        if (action.data) {
                            action.data.is_verified = true;
                            action.data.origin = 'human';
                        }
                        onUpdate(newTracks);
                    }
                }
            }
            // Case 2: 正在画新片段 (Creating)
            else if (creatingAction) {
                setCreatingAction(prev => ({
                    ...prev,
                    currentX: e.clientX
                }));
            }
        };

        const handleMouseUp = () => {
            // Case 1: 结束调整
            if (draggingAction) {
                setDraggingAction(null);
            }
            // Case 2: 结束创建 -> 提交数据
            else if (creatingAction) {
                const deltaX = creatingAction.currentX - creatingAction.startX;
                // 只有拖动距离超过一定阈值才算创建，避免误触
                if (Math.abs(deltaX) > 5) {
                    // 计算 Start / End
                    // 注意：可能向左拖，也可能向右拖
                    const x1 = creatingAction.startAbsoluteX;
                    const x2 = creatingAction.startAbsoluteX + deltaX;

                    const startPixel = Math.min(x1, x2);
                    const endPixel = Math.max(x1, x2);

                    const startTime = Math.max(0, startPixel / scale);
                    const endTime = Math.max(0, endPixel / scale);

                    if (onCreate && (endTime - startTime > 0.1)) {
                        onCreate(creatingAction.trackId, startTime, endTime);
                    }
                }
                setCreatingAction(null);
            }
        };

        if (draggingAction || creatingAction) {
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
        }

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, [draggingAction, creatingAction, tracks, onUpdate, onCreate, scale]);


    return (
        <div ref={containerRef} className="timeline-container custom-scrollbar" onWheel={() => {}}>
            <div className="timeline-inner-wrapper" style={{ width: totalWidth }}>

                {/* 1. 标尺 */}
                <div
                    className="timeline-ruler"
                    style={{ height: HEADER_HEIGHT }}
                    onMouseDown={handleRulerClick}
                >
                    {renderRuler()}
                </div>

                {/* 2. 波形图 */}
                <div className="border-b border-gray-700 bg-gray-900/50 relative">
                    <div className="absolute inset-0 border-b border-gray-800 pointer-events-none" />
                    <div className="sticky left-0 z-10 w-24 h-full flex items-center px-2 bg-gray-800/80 border-r border-gray-700 text-xs text-gray-400 font-bold backdrop-blur-sm absolute top-0">
                        AUDIO
                    </div>
                    <div style={{ paddingLeft: 0 }}>
                        <Waveform url={videoUrl} waveformUrl={waveformUrl} scale={scale} height={WAVEFORM_HEIGHT} />
                    </div>
                </div>

                {/* 3. 轨道区域 */}
                <div className="timeline-track-area">
                    {tracks.map(track => {
                        // 检查当前轨道是否支持 resize
                        const canResize = canTrackDo(track.id, 'resize');

                        return (
                            <div
                                key={track.id}
                                className="timeline-track"
                                style={{ height: TRACK_HEIGHT }}
                                onMouseDown={(e) => handleTrackMouseDown(e, track.id)}
                            >
                                <div className="timeline-track-bg" />
                                <div className="timeline-track-label select-none">{track.name}</div>

                                {track.actions.map(action => {
                                    const isDragging = draggingAction?.actionId === action.id;
                                    const isSelected = selectedActionId === action.id;

                                    return (
                                        <Tooltip key={action.id} title={isDragging ? '' : (action.data.label || action.data.text)}>
                                            <div
                                                className={`timeline-clip ${isDragging ? 'dragging' : ''}`}
                                                style={{
                                                    left: action.start * scale,
                                                    width: (action.end - action.start) * scale,
                                                    backgroundColor: track.color || '#6366f1',
                                                    cursor: isDragging ? 'grabbing' : 'grab',
                                                    // ... 其他样式保持不变，或者已移入 css 类
                                                    border: isSelected ? '2px solid #fbbf24' : '1px solid rgba(255, 255, 255, 0.2)',
                                                    boxShadow: isSelected ? '0 0 8px rgba(251, 191, 36, 0.5)' : 'none'
                                                }}
                                                onMouseDown={(e) => handleClipMouseDown(e, track.id, action, 'move')}
                                            >
                                                {/* [核心修复] 只有支持 Resize 的轨道才渲染手柄 */}
                                                {canResize && (
                                                    <div
                                                        className="timeline-clip-handle timeline-clip-handle-left"
                                                        onMouseDown={(e) => handleClipMouseDown(e, track.id, action, 'left')}
                                                    />
                                                )}

                                                <div className="timeline-clip-content">
                                                    {action.data.label || action.data.text}
                                                </div>

                                                {canResize && (
                                                    <div
                                                        className="timeline-clip-handle timeline-clip-handle-right"
                                                        onMouseDown={(e) => handleClipMouseDown(e, track.id, action, 'right')}
                                                    />
                                                )}
                                            </div>
                                        </Tooltip>
                                    );
                                })}

                                {/* 幽灵片段 (保持不变) */}
                                {creatingAction && creatingAction.trackId === track.id && (
                                    <div
                                        className="absolute top-1 bottom-1 bg-white/30 border border-white/50 rounded pointer-events-none z-40"
                                        style={{
                                            left: Math.min(creatingAction.startAbsoluteX, creatingAction.startAbsoluteX + (creatingAction.currentX - creatingAction.startX)),
                                            width: Math.abs(creatingAction.currentX - creatingAction.startX)
                                        }}
                                    />
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* 4. 游标 */}
                <div
                    className="timeline-cursor"
                    style={{ left: currentTime * scale }}
                >
                    <div className="timeline-cursor-head" />
                    <div className="w-px h-full bg-red-500/50" />
                </div>

            </div>
        </div>
    );
};

export default SimpleTimeline;