import { BookOpenCheck, FileText, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';

export interface EvidenceDrawerItem {
  id: string;
  title: string;
  description?: string;
  status?: 'verified' | 'pending' | 'gap';
  source?: string;
}

interface EvidenceDrawerProps {
  items: EvidenceDrawerItem[];
  title?: string;
  triggerLabel?: string;
}

export function EvidenceDrawer({ items, title = '依据与待确认项', triggerLabel = '查看依据' }: EvidenceDrawerProps) {
  const verified = items.filter((item) => item.status === 'verified').length;

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm">
          <BookOpenCheck className="mr-2 h-4 w-4" />
          {triggerLabel}
          {items.length > 0 && <Badge variant="secondary" className="ml-2">{verified}/{items.length}</Badge>}
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>先看来源，再决定是否采纳或外发。</SheetDescription>
        </SheetHeader>
        <div className="mt-6 divide-y border-y">
          {items.map((item) => (
            <article key={item.id} className="py-4">
              <div className="flex items-start gap-3">
                <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate text-sm font-medium">{item.title}</h3>
                    <Badge variant={item.status === 'verified' ? 'default' : item.status === 'gap' ? 'destructive' : 'secondary'}>
                      {item.status === 'verified' ? '已核验' : item.status === 'gap' ? '缺证据' : '待确认'}
                    </Badge>
                  </div>
                  {item.description && <p className="mt-1 line-clamp-3 text-xs leading-5 text-muted-foreground">{item.description}</p>}
                  {item.source && <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground"><ShieldCheck className="h-3 w-3" />{item.source}</p>}
                </div>
              </div>
            </article>
          ))}
          {!items.length && (
            <div className="py-12 text-center">
              <BookOpenCheck className="mx-auto h-7 w-7 text-muted-foreground/40" />
              <p className="mt-3 text-sm font-medium">还没有可引用依据</p>
              <p className="mt-1 text-xs text-muted-foreground">先上传产品资料、手册或客户文件。</p>
              <Button asChild variant="outline" size="sm" className="mt-4"><Link to="/knowledge">打开企业资料</Link></Button>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
