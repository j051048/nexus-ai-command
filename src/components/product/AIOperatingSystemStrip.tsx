import { Link } from 'react-router-dom';
import { ArrowRight, Bot, Network, Rocket, Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

export function AIOperatingSystemStrip() {
  return (
    <section className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-fuchsia-500/10 text-fuchsia-600">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">P0-P6</Badge>
              <Badge variant="secondary">AI 作战操作系统</Badge>
            </div>
            <h2 className="mt-2 font-semibold">从“企业 AI 平台”收敛为科学仪器销售 AI 作战室</h2>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              统一管理超级场景、Agent 仿真沙盒、SOP→AOP、业务知识图谱、AI 价值仪表盘、模板库、Demo 空间和角色化工作台。
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm">
            <Link to="/ai-operating-system">
              打开作战系统
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              triggerAI('请把 Nexus 的 P0-P6 产品升级压缩成今天可执行的 5 个落地动作。')
            }
          >
            <Sparkles className="mr-2 h-4 w-4" />
            生成今日落地动作
          </Button>
        </div>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        {[
          { label: 'VMD 超级场景', value: '线索 / 投标 / 竞品 / 跟进', icon: Rocket },
          { label: 'Agent 生命周期', value: '定义 / 仿真 / 上线 / 运营', icon: Bot },
          { label: '业务上下文层', value: '客户 / 项目 / 合同 / 审批 / 文档', icon: Network },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="rounded-md border bg-background/60 p-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Icon className="h-4 w-4 text-primary" />
                {item.label}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{item.value}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default AIOperatingSystemStrip;
