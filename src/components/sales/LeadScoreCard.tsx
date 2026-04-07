import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { Target, TrendingUp, AlertCircle, CheckCircle2 } from 'lucide-react';
import { iconColors, typography } from '@/lib/design-tokens';

interface LeadScoreCardProps {
  score: number;
  factors: Array<{ name: string; impact: 'positive' | 'negative'; weight: number }>;
  className?: string;
}

export function LeadScoreCard({ score, factors, className }: LeadScoreCardProps) {
  let colorClass = 'text-green-500';
  let progressClass = '[&>div]:bg-green-500';
  let status = '高意向';
  let statusIcon = <CheckCircle2 className="w-5 h-5 text-green-500" />;

  if (score < 40) {
    colorClass = 'text-red-500';
    progressClass = '[&>div]:bg-red-500';
    status = '低意向';
    statusIcon = <AlertCircle className="w-5 h-5 text-red-500" />;
  } else if (score < 70) {
    colorClass = 'text-yellow-500';
    progressClass = '[&>div]:bg-yellow-500';
    status = '中等意向';
    statusIcon = <Target className="w-5 h-5 text-yellow-500" />;
  }

  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardContent className="p-6">
        <div className="flex justify-between items-start mb-6">
          <div>
            <h3 className={cn(typography.h3, 'text-muted-foreground')}>AI 意向潜能评分</h3>
            <div className="flex items-center gap-2 mt-1">
              <span className={cn(typography.h1, colorClass)}>{score}</span>
              <span className="text-sm font-medium text-muted-foreground">/ 100</span>
            </div>
            <div className="flex items-center gap-1 mt-2">
              {statusIcon}
              <span className="font-medium">{status}</span>
            </div>
          </div>
          <div className="w-16 h-16 rounded-full bg-slate-50 flex items-center justify-center">
            <TrendingUp className={cn('w-8 h-8', colorClass)} />
          </div>
        </div>

        <Progress value={score} className={cn('h-2 mb-6', progressClass)} />

        <div className="space-y-3">
          <h4 className="text-sm font-medium">关键影响因素</h4>
          <div className="space-y-2">
            {factors.map((f, i) => (
              <div key={i} className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">{f.name}</span>
                <Badge variant={f.impact === 'positive' ? 'default' : 'secondary'} 
                       className={f.impact === 'positive' ? 'bg-green-100 text-green-700 hover:bg-green-100' : 'bg-red-100 text-red-700 hover:bg-red-100'}>
                  {f.weight > 0 ? '+' : ''}{f.weight}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default LeadScoreCard;
