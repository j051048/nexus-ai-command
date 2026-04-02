/**
 * 批量审批组件 + AI智能推荐
 * P0-2: 多选框、批量操作、AI推荐审批决策
 */
import React, { useState } from 'react';
import { CheckSquare, XSquare, Sparkles } from 'lucide-react';

interface ApprovalRequest {
  id: string;
  title: string;
  amount: number;
}

interface AISuggestion {
  approve_count: number;
  reject_count: number;
  reason: string;
}

interface BatchApprovalProps {
  requests: ApprovalRequest[];
  onBatchApprove: (ids: string[]) => void;
  onBatchReject: (ids: string[]) => void;
}

export function BatchApproval({ requests, onBatchApprove, onBatchReject }: BatchApprovalProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [aiSuggestions, setAiSuggestions] = useState<AISuggestion | null>(null);

  // 全选/取消全选
  const toggleSelectAll = () => {
    if (selectedIds.length === requests.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(requests.map(r => r.id));
    }
  };

  // AI智能推荐
  const getAiSuggestions = async () => {
    const response = await fetch('/api/ai/batch-approval-suggestions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_ids: selectedIds })
    });
    const data = await response.json();
    setAiSuggestions(data);
  };

  return (
    <div className="batch-approval">
      {/* 批量操作栏 */}
      <div className="batch-toolbar flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
        <input
          type="checkbox"
          checked={selectedIds.length === requests.length}
          onChange={toggleSelectAll}
        />
        <span className="text-sm text-gray-600">
          已选 {selectedIds.length}/{requests.length}
        </span>

        {selectedIds.length > 0 && (
          <>
            <button
              onClick={() => onBatchApprove(selectedIds)}
              className="px-3 py-1 bg-green-500 text-white rounded"
            >
              <CheckSquare className="inline w-4 h-4 mr-1" />
              批量通过
            </button>
            <button
              onClick={() => onBatchReject(selectedIds)}
              className="px-3 py-1 bg-red-500 text-white rounded"
            >
              <XSquare className="inline w-4 h-4 mr-1" />
              批量驳回
            </button>
            <button
              onClick={getAiSuggestions}
              className="px-3 py-1 bg-purple-500 text-white rounded"
            >
              <Sparkles className="inline w-4 h-4 mr-1" />
              AI建议
            </button>
          </>
        )}
      </div>

      {/* AI建议面板 */}
      {aiSuggestions && (
        <div className="ai-suggestions mt-3 p-4 bg-purple-50 rounded-lg">
          <h4 className="font-medium mb-2">AI审批建议</h4>
          <div className="space-y-2">
            <p className="text-sm">
              建议通过: {aiSuggestions.approve_count}个
            </p>
            <p className="text-sm">
              建议驳回: {aiSuggestions.reject_count}个
            </p>
            <p className="text-sm text-gray-600">
              {aiSuggestions.reason}
            </p>
          </div>
        </div>
      )}

      {/* 审批列表 */}
      <div className="approval-list mt-4 space-y-2">
        {requests.map(req => (
          <div key={req.id} className="flex items-center gap-3 p-3 border rounded">
            <input
              type="checkbox"
              checked={selectedIds.includes(req.id)}
              onChange={(e) => {
                if (e.target.checked) {
                  setSelectedIds([...selectedIds, req.id]);
                } else {
                  setSelectedIds(selectedIds.filter(id => id !== req.id));
                }
              }}
            />
            <div className="flex-1">
              <h4 className="font-medium">{req.title}</h4>
              <p className="text-sm text-gray-600">¥{req.amount}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}