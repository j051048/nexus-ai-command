import { useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { Node } from '@xyflow/react';
import { Settings2 } from 'lucide-react';

interface WorkflowPropertiesProps {
  selectedNode: Node | null;
  onNodeUpdate: (nodeId: string, data: Record<string, unknown>) => void;
}

export function WorkflowProperties({ selectedNode, onNodeUpdate }: WorkflowPropertiesProps) {
  const updateField = useCallback(
    (field: string, value: unknown) => {
      if (!selectedNode) return;
      onNodeUpdate(selectedNode.id, {
        ...selectedNode.data,
        [field]: value,
      });
    },
    [selectedNode, onNodeUpdate]
  );

  if (!selectedNode) {
    return (
      <Card className="w-64 flex-shrink-0 h-full">
        <CardContent className="flex flex-col items-center justify-center h-full text-center p-6">
          <Settings2 className="w-10 h-10 text-muted-foreground/40 mb-3" />
          <p className="text-sm text-muted-foreground">
            选择一个节点以编辑其属性
          </p>
        </CardContent>
      </Card>
    );
  }

  const nodeData = selectedNode.data as Record<string, unknown>;
  const nodeType = selectedNode.type;

  return (
    <Card className="w-64 flex-shrink-0 h-full overflow-auto">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">节点属性</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        {/* 通用: 标签名称 */}
        <div className="space-y-1.5">
          <Label className="text-xs">节点名称</Label>
          <Input
            value={(nodeData.label as string) || ''}
            onChange={(e) => updateField('label', e.target.value)}
            placeholder="输入节点名称"
            className="h-8 text-sm"
          />
        </div>

        {/* 审批人节点 */}
        {nodeType === 'approver' && (
          <>
            <div className="space-y-1.5">
              <Label className="text-xs">审批角色</Label>
              <Select
                value={(nodeData.role as string) || 'manager'}
                onValueChange={(v) => updateField('role', v)}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="manager">部门经理</SelectItem>
                  <SelectItem value="director">总监</SelectItem>
                  <SelectItem value="cfo">CFO</SelectItem>
                  <SelectItem value="ceo">CEO</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">超时时间 (小时)</Label>
              <Input
                type="number"
                value={(nodeData.timeout_hours as number) || 0}
                onChange={(e) => updateField('timeout_hours', Number(e.target.value))}
                className="h-8 text-sm"
                min={0}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-xs">允许委托</Label>
              <Switch
                checked={!!nodeData.can_delegate}
                onCheckedChange={(v) => updateField('can_delegate', v)}
              />
            </div>
          </>
        )}

        {/* 条件分支节点 */}
        {nodeType === 'condition' && (
          <>
            <div className="space-y-1.5">
              <Label className="text-xs">条件字段</Label>
              <Select
                value={(nodeData.field as string) || 'amount'}
                onValueChange={(v) => updateField('field', v)}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="amount">金额</SelectItem>
                  <SelectItem value="type">类型</SelectItem>
                  <SelectItem value="department">部门</SelectItem>
                  <SelectItem value="level">级别</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">操作符</Label>
              <Select
                value={(nodeData.operator as string) || 'gt'}
                onValueChange={(v) => updateField('operator', v)}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gt">大于 (&gt;)</SelectItem>
                  <SelectItem value="gte">大于等于 (&gt;=)</SelectItem>
                  <SelectItem value="lt">小于 (&lt;)</SelectItem>
                  <SelectItem value="lte">小于等于 (&lt;=)</SelectItem>
                  <SelectItem value="eq">等于 (=)</SelectItem>
                  <SelectItem value="neq">不等于 (!=)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">条件值</Label>
              <Input
                value={(nodeData.value as string) || ''}
                onChange={(e) => updateField('value', e.target.value)}
                placeholder="例如: 5000"
                className="h-8 text-sm"
              />
            </div>
          </>
        )}

        {/* 并行审批节点 */}
        {nodeType === 'parallel' && (
          <div className="space-y-1.5">
            <Label className="text-xs">并行人数</Label>
            <Input
              type="number"
              value={(nodeData.parallel_count as number) || 2}
              onChange={(e) => updateField('parallel_count', Number(e.target.value))}
              className="h-8 text-sm"
              min={2}
              max={10}
            />
          </div>
        )}

        {/* 自动审批节点 */}
        {nodeType === 'auto_approve' && (
          <div className="space-y-1.5">
            <Label className="text-xs">自动审批金额上限</Label>
            <Input
              type="number"
              value={(nodeData.max_amount as number) || 0}
              onChange={(e) => updateField('max_amount', Number(e.target.value))}
              placeholder="例如: 1000"
              className="h-8 text-sm"
              min={0}
            />
          </div>
        )}

        {/* 通知节点 */}
        {nodeType === 'notify' && (
          <>
            <div className="space-y-2">
              <Label className="text-xs">通知渠道</Label>
              {[
                { value: 'email', label: '邮件' },
                { value: 'wechat_work', label: '企业微信' },
                { value: 'dingtalk', label: '钉钉' },
                { value: 'sms', label: '短信' },
              ].map((channel) => {
                const channels = (nodeData.channels as string[]) || [];
                const isChecked = channels.includes(channel.value);
                return (
                  <div key={channel.value} className="flex items-center gap-2">
                    <Checkbox
                      id={`channel-${channel.value}`}
                      checked={isChecked}
                      onCheckedChange={(checked) => {
                        const newChannels = checked
                          ? [...channels, channel.value]
                          : channels.filter((c) => c !== channel.value);
                        updateField('channels', newChannels);
                      }}
                    />
                    <Label htmlFor={`channel-${channel.value}`} className="text-xs">
                      {channel.label}
                    </Label>
                  </div>
                );
              })}
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">通知模板</Label>
              <Select
                value={(nodeData.template as string) || 'default'}
                onValueChange={(v) => updateField('template', v)}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">默认模板</SelectItem>
                  <SelectItem value="approval_passed">审批通过通知</SelectItem>
                  <SelectItem value="approval_rejected">审批拒绝通知</SelectItem>
                  <SelectItem value="pending_reminder">待审批提醒</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
