import React, { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

interface FormField {
  name: string;
  label: string;
  type?: 'text' | 'number' | 'email' | 'select';
  options?: string[];
  required?: boolean;
  placeholder?: string;
}

interface FormBuilderProps {
  title?: string;
  fields: FormField[];
  submitLabel?: string;
  onSubmit?: (data: Record<string, string>) => void;
}

export default function FormBuilder({ title, fields = [], submitLabel = '提交', onSubmit }: FormBuilderProps) {
  const [values, setValues] = useState<Record<string, string>>({});

  const handleChange = (name: string, value: string) => {
    setValues(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit?.(values);
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 space-y-4">
      {title && <h3 className="text-sm font-semibold text-foreground">{title}</h3>}
      {fields.map((field) => (
        <div key={field.name} className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            {field.label}{field.required && <span className="text-red-500 ml-0.5">*</span>}
          </label>
          {field.type === 'select' ? (
            <select
              className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
              value={values[field.name] || ''}
              onChange={(e) => handleChange(field.name, e.target.value)}
              required={field.required}
            >
              <option value="">{field.placeholder || '请选择'}</option>
              {field.options?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
            </select>
          ) : (
            <Input
              type={field.type || 'text'}
              placeholder={field.placeholder}
              value={values[field.name] || ''}
              onChange={(e) => handleChange(field.name, e.target.value)}
              required={field.required}
            />
          )}
        </div>
      ))}
      <Button type="submit" size="sm">{submitLabel}</Button>
    </form>
  );
}
