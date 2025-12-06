import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppProvider } from '@/shared/theme';
import InferenceRag from '../features/inference/InferenceRag';

const rootNode = document.getElementById('react-root-rag');
if (rootNode) {
    const root = ReactDOM.createRoot(rootNode);
    root.render(
        <AppProvider>
            <InferenceRag />
        </AppProvider>
    );
}