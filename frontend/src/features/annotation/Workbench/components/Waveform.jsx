import React, { useEffect, useRef, useState } from 'react';
import WaveSurfer from 'wavesurfer.js';

const Waveform = ({ url, scale, height = 60 }) => {
    const containerRef = useRef(null);
    const wavesurfer = useRef(null);
    const [isReady, setIsReady] = useState(false); // [新增] 就绪状态

    // 1. 初始化 WaveSurfer
    useEffect(() => {
        if (!containerRef.current || !url) return;

        // 防止重复初始化
        if (wavesurfer.current) {
            wavesurfer.current.destroy();
        }

        const ws = WaveSurfer.create({
            container: containerRef.current,
            waveColor: '#6b7280',
            progressColor: '#6b7280',
            cursorWidth: 0,
            height: height,
            normalize: true,
            minPxPerSec: scale,   // 初始缩放
            fillParent: true,
            interact: false,
            scrollbar: false,
            hideScrollbar: true,
            // [新增] 尝试使用 MediaElement 模式可能更稳定，但 Web Audio 性能更好
            // backend: 'WebAudio',
        });

        // [新增] 监听加载完成事件
        ws.on('ready', () => {
            console.log('[Waveform] Ready');
            setIsReady(true);
        });

        ws.on('error', (e) => {
            console.warn('[Waveform] Load Error:', e);
        });

        // 加载音频
        try {
            ws.load(url);
        } catch (e) {
            console.error(e);
        }

        wavesurfer.current = ws;

        // 清理
        return () => {
            if (wavesurfer.current) {
                try {
                    wavesurfer.current.destroy();
                } catch (e) {
                    // 忽略销毁时的潜在报错
                }
                wavesurfer.current = null;
            }
        };
    }, [url]); // 仅当 URL 变化时重新初始化

    // 2. 响应缩放 (Zoom) - [核心修复]
    useEffect(() => {
        // 只有当实例存在 且 音频已就绪 时才执行 Zoom
        if (wavesurfer.current && isReady && scale) {
            try {
                wavesurfer.current.zoom(scale);
            } catch (e) {
                console.warn('[Waveform] Zoom skipped:', e.message);
            }
        }
    }, [scale, isReady]); // 依赖 isReady

    return (
        <div
            ref={containerRef}
            className="w-full relative pointer-events-none"
            style={{ height }}
        />
    );
};

export default Waveform;