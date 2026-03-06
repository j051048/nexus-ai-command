/**
 * VMD 场景选择器组件
 * 可复用的场景卡片选择网格，供多个 VMD 页面引用
 */
/* eslint-disable react-refresh/only-export-components */

import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export interface VMDScene {
  code: string;
  name: string;
  description: string;
  icon: string;
  agents: string[];
}

export const SCENES: VMDScene[] = [
  { code: 'new_product_launch', name: '新品上市策划', description: '全案策划与执行', icon: '\uD83D\uDE80', agents: ['director', 'content', 'design', 'media'] },
  { code: 'bid_support', name: '招投标支持', description: '标书生成与合规校验', icon: '\uD83D\uDCCB', agents: ['content', 'clue', 'compliance'] },
  { code: 'exhibition', name: '展会运营', description: '展会全流程管理', icon: '\uD83C\uDFAA', agents: ['content', 'design', 'operation'] },
  { code: 'content_marketing', name: '日常内容营销', description: '内容生成与投放', icon: '\u270D\uFE0F', agents: ['content', 'media'] },
  { code: 'rnd_synergy', name: '研产销协同', description: '市场洞察与需求协同', icon: '\uD83D\uDD2C', agents: ['synergy', 'pr'] },
  { code: 'after_sales', name: '售后运营', description: '客户生命周期管理', icon: '\uD83E\uDD1D', agents: ['operation', 'sales'] },
];

const AGENT_NAMES: Record<string, string> = {
  director: '市场总监',
  content: '内容营销',
  design: '设计',
  media: '媒介投放',
  clue: '线索挖掘',
  compliance: '合规校验',
  operation: '运营',
  synergy: '协同',
  pr: '公关',
  sales: '销售',
};

interface SceneSelectorProps {
  onSelect: (sceneCode: string) => void;
  selectedScene?: string;
  compact?: boolean;
}

export function SceneSelector({ onSelect, selectedScene, compact = false }: SceneSelectorProps) {
  return (
    <div className={cn(
      "grid gap-4",
      compact ? "grid-cols-2 md:grid-cols-3" : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
    )}>
      {SCENES.map((scene) => {
        const isSelected = selectedScene === scene.code;
        return (
          <Card
            key={scene.code}
            onClick={() => onSelect(scene.code)}
            className={cn(
              "cursor-pointer transition-all hover:shadow-md group",
              isSelected
                ? "border-primary ring-2 ring-primary/20 bg-primary/5"
                : "border-border/50 hover:border-primary/50"
            )}
          >
            <CardContent className={cn("flex flex-col gap-2", compact ? "p-3" : "p-4")}>
              <div className="flex items-center gap-3">
                <span className={cn("shrink-0", compact ? "text-xl" : "text-2xl")}>
                  {scene.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <h4 className={cn(
                    "font-semibold truncate",
                    compact ? "text-sm" : "text-base"
                  )}>
                    {scene.name}
                  </h4>
                  <p className="text-xs text-muted-foreground truncate">
                    {scene.description}
                  </p>
                </div>
              </div>
              {!compact && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {scene.agents.map((agent) => (
                    <Badge key={agent} variant="secondary" className="text-[10px] px-1.5 py-0">
                      {AGENT_NAMES[agent] || agent}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

export default SceneSelector;
