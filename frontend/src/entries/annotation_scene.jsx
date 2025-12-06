import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppProvider } from '@/shared/theme';
import SceneAnnotation from '../features/annotation/SceneAnnotation';

const context = window.SERVER_CONTEXT || { items: [], pagination: {}, filter: {}, statusOptions: [] };

const rootNode = document.getElementById('react-root-l2');
if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(
        <AppProvider>
            <SceneAnnotation context={context} />
        </AppProvider>
    );
}