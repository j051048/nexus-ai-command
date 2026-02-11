import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAuth } from '@/components/auth/AuthContext';
import { Upload, Download, FileUp, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

interface PreviewData {
  rows: Array<Record<string, unknown>>;
  total: number;
}

interface ImportResult {
  success_count: number;
  skip_count: number;
  error_count: number;
  errors?: Array<{
    row: number;
    data: Record<string, unknown>;
    reason: string;
    field: string;
  }>;
}

export default function DataImportPage() {
  const [activeTab, setActiveTab] = useState<'employees' | 'customers'>('employees');
  const [isIncremental, setIsIncremental] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  
  const { session } = useAuth();
  const { toast } = useToast();
  
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  
  // 文件类型和大小限制
  const ALLOWED_TYPES = ['.csv', '.xlsx', '.xls'];
  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
  
  // 重置状态
  const resetState = useCallback(() => {
    setFile(null);
    setPreviewData(null);
    setImportResult(null);
  }, []);
  
  // 下载模板
  const handleDownloadTemplate = async () => {
    try {
      const token = session?.access_token;
      if (!token) {
        toast({
          title: '未登录',
          description: '请先登录后再下载模板',
          variant: 'destructive',
        });
        return;
      }
      
      const response = await fetch(`${apiBaseUrl}/api/import/templates/${activeTab}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      
      if (!response.ok) {
        throw new Error('下载模板失败');
      }
      
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${activeTab}_template.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      toast({
        title: '下载成功',
        description: '模板已下载到本地',
      });
    } catch (error) {
      console.error('下载模板失败:', error);
      toast({
        title: '下载失败',
        description: error instanceof Error ? error.message : '下载模板时出现错误',
        variant: 'destructive',
      });
    }
  };
  
  // 验证文件
  const validateFile = (file: File): boolean => {
    const fileName = file.name.toLowerCase();
    const fileExt = '.' + fileName.split('.').pop();
    
    if (!ALLOWED_TYPES.includes(fileExt)) {
      toast({
        title: '文件类型不支持',
        description: `仅支持 ${ALLOWED_TYPES.join(', ')} 格式`,
        variant: 'destructive',
      });
      return false;
    }
    
    if (file.size > MAX_FILE_SIZE) {
      toast({
        title: '文件过大',
        description: '文件大小不能超过 10MB',
        variant: 'destructive',
      });
      return false;
    }
    
    return true;
  };
  
  // 预览文件
  const previewFile = async (file: File) => {
    if (!validateFile(file)) {
      return;
    }
    
    setIsUploading(true);
    setPreviewData(null);
    setImportResult(null);
    
    try {
      const token = session?.access_token;
      if (!token) {
        throw new Error('未登录');
      }
      
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch(`${apiBaseUrl}/api/import/preview`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || '预览失败');
      }
      
      const result = await response.json();
      setPreviewData(result.data);
      setFile(file);
      
      toast({
        title: '预览成功',
        description: `解析到 ${result.data.total} 条记录`,
      });
    } catch (error) {
      console.error('预览失败:', error);
      toast({
        title: '预览失败',
        description: error instanceof Error ? error.message : '预览文件时出现错误',
        variant: 'destructive',
      });
      setFile(null);
    } finally {
      setIsUploading(false);
    }
  };
  
  // 文件选择
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      previewFile(selectedFile);
    }
  };
  
  // 拖拽处理
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };
  
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      previewFile(droppedFile);
    }
  };
  
  // 执行导入
  const handleImport = async () => {
    if (!file) {
      toast({
        title: '未选择文件',
        description: '请先选择要导入的文件',
        variant: 'destructive',
      });
      return;
    }
    
    setIsImporting(true);
    setImportResult(null);
    
    try {
      const token = session?.access_token;
      if (!token) {
        throw new Error('未登录');
      }
      
      const formData = new FormData();
      formData.append('file', file);
      
      // 构建 URL，包含增量模式参数
      const url = new URL(`${apiBaseUrl}/api/import/${activeTab}`);
      if (isIncremental) {
        url.searchParams.append('mode', 'incremental');
      }
      
      const response = await fetch(url.toString(), {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || '导入失败');
      }
      
      const result = await response.json();
      setImportResult(result.data);
      
      toast({
        title: '导入完成',
        description: `成功导入 ${result.data.success_count} 条记录`,
      });
    } catch (error) {
      console.error('导入失败:', error);
      toast({
        title: '导入失败',
        description: error instanceof Error ? error.message : '导入数据时出现错误',
        variant: 'destructive',
      });
    } finally {
      setIsImporting(false);
    }
  };
  
  // 切换 Tab 时重置
  const handleTabChange = (tab: string) => {
    setActiveTab(tab as 'employees' | 'customers');
    resetState();
  };
  
  // 渲染上传区域
  const renderUploadArea = () => (
    <div
      className={cn(
        'border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer',
        isDragging
          ? 'border-primary bg-primary/5'
          : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-accent/50'
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => document.getElementById('file-input')?.click()}
    >
      <input
        id="file-input"
        type="file"
        accept={ALLOWED_TYPES.join(',')}
        onChange={handleFileChange}
        className="hidden"
      />
      
      {isUploading ? (
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-10 h-10 text-primary animate-spin" />
          <p className="text-sm text-muted-foreground">解析文件中...</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
            <Upload className="w-6 h-6 text-primary" />
          </div>
          <div>
            <p className="text-sm font-medium">拖拽文件到这里，或点击选择文件</p>
            <p className="text-xs text-muted-foreground mt-1">
              支持 {ALLOWED_TYPES.join(', ')} 格式，最大 10MB
            </p>
          </div>
        </div>
      )}
    </div>
  );
  
  // 渲染预览表格
  const renderPreviewTable = () => {
    if (!previewData || previewData.rows.length === 0) {
      return null;
    }
    
    const columns = Object.keys(previewData.rows[0]);
    
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium">数据预览（前10行）</h3>
            <p className="text-xs text-muted-foreground mt-1">
              共 {previewData.total} 条记录
            </p>
          </div>
          <Button
            onClick={resetState}
            variant="outline"
            size="sm"
          >
            重新选择文件
          </Button>
        </div>
        
        <div className="border rounded-lg overflow-hidden">
          <div className="max-h-[400px] overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">#</TableHead>
                  {columns.map((col) => (
                    <TableHead key={col}>{col}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewData.rows.map((row, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-medium">{idx + 1}</TableCell>
                    {columns.map((col) => (
                      <TableCell key={col}>
                        {row[col] !== null && row[col] !== undefined ? String(row[col]) : '-'}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <Button
            onClick={handleImport}
            disabled={isImporting}
            className="flex-1"
          >
            {isImporting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                导入中...
              </>
            ) : (
              <>
                <FileUp className="w-4 h-4 mr-2" />
                确认导入 {previewData.total} 条数据
              </>
            )}
          </Button>
        </div>
      </div>
    );
  };
  
  // 渲染导入结果
  const renderImportResult = () => {
    if (!importResult) {
      return null;
    }
    
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">导入结果</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-success" />
              <span className="text-sm">
                成功导入: <strong className="text-success">{importResult.success_count}</strong> 条
              </span>
            </div>
            
            {importResult.skip_count > 0 && (
              <div className="flex items-center gap-2">
                <XCircle className="w-5 h-5 text-warning" />
                <span className="text-sm">
                  跳过（已存在）: <strong className="text-warning">{importResult.skip_count}</strong> 条
                </span>
              </div>
            )}
            
            {importResult.error_count > 0 && (
              <div className="flex items-center gap-2">
                <XCircle className="w-5 h-5 text-destructive" />
                <span className="text-sm">
                  失败: <strong className="text-destructive">{importResult.error_count}</strong> 条
                </span>
              </div>
            )}
            
            {importResult.errors && importResult.errors.length > 0 && (
              <div className="mt-4 space-y-2">
                <p className="text-sm font-medium">错误详情（前20条）:</p>
                <div className="max-h-[200px] overflow-auto border rounded-lg p-3 space-y-2">
                  {importResult.errors.map((err, idx) => (
                    <div key={idx} className="text-xs">
                      <span className="font-medium text-destructive">第 {err.row} 行:</span>{' '}
                      <span className="text-muted-foreground">{err.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
        
        <Button
          onClick={resetState}
          variant="outline"
          className="w-full"
        >
          继续导入
        </Button>
      </div>
    );
  };
  
  // 渲染 Tab 内容
  const renderTabContent = () => (
    <div className="space-y-6">
      {/* 模板下载和增量模式 */}
      <div className="flex items-center justify-between gap-4">
        <Button
          onClick={handleDownloadTemplate}
          variant="outline"
          className="flex-1"
        >
          <Download className="w-4 h-4 mr-2" />
          下载导入模板
        </Button>
        
        <div className="flex items-center gap-2">
          <Switch
            id="incremental-mode"
            checked={isIncremental}
            onCheckedChange={setIsIncremental}
          />
          <Label htmlFor="incremental-mode" className="text-sm cursor-pointer">
            增量模式（更新已有记录）
          </Label>
        </div>
      </div>
      
      {/* 文件上传区域 */}
      {!file && !importResult && renderUploadArea()}
      
      {/* 预览表格 */}
      {file && !importResult && renderPreviewTable()}
      
      {/* 导入结果 */}
      {importResult && renderImportResult()}
    </div>
  );
  
  return (
    <div className="container max-w-6xl py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">数据导入</h1>
        <p className="text-muted-foreground mt-2">
          批量导入员工和客户数据，支持 CSV 和 Excel 格式
        </p>
      </div>
      
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="employees">员工导入</TabsTrigger>
          <TabsTrigger value="customers">客户导入</TabsTrigger>
        </TabsList>
        
        <TabsContent value="employees" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>员工批量导入</CardTitle>
              <CardDescription>
                上传包含员工信息的文件，系统将自动导入到员工管理系统
              </CardDescription>
            </CardHeader>
            <CardContent>
              {renderTabContent()}
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="customers" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>客户批量导入</CardTitle>
              <CardDescription>
                上传包含客户信息的文件，系统将自动导入到客户管理系统
              </CardDescription>
            </CardHeader>
            <CardContent>
              {renderTabContent()}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
