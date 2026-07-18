/* eslint-disable react-refresh/only-export-components */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, MessageSquare, PlusCircle, Sparkles, SunMoon, Users } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

import { aiClient } from '@/api/aiClient';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from '@/components/ui/command';
import { usePageContext } from '@/hooks/usePageContext';

import {
  AI_QUICK_ACTIONS,
  COMMAND_ITEMS,
  COMMAND_ITEM_VALUES,
  detectIntent,
  EXECUTION_COMMANDS,
  isCommandFeatureEnabled,
  type NavCommandItem,
  PAGE_SUGGESTIONS,
} from './globalCommandCatalog';

interface CustomerResult {
  id: string;
  name: string;
  company?: string;
}

export const COMMAND_BAR_CHAT_EVENT = 'nexus:command-bar-chat';
export const COMMAND_BAR_NEW_CHAT_EVENT = 'nexus:command-bar-new-chat';

export function dispatchAIChatMessage(message: string) {
  window.dispatchEvent(new CustomEvent(COMMAND_BAR_CHAT_EVENT, { detail: { message } }));
}

export function dispatchNewChat() {
  window.dispatchEvent(new CustomEvent(COMMAND_BAR_NEW_CHAT_EVENT));
}

export function GlobalCommandBar() {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [customerResults, setCustomerResults] = useState<CustomerResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { pageContext } = usePageContext();
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const intent = useMemo(() => detectIntent(searchQuery), [searchQuery]);
  const pageSuggestions = useMemo(() => {
    const path = location.pathname;
    for (const [prefix, suggestions] of Object.entries(PAGE_SUGGESTIONS)) {
      if (path.startsWith(prefix)) return suggestions;
    }
    return [];
  }, [location.pathname]);

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((previous) => !previous);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  useEffect(() => {
    if (!open) {
      setSearchQuery('');
      setCustomerResults([]);
      setIsSearching(false);
    }
  }, [open]);

  useEffect(() => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    if (searchQuery.length < 2) {
      setCustomerResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    debounceTimerRef.current = setTimeout(async () => {
      try {
        const data = await aiClient.fetch<CustomerResult[]>(
          `api/crm/customers?search=${encodeURIComponent(searchQuery)}`
        );
        setCustomerResults(Array.isArray(data) ? data : []);
      } catch {
        setCustomerResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [searchQuery]);

  const handleSelect = useCallback((path: string) => {
    setOpen(false);
    navigate(path);
  }, [navigate]);
  const handleAIChat = useCallback((message: string) => {
    setOpen(false);
    dispatchAIChatMessage(message);
  }, []);
  const handleNewChat = useCallback(() => {
    setOpen(false);
    dispatchNewChat();
  }, []);
  const handleThemeToggle = useCallback(() => {
    setOpen(false);
    document.documentElement.classList.toggle('dark');
  }, []);

  const groups = COMMAND_ITEMS.filter(isCommandFeatureEnabled).reduce<Record<string, NavCommandItem[]>>(
    (accumulator, item) => {
      if (!accumulator[item.group]) accumulator[item.group] = [];
      accumulator[item.group].push(item);
      return accumulator;
    },
    {}
  );

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        data-testid="global-command-input"
        placeholder={intent === 'ai_action' ? 'AI 将处理你的请求...' : '搜索功能、页面，或直接提问 AI... (Ctrl+K)'}
        value={searchQuery}
        onValueChange={setSearchQuery}
      />
      <CommandList>
        <CommandEmpty>
          <div className="py-2 text-center">
            <p className="text-sm text-muted-foreground">
              {intent === 'ai_action' ? '按回车让 AI 处理' : '未找到匹配的功能'}
            </p>
            {searchQuery.trim() && (
              <button
                className="mt-2 inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                onClick={() => handleAIChat(searchQuery)}
              >
                <Sparkles className="h-3.5 w-3.5" />
                {intent === 'ai_action' ? '发送给 AI' : '问问 AI'}: &ldquo;{searchQuery}&rdquo;
              </button>
            )}
          </div>
        </CommandEmpty>

        {pageSuggestions.length > 0 && !searchQuery && (
          <>
            <CommandGroup heading="当前页面建议">
              {pageSuggestions.map((suggestion) => (
                <CommandItem
                  key={suggestion.prompt}
                  value={`建议 ${suggestion.label} ${suggestion.prompt}`}
                  onSelect={() => handleAIChat(suggestion.prompt)}
                >
                  <Sparkles className="mr-2 h-4 w-4 text-amber-500" />
                  <span>{suggestion.label}</span>
                  <MessageSquare className="ml-auto h-3.5 w-3.5 text-muted-foreground" />
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}

        {intent === 'ai_action' && searchQuery.trim() && (
          <>
            <CommandGroup heading="AI 智能处理">
              <CommandItem value={`AI 执行 ${searchQuery}`} onSelect={() => handleAIChat(searchQuery)}>
                <Sparkles className="mr-2 h-4 w-4 text-primary" />
                <span>让 AI 处理: &ldquo;{searchQuery}&rdquo;</span>
              </CommandItem>
            </CommandGroup>
            <CommandSeparator />
          </>
        )}

        <CommandGroup heading="AI 智能助手">
          <CommandItem value="新建对话 new chat 清空" onSelect={handleNewChat}>
            <PlusCircle className="mr-2 h-4 w-4" />
            <span>新建对话</span>
            <CommandShortcut>/new</CommandShortcut>
          </CommandItem>
          {AI_QUICK_ACTIONS.map((action) => (
            <CommandItem
              key={action.prompt}
              value={`AI ${action.label} ${action.prompt}`}
              onSelect={() => handleAIChat(action.prompt)}
            >
              <action.icon className="mr-2 h-4 w-4" />
              <span>{action.label}</span>
              <MessageSquare className="ml-auto h-3.5 w-3.5 text-muted-foreground" />
            </CommandItem>
          ))}
          {searchQuery.trim() && (
            <CommandItem value={`AI 提问 ${searchQuery}`} onSelect={() => handleAIChat(searchQuery)}>
              <Sparkles className="mr-2 h-4 w-4" />
              <span>问 AI: &ldquo;{searchQuery}&rdquo;</span>
            </CommandItem>
          )}
        </CommandGroup>

        <CommandSeparator />
        <CommandGroup heading="常用动作">
          {EXECUTION_COMMANDS.map((action) => (
            <CommandItem
              key={action.label}
              value={`动作 ${action.label} ${action.prompt}`}
              onSelect={() => handleAIChat(action.prompt)}
            >
              <action.icon className="mr-2 h-4 w-4" />
              <span>{action.label}</span>
              <CommandShortcut>{action.path}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>

        {pageContext && (
          <>
            <CommandSeparator />
            <CommandGroup heading="AI 当前上下文">
              <CommandItem value={`当前上下文 ${pageContext.type} ${pageContext.name ?? ''}`} disabled>
                <Sparkles className="mr-2 h-4 w-4 text-primary" />
                <span>
                  {pageContext.type}
                  {pageContext.name ? ` / ${pageContext.name}` : ''}
                  {pageContext.id ? ` / ${pageContext.id.slice(0, 8)}` : ''}
                </span>
              </CommandItem>
            </CommandGroup>
          </>
        )}

        <CommandSeparator />
        {(isSearching || customerResults.length > 0) && (
          <>
            <CommandGroup heading="搜索结果">
              {isSearching && (
                <CommandItem value="__searching__" disabled>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  <span className="text-muted-foreground">正在搜索...</span>
                </CommandItem>
              )}
              {customerResults.map((customer) => (
                <CommandItem
                  key={`customer-${customer.id}`}
                  value={`客户 ${customer.name} ${customer.company || ''}`}
                  onSelect={() => handleSelect('/crm')}
                >
                  <Users className="mr-2 h-4 w-4" />
                  <span>{customer.name}</span>
                  {customer.company && (
                    <span className="ml-2 text-xs text-muted-foreground">{customer.company}</span>
                  )}
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}

        {Object.entries(groups).map(([group, items], index) => (
          <React.Fragment key={group}>
            {index > 0 && <CommandSeparator />}
            <CommandGroup heading={group}>
              {items.map((item) => (
                <CommandItem
                  key={item.path}
                  value={COMMAND_ITEM_VALUES.get(item.path) || item.label}
                  onSelect={() => handleSelect(item.path)}
                >
                  <item.icon className="mr-2 h-4 w-4" />
                  <span>{item.label}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </React.Fragment>
        ))}

        <CommandSeparator />
        <CommandGroup heading="通用">
          <CommandItem value="切换主题 theme dark light 深色 浅色" onSelect={handleThemeToggle}>
            <SunMoon className="mr-2 h-4 w-4" />
            <span>切换主题</span>
            <CommandShortcut>Ctrl+J</CommandShortcut>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
