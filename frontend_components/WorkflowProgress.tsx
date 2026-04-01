/**
 * 工作流实时进度追踪组件
 * Phase 1: 显示当前审批进度、预计完成时间
 */
import React from 'react';
import { CheckCircle, Clock, Circle } from 'lucide-react';

interface Step {
  name: string;
  status: 'completed' | 'current' | 'pending';
  approver?: string;
  time?: string;
  estimatedTime?: string;
}

interface WorkflowProgressProps {
  requestId: string;
  steps: Step[];
}

export function WorkflowProgress({ requestId, steps }: WorkflowProgressProps) {
  return (
    <div className="workflow-progress">
      <div className="timeline">
        {steps.map((step, index) => (
          <div key={index} className={`step step-${step.status}`}>
            <div className="step-icon">
              {step.status === 'completed' && <CheckCircle className="text-green-500" />}
              {step.status === 'current' && <Clock className="text-blue-500 animate-pulse" />}
              {step.status === 'pending' && <Circle className="text-gray-300" />}
            </div>
            <div className="step-content">
              <h4 className="font-medium">{step.name}</h4>
              {step.approver && <p className="text-sm text-gray-600">审批人: {step.approver}</p>}
              {step.time && <span className="text-xs text-gray-500">{step.time}</span>}
              {step.estimatedTime && (
                <span className="text-xs text-orange-500">{step.estimatedTime}</span>
              )}
            </div>
            {index < steps.length - 1 && <div className="step-connector" />}
          </div>
        ))}
      </div>
    </div>
  );
}
