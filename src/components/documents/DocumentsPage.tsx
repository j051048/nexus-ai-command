import React, { useState, useRef } from 'react';
import { supabase } from '@/integrations/supabase/client';
import {
    FileText,
    Upload,
    Search,
    Filter,
    MoreHorizontal,
    Download,
    Trash2,
    Clock,
    CheckCircle,
    AlertCircle,
    FileCheck,
    ChevronRight,
    FolderOpen
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface Document {
    id: string;
    name: string;
    doc_type: 'contract' | 'bid' | 'product' | 'other';
    size: string;
    updated_at: string;
    extracted_data?: {
        client_name?: string;
        amount?: number;
        date?: string;
    };
}

import { useUser } from '@/contexts/UserContext';

export function DocumentsPage() {
    const { user } = useUser();
    const isBoss = user?.role === 'boss';

    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [uploadStage, setUploadStage] = useState<'uploading' | 'extracting' | 'indexing'>('uploading');
    const [searchQuery, setSearchQuery] = useState('');
    const [activeFilter, setActiveFilter] = useState<'all' | 'contract' | 'bid' | 'product'>('all');
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Mock Data for MVP Visualization
    const [documents, setDocuments] = useState<Document[]>([
        {
            id: '1',
            name: '2024年高校液相色谱采购合同.pdf',
            doc_type: 'contract',
            size: '2.4 MB',
            updated_at: '2024-01-25',
            extracted_data: { client_name: '北京大学', amount: 450000, date: '2024-01-20' }
        },
        {
            id: '2',
            name: '疾控中心气相色谱投标书_v3.pdf',
            doc_type: 'bid',
            size: '15.1 MB',
            updated_at: '2024-01-24',
            extracted_data: { client_name: '朝阳疾控', amount: 800000 }
        },
        {
            id: '3',
            name: 'Nexus_AI_中控系统产品白皮书.pdf',
            doc_type: 'product',
            size: '5.2 MB',
            updated_at: '2024-01-26',
            extracted_data: { client_name: '内部资料' }
        }
    ]);

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        setIsUploading(true);
        setUploadProgress(0);
        setUploadStage('uploading');

        // Simulate Upload Process
        const interval = setInterval(() => {
            setUploadProgress(prev => {
                if (prev >= 95) {
                    clearInterval(interval);
                    return 95;
                }
                return prev + 5;
            });
        }, 200);

        try {
            // 1. Uploading
            await new Promise(r => setTimeout(r, 1500));
            setUploadStage('extracting');

            // 2. Extracting (Simulated delay for AI)
            await new Promise(r => setTimeout(r, 2000));
            setUploadStage('indexing');

            // 3. Real Backend Call
            const formData = new FormData();
            formData.append('files', file);

            let url = import.meta.env.VITE_API_BASE_URL || 'https://aizhz.zeabur.app';
            if (!url.startsWith('http')) url = `https://${url}`;

            const response = await fetch(`${url}/api/documents/upload`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) throw new Error('Upload failed');
            const result = await response.json();

            setDocuments(prev => [{
                id: Date.now().toString(),
                name: file.name,
                doc_type: 'other', // In real app, this comes from backend result
                size: `${(file.size / 1024 / 1024).toFixed(1)} MB`,
                updated_at: new Date().toISOString().split('T')[0],
                extracted_data: { client_name: '正在分析...', amount: 0 }
            }, ...prev]);

            toast.success('上传成功！AI已提取关键信息');
        } catch (error) {
            console.error(error);
            toast.error('上传失败');
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
            clearInterval(interval);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const filteredDocs = documents.filter(doc => {
        if (activeFilter !== 'all' && doc.doc_type !== activeFilter) return false;
        return doc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            doc.extracted_data?.client_name?.includes(searchQuery);
    });

    return (
        <div className="h-full flex flex-col bg-background animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between px-8 py-6 border-b border-border">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-3">
                        <FolderOpen className="w-8 h-8 text-primary" />
                        {isBoss ? '企业知识库管理' : '文档管理中心'}
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        {isBoss ? '上传、维护企业核心知识资产，实时更新 AI 认知' : 'AI 驱动的智能知识库，自动提取、自动归档'}
                    </p>
                </div>
                <div className="flex gap-3">
                    <button className="px-4 py-2 bg-secondary text-foreground rounded-lg hover:bg-secondary/80 transition-colors flex items-center gap-2">
                        <Filter className="w-4 h-4" />
                        筛选
                    </button>
                    <input
                        type="file"
                        ref={fileInputRef}
                        className="hidden"
                        onChange={handleFileUpload}
                        accept=".pdf,.docx,.txt"
                    />
                    <button
                        onClick={() => fileInputRef.current?.click()}
                        className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-2 shadow-lg shadow-primary/20"
                    >
                        <Upload className="w-4 h-4" />
                        上传文档
                    </button>
                </div>
            </div>

            {/* Upload Progress Area */}
            {isUploading && (
                <div className="px-8 py-4 bg-primary/5 border-b border-primary/10">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-primary flex items-center gap-2">
                            {uploadStage === 'uploading' && <Upload className="w-4 h-4 animate-bounce" />}
                            {uploadStage === 'extracting' && <FileText className="w-4 h-4 animate-pulse" />}
                            {uploadStage === 'indexing' && <CheckCircle className="w-4 h-4" />}

                            {uploadStage === 'uploading' && '正在上传文件...'}
                            {uploadStage === 'extracting' && 'AI 正在阅读并提取关键信息...'}
                            {uploadStage === 'indexing' && '正在构建向量索引...'}
                        </span>
                        <span className="text-xs text-muted-foreground">{uploadProgress}%</span>
                    </div>
                    <div className="h-2 bg-secondary rounded-full overflow-hidden">
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
                <div className="w-64 border-r border-border p-6 space-y-6">
                    <div>
                        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 block">直接筛选</label>
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
                                        "w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors",
                                        activeFilter === filter.id
                                            ? "bg-primary/10 text-primary font-medium"
                                            : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                                    )}
                                >
                                    {filter.label}
                                    <span className="text-xs bg-background border border-border px-1.5 py-0.5 rounded-full">{filter.count}</span>
                                </button>
                            ))}
                        </div>
                    </div>

                    <div>
                        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 block">智能筛选</label>
                        <div className="space-y-2">
                            <div className="p-3 bg-secondary/30 rounded-lg border border-border">
                                <p className="text-xs text-muted-foreground mb-2">按金额范围</p>
                                <div className="flex items-center gap-2">
                                    <input className="w-full bg-background border border-border rounded px-2 py-1 text-xs" placeholder="Min" />
                                    <span className="text-muted-foreground">-</span>
                                    <input className="w-full bg-background border border-border rounded px-2 py-1 text-xs" placeholder="Max" />
                                </div>
                            </div>
                            <div className="p-3 bg-secondary/30 rounded-lg border border-border">
                                <p className="text-xs text-muted-foreground mb-2">按签订日期</p>
                                <input type="date" className="w-full bg-background border border-border rounded px-2 py-1 text-xs" />
                            </div>
                        </div>
                    </div>
                </div>

                {/* List View */}
                <div className="flex-1 overflow-y-auto bg-stone-50/30 dark:bg-background">
                    <div className="p-6">
                        {/* Search Bar */}
                        <div className="relative mb-6">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <input
                                type="text"
                                placeholder="搜索文档名称、客户名或合同金额..."
                                className="w-full pl-10 pr-4 py-3 rounded-xl border border-input bg-background shadow-sm focus:ring-2 focus:ring-primary/20 outline-none transition-all"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                        </div>

                        {/* Table Header */}
                        <div className="grid grid-cols-12 gap-4 px-4 py-3 text-xs font-medium text-muted-foreground border-b border-border">
                            <div className="col-span-5">文件名 / 客户</div>
                            <div className="col-span-2">类型</div>
                            <div className="col-span-2">金额 (¥)</div>
                            <div className="col-span-2">更新时间</div>
                            <div className="col-span-1 text-right">操作</div>
                        </div>

                        {/* Table Body */}
                        <div className="space-y-2 mt-2">
                            {filteredDocs.map((doc) => (
                                <div key={doc.id} className="grid grid-cols-12 gap-4 px-4 py-4 items-center bg-card hover:bg-card-elevated border border-border/50 hover:border-primary/20 rounded-xl transition-all group animate-fade-in cursor-pointer">
                                    <div className="col-span-5 flex items-center gap-3">
                                        <div className={cn(
                                            "w-10 h-10 rounded-lg flex items-center justify-center shrink-0",
                                            doc.doc_type === 'contract' ? "bg-blue-100 text-blue-600 dark:bg-blue-900/20" :
                                                doc.doc_type === 'bid' ? "bg-orange-100 text-orange-600 dark:bg-orange-900/20" :
                                                    doc.doc_type === 'product' ? "bg-purple-100 text-purple-600 dark:bg-purple-900/20" :
                                                        "bg-gray-100 text-gray-600 dark:bg-gray-800"
                                        )}>
                                            <FileText className="w-5 h-5" />
                                        </div>
                                        <div className="min-w-0">
                                            <h4 className="font-medium text-sm text-foreground truncate group-hover:text-primary transition-colors">{doc.name}</h4>
                                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                                                {doc.extracted_data?.client_name || '未识别客户'}
                                                {doc.extracted_data?.client_name && <CheckCircle className="w-3 h-3 text-success" />}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="col-span-2">
                                        <span className={cn(
                                            "px-2.5 py-1 rounded-full text-xs font-medium",
                                            doc.doc_type === 'contract' ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" :
                                                doc.doc_type === 'bid' ? "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300" :
                                                    doc.doc_type === 'product' ? "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300" :
                                                        "bg-gray-100 text-gray-700"
                                        )}>
                                            {doc.doc_type === 'contract' ? '销售合同' : doc.doc_type === 'bid' ? '投标文件' : doc.doc_type === 'product' ? '产品资料' : '其他'}
                                        </span>
                                    </div>
                                    <div className="col-span-2 font-mono text-sm">
                                        {doc.extracted_data?.amount ? `¥${doc.extracted_data.amount.toLocaleString()}` : '-'}
                                    </div>
                                    <div className="col-span-2 text-sm text-muted-foreground flex items-center gap-2">
                                        <Clock className="w-3 h-3" />
                                        {doc.updated_at}
                                    </div>
                                    <div className="col-span-1 flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button className="p-2 hover:bg-secondary rounded-lg text-muted-foreground hover:text-primary">
                                            <Download className="w-4 h-4" />
                                        </button>
                                        <button className="p-2 hover:bg-destructive/10 rounded-lg text-muted-foreground hover:text-destructive">
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
