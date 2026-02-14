import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import {
  LayoutTemplate,
  Search,
  Loader2,
  Play,
  FileX2,
  DollarSign,
  ShoppingCart,
  Users,
  Plane,
  Scale,
  Tag,
  ArrowRight,
} from 'lucide-react';

// ─── Types ──────────────────────────────────────────────────

interface WorkflowStep {
  id: string;
  type: string;
  label: string;
  config: Record<string, unknown>;
}

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  applies_to: string[];
  is_builtin: boolean;
  usage_count: number;
  steps: WorkflowStep[];
  source: 'builtin' | 'shared';
  preview_image?: string | null;
}

interface CategoryMeta {
  label: string;
  color: string;
}

interface TemplateListResponse {
  success: boolean;
  data: {
    templates: WorkflowTemplate[];
    categories: Record<string, CategoryMeta>;
  };
}

// ─── Constants ──────────────────────────────────────────────

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://aizhz.zeabur.app';

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  finance: <DollarSign className="w-4 h-4" />,
  procurement: <ShoppingCart className="w-4 h-4" />,
  hr: <Users className="w-4 h-4" />,
  travel: <Plane className="w-4 h-4" />,
  legal: <Scale className="w-4 h-4" />,
  custom: <Tag className="w-4 h-4" />,
};

const CATEGORY_COLORS: Record<string, string> = {
  finance: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  procurement: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  hr: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  travel: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  legal: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  custom: 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400',
};

// ─── Auth Fetch Helper ──────────────────────────────────────

async function authFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

  let baseUrl = API_BASE_URL;
  if (!baseUrl.startsWith('http')) {
    baseUrl = baseUrl.includes('localhost') ? `http://${baseUrl}` : `https://${baseUrl}`;
  }
  const cleanBase = baseUrl.replace(/\/$/, '');
  const cleanEndpoint = url.startsWith('/') ? url.slice(1) : url;
  const fullUrl = `${cleanBase}/${cleanEndpoint}`;

  const response = await fetch(fullUrl, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers as Record<string, string>),
    },
  });

  if (!response.ok) {
    let errorMessage = `请求失败 (${response.status})`;
    try {
      const errorData = await response.json();
      if (errorData.error?.message) errorMessage = errorData.error.message;
      else if (typeof errorData.detail === 'string') errorMessage = errorData.detail;
    } catch {
      // ignore
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

// ─── Component ──────────────────────────────────────────────

function WorkflowTemplates() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const queryClient = useQueryClient();

  // Fetch templates
  const { data, isLoading, error } = useQuery({
    queryKey: ['workflow-templates', selectedCategory],
    queryFn: async () => {
      const params = selectedCategory ? `?category=${selectedCategory}` : '';
      const result = await authFetch<TemplateListResponse>(
        `api/workflow-templates${params}`
      );
      return result.data;
    },
  });

  const templates = data?.templates ?? [];
  const categories = data?.categories ?? {};

  // Create workflow from template
  const createFromTemplate = useMutation({
    mutationFn: async (templateId: string) => {
      const result = await authFetch<{ data: Record<string, unknown> }>(
        `api/workflow-templates/create-from/${templateId}`,
        { method: 'POST', body: JSON.stringify({}) }
      );
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      toast.success('工作流已创建', { description: '可前往流程设计器查看和编辑' });
    },
    onError: (err: Error) => {
      toast.error(err.message || '创建失败');
    },
  });

  // Filter templates by search
  const filteredTemplates = templates.filter((tpl) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      tpl.name.toLowerCase().includes(term) ||
      tpl.description.toLowerCase().includes(term)
    );
  });

  const categoryList = Object.entries(categories);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <LayoutTemplate className="w-6 h-6" />
            工作流模板市场
          </h1>
          <p className="text-muted-foreground mt-1">
            从预置模板快速创建审批流程，也可以将自定义流程分享为模板
          </p>
        </div>
      </div>

      {/* Search + Category Filter */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="搜索模板..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant={selectedCategory === null ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSelectedCategory(null)}
          >
            全部
          </Button>
          {categoryList.map(([key, meta]) => (
            <Button
              key={key}
              variant={selectedCategory === key ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedCategory(key)}
              className="gap-1.5"
            >
              {CATEGORY_ICONS[key]}
              {meta.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      )}

      {/* Error */}
      {error && (
        <Card>
          <CardContent className="py-10 text-center">
            <p className="text-destructive">
              加载失败: {error instanceof Error ? error.message : '未知错误'}
            </p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => window.location.reload()}
            >
              重新加载
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Empty state */}
      {!isLoading && !error && filteredTemplates.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <FileX2 className="w-16 h-16 text-muted-foreground/40 mb-4" />
            <h3 className="text-lg font-medium mb-2">暂无匹配模板</h3>
            <p className="text-sm text-muted-foreground">
              {searchTerm ? '尝试其他搜索词或清除筛选条件' : '当前分类下暂无可用模板'}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Template Grid */}
      {!isLoading && filteredTemplates.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredTemplates.map((tpl) => (
            <Card
              key={tpl.id}
              className="group relative transition-all hover:shadow-md"
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-base font-semibold truncate">
                      {tpl.name}
                    </CardTitle>
                  </div>
                  <Badge
                    variant="secondary"
                    className={`ml-2 text-xs shrink-0 ${CATEGORY_COLORS[tpl.category] || CATEGORY_COLORS.custom}`}
                  >
                    {CATEGORY_ICONS[tpl.category]}
                    <span className="ml-1">
                      {categories[tpl.category]?.label || tpl.category}
                    </span>
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="pt-0 space-y-3">
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {tpl.description}
                </p>

                {/* Meta info */}
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span>{tpl.steps?.length || 0} 个节点</span>
                  {tpl.source === 'builtin' && (
                    <Badge variant="outline" className="text-xs">
                      官方模板
                    </Badge>
                  )}
                  {tpl.source === 'shared' && (
                    <Badge variant="outline" className="text-xs">
                      组织共享
                    </Badge>
                  )}
                  {(tpl.usage_count ?? 0) > 0 && (
                    <span>已使用 {tpl.usage_count} 次</span>
                  )}
                </div>

                {/* Action button */}
                <Button
                  className="w-full gap-2"
                  size="sm"
                  onClick={() => createFromTemplate.mutate(tpl.id)}
                  disabled={createFromTemplate.isPending}
                >
                  {createFromTemplate.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  使用此模板
                  <ArrowRight className="w-3 h-3 ml-auto" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default WorkflowTemplates;
