import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import WorkflowDesigner from '@/pages/WorkflowDesigner';
import { describe, it, expect, vi } from 'vitest';
import '@testing-library/jest-dom';

// P1: 前端核心特色组件测试 (React Flow 设计器)

/**
 * 确保审批流 Canvas 在进行节点操作后，能够持久化状态或同步至内部状态，
 * 避免撤销/保存动作失效。
 */
describe('WorkflowDesigner Persistence & Visual Logic', () => {
    
    it('正确渲染画布并能在添加节点后保留该状态', async () => {
        // 使用 ReactFlowProvider 包裹以注入 Context
        const { container } = render(
            <ReactFlowProvider>
                <WorkflowDesigner />
            </ReactFlowProvider>
        );

        // 1. 验证基础 Canvas 是否渲染
        expect(container.querySelector('.react-flow')).toBeInTheDocument();

        // 2. 模拟按钮点击添加一个“审批节点”
        const addBtn = screen.getByText(/添加节点/i);
        fireEvent.click(addBtn);

        // 3. 验证节点是否出现在 DOM 中
        await waitFor(() => {
            const nodes = container.querySelectorAll('.react-flow__node');
            expect(nodes.length).toBeGreaterThan(0);
        });

        // 4. 模拟保存操作
        const saveBtn = screen.getByText(/保存/i);
        fireEvent.click(saveBtn);
        
        // 验证 Toast 提示 (基于 sonner)
        await waitFor(() => {
            expect(screen.getByText(/已保存/i)).toBeInTheDocument();
        });
    });

    it('撤销操作 (Undo) 能够将 Canvas 回滚至上一个状态', async () => {
        const { container } = render(
            <ReactFlowProvider>
                <WorkflowDesigner />
            </ReactFlowProvider>
        );

        // a. 添加节点
        fireEvent.click(screen.getByText(/添加节点/i));
        
        // b. 确认节点个数
        let nodeCount = container.querySelectorAll('.react-flow__node').length;
        
        // c. 点击撤销按钮
        const undoBtn = screen.getByLabelText(/撤销/i); // 假设由 aria-label="撤销"
        fireEvent.click(undoBtn);

        // d. 确认节点个数回滚
        await waitFor(() => {
            expect(container.querySelectorAll('.react-flow__node').length).toBe(nodeCount - 1);
        });
    });
});
