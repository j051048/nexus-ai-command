import React from 'react';
import { BossApprovalView } from '@/components/approval/ApprovalCenter';
import { AlertTriangle } from 'lucide-react';

export default function ExceptionsPage() {
    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-warning/20 flex items-center justify-center">
                    <AlertTriangle className="w-6 h-6 text-warning" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-foreground">异常待办中心</h1>
                    <p className="text-muted-foreground mt-1">
                        集中处理超出阈值、合规风险及紧急审批事项
                    </p>
                </div>
            </div>

            <div className="bg-warning/5 border border-warning/20 rounded-lg p-4 mb-6">
                <h3 className="text-warning font-semibold flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-4 h-4" />
                    系统检测到以下异常
                </h3>
                <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                    <li>3笔采购申请超出部门预算阈值（&gt;¥5,000）</li>
                    <li>1笔差旅报销单据日期与行程不符</li>
                </ul>
            </div>

            <BossApprovalView />
        </div>
    );
}
