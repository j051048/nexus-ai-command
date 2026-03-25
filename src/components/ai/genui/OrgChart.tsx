import React from 'react';
import { User, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

// 安全提取字符串值（防止 AI 生成的数据含对象导致 React #301）
function safeStr(v: unknown): string {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (typeof v === 'object') {
    const name = (v as Record<string, unknown>).name;
    if (typeof name === 'string') return name;
    return JSON.stringify(v);
  }
  return String(v);
}

interface OrgNode {
  id: string;
  name: string;
  title?: string;
  children?: string[];
  avatar?: string;
}

interface OrgChartProps {
  nodes: OrgNode[];
  title?: string;
}

function NodeCard({ node }: { node: OrgNode }) {
  return (
    <div className="inline-flex flex-col items-center gap-1.5 rounded-lg border bg-card p-3 shadow-sm min-w-[120px]">
      {node.avatar ? (
        <img
          src={node.avatar}
          alt={node.name}
          className="w-10 h-10 rounded-full object-cover border"
        />
      ) : (
        <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
          <User className="w-5 h-5 text-muted-foreground" />
        </div>
      )}
      <div className="text-center">
        <p className="text-sm font-medium leading-tight">{safeStr(node.name)}</p>
        {node.title && (
          <p className="text-xs text-muted-foreground leading-tight mt-0.5">{safeStr(node.title)}</p>
        )}
      </div>
    </div>
  );
}

function TreeNode({
  node,
  nodeMap,
  depth,
}: {
  node: OrgNode;
  nodeMap: Map<string, OrgNode>;
  depth: number;
}) {
  const childNodes = (node.children || [])
    .map((id) => nodeMap.get(id))
    .filter(Boolean) as OrgNode[];

  return (
    <div className="flex flex-col items-center">
      <NodeCard node={node} />

      {childNodes.length > 0 && (
        <>
          {/* Vertical connector from parent */}
          <div className="w-0.5 h-4 bg-border" />

          {childNodes.length === 1 ? (
            <TreeNode
              node={childNodes[0]}
              nodeMap={nodeMap}
              depth={depth + 1}
            />
          ) : (
            <>
              {/* Horizontal connector bar */}
              <div className="flex items-start">
                {childNodes.map((child, i) => {
                  const isFirst = i === 0;
                  const isLast = i === childNodes.length - 1;

                  return (
                    <div key={child.id} className="flex flex-col items-center">
                      {/* Top horizontal line + vertical drop */}
                      <div className="flex">
                        <div
                          className={cn(
                            'h-0.5 w-6',
                            isFirst ? 'bg-transparent' : 'bg-border'
                          )}
                        />
                        <div className="w-0.5 h-4 bg-border" />
                        <div
                          className={cn(
                            'h-0.5 w-6',
                            isLast ? 'bg-transparent' : 'bg-border'
                          )}
                        />
                      </div>
                      <TreeNode
                        node={child}
                        nodeMap={nodeMap}
                        depth={depth + 1}
                      />
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

export default function OrgChart({ nodes, title }: OrgChartProps) {
  if (!nodes || nodes.length === 0) return null;

  const nodeMap = new Map<string, OrgNode>();
  nodes.forEach((n) => nodeMap.set(n.id, n));

  // Find root nodes (nodes that are not referenced as children by anyone)
  const childIds = new Set<string>();
  nodes.forEach((n) => {
    (n.children || []).forEach((cid) => childIds.add(cid));
  });
  const roots = nodes.filter((n) => !childIds.has(n.id));

  // Fallback: if no root found, use the first node
  const rootNodes = roots.length > 0 ? roots : [nodes[0]];

  return (
    <div className="p-4">
      {title && <h4 className="text-sm font-semibold mb-4">{safeStr(title)}</h4>}
      <div className="overflow-x-auto">
        <div className="inline-flex gap-8 min-w-fit">
          {rootNodes.map((root) => (
            <TreeNode key={root.id} node={root} nodeMap={nodeMap} depth={0} />
          ))}
        </div>
      </div>
    </div>
  );
}
