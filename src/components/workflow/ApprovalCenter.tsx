/**
 * 审批中心主页面
 * Phase 1-3: 包含待办列表、流程可视化、数据分析看板
 */
import React, { useState, useEffect } from 'react';

export function ApprovalCenter() {
  const [activeTab, setActiveTab] = useState('pending');
  const [requests, setRequests] = useState([]);

  return (
    <div className="approval-center">
      {/* 顶部统计卡片 */}
      <div className="stats-grid grid grid-cols-4 gap-4 mb-6">
        <div className="stat-card bg-orange-50 p-4 rounded-lg">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white rounded">
              <span>📝</span>
            </div>
            <div>
              <p className="text-sm text-gray-600">待审批</p>
              <p className="text-2xl font-bold text-orange-600">12</p>
            </div>
          </div>
        </div>

        <div className="stat-card bg-blue-50 p-4 rounded-lg">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white rounded">
              <span>⏱️</span>
            </div>
            <div>
              <p className="text-sm text-gray-600">进行中</p>
              <p className="text-2xl font-bold text-blue-600">5</p>
            </div>
          </div>
        </div>

        <div className="stat-card bg-green-50 p-4 rounded-lg">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white rounded">
              <span>✅</span>
            </div>
            <div>
              <p className="text-sm text-gray-600">已完成</p>
              <p className="text-2xl font-bold text-green-600">38</p>
            </div>
          </div>
        </div>

        <div className="stat-card bg-purple-50 p-4 rounded-lg">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white rounded">
              <span>📈</span>
            </div>
            <div>
              <p className="text-sm text-gray-600">本月费用</p>
              <p className="text-2xl font-bold text-purple-600">¥52,340</p>
            </div>
          </div>
        </div>
      </div>

      {/* 标签页 */}
      <div className="tabs-container">
        <div className="border-b">
          <div className="flex gap-8">
            <button
              className={`pb-3 px-1 ${activeTab === 'pending' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('pending')}
            >
              待办事项
            </button>
            <button
              className={`pb-3 px-1 ${activeTab === 'submitted' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('submitted')}
            >
              我发起的
            </button>
            <button
              className={`pb-3 px-1 ${activeTab === 'completed' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('completed')}
            >
              已完成
            </button>
            <button
              className={`pb-3 px-1 ${activeTab === 'analytics' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('analytics')}
            >
              数据分析
            </button>
          </div>
        </div>

        {/* 待办列表 */}
        {activeTab === 'pending' && (
          <div className="pending-list mt-6 space-y-3">
            {/* 示例审批卡片 */}
            <div className="approval-card border rounded-lg p-4 bg-white">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-1 bg-blue-100 text-blue-600 text-xs rounded">差旅报销</span>
                    <h3 className="font-medium">张三的差旅报销申请</h3>
                  </div>
                  <p className="text-sm text-gray-600">金额: ¥1,926</p>
                  <div className="flex items-center gap-2 mt-3">
                    <div className="flex-1 h-2 bg-gray-200 rounded">
                      <div className="h-2 bg-blue-500 rounded" style={{width: '50%'}}></div>
                    </div>
                    <span className="text-xs text-gray-500">2/4步</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="px-3 py-1 text-sm border rounded hover:bg-gray-50">查看</button>
                  <button className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600">审批</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 数据分析 */}
        {activeTab === 'analytics' && (
          <div className="analytics-dashboard mt-6 grid grid-cols-2 gap-6">
            {/* 费用趋势 */}
            <div className="border rounded-lg p-6 bg-white">
              <h3 className="text-lg font-semibold mb-4">部门费用趋势</h3>
              <div className="h-64 flex items-center justify-center text-gray-400">
                图表区域 - 近6个月费用趋势
              </div>
            </div>

            {/* 审批效率 */}
            <div className="border rounded-lg p-6 bg-white">
              <h3 className="text-lg font-semibold mb-4">审批效率分析</h3>
              <div className="space-y-4">
                <div className="flex justify-between">
                  <span>审批通过率</span>
                  <span className="font-bold text-green-600">85.3%</span>
                </div>
                <div className="flex justify-between">
                  <span>平均审批时长</span>
                  <span className="font-bold">24小时</span>
                </div>
                <div className="flex justify-between">
                  <span>超时率</span>
                  <span className="font-bold text-orange-500">10%</span>
                </div>
                <div className="flex justify-between">
                  <span>本月总申请</span>
                  <span className="font-bold">55</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}