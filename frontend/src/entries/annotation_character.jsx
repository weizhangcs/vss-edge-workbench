import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppProvider } from '@/shared/theme';
import CharacterAnnotation from "../features/annotation/CharacterAnnotation";

// 注意：这里 context 可能为空，需要默认值防崩
const context = window.SERVER_CONTEXT || { items: [], pagination: {}, filter: {}, statusOptions: [] };

const rootNode = document.getElementById('react-root-l1');
if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(
        <AppProvider>
            <CharacterAnnotation context={context} />
        </AppProvider>
    );
}