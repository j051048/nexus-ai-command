/**
 * VMD Agent 配置管理页面
 * Agent卡片网格 + 编辑弹窗（系统提示词、工具白名单、场景、模型层级）
 */

import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import {
  Bot,
  Settings2,
  Loader2,
  Wrench,
  Zap,
  Shield,
} from 'lucide-react';
import { useVMDAgents, useUpdateVMDAgent, type VMDAgent } from '@/hooks/useVMD';
import { SCENES } from '@/components/vmd/SceneSelector';

// Agent 默认配置（用于在 API 返回数据前展示占位）
const DEFAULT_AGENTS: Partial<VMDAgent>[] = [
  { agent_code: 'director', name: '市场总监Agent', role_description: '全局协调、任务拆解与资源调度', icon: '\uD83C\uDFAF' },
  { agent_code: 'content', name: '内容营销Agent', role_description: '文案撰写、内容策划与SEO优化', icon: '\u270D\uFE0F' },
  { agent_code: 'design', name: '设计Agent', role_description: '视觉设计、排版与素材生成', icon: '\uD83C\uDFA8' },
  { agent_code: 'media', name: '媒介投放Agent', role_description: '渠道选择、预算分配与投放优化', icon: '\uD83D\uDCE2' },
  { agent_code: 'clue', name: '线索挖掘Agent', role_description: '市场情报收集、线索评分与分配', icon: '\uD83D\uDD0D' },
  { agent_code: 'compliance', name: '合规校验Agent', role_description: '广告法/计量法/招投标法合规审查', icon: '\uD83D\uDEE1\uFE0F' },
  { agent_code: 'operation', name: '运营Agent', role_description: '活动运营、展会管理与数据分析', icon: '\u2699\uFE0F' },
  { agent_code: 'synergy', name: '研产销协同Agent', role_description: '需求协同、市场洞察与产品反馈', icon: '\uD83D\uDD17' },
  { agent_code: 'pr', name: '公关Agent', role_description: '舆情监控、危机公关与媒体关系', icon: '\uD83D\uDCF0' },
  { agent_code: 'sales', name: '销售支持Agent', role_description: '销售物料、话术生成与客户跟进', icon: '\uD83D\uDCB0' },
];

// 所有可用工具
const ALL_TOOLS = [
  'web_search', 'content_generate', 'image_generate', 'compliance_check',
  'clue_search', 'bid_monitor', 'data_analyze', 'email_send',
  'social_post', 'document_generate', 'crm_update', 'task_create',
];

const TOOL_NAMES: Record<string, string> = {
  web_search: '网络搜索',
  content_generate: '内容生成',
  image_generate: '图片生成',
  compliance_check: '合规校验',
  clue_search: '线索搜索',
  bid_monitor: '招标监控',
  data_analyze: '数据分析',
  email_send: '邮件发送',
  social_post: '社媒发布',
  document_generate: '文档生成',
  crm_update: 'CRM更新',
  task_create: '任务创建',
};

export default function VMDAgentConfig() {
  const { data: agents, isLoading } = useVMDAgents();
  const updateAgent = useUpdateVMDAgent();
  const [editAgent, setEditAgent] = useState<VMDAgent | null>(null);

  // Use API data or fallback to defaults for display
  const displayAgents = agents || DEFAULT_AGENTS.map((a, i) => ({
    id: `default-${i}`,
    agent_code: a.agent_code || '',
    name: a.name || '',
    role_description: a.role_description || '',
    system_prompt: '',
    tool_whitelist: [],
    scene_codes: [],
    model_tier: 'standard' as const,
    is_active: true,
    icon: a.icon || '\uD83E\uDD16',
  }));

  const handleSave = async () => {
    if (!editAgent || editAgent.id.startsWith('default-')) return;
    await updateAgent.mutateAsync(editAgent);
    setEditAgent(null);
  };

  const handleToggleActive = async (agent: VMDAgent) => {
    if (agent.id.startsWith('default-')) return;
    await updateAgent.mutateAsync({ id: agent.id, is_active: !agent.is_active });
  };

  const toggleTool = (tool: string) => {
    if (!editAgent) return;
    const current = editAgent.tool_whitelist || [];
    setEditAgent({
      ...editAgent,
      tool_whitelist: current.includes(tool)
        ? current.filter(t => t !== tool)
        : [...current, tool],
    });
  };

  const toggleScene = (sceneCode: string) => {
    if (!editAgent) return;
    const current = editAgent.scene_codes || [];
    setEditAgent({
      ...editAgent,
      scene_codes: current.includes(sceneCode)
        ? current.filter(s => s !== sceneCode)
        : [...current, sceneCode],
    });
  };

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight">Agent 配置</h1>
        <p className="text-muted-foreground">管理虚拟市场部的 10 个专业 AI Agent 角色配置</p>
      </div>

      {/* Agent Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="h-48 w-full rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {displayAgents.map((agent) => (
            <Card
              key={agent.id}
              className={cn(
                "group hover:shadow-md transition-all cursor-pointer border-border/50 hover:border-primary/50 relative",
                !agent.is_active && "opacity-60"
              )}
              onClick={() => setEditAgent(agent as VMDAgent)}
            >
              <CardContent className="p-5">
                {/* Active indicator */}
                <div className="absolute top-3 right-3">
                  <div className={cn(
                    "w-2.5 h-2.5 rounded-full",
                    agent.is_active ? "bg-green-500" : "bg-gray-400"
                  )} />
                </div>

                <div className="flex flex-col items-center text-center">
                  <span className="text-4xl mb-3">{agent.icon}</span>
                  <h3 className="font-semibold text-sm mb-1">{agent.name}</h3>
                  <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
                    {agent.role_description}
                  </p>

                  <div className="flex items-center gap-2 flex-wrap justify-center">
                    <Badge variant="secondary" className="text-[10px] gap-1">
                      <Wrench className="w-3 h-3" />
                      {(agent.tool_whitelist || []).length} 工具
                    </Badge>
                    <Badge
                      variant="secondary"
                      className={cn(
                        "text-[10px] gap-1",
                        agent.model_tier === 'high'
                          ? "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
                          : ""
                      )}
                    >
                      <Zap className="w-3 h-3" />
                      {agent.model_tier === 'high' ? '高能力' : '标准'}
                    </Badge>
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-border/50 flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">
                    {agent.is_active ? '已启用' : '已停用'}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditAgent(agent as VMDAgent);
                    }}
                  >
                    <Settings2 className="w-3 h-3 mr-1" /> 配置
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog open={!!editAgent} onOpenChange={(open) => { if (!open) setEditAgent(null); }}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <span className="text-xl">{editAgent?.icon}</span>
              {editAgent?.name}
            </DialogTitle>
            <DialogDescription>{editAgent?.role_description}</DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh] pr-4">
            <div className="space-y-6 py-2">
              {/* Active Toggle */}
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">启用状态</Label>
                  <p className="text-xs text-muted-foreground">停用后该 Agent 将不参与任务执行</p>
                </div>
                <Switch
                  checked={editAgent?.is_active ?? true}
                  onCheckedChange={(checked) =>
                    editAgent && setEditAgent({ ...editAgent, is_active: checked })
                  }
                />
              </div>

              {/* System Prompt */}
              <div className="space-y-2">
                <Label>系统提示词 (System Prompt)</Label>
                <Textarea
                  className="font-mono text-xs min-h-[150px]"
                  placeholder="定义该 Agent 的角色、能力和行为准则..."
                  value={editAgent?.system_prompt || ''}
                  onChange={(e) =>
                    editAgent && setEditAgent({ ...editAgent, system_prompt: e.target.value })
                  }
                />
              </div>

              {/* Model Tier */}
              <div className="space-y-2">
                <Label>模型层级</Label>
                <Select
                  value={editAgent?.model_tier || 'standard'}
                  onValueChange={(v) =>
                    editAgent && setEditAgent({ ...editAgent, model_tier: v as 'high' | 'standard' })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high">高能力模型（GPT-4 级别）</SelectItem>
                    <SelectItem value="standard">标准模型（GPT-3.5 级别）</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Tool Whitelist */}
              <div className="space-y-2">
                <Label>工具白名单</Label>
                <div className="flex flex-wrap gap-2">
                  {ALL_TOOLS.map((tool) => {
                    const selected = (editAgent?.tool_whitelist || []).includes(tool);
                    return (
                      <Badge
                        key={tool}
                        variant={selected ? "default" : "outline"}
                        className={cn(
                          "cursor-pointer transition-colors text-xs",
                          selected ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                        )}
                        onClick={() => toggleTool(tool)}
                      >
                        {TOOL_NAMES[tool] || tool}
                      </Badge>
                    );
                  })}
                </div>
              </div>

              {/* Scene Codes */}
              <div className="space-y-2">
                <Label>适用场景</Label>
                <div className="flex flex-wrap gap-2">
                  {SCENES.map((scene) => {
                    const selected = (editAgent?.scene_codes || []).includes(scene.code);
                    return (
                      <Badge
                        key={scene.code}
                        variant={selected ? "default" : "outline"}
                        className={cn(
                          "cursor-pointer transition-colors text-xs",
                          selected ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                        )}
                        onClick={() => toggleScene(scene.code)}
                      >
                        {scene.icon} {scene.name}
                      </Badge>
                    );
                  })}
                </div>
              </div>
            </div>
          </ScrollArea>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditAgent(null)}>取消</Button>
            <Button onClick={handleSave} disabled={updateAgent.isPending || editAgent?.id.startsWith('default-')}>
              {updateAgent.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              保存配置
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
