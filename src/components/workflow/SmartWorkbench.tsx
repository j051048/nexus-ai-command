/**
 * 智能工作台首页
 * P2-5: 渐进式引导,不删功能
 */
import React from 'react';
import { QuickActions } from './QuickActions';

export function SmartWorkbench() {
  return (
    <div className="smart-workbench p-6">
      {/* AI助手对话框 */}
      <div className="ai-chat mb-6 p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg">
        <h2 className="text-xl font-bold mb-2">👋 你好,我是AI助手</h2>
        <p className="text-gray-600 mb-3">我可以帮你快速完成工作</p>
        <input
          type="text"
          placeholder="试试说: 帮我报销昨天去广德的机票1926元"
          className="w-full p-3 border rounded-lg"
        />
      </div>

      {/* 快速操作 */}
      <QuickActions onSubmit={(data) => console.log(data)} />

      {/* 最近任务 */}
      <div className="recent-tasks mt-6">
        <h3 className="font-semibold mb-3">最近任务</h3>
        <div className="space-y-2">
          <div className="p-3 border rounded hover:bg-gray-50">
            <p className="font-medium">差旅报销审批中</p>
            <p className="text-sm text-gray-500">2小时前</p>
          </div>
        </div>
      </div>
    </div>
  );
}