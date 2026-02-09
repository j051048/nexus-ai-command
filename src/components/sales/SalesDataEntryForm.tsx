import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { format } from 'date-fns';
import { Calendar as CalendarIcon, Save, Loader2, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { useSaveSalesMetric } from '@/hooks/useSalesData';
import { toast } from 'sonner';

// Validation schema with zod
const salesFormSchema = z.object({
  date: z.date({
    required_error: "请选择日期",
  }),
  leads_count: z.coerce
    .number()
    .int({ message: "必须为整数" })
    .min(0, { message: "不能为负数" })
    .max(1000, { message: "数值过大" }),
  conversions: z.coerce
    .number()
    .int({ message: "必须为整数" })
    .min(0, { message: "不能为负数" })
    .max(100, { message: "数值过大" }),
  revenue: z.coerce
    .number()
    .min(0, { message: "不能为负数" })
    .max(100000000, { message: "数值过大" }),
  win_rate: z.coerce
    .number()
    .min(0, { message: "赢率不能为负" })
    .max(100, { message: "赢率不能超过100%" }),
  calls_made: z.coerce
    .number()
    .int({ message: "必须为整数" })
    .min(0, { message: "不能为负数" })
    .max(500, { message: "数值过大" }),
  score: z.coerce
    .number()
    .int({ message: "必须为整数" })
    .min(0, { message: "不能为负数" })
    .max(100, { message: "绩效分不能超过100" }),
}).refine((data) => {
  // Validate that conversions <= leads
  return data.conversions <= data.leads_count;
}, {
  message: "转化数不能大于线索数",
  path: ["conversions"],
});

type SalesFormValues = z.infer<typeof salesFormSchema>;

const defaultValues: Partial<SalesFormValues> = {
  date: new Date(),
  leads_count: 0,
  conversions: 0,
  revenue: 0,
  win_rate: 0,
  calls_made: 0,
  score: 0,
};

interface SalesDataEntryFormProps {
  onSuccess?: () => void;
}

export function SalesDataEntryForm({ onSuccess }: SalesDataEntryFormProps) {
  const saveMutation = useSaveSalesMetric();

  const form = useForm<SalesFormValues>({
    resolver: zodResolver(salesFormSchema),
    defaultValues,
    mode: 'onChange',
  });

  // Auto-calculate win rate when leads and conversions change
  const leadsCount = form.watch('leads_count');
  const conversions = form.watch('conversions');

  React.useEffect(() => {
    if (leadsCount > 0) {
      const calculatedWinRate = Math.round((conversions / leadsCount) * 100);
      form.setValue('win_rate', calculatedWinRate);
    }
  }, [leadsCount, conversions, form]);

  async function onSubmit(data: SalesFormValues) {
    try {
      await saveMutation.mutateAsync({
        date: format(data.date, 'yyyy-MM-dd'),
        leads_count: data.leads_count,
        conversions: data.conversions,
        revenue: data.revenue,
        win_rate: data.win_rate,
        calls_made: data.calls_made,
        score: data.score,
      });
      
      toast.success('销售数据已保存！');
      form.reset(defaultValues);
      onSuccess?.();
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      toast.error('保存失败: ' + message);
    }
  }

  return (
    <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center">
          <TrendingUp className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-foreground">录入销售数据</h2>
          <p className="text-sm text-muted-foreground">记录每日销售绩效指标</p>
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          {/* Date Picker */}
          <FormField
            control={form.control}
            name="date"
            render={({ field }) => (
              <FormItem className="flex flex-col">
                <FormLabel>日期</FormLabel>
                <Popover>
                  <PopoverTrigger asChild>
                    <FormControl>
                      <Button
                        variant="outline"
                        className={cn(
                          "w-full sm:w-[240px] pl-3 text-left font-normal",
                          !field.value && "text-muted-foreground"
                        )}
                      >
                        {field.value ? (
                          format(field.value, "yyyy-MM-dd")
                        ) : (
                          <span>选择日期</span>
                        )}
                        <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                      </Button>
                    </FormControl>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={field.value}
                      onSelect={field.onChange}
                      disabled={(date) =>
                        date > new Date() || date < new Date("2020-01-01")
                      }
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
                <FormDescription>
                  选择数据对应的日期
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Main Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <FormField
              control={form.control}
              name="leads_count"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>线索数</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="0"
                      {...field}
                      className="mono-number"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="conversions"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>转化数</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="0"
                      {...field}
                      className="mono-number"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="calls_made"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>通话数</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="0"
                      {...field}
                      className="mono-number"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="revenue"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>营收 (元)</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="0"
                      {...field}
                      className="mono-number"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="win_rate"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>赢率 (%)</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="0"
                      {...field}
                      className="mono-number bg-muted"
                      disabled
                    />
                  </FormControl>
                  <FormDescription className="text-xs">
                    自动计算
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="score"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>绩效分</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="0-100"
                      {...field}
                      className="mono-number"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <Button 
            type="submit" 
            disabled={saveMutation.isPending}
            className="w-full sm:w-auto"
          >
            {saveMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                保存中...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                保存数据
              </>
            )}
          </Button>
        </form>
      </Form>
    </div>
  );
}
