import { useState, useRef } from 'react';

export const usePlayerController = () => {
    const [playing, setPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [scale, setScale] = useState(20);
    const videoRef = useRef(null);

    const togglePlay = () => setPlaying(!playing);

    // 视频 -> UI
    const handleProgress = (state) => setCurrentTime(state.playedSeconds);

    // UI -> 视频 (Seek)
    const handleSeek = (time) => {
        setCurrentTime(time);
        if (playing) setPlaying(false); // 拖动即暂停
        if (videoRef.current) videoRef.current.seekTo(time);
    };

    // 键盘快捷键
    const handleKeyDown = (e, actions) => {
        if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

        switch(e.code) {
            case 'Space':
                e.preventDefault();
                togglePlay();
                break;
            case 'Backspace':
            case 'Delete':
                if (actions.selectedId) {
                    e.preventDefault();
                    actions.onDelete(actions.selectedId);
                }
                break;
            case 'KeyS':
                e.preventDefault();
                actions.onSplit();
                break;
            case 'KeyM':
                e.preventDefault();
                actions.onMerge();
                break;
        }
    };

    return {
        videoRef,
        playing, setPlaying,
        currentTime, setCurrentTime,
        duration, setDuration,
        scale, setScale,
        togglePlay, handleProgress, handleSeek, handleKeyDown
    };
};