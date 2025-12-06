import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppProvider } from '@/shared/theme';
import InferenceFacts from '../features/inference/InferenceFacts';

const context = window.SERVER_CONTEXT || { items: [] };

const rootNode = document.getElementById('react-root-facts');
if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(
        <AppProvider>
            <InferenceFacts context={context} />
        </AppProvider>
    );
}