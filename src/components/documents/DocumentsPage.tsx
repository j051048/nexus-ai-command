import React, { useState, useRef, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';
import {
    FileText,
    Upload,
    Search,
    FolderOpen,
    Loader2
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
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Fetch documents from Supabase
    const fetchDocuments = async () => {
        setIsLoading(true);
        try {
            // Using casting to any to bypass strict type check for the dynamically created 'documents' table
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
                    : doc.extracted_data
            }));

            setDocuments(formattedDocs);
        } catch (error: any) {
            console.error('Fetch error:', error);
            // Don't toast on initial load to avoid noise if table doesn't exist yet
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
            setUploadProgress(prev => Math.min(prev + 2, 98));
        }, 150);

        try {
            const formData = new FormData();
            formData.append('files', file);

            let url = import.meta.env.VITE_API_BASE_URL || 'https://aizhz.zeabur.app';
            if (!url.startsWith('http')) url = `https://${url}`;

            const response = await fetch(`${url}/api/documents/upload`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.reason || '上传后解析失败');
            }

            setUploadStage('indexing');
            await new Promise(r => setTimeout(r, 800));

            toast.success('上传成功并已完成 AI 知识提取');
            await fetchDocuments();
        } catch (error: any) {
            console.error(error);
            toast.error(error.message || '处理失败，请重试');
            setDocuments(prev => prev.map(d => d.id === tempId ? { ...d, status: 'error' } : d));
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
            clearInterval(interval);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const filteredDocs = documents.filter(doc => {
        const matchesType = activeFilter === 'all' || doc.doc_type === activeFilter;
        const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            doc.extracted_data?.client_name?.includes(searchQuery);
        return matchesType && matchesSearch;
    });

    return (
        <div className="h-full flex flex-col bg-background animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex items-center justify-between px-8 py-6 border-b border-border">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-3">
                        <FolderOpen className="w-8 h-8 text-primary" />
                        {isBoss ? '企业知识库管理' : '文档管理中心'}
                    </h1>
                    <p className="text-muted-foreground mt-1">
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
                        className="px-6 py-2.5 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition-all flex items-center gap-2 shadow-lg shadow-primary/20 disabled:opacity-50"
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
                <div className="w-64 border-r border-border p-6 space-y-6 hidden lg:block bg-secondary/10">
                    <div>
                        <label className="text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-4 block">知识库分类</label>
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
                                        "w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-sm transition-all",
                                        activeFilter === filter.id
                                            ? "bg-primary text-primary-foreground shadow-md shadow-primary/10 font-bold"
                                            : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                                    )}
                                >
                                    {filter.label}
                                    <span className={cn(
                                        "text-[10px] px-1.5 py-0.5 rounded-md border",
                                        activeFilter === filter.id ? "bg-white/20 border-white/30 text-white" : "bg-background border-border"
                                    )}>
                                        {filter.count}
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Document List */}
                <div className="flex-1 overflow-y-auto p-8">
                    <div className="max-w-4xl mx-auto space-y-6">
                        <div className="relative">
                            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="通过文件名、客户名称、合同金额进行语义搜索..."
                                className="w-full bg-card border border-border rounded-2xl pl-12 pr-4 py-3.5 text-sm focus:ring-2 focus:ring-primary/20 transition-all shadow-sm"
                            />
                        </div>

                        {isLoading ? (
                            <div className="flex flex-col items-center justify-center py-20 gap-3">
                                <Loader2 className="w-8 h-8 animate-spin text-primary/50" />
                                <p className="text-sm text-muted-foreground">正在同步云端知识库...</p>
                            </div>
                        ) : filteredDocs.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-32 text-muted-foreground">
                                <div className="w-20 h-20 rounded-full bg-secondary flex items-center justify-center mb-6">
                                    <FileText className="w-10 h-10 opacity-20" />
                                </div>
                                <h3 className="text-lg font-bold text-foreground">暂无文档</h3>
                                <p className="text-sm mt-1">上传 PDF 或其他文档，AI 将自动处理</p>
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
                    </div>
                </div>
            </div>
        </div>
    );
}
