/**
 * 批量操作按钮组
 */
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Upload, UserPlus } from 'lucide-react';
import { toast } from 'sonner';
import { batchImportCustomers, batchAssignLeads } from '@/lib/newFeaturesApi';

interface BatchActionsProps {
  selectedIds?: string[];
  onSuccess?: () => void;
}

export function BatchActions({ selectedIds = [], onSuccess }: BatchActionsProps) {
  const [loading, setLoading] = useState(false);

  const handleImport = async () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv,.xlsx';
    input.onchange = async (e: Event) => {
      const target = e.target as HTMLInputElement;
      const file = target.files?.[0];
      if (!file) return;

      // 简化：这里应该解析文件，暂时提示
      toast.info('文件解析功能开发中');
    };
    input.click();
  };

  const handleAssign = async () => {
    if (selectedIds.length === 0) {
      toast.error('请先选择线索');
      return;
    }

    // 简化：这里应该弹出选择负责人对话框
    toast.info('请在后续版本中选择负责人');
  };

  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={handleImport}>
        <Upload className="w-4 h-4 mr-2" />
        批量导入
      </Button>
      <Button variant="outline" size="sm" onClick={handleAssign} disabled={selectedIds.length === 0}>
        <UserPlus className="w-4 h-4 mr-2" />
        批量分配 {selectedIds.length > 0 && `(${selectedIds.length})`}
      </Button>
    </div>
  );
}
