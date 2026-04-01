import React, { useState, useRef, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { getApiBaseUrl } from '@/lib/apiConfig';
import { httpClient } from '@/lib/httpClient';
import {
    FileText,
    Upload,
    Search,
    FolderOpen,
    Loader2,
    Calendar,
    Currency,
    Filter,
    Trash2,
    PackagePlus,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { DocumentCard } from './components/DocumentCard';
import { useUser } from '@/contexts/UserContext';
import { NexusDocument } from '@/types/nexus';

const DOC_TYPE_OPTIONS = [
    { value: 'contract', label: '销售合同' },
    { value: 'tender',   label: '招标文件' },
    { value: 'bid',      label: '投标文件' },
    { value: 'product',  label: '产品资料' },
    { value: 'proposal', label: '方案文档' },
    { value: 'invoice',  label: '发票' },
    { value: 'legal',    label: '法律法规' },
    { value: 'other',    label: '其他' },
] as const;

export function DocumentsPage({ onNavigate }: { onNavigate?: (nav: string) => void }) {
    const { user } = useUser();
    const isBoss = user?.role === 'boss';

    const [documents, setDocuments] = useState<NexusDocument[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [uploadStage, setUploadStage] = useState<'uploading' | 'extracting' | 'indexing'>('uploading');
    const [searchQuery, setSearchQuery] = useState('');
    const [activeFilter, setActiveFilter] = useState<string>('all');

    // Selection for Batch Delete
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [isDeleting, setIsDeleting] = useState(false);

    // Smart Filter States
    const [minAmount, setMinAmount] = useState<string>('');
    const [maxAmount, setMaxAmount] = useState<string>('');
    const [filterDate, setFilterDate] = useState<string>('');
    const [isBulkImporting, setIsBulkImporting] = useState(false);

    const fileInputRef = useRef<HTMLInputElement>(null);
    const bulkImportInputRef = useRef<HTMLInputElement>(null);

    // Fetch documents from Supabase
    const fetchDocuments = async () => {
        setIsLoading(true);
        try {
            const response = await httpClient.get('/api/documents');
            const data = response.data?.documents || [];

            const formattedDocs: NexusDocument[] = (data || []).map((doc) => ({
                id: doc.id,
                name: doc.name,
                doc_type: doc.doc_type || 'other',
                created_at: doc.created_at,
                status: doc.status === 'ready' ? 'completed'
                    : doc.status === 'pending' || doc.status === 'processing' ? 'processing'
                    : doc.status === 'failed' || doc.status === 'error' ? 'error'
                    : 'completed',
                extracted_data: typeof doc.extracted_data === 'string'
                    ? JSON.parse(doc.extracted_data)
                    : (doc.extracted_data || {})
            }));

            setDocuments(formattedDocs);
            setSelectedIds(new Set()); // Clear selection on refresh
        } catch (error) {
            toast.error('加载文档失败，请刷新重试');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchDocuments();
    }, []);

    // 轮询机制：当有文档处于 processing 状态时，每 5 秒自动刷新
    useEffect(() => {
        const hasProcessing = documents.some(d => d.status === 'processing');
        if (!hasProcessing) return;

        const pollInterval = setInterval(() => {
            fetchDocuments();
        }, 5000);

        return () => clearInterval(pollInterval);
    }, [documents]);

    const toggleSelect = (id: string) => {
        const newSet = new Set(selectedIds);
        if (newSet.has(id)) {
            newSet.delete(id);
        } else {
            newSet.add(id);
        }
        setSelectedIds(newSet);
    };

    const handleBatchDelete = async () => {
        if (selectedIds.size === 0) return;

        if (!confirm(`确定要删除选中的 ${selectedIds.size} 份文档吗？删除后将无法恢复。`)) {
            return;
        }

        setIsDeleting(true);
        try {
            const endpoint = `${getApiBaseUrl()}/api/documents/batch-delete`;

            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': token ? `Bearer ${token}` : ''
                },
                body: JSON.stringify({
                    document_ids: Array.from(selectedIds)
                })
            });

            if (!response.ok) {
                if (!token) {
                    toast.error('请先登录');
                    return;
                }
                const errorBody = await response.json().catch(() => ({}));
                throw new Error(errorBody.message || '批量删除失败');
            }

            // Parse actual deleted count from backend
            const result = await response.json().catch(() => null);
            const deletedCount = result?.data?.deleted_count ?? selectedIds.size;

            // Optimistic UI: immediately remove deleted docs
            setDocuments(prev => prev.filter(d => !selectedIds.has(d.id)));
            setSelectedIds(new Set());

            if (deletedCount === 0) {
                toast.warning('删除请求已发送，但未能删除文档，请刷新页面重试');
            } else {
                toast.success(`已删除 ${deletedCount} 份文档`);
            }

            // Sync with server truth
            await fetchDocuments();
        } catch (error) {
            toast.error('删除操作失败，请重试');
            // Refresh to restore correct state on error
            await fetchDocuments();
        } finally {
            setIsDeleting(false);
        }
    };

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        setIsUploading(true);
        setUploadProgress(0);
        setUploadStage('uploading');

        const tempId = Date.now().toString();
        const placeholderDoc: NexusDocument = {
            id: tempId,
            name: file.name,
            doc_type: 'other',
            created_at: new Date().toISOString(),
            status: 'processing',
            extracted_data: { client_name: 'AI 识别中...' }
        };
        setDocuments(prev => [placeholderDoc, ...prev]);

        const interval = setInterval(() => {
            setUploadProgress(prev => Math.min(prev + 3, 98));
        }, 150);

        try {
            const formData = new FormData();
            formData.append('files', file);
            if (user?.id) {
                formData.append('userId', user.id);
            }

            const endpoint = `${getApiBaseUrl()}/api/documents/upload`;

            // P0: Secure Identity Verification
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Authorization': token ? `Bearer ${token}` : ''
                },
                body: formData,
                mode: 'cors',
            }).catch(err => {
                throw new Error(`网络连接异常: 无法触达后端 [${endpoint}]。请确认后端服务已启动且 CORS 已放行。`);
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.reason || result.message || '服务器内部错误');
            }

            // Check if backend reported an error in processing details
            // Backend returns: { success, data: { summary, results: [...] } }
            const fileInfo = result.data?.results?.[0] || result.details?.[0];
            if (fileInfo && (fileInfo.status === 'error' || fileInfo.status === 'skipped')) {
                throw new Error(fileInfo.reason || fileInfo.message || 'AI 解析文档失败，请检查后端 API 密钥或代理配置');
            }

            setUploadStage('indexing');
            await new Promise(r => setTimeout(r, 600));

            toast.success('上传成功并已完成 AI 知识提取');
            await fetchDocuments();
        } catch (error) {
            const message = error instanceof Error ? error.message : '上传处理异常，请重试';
            toast.error(message);
            setDocuments(prev => prev.map(d => d.id === tempId ? { ...d, status: 'error' } : d));
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
            clearInterval(interval);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleCategoryChange = async (docId: string, newType: string) => {
        try {
            const { error } = await supabase
                .from('documents')
                .update({ doc_type: newType })
                .eq('id', docId);
            if (error) throw error;

            // Optimistic UI update
            setDocuments(prev => prev.map(d =>
                d.id === docId ? { ...d, doc_type: newType as NexusDocument['doc_type'] } : d
            ));
            toast.success('文档分类已更新');
        } catch (error) {
            toast.error('更新分类失败');
        }
    };

    const handleBulkImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        if (!file.name.endsWith('.json')) {
            toast.error('请上传 JSON 格式的批量导入文件');
            return;
        }

        setIsBulkImporting(true);
        try {
            const text = await file.text();
            const parsed = JSON.parse(text);

            // Validate format: expect { documents: [...] } or just [...]
            const documents = Array.isArray(parsed) ? parsed : parsed.documents;
            if (!Array.isArray(documents) || documents.length === 0) {
                throw new Error('JSON 格式无效：需要包含 documents 数组');
            }

            const endpoint = `${getApiBaseUrl()}/api/documents/bulk-import`;

            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;

            if (!token) {
                toast.error('请先登录');
                return;
            }

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ documents }),
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result?.detail?.message || result?.message || '批量导入失败');
            }

            const data = result.data;
            toast.success(
                `批量导入完成：${data.success_count} 成功, ${data.skip_count} 跳过, ${data.error_count} 失败`
            );

            await fetchDocuments();
        } catch (error) {
            const message = error instanceof Error ? error.message : '批量导入失败';
            toast.error(message);
        } finally {
            setIsBulkImporting(false);
            if (bulkImportInputRef.current) bulkImportInputRef.current.value = '';
        }
    };

    const filteredDocs = documents.filter(doc => {
        // 1. Category Filter
        if (activeFilter !== 'all' && doc.doc_type !== activeFilter) return false;

        // 2. Search Query
        const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            doc.extracted_data?.client_name?.toLowerCase().includes(searchQuery.toLowerCase());
        if (!matchesSearch) return false;

        // 3. Amount Filter
        const docAmount = doc.extracted_data?.amount || 0;
        if (minAmount && docAmount < parseFloat(minAmount)) return false;
        if (maxAmount && docAmount > parseFloat(maxAmount)) return false;

        // 4. Date Filter
        if (filterDate) {
            const docDate = doc.extracted_data?.date || ''; // Formatted as YYYY-MM-DD
            if (docDate && !docDate.includes(filterDate)) return false;
        }

        return true;
    });

    return (
        <div className="h-full flex flex-col bg-background animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex items-center justify-between px-8 py-6 border-b border-border bg-white/50 backdrop-blur-md sticky top-0 z-10">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-3">
                        <div className="p-2 bg-primary/10 rounded-lg">
                            <FolderOpen className="w-6 h-6 text-primary" />
                        </div>
                        {isBoss ? '企业知识库管理' : '文档管理中心'}
                    </h1>
                    <p className="text-muted-foreground mt-1 text-sm">
                        AI 驱动的智能知识库 · 自动提取元数据 · 语义搜索就绪
                    </p>
                </div>
                <div className="flex gap-3">
                    {/* Bulk Import Button for Boss */}
                    {isBoss && (
                        <>
                            <input
                                type="file"
                                ref={bulkImportInputRef}
                                className="hidden"
                                onChange={handleBulkImport}
                                accept=".json"
                            />
                            <button
                                onClick={() => bulkImportInputRef.current?.click()}
                                disabled={isUploading || isBulkImporting}
                                className="px-5 py-2.5 bg-amber-500 text-white rounded-xl hover:bg-amber-600 transition-all flex items-center gap-2 shadow-lg shadow-amber-500/20 disabled:opacity-50 active:scale-95"
                            >
                                {isBulkImporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <PackagePlus className="w-4 h-4" />}
                                批量导入
                            </button>
                        </>
                    )}

                    {/* Delete Button for Boss */}
                    {isBoss && (
                        <button
                            onClick={handleBatchDelete}
                            disabled={isUploading || isDeleting || selectedIds.size === 0}
                            className={cn(
                                "px-5 py-2.5 rounded-xl transition-all flex items-center gap-2",
                                selectedIds.size > 0
                                    ? "bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-lg shadow-destructive/20"
                                    : "bg-secondary text-muted-foreground cursor-not-allowed opacity-50"
                            )}
                        >
                            {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                            删除选中 ({selectedIds.size})
                        </button>
                    )}

                    <input
                        type="file"
                        ref={fileInputRef}
                        className="hidden"
                        onChange={handleFileUpload}
                        accept=".pdf,.docx,.txt"
                    />
                    <button
                        onClick={() => fileInputRef.current?.click()}
                        disabled={isUploading}
                        className="px-6 py-2.5 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition-all flex items-center gap-2 shadow-lg shadow-primary/20 disabled:opacity-50 active:scale-95"
                    >
                        {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                        上传文档
                    </button>
                </div>
            </div>

            {/* Upload Progress Area */}
            {isUploading && (
                <div className="px-8 py-4 bg-primary/5 border-b border-primary/10 animate-in slide-in-from-top duration-300">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-bold text-primary flex items-center gap-2">
                            {uploadStage === 'uploading' ? '正在上传数据...' :
                                uploadStage === 'extracting' ? 'AI 正在阅读文档并提取元数据...' :
                                    '正在执行向量片段索引...'}
                        </span>
                        <span className="text-xs font-mono text-primary/60">{uploadProgress}%</span>
                    </div>
                    <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                        <div
                            className="h-full bg-primary transition-all duration-300 ease-out"
                            style={{ width: `${uploadProgress}%` }}
                        />
                    </div>
                </div>
            )}

            {/* Content Area */}
            <div className="flex-1 flex overflow-hidden">
                {/* Sidebar Filter */}
                <div className="w-72 border-r border-border p-6 space-y-8 hidden lg:block bg-secondary/5 overflow-y-auto">
                    <div>
                        <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-4 flex items-center gap-2">
                            <Filter className="w-3 h-3" />
                            知识库分类
                        </label>
                        <div className="space-y-1">
                            {[
                                { id: 'all', label: '全部文档', count: documents.length },
                                ...DOC_TYPE_OPTIONS.map(opt => ({
                                    id: opt.value,
                                    label: opt.label,
                                    count: documents.filter(d => d.doc_type === opt.value).length,
                                })),
                            ].map(filter => (
                                <button
                                    key={filter.id}
                                    onClick={() => setActiveFilter(filter.id)}
                                    className={cn(
                                        "w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-sm transition-all group",
                                        activeFilter === filter.id
                                            ? "bg-primary text-primary-foreground shadow-md shadow-primary/10 font-bold"
                                            : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                                    )}
                                >
                                    {filter.label}
                                    <span className={cn(
                                        "text-[10px] px-1.5 py-0.5 rounded-md border transition-colors",
                                        activeFilter === filter.id ? "bg-white/20 border-white/30 text-white" : "bg-background border-border group-hover:border-primary/30"
                                    )}>
                                        {filter.count}
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="space-y-4">
                        <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest block">智能筛选面板</label>

                        {/* Amount Range */}
                        <div className="p-4 bg-background rounded-2xl border border-border shadow-sm space-y-3">
                            <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                                <Currency className="w-3.5 h-3.5 text-primary" />
                                合同金额范围
                            </div>
                            <div className="flex items-center gap-2">
                                <input
                                    type="number"
                                    value={minAmount}
                                    onChange={(e) => setMinAmount(e.target.value)}
                                    className="w-full bg-secondary/30 border-none rounded-lg px-2 py-1.5 text-xs placeholder:text-muted-foreground/50 focus:ring-1 ring-primary/20"
                                    placeholder="最小"
                                />
                                <span className="text-muted-foreground">-</span>
                                <input
                                    type="number"
                                    value={maxAmount}
                                    onChange={(e) => setMaxAmount(e.target.value)}
                                    className="w-full bg-secondary/30 border-none rounded-lg px-2 py-1.5 text-xs placeholder:text-muted-foreground/50 focus:ring-1 ring-primary/20"
                                    placeholder="最大"
                                />
                            </div>
                        </div>

                        {/* Date Picker */}
                        <div className="p-4 bg-background rounded-2xl border border-border shadow-sm space-y-3">
                            <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                                <Calendar className="w-3.5 h-3.5 text-primary" />
                                签订日期定位
                            </div>
                            <input
                                type="date"
                                value={filterDate}
                                onChange={(e) => setFilterDate(e.target.value)}
                                className="w-full bg-secondary/30 border-none rounded-lg px-3 py-2 text-xs focus:ring-1 ring-primary/20"
                            />
                        </div>

                        <button
                            onClick={() => {
                                setMinAmount('');
                                setMaxAmount('');
                                setFilterDate('');
                                setSearchQuery('');
                            }}
                            className="w-full py-2 text-[10px] font-bold text-muted-foreground hover:text-primary transition-colors uppercase tracking-widest"
                        >
                            重置所有筛选器
                        </button>
                    </div>
                </div>

                {/* Document List */}
                <div className="flex-1 overflow-y-auto p-8 bg-dot-pattern">
                    <div className="max-w-4xl mx-auto space-y-6">
                        <div className="relative group">
                            <div className="absolute inset-0 bg-primary/5 rounded-2xl blur-xl group-focus-within:bg-primary/10 transition-colors" />
                            <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="通过文件名、客户名称或 AI 摘要关键词进行检索..."
                                className="w-full relative bg-white border border-border rounded-2xl pl-14 pr-4 py-4 text-sm focus:ring-0 focus:border-primary/50 transition-all shadow-sm group-focus-within:shadow-md"
                            />
                        </div>

                        {isLoading ? (
                            <div className="flex flex-col items-center justify-center py-32 gap-4">
                                <div className="relative">
                                    <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
                                    <FolderOpen className="w-4 h-4 text-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                                </div>
                                <p className="text-sm font-medium text-muted-foreground">正在同步云端知识库...</p>
                            </div>
                        ) : filteredDocs.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-40 text-muted-foreground animate-in zoom-in-95 duration-300">
                                <div className="w-20 h-20 rounded-full bg-secondary/30 flex items-center justify-center mb-6">
                                    <FileText className="w-10 h-10 opacity-10" />
                                </div>
                                <h3 className="text-lg font-bold text-foreground">未找到匹配文档</h3>
                                <p className="text-sm mt-1">尝试调整筛选条件或是上传新文档</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 gap-4">
                                {filteredDocs.map((doc) => (
                                    <DocumentCard
                                        key={doc.id}
                                        doc={doc}
                                        showCheckbox={isBoss}
                                        isSelected={selectedIds.has(doc.id)}
                                        onToggleSelect={() => toggleSelect(doc.id)}
                                        docTypeOptions={DOC_TYPE_OPTIONS}
                                        onCategoryChange={(newType) => handleCategoryChange(doc.id, newType)}
                                        onClick={() => {
                                            const docType = doc.doc_type || (doc.extracted_data as Record<string, unknown>)?.doc_type;
                                            if ((docType === 'bid' || docType === 'tender') && onNavigate) {
                                                onNavigate('tender-analysis');
                                                toast.success("已为您打开标书深度分析视图");
                                            } else {
                                                // Check for contract or other types
                                                if (doc.doc_type === 'contract') {
                                                    toast.info("合同分析模块正在开发中", { description: "Coming Soon: 法律条款风险自动审查" });
                                                } else {
                                                    toast.info("该文档详情暂不支持预览", { description: "目前仅开放[投标文件]类型的深度分析报告" });
                                                }
                                            }
                                        }}
                                    />
                                ))}
                            </div>
                        )}

                        <div className="pt-10 flex items-center justify-center">
                            <p className="text-[10px] text-muted-foreground border-t border-border pt-4 w-full text-center">
                                已加载全部 {filteredDocs.length} 份文档 · 由 Nexus AI 高级文档引擎驱动
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
