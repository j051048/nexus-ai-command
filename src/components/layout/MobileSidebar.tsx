import React, { useState } from 'react';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Menu, X } from 'lucide-react';
import { Sidebar } from './Sidebar';

interface MobileSidebarProps {
  children?: React.ReactNode;
}

export function MobileSidebar({ children }: MobileSidebarProps) {
  const [open, setOpen] = useState(false);

  const handleNavClick = () => {
    setOpen(false);
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button 
          variant="ghost" 
          size="icon" 
          className="md:hidden fixed top-4 left-4 z-50 bg-background/80 backdrop-blur-sm border shadow-sm"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          <span className="sr-only">切换菜单</span>
        </Button>
      </SheetTrigger>
      <SheetContent 
        side="left" 
        className="p-0 w-64 border-r-0"
        onInteractOutside={() => setOpen(false)}
      >
        <div className="h-full overflow-hidden">
          <Sidebar onNavClick={handleNavClick} />
        </div>
      </SheetContent>
    </Sheet>
  );
}

export default MobileSidebar;