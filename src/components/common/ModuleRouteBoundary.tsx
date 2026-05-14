import React, { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { ModuleErrorBoundary } from "@/components/common/ModuleErrorBoundary";

interface ModuleRouteBoundaryProps {
  moduleName: string;
  children: React.ReactNode;
}

function ModuleRouteSkeleton({ moduleName }: { moduleName: string }) {
  return (
    <section
      aria-label={`${moduleName} loading`}
      className="w-full space-y-6 p-4 md:p-6"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="space-y-3">
          <Skeleton className="h-8 w-44" />
          <Skeleton className="h-4 w-72 max-w-[70vw]" />
        </div>
        <Skeleton className="hidden h-10 w-28 sm:block" />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="rounded-lg border bg-card p-4">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="mt-6 h-8 w-24" />
          </div>
        ))}
      </div>

      <div className="rounded-lg border bg-card p-4">
        <Skeleton className="h-5 w-40" />
        <div className="mt-6 space-y-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      </div>
    </section>
  );
}

export function ModuleRouteBoundary({
  moduleName,
  children,
}: ModuleRouteBoundaryProps) {
  return (
    <ModuleErrorBoundary moduleName={moduleName}>
      <Suspense fallback={<ModuleRouteSkeleton moduleName={moduleName} />}>
        {children}
      </Suspense>
    </ModuleErrorBoundary>
  );
}
