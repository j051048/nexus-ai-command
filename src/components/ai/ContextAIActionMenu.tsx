import { ChevronDown, Sparkles } from 'lucide-react';

import { dispatchAIChatMessage } from '@/components/layout/GlobalCommandBar';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export interface ContextAIAction {
  label: string;
  prompt: string;
}

interface ContextAIActionMenuProps {
  actions: ContextAIAction[];
  label?: string;
}

export function ContextAIActionMenu({ actions, label = '交给 AI' }: ContextAIActionMenuProps) {
  const run = (prompt: string) => {
    window.dispatchEvent(new CustomEvent('proactive-chat'));
    window.setTimeout(() => dispatchAIChatMessage(prompt), 80);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="sm" variant="outline">
          <Sparkles className="mr-2 h-4 w-4" />{label}<ChevronDown className="ml-2 h-3.5 w-3.5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        {actions.map((action) => (
          <DropdownMenuItem key={action.label} onSelect={() => run(action.prompt)} className="py-2.5">
            {action.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
