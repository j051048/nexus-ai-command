import { useState } from 'react';
import { Activity, BrainCircuit, GitCompareArrows, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AgentOpsOverview } from '@/components/agent-ops/AgentOpsOverview';
import { AgentOpsQuality } from '@/components/agent-ops/AgentOpsQuality';
import { AgentOpsReleases } from '@/components/agent-ops/AgentOpsReleases';
import { AgentOpsRuntime } from '@/components/agent-ops/AgentOpsRuntime';
import {
  useAgentCI,
  useAeonInspiredOps,
  useAgentEvolutionOps,
  useAgentImprovementProposals,
  useDecideAgentProposal,
  useMemoryHygiene,
  usePromptRegistry,
  useRegisterAeonHeartbeatSchedule,
  useRunAeonInspiredHeartbeat,
} from '@/hooks/useAIOperatingSystem';

type AgentOpsSection = 'overview' | 'quality' | 'releases' | 'runtime';

export default function AgentImprovementCenterPage() {
  const [activeSection, setActiveSection] = useState<AgentOpsSection>('overview');
  const registry = usePromptRegistry();
  const proposals = useAgentImprovementProposals();
  const memory = useMemoryHygiene();
  const evolutionOps = useAgentEvolutionOps();
  const aeonOps = useAeonInspiredOps('scientific instrument sales');
  const runAeonHeartbeat = useRunAeonInspiredHeartbeat();
  const registerAeonSchedule = useRegisterAeonHeartbeatSchedule();
  const decideProposal = useDecideAgentProposal();
  const agentCI = useAgentCI();

  const runQualityGate = () => {
    agentCI.mutate({
      candidate_metadata: { source: 'operator_button', estimated_tokens: 3200 },
    });
  };

  const decide = (proposalKey: string, action: 'gray_release' | 'rollback') => {
    decideProposal.mutate({
      proposal_key: proposalKey,
      action,
      gray_percentage: action === 'gray_release' ? 10 : undefined,
      reviewer_note: action === 'gray_release'
        ? 'Operator starts a governed 10% gray release.'
        : 'Operator rolls back the proposal from Agent Ops.',
    });
  };

  return (
    <main className="mx-auto max-w-7xl space-y-4">
      <header className="flex flex-col gap-3 border-b pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2 text-xs font-medium text-primary">
            <BrainCircuit className="h-4 w-4" />
            Agent Ops
          </div>
          <h1 className="text-xl font-semibold">Agent 运营中心</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            监控质量、发布和运行风险。所有自我改进必须经过检查、人工审批与灰度。
          </p>
        </div>
        <Button size="sm" onClick={runQualityGate} disabled={agentCI.isPending}>
          <GitCompareArrows className="mr-1.5 h-4 w-4" />
          {agentCI.isPending ? '检查中' : '运行质量检查'}
        </Button>
      </header>

      <Tabs value={activeSection} onValueChange={(value) => setActiveSection(value as AgentOpsSection)}>
        <TabsList className="h-10 w-full justify-start overflow-x-auto bg-transparent p-0">
          <TabsTrigger value="overview" className="gap-1.5">总览</TabsTrigger>
          <TabsTrigger value="quality" className="gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5" />
            质量
          </TabsTrigger>
          <TabsTrigger value="releases" className="gap-1.5">
            <GitCompareArrows className="h-3.5 w-3.5" />
            发布
          </TabsTrigger>
          <TabsTrigger value="runtime" className="gap-1.5">
            <Activity className="h-3.5 w-3.5" />
            运行
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          <AgentOpsOverview
            memory={memory.data}
            evolution={evolutionOps.data}
            aeon={aeonOps.data}
            proposals={proposals.data}
            ci={agentCI.data}
            onOpenSection={setActiveSection}
          />
        </TabsContent>

        <TabsContent value="quality" className="mt-4">
          <AgentOpsQuality
            registry={registry.data ?? []}
            memory={memory.data}
            evolution={evolutionOps.data}
          />
        </TabsContent>

        <TabsContent value="releases" className="mt-4">
          <AgentOpsReleases
            ci={agentCI.data}
            proposals={proposals.data}
            evolution={evolutionOps.data}
            isRunningCI={agentCI.isPending}
            isDeciding={decideProposal.isPending}
            onRunCI={runQualityGate}
            onDecision={decide}
          />
        </TabsContent>

        <TabsContent value="runtime" className="mt-4">
          <AgentOpsRuntime
            aeon={aeonOps.data}
            evolution={evolutionOps.data}
            isRunningHeartbeat={runAeonHeartbeat.isPending}
            isRegisteringSchedule={registerAeonSchedule.isPending}
            onRunHeartbeat={() => runAeonHeartbeat.mutate('scientific instrument sales')}
            onRegisterSchedule={() => registerAeonSchedule.mutate('scientific instrument sales')}
          />
        </TabsContent>
      </Tabs>
    </main>
  );
}
