/**
 * 响应式对话框：移动端自动使用底部 Drawer，桌面端保持居中 Dialog
 * 基于已有的 dialog.tsx (Radix) 和 drawer.tsx (Vaul)
 */
import * as React from 'react';
import { useIsMobile } from '@/hooks/use-mobile';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from './dialog';
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from './drawer';

interface ResponsiveDialogProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

function ResponsiveDialog({ open, onOpenChange, children }: ResponsiveDialogProps) {
  const isMobile = useIsMobile();

  if (isMobile) {
    return (
      <Drawer open={open} onOpenChange={onOpenChange}>
        {children}
      </Drawer>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {children}
    </Dialog>
  );
}

function ResponsiveDialogTrigger({
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogTrigger>) {
  const isMobile = useIsMobile();
  return isMobile ? (
    <DrawerTrigger {...props}>{children}</DrawerTrigger>
  ) : (
    <DialogTrigger {...props}>{children}</DialogTrigger>
  );
}

function ResponsiveDialogContent({
  children,
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogContent>) {
  const isMobile = useIsMobile();
  return isMobile ? (
    <DrawerContent className={className} {...(props as React.ComponentPropsWithoutRef<typeof DrawerContent>)}>
      <div className="overflow-y-auto max-h-[85dvh] px-4 pb-4">{children}</div>
    </DrawerContent>
  ) : (
    <DialogContent className={className} {...props}>
      {children}
    </DialogContent>
  );
}

function ResponsiveDialogHeader({
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const isMobile = useIsMobile();
  return isMobile ? (
    <DrawerHeader {...props}>{children}</DrawerHeader>
  ) : (
    <DialogHeader {...props}>{children}</DialogHeader>
  );
}

function ResponsiveDialogTitle({
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogTitle>) {
  const isMobile = useIsMobile();
  return isMobile ? (
    <DrawerTitle {...props}>{children}</DrawerTitle>
  ) : (
    <DialogTitle {...props}>{children}</DialogTitle>
  );
}

function ResponsiveDialogDescription({
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogDescription>) {
  const isMobile = useIsMobile();
  return isMobile ? (
    <DrawerDescription {...props}>{children}</DrawerDescription>
  ) : (
    <DialogDescription {...props}>{children}</DialogDescription>
  );
}

function ResponsiveDialogFooter({
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const isMobile = useIsMobile();
  return isMobile ? (
    <DrawerFooter {...props}>{children}</DrawerFooter>
  ) : (
    <DialogFooter {...props}>{children}</DialogFooter>
  );
}

function ResponsiveDialogClose({
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogClose>) {
  const isMobile = useIsMobile();
  return isMobile ? (
    <DrawerClose {...props}>{children}</DrawerClose>
  ) : (
    <DialogClose {...props}>{children}</DialogClose>
  );
}

export {
  ResponsiveDialog,
  ResponsiveDialogTrigger,
  ResponsiveDialogContent,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogClose,
};
