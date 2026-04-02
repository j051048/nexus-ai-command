/**
 * 智能数据分析面板
 */
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card } from '@/components/ui/card';
import { Loader2, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { analyzeData } from '@/lib/newFeaturesApi';

interface SmartAnalysisResult {
  success: boolean;
  sql?: string;
  insight?: string;
  total_rows?: number;
  error?: string;
}

export function SmartAnalysisPanel() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SmartAnalysisResult | null>(null);

  const handleAnalyze = async () => {
    if (!query.trim()) {
      toast.error('请输入查询内容');
      return;
    }

    setLoading(true);
    try {
      const res = await analyzeData(query);
      if (res.data?.success) {
        setResult(res.data);
        toast.success('分析完成');
      } else {
        toast.error(res.data?.error || '分析失败');
      }
    } catch (error) {
      toast.error('分析失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="p-6">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-primary" />
          <h3 className="text-lg font-semibold">智能数据分析</h3>
        </div>

        <Textarea
          placeholder="用自然语言提问，例如：本季度各销售人员的业绩排名"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
        />

        <Button onClick={handleAnalyze} disabled={loading}>
          {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
          分析
        </Button>

        {result && (
          <div className="mt-4 space-y-3">
            <div className="text-sm text-muted-foreground">
              SQL: <code className="bg-muted px-2 py-1 rounded">{result.sql}</code>
            </div>
            <div className="text-sm">
              <strong>洞察：</strong>{result.insight}
            </div>
            <div className="text-sm text-muted-foreground">
              共 {result.total_rows} 条结果
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
