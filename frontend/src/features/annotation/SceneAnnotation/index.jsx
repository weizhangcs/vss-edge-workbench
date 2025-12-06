// frontend/src/features/annotation/SceneAnnotation/index.jsx
import React from 'react';
import TaskTable from '../components/TaskTable';

const SceneAnnotation = ({ context }) => {
    const { items, pagination, filter, statusOptions } = context;

    const updateUrl = (params) => {
        const searchParams = new URLSearchParams(window.location.search);
        Object.keys(params).forEach(key => {
            if (params[key] === 'ALL' || !params[key]) {
                searchParams.delete(key);
            } else {
                searchParams.set(key, params[key]);
            }
        });
        window.location.search = searchParams.toString();
    };

    const handleFilterChange = (value) => {
        updateUrl({ l2l3_status: value, l2l3_page: 1 });
    };

    const handlePageChange = (page) => {
        updateUrl({ l2l3_page: page });
    };

    return (
        <TaskTable
            title="子任务列表：场景标注"
            dataSource={items}
            pagination={pagination}
            filter={{ currentValue: filter.active }}
            statusOptions={statusOptions}
            onFilterChange={handleFilterChange}
            onPageChange={handlePageChange}
        />
    );
};

export default SceneAnnotation;