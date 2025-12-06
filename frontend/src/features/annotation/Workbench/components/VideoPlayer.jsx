import React, { forwardRef, useImperativeHandle, useRef, useEffect } from 'react';

const VideoPlayer = forwardRef(({ url, playing, onProgress, onDuration, onReady, onPlay, onPause }, ref) => {
    const videoRef = useRef(null);
    const lastLogTime = useRef(0); // 用于限制日志频率

    useImperativeHandle(ref, () => ({
        seekTo: (seconds) => {
            if (videoRef.current) {
                console.log(`[VideoPlayer] 执行 Seek -> ${seconds}s`);
                videoRef.current.currentTime = seconds;
            }
        },
        getCurrentTime: () => {
            return videoRef.current ? videoRef.current.currentTime : 0;
        }
    }));

    // 状态同步：React -> Native
    useEffect(() => {
        const video = videoRef.current;
        if (!video) return;
        if (playing && video.paused) {
            video.play().catch(e => console.error("[VideoPlayer] Play Error:", e));
        } else if (!playing && !video.paused) {
            video.pause();
        }
    }, [playing]);

    return (
        <div className="w-full h-full bg-black flex items-center justify-center overflow-hidden">
            <video
                ref={videoRef}
                src={url}
                className="w-full h-full object-contain"
                controls={true} // 保持原生控件用于调试

                onPlay={() => {
                    console.log('[VideoPlayer] Native Play Event');
                    if (onPlay) onPlay();
                }}
                onPause={() => {
                    console.log('[VideoPlayer] Native Pause Event');
                    if (onPause) onPause();
                }}
                onLoadedMetadata={() => {
                    console.log('[VideoPlayer] Metadata Loaded. Duration:', videoRef.current?.duration);
                    if (onDuration && videoRef.current) onDuration(videoRef.current.duration);
                    if (onReady) onReady();
                }}
                onTimeUpdate={() => {
                    if (videoRef.current) {
                        const now = videoRef.current.currentTime;
                        // 限制日志频率：每2秒打一次，证明还在活著
                        if (Math.abs(now - lastLogTime.current) > 2) {
                            console.log(`[VideoPlayer] TimeUpdate: ${now.toFixed(2)}s`);
                            lastLogTime.current = now;
                        }

                        if (onProgress) {
                            onProgress({ playedSeconds: now });
                        }
                    }
                }}
                onError={(e) => console.error('[VideoPlayer] Native Error:', e)}
            />
        </div>
    );
});

export default VideoPlayer;