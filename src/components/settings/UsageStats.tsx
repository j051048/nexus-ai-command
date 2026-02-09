import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  Activity, 
  Coins, 
  MessageSquare, 
  TrendingUp,
  AlertTriangle 
} from 'lucide-react';
import { aiClient } from '@/api/aiClient';

interface UsageData {
  date: string;
  tokens_used: number;
  tokens_limit: number;
  tokens_remaining: number;
  cost_usd: number;
  cost_limit_usd: number;
  requests: number;
  requests_limit: number;
}

export function UsageStats() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['usage-stats'],
    queryFn: async () => {
      const response = await aiClient.fetch<{ success: boolean; data: UsageData }>('api/usage');
      return response.data;
    },
    refetchInterval: 60000, // Refresh every minute
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-48" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="w-5 h-5" />
            使用统计
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-muted-foreground">
            <AlertTriangle className="w-4 h-4" />
            <span>暂时无法加载使用统计</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const tokenPercentage = Math.min(100, (data.tokens_used / data.tokens_limit) * 100);
  const costPercentage = Math.min(100, (data.cost_usd / data.cost_limit_usd) * 100);
  const requestPercentage = Math.min(100, (data.requests / data.requests_limit) * 100);

  const getStatusColor = (percentage: number) => {
    if (percentage >= 90) return 'text-destructive';
    if (percentage >= 70) return 'text-warning';
    return 'text-success';
  };

  const getProgressColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-destructive';
    if (percentage >= 70) return 'bg-warning';
    return 'bg-success';
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="w-5 h-5" />
          今日使用统计
        </CardTitle>
        <CardDescription>
          {data.date} · 每日限额重置于午夜
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Token Usage */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Token 使用量</span>
            </div>
            <span className={`text-sm font-medium ${getStatusColor(tokenPercentage)}`}>
              {data.tokens_used.toLocaleString()} / {data.tokens_limit.toLocaleString()}
            </span>
          </div>
          <Progress value={tokenPercentage} className="h-2" />
          <p className="text-xs text-muted-foreground">
            剩余 {data.tokens_remaining.toLocaleString()} tokens
          </p>
        </div>

        {/* Cost */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Coins className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">预估成本</span>
            </div>
            <span className={`text-sm font-medium ${getStatusColor(costPercentage)}`}>
              ${data.cost_usd.toFixed(4)} / ${data.cost_limit_usd.toFixed(2)}
            </span>
          </div>
          <Progress value={costPercentage} className="h-2" />
        </div>

        {/* Requests */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">请求次数</span>
            </div>
            <span className={`text-sm font-medium ${getStatusColor(requestPercentage)}`}>
              {data.requests} / {data.requests_limit}
            </span>
          </div>
          <Progress value={requestPercentage} className="h-2" />
        </div>

        {/* Warnings */}
        {(tokenPercentage >= 80 || costPercentage >= 80) && (
          <div className="flex items-center gap-2 p-3 bg-warning/10 rounded-lg">
            <AlertTriangle className="w-4 h-4 text-warning" />
            <span className="text-sm text-warning">
              {tokenPercentage >= 90 || costPercentage >= 90 
                ? '即将达到每日限额，请注意使用' 
                : '使用量较高，建议合理规划'}
            </span>
          </div>
        )}

        {/* Status Badge */}
        <div className="flex justify-end">
          <Badge variant={tokenPercentage < 70 ? 'default' : tokenPercentage < 90 ? 'secondary' : 'destructive'}>
            {tokenPercentage < 70 ? '正常' : tokenPercentage < 90 ? '较高' : '接近限额'}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}

export default UsageStats;