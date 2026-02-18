import { Construction } from 'lucide-react';

interface FeatureComingSoonProps {
  title: string;
  description?: string;
}

export function FeatureComingSoon({ title, description }: FeatureComingSoonProps) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <Construction className="w-16 h-16 text-muted-foreground/40 mb-6" />
      <h3 className="text-lg font-semibold text-foreground mb-2">
        {title} · 功能建设中
      </h3>
      <p className="text-sm text-muted-foreground max-w-md">
        {description || '该模块正在紧锣密鼓地开发中，敬请期待'}
      </p>
    </div>
  );
}
