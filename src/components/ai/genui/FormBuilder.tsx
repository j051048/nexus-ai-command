import React, { useState, useMemo } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, Check } from 'lucide-react';

export interface FormField {
  name: string;
  label: string;
  type?: 'text' | 'number' | 'email' | 'select' | 'date' | 'textarea' | 'checkbox';
  options?: string[];
  required?: boolean;
  placeholder?: string;
  default_value?: string;
  step?: number;
}

interface FormBuilderProps {
  title?: string;
  fields: FormField[];
  submitLabel?: string;
  onSubmit?: (data: Record<string, string>) => void;
}

export default function FormBuilder({ title, fields = [], submitLabel = '提交', onSubmit }: FormBuilderProps) {
  // Initialize with default values
  const [values, setValues] = useState<Record<string, string>>(() => {
    const defaults: Record<string, string> = {};
    for (const f of fields) {
      if (f.default_value) defaults[f.name] = f.default_value;
    }
    return defaults;
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [currentStep, setCurrentStep] = useState(1);

  // Detect multi-step mode
  const isMultiStep = fields.some((f) => f.step && f.step > 1);
  const totalSteps = isMultiStep ? Math.max(...fields.map((f) => f.step || 1)) : 1;

  const currentFields = useMemo(
    () => (isMultiStep ? fields.filter((f) => (f.step || 1) === currentStep) : fields),
    [fields, currentStep, isMultiStep]
  );

  const handleChange = (name: string, value: string) => {
    setValues((prev) => ({ ...prev, [name]: value }));
    // Clear error on change
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const validate = (fieldsToValidate: FormField[]): boolean => {
    const newErrors: Record<string, string> = {};
    for (const f of fieldsToValidate) {
      const val = values[f.name] || '';
      if (f.required && !val.trim()) {
        newErrors[f.name] = `${f.label}为必填项`;
      }
      if (f.type === 'number' && val && isNaN(Number(val))) {
        newErrors[f.name] = '请输入有效数字';
      }
      if (f.type === 'email' && val && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) {
        newErrors[f.name] = '请输入有效邮箱';
      }
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validate(currentFields)) {
      setCurrentStep((s) => Math.min(s + 1, totalSteps));
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const fieldsToValidate = isMultiStep ? fields : currentFields;
    if (validate(fieldsToValidate)) {
      onSubmit?.(values);
    }
  };

  const renderField = (field: FormField) => {
    const val = values[field.name] || '';
    const error = errors[field.name];

    return (
      <div key={field.name} className="space-y-1.5">
        {field.type !== 'checkbox' && (
          <label className="text-xs font-medium text-muted-foreground">
            {field.label}
            {field.required && <span className="text-red-500 ml-0.5">*</span>}
          </label>
        )}

        {field.type === 'select' ? (
          <select
            className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={val}
            onChange={(e) => handleChange(field.name, e.target.value)}
          >
            <option value="">{field.placeholder || '请选择'}</option>
            {field.options?.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        ) : field.type === 'textarea' ? (
          <textarea
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[80px] resize-y focus:outline-none focus:ring-2 focus:ring-primary/50"
            placeholder={field.placeholder}
            value={val}
            onChange={(e) => handleChange(field.name, e.target.value)}
            rows={3}
          />
        ) : field.type === 'checkbox' ? (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              className="rounded border-input"
              checked={val === 'true'}
              onChange={(e) => handleChange(field.name, String(e.target.checked))}
            />
            <span className="text-sm text-foreground">{field.label}</span>
          </label>
        ) : (
          <Input
            type={field.type || 'text'}
            placeholder={field.placeholder}
            value={val}
            onChange={(e) => handleChange(field.name, e.target.value)}
          />
        )}

        {error && <p className="text-xs text-destructive">{error}</p>}
      </div>
    );
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 space-y-4 rounded-xl border border-blue-500/30 bg-blue-50 dark:bg-blue-950/20 mx-4 mb-2">
      {title && <h3 className="text-sm font-semibold text-foreground">{title}</h3>}

      {/* Step progress indicator */}
      {isMultiStep && (
        <div className="flex items-center gap-1 justify-center">
          {Array.from({ length: totalSteps }, (_, i) => {
            const step = i + 1;
            return (
              <React.Fragment key={step}>
                {i > 0 && (
                  <div className={`h-px w-6 ${step <= currentStep ? 'bg-primary' : 'bg-border'}`} />
                )}
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium ${
                    step < currentStep
                      ? 'bg-primary text-primary-foreground'
                      : step === currentStep
                        ? 'bg-primary/20 text-primary border border-primary'
                        : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {step < currentStep ? <Check className="w-3 h-3" /> : step}
                </div>
              </React.Fragment>
            );
          })}
        </div>
      )}

      {currentFields.map(renderField)}

      <div className="flex items-center gap-2 pt-1">
        {isMultiStep && currentStep > 1 && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setCurrentStep((s) => s - 1)}
          >
            <ChevronLeft className="w-3 h-3 mr-1" />
            上一步
          </Button>
        )}
        {isMultiStep && currentStep < totalSteps ? (
          <Button type="button" size="sm" onClick={handleNext}>
            下一步
            <ChevronRight className="w-3 h-3 ml-1" />
          </Button>
        ) : (
          <Button type="submit" size="sm">{submitLabel}</Button>
        )}
      </div>
    </form>
  );
}
