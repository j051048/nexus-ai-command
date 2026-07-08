import { Link } from 'react-router-dom';
import { ArrowRight, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

export function AIOperatingSystemStrip() {
  return (
    <section className="rounded-lg border bg-muted/20 px-3 py-2.5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 items-center gap-2.5">
          <Sparkles className="h-4 w-4 shrink-0 text-primary" />
          <div className="min-w-0">
            <h2 className="text-sm font-medium">AI 作战系统</h2>
            <p className="truncate text-xs text-muted-foreground">
              VMD、Agent 仿真、SOP→AOP 和业务知识图谱都在这里。
            </p>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button asChild size="sm" variant="outline" className="h-8">
            <Link to="/ai-operating-system">
              打开
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-8"
            onClick={() => triggerAI('把 Nexus 的 P0-P6 产品升级压缩成今天可执行的 5 个落地动作。')}
          >
            生成计划
          </Button>
        </div>
      </div>
    </section>
  );
}

export default AIOperatingSystemStrip;
