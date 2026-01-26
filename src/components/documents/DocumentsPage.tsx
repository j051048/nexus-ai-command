import React, { useState, useRef, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';
import {
    FileText,
    Upload,
    Search,
    FolderOpen,
    Loader2,
    Calendar,
    Currency,
    Filter
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { DocumentCard } from './components/DocumentCard';
import { useUser } from '@/contexts/UserContext';
import { NexusDocument } from '@/types/nexus';

export function DocumentsPage() {
    const { user } = useUser();
    const isBoss = user?.role === 'boss';

    const [documents, setDocuments] = useState<NexusDocument[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [uploadStage, setUploadStage] = useState<'uploading' | 'extracting' | 'indexing'>('uploading');
    const [searchQuery, setSearchQuery] = useState('');
    const [activeFilter, setActiveFilter] = useState<'all' | 'contract' | 'bid' | 'product'>('all');

    // Smart Filter States
    const [minAmount, setMinAmount] = useState<string>('');
    const [maxAmount, setMaxAmount] = useState<string>('');
    const [filterDate, setFilterDate] = useState<string>('');

    const fileInputRef = useRef<HTMLInputElement>(null);

    // Fetch documents from Supabase
    const fetchDocuments = async () => {
        setIsLoading(true);
        try {
            const { data, error } = await (supabase.from('documents' as any) as any)
                .select('*')
                .order('created_at', { ascending: false });

            if (error) throw error;

            const formattedDocs: NexusDocument[] = (data || []).map((doc: any) => ({
                id: doc.id,
                name: doc.name,
                doc_type: (doc.doc_type as any) || 'other',
                created_at: doc.created_at,
                status: 'completed',
                extracted_data: typeof doc.extracted_data === 'string'
                    ? JSON.parse(doc.extracted_data)
                    : (doc.extracted_data || {})
            }));

            setDocuments(formattedDocs);
        } catch (error: any) {
            console.error('Fetch error:', error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchDocuments();
    }, []);

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

            // Get standard API root
            let base = import.meta.env.VITE_API_BASE_URL || 'https://aizhz.zeabur.app';
            if (!base.startsWith('http')) base = `https://${base}`;
            const url = `${base}/api/documents/upload`;

            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                mode: 'cors',
                credentials: 'omit', // Standard for public APIs to avoid Preflight issues
            }).catch(err => {
                if (err.name === 'TypeError' && err.message === 'Failed to fetch') {
                    throw new Error('网络连接错误：无法连接到后端服务器，请检查基础 URL 配置或跨域限制');
                }
                throw err;
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.reason || result.message || '上传后解析失败');
            }

            setUploadStage('indexing');
            await new Promise(r => setTimeout(r, 600));

            toast.success('上传成功并已完成 AI 知识提取');
            await fetchDocuments();
        } catch (error: any) {
            console.error(error);
            toast.error(error.message || '处理故障，AI 服务暂时响应异常');
            setDocuments(prev => prev.map(d => d.id === tempId ? { ...d, status: 'error' } : d));
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
            clearInterval(interval);
            if (fileInputRef.current) fileInputRef.current.value = '';
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
                                { id: 'contract', label: '销售合同', count: documents.filter(d => d.doc_type === 'contract').length },
                                { id: 'bid', label: '投标文件', count: documents.filter(d => d.doc_type === 'bid').length },
                                { id: 'product', label: '产品资料', count: documents.filter(d => d.doc_type === 'product').length },
                            ].map(filter => (
                                <button
                                    key={filter.id}
                                    onClick={() => setActiveFilter(filter.id as any)}
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
                                        onClick={() => { }}
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
