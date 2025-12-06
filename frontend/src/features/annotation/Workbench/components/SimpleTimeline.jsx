import React, { useRef, useState, useEffect } from 'react';
import { Tooltip } from 'antd';
import _ from 'lodash';
import '../style.css';

const TRACK_HEIGHT = 40;
const HEADER_HEIGHT = 30;

const SimpleTimeline = ({
                            currentTime = 0,
                            duration = 600,
                            tracks = [],
                            onSeek,
                            onUpdate, // [新增] 父组件传入的更新回调
                            // [新增] 接收选中状态和选中回调
                            selectedActionId,
                            onSelect
                        }) => {
    const containerRef = useRef(null);
    const pixelsPerSecond = 20;
    const totalWidth = Math.max(duration * pixelsPerSecond, 1000);

    // [新增] 拖拽状态
    const [draggingAction, setDraggingAction] = useState(null); // { trackId, actionId, startX, originalStart, originalEnd }

    // --- 1. 标尺点击 (Seek) ---
    const handleRulerClick = (e) => {
        if (!containerRef.current) return;
        const rect = containerRef.current.getBoundingClientRect();
        const scrollLeft = containerRef.current.scrollLeft;
        const clickX = e.clientX - rect.left + scrollLeft;
        const newTime = Math.max(0, clickX / pixelsPerSecond);
        if (onSeek) onSeek(newTime);
    };

    const renderRuler = () => {
        const step = 5;
        const count = Math.ceil(duration / step);
        return Array.from({ length: count }).map((_, i) => {
            const time = i * step;
            return (
                <div key={i} className="timeline-tick" style={{ left: time * pixelsPerSecond }}>
                    {time}s
                </div>
            );
        });
    };

    // --- 2. 核心拖拽逻辑 ---

    // A. 开始拖拽 (MouseDown)
    const handleClipMouseDown = (e, trackId, action) => {
        e.stopPropagation(); // 防止触发 Seek

        setDraggingAction({
            trackId,
            actionId: action.id,
            startX: e.clientX,
            originalStart: action.start,
            originalEnd: action.end
        });
    };

    // B. 处理移动 (MouseMove) - 使用 useEffect 绑定到全局
    useEffect(() => {
        const handleMouseMove = (e) => {
            if (!draggingAction) return;

            const deltaX = e.clientX - draggingAction.startX;
            const deltaTime = deltaX / pixelsPerSecond;

            // 计算新时间 (限制不能小于0)
            let newStart = Math.max(0, draggingAction.originalStart + deltaTime);
            let newEnd = Math.max(0, draggingAction.originalEnd + deltaTime);

            // 实时更新本地数据 (为了流畅性，我们直接修改 tracks 副本并通知父组件)
            // 注意：这里频繁调用 onUpdate 可能会导致父组件重绘，生产环境通常会用防抖或只在 MouseUp 时提交
            // 但为了演示“实时跟随”，我们先直接更新
            const newTracks = _.cloneDeep(tracks);
            const track = newTracks.find(t => t.id === draggingAction.trackId);
            const action = track.actions.find(a => a.id === draggingAction.actionId);

            if (action) {
                action.start = newStart;
                action.end = newEnd;
                onUpdate(newTracks);
            }
        };

        const handleMouseUp = () => {
            if (draggingAction) {
                setDraggingAction(null); // 结束拖拽
            }
        };

        if (draggingAction) {
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
        }

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, [draggingAction, tracks, onUpdate, pixelsPerSecond]);


    return (
        <div ref={containerRef} className="timeline-container custom-scrollbar">
            <div className="timeline-inner-wrapper" style={{ width: totalWidth }}>

                {/* 标尺 */}
                <div
                    className="timeline-ruler"
                    style={{ height: HEADER_HEIGHT }}
                    onMouseDown={handleRulerClick}
                >
                    {renderRuler()}
                </div>

                {/* 轨道 */}
                <div className="timeline-track-area">
                    {tracks.map(track => (
                        <div key={track.id} className="timeline-track" style={{ height: TRACK_HEIGHT }}>
                            <div className="timeline-track-bg" />
                            <div className="timeline-track-label">{track.name}</div>

                            {track.actions.map(action => {
                                const isDragging = draggingAction?.actionId === action.id;
                                const isSelected = selectedActionId === action.id;

                                return (
                                    <Tooltip key={action.id} title={isDragging ? '' : `${action.data.label || action.data.text}`}>
                                        <div
                                            className="timeline-clip"
                                            style={{
                                                left: action.start * pixelsPerSecond,
                                                width: (action.end - action.start) * pixelsPerSecond,
                                                backgroundColor: track.color || '#6366f1',
                                                cursor: isDragging ? 'grabbing' : 'grab',
                                                opacity: isDragging ? 0.8 : 1,
                                                zIndex: isDragging ? 50 : 1,
                                                transition: isDragging ? 'none' : 'left 0.1s, width 0.1s', // 拖拽时取消过渡，更跟手
                                                // [新增] 选中时的高亮样式 (黄色边框 + 阴影)
                                                border: isSelected ? '2px solid #fbbf24' : '1px solid rgba(255, 255, 255, 0.2)',
                                                boxShadow: isSelected ? '0 0 8px rgba(251, 191, 36, 0.5)' : 'none'
                                            }}
                                            onMouseDown={(e) => handleClipMouseDown(e, track.id, action)}
                                            // [新增] 点击选中
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                if (onSelect) onSelect(action, track);
                                            }}
                                        >
                                            {action.data.label || action.data.text}
                                        </div>
                                    </Tooltip>
                                );
                            })}
                        </div>
                    ))}
                </div>

                {/* 游标 */}
                <div
                    className="timeline-cursor"
                    style={{ left: currentTime * pixelsPerSecond }}
                >
                    <div className="timeline-cursor-head" />
                </div>

            </div>
        </div>
    );
};

export default SimpleTimeline;