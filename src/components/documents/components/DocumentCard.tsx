import React from 'react';
import { FileText, CheckCircle, Clock, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { AICopilotInsight } from '@/components/common/AICopilotInsight';
import { Checkbox } from "@/components/ui/checkbox";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { NexusDocument } from '@/types/nexus';

interface DocTypeOption {
    readonly value: string;
    readonly label: string;
}

interface DocumentCardProps {
    doc: NexusDocument;
    onClick: () => void;
    showCheckbox?: boolean;
    isSelected?: boolean;
    onToggleSelect?: () => void;
    docTypeOptions?: readonly DocTypeOption[];
    onCategoryChange?: (newType: string) => void;
}

export function DocumentCard({ doc, onClick, showCheckbox, isSelected, onToggleSelect, docTypeOptions, onCategoryChange }: DocumentCardProps) {
    const isCompleted = doc.status === 'completed';
    const isError = doc.status === 'error';
    const currentLabel = docTypeOptions?.find(o => o.value === doc.doc_type)?.label || '其他';

    return (
        <div
            onClick={(e) => {
                // Determine if we are clicking specific interactive elements inside
                // If checkbox is clicked, don't trigger main click
                // But checkbox handler usually handles stopPropagation
                onClick();
            }}
            className={cn(
                "flex items-center gap-4 p-4 rounded-xl bg-secondary/30 border transition-all cursor-pointer group hover:bg-secondary/50",
                isSelected ? "border-primary bg-primary/5" : "border-border/50 hover:border-primary/50"
            )}
        >
            <div className={cn(
                "w-12 h-12 rounded-xl flex items-center justify-center shrink-0 transition-transform group-hover:scale-105",
                isCompleted ? "bg-success/10 text-success" :
                    isError ? "bg-destructive/10 text-destructive" : "bg-primary/10 text-primary"
            )}>
                <FileText className="w-6 h-6" />
            </div>

            <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                    <h4 className="font-bold text-sm text-foreground truncate group-hover:text-primary transition-colors">
                        {doc.name}
                    </h4>
                    {isCompleted && (
                        <AICopilotInsight
                            title={doc.name}
                            context={`Document Type: ${doc.doc_type}, Client: ${doc.extracted_data?.client_name}`}
                            insights={
                                doc.doc_type === 'contract' ? [
                                    { type: 'risk', content: '发现违约金条款比例（20%）偏高于行业基准（15%）。' },
                                    { type: 'suggestion', content: '建议增加关于不可抗力的细化描述。' }
                                ] : [
                                    { type: 'summary', content: '该文档已成功解析，提取了客户名称和关键财务指标。' }
                                ]
                            }
                            className="opacity-0 group-hover:opacity-100 transition-opacity"
                            onViewReport={onClick}
                        />
                    )}
                </div>
                <div className="flex items-center gap-3 mt-1">
                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                        {doc.extracted_data?.client_name || '未识别客户'}
                        {isCompleted && <CheckCircle className="w-3 h-3 text-success fill-success/10" />}
                    </p>
                    <span className="text-[10px] text-muted-foreground opacity-50">•</span>
                    {docTypeOptions && onCategoryChange ? (
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <button
                                    onClick={(e) => e.stopPropagation()}
                                    className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                                >
                                    {currentLabel}
                                    <ChevronDown className="w-3 h-3" />
                                </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="start" onClick={(e) => e.stopPropagation()}>
                                {docTypeOptions.map(opt => (
                                    <DropdownMenuItem
                                        key={opt.value}
                                        onClick={() => onCategoryChange(opt.value)}
                                        className={cn(opt.value === doc.doc_type && "font-bold text-primary")}
                                    >
                                        {opt.label}
                                    </DropdownMenuItem>
                                ))}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    ) : (
                        <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-primary/10 text-primary">
                            {currentLabel}
                        </span>
                    )}
                    <span className="text-[10px] text-muted-foreground opacity-50">•</span>
                    <p className="text-[10px] text-muted-foreground max-w-[300px] truncate">
                        {doc.extracted_data?.summary || '文档已入库，AI 索引已完成'}
                    </p>
                    <span className="text-[10px] text-muted-foreground opacity-50">•</span>
                    <p className="text-[10px] text-muted-foreground">
                        {new Date(doc.created_at).toLocaleDateString()}
                    </p>
                </div>
            </div>

            <div className="flex flex-col items-end gap-1">
                {doc.status === 'processing' ? (
                    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-primary/10 text-primary animate-pulse">
                        <Clock size={10} />
                        <span className="text-[10px] font-bold uppercase">AI 解析中</span>
                    </div>
                ) : isCompleted ? (
                    <span className="text-[10px] font-extrabold text-success uppercase tracking-widest px-2 py-0.5 rounded-full bg-success/10">已入库</span>
                ) : (
                    <span className="text-[10px] font-extrabold text-destructive uppercase tracking-widest px-2 py-0.5 rounded-full bg-destructive/10">解析异常</span>
                )}
                {doc.extracted_data?.amount && (
                    <p className="text-xs font-bold text-foreground mt-1">¥{doc.extracted_data.amount.toLocaleString()}</p>
                )}
            </div>

            {showCheckbox && (
                <div onClick={(e) => e.stopPropagation()} className="pl-2 border-l border-border/50 ml-2">
                    <Checkbox
                        checked={isSelected}
                        onCheckedChange={() => onToggleSelect?.()}
                        className="data-[state=checked]:bg-destructive data-[state=checked]:border-destructive"
                    />
                </div>
            )}
        </div>
    );
}
