/* eslint-disable react-refresh/only-export-components */
/**
 * P1 UX Enhancement: Multi-Step Form Component
 * 多步骤表单组件，支持步骤导航、验证和状态管理
 */

import React, { useState, useCallback, useMemo, createContext, useContext } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertCircle,
  Circle,
} from 'lucide-react';
import { getEnterAnimationClass } from '@/lib/animations';

// ==================== 类型定义 ====================

export interface StepConfig {
  id: string;
  title: string;
  description?: string;
  icon?: React.ReactNode;
  optional?: boolean;
  validate?: () => boolean | Promise<boolean>;
}

export interface MultiStepFormContextValue<T = Record<string, unknown>> {
  currentStep: number;
  totalSteps: number;
  formData: T;
  updateFormData: (data: Partial<T>) => void;
  goToStep: (step: number) => void;
  nextStep: () => Promise<void>;
  prevStep: () => void;
  isFirstStep: boolean;
  isLastStep: boolean;
  isSubmitting: boolean;
  errors: Record<string, string>;
  setErrors: (errors: Record<string, string>) => void;
}

interface MultiStepFormProps<T> {
  steps: StepConfig[];
  initialData?: T;
  onSubmit: (data: T) => Promise<void>;
  onStepChange?: (step: number, data: T) => void;
  children: React.ReactNode;
  className?: string;
  showProgress?: boolean;
  showStepIndicator?: boolean;
  allowSkip?: boolean;
  submitLabel?: string;
  nextLabel?: string;
  prevLabel?: string;
}

interface StepContentProps {
  step: number;
  children: React.ReactNode;
  className?: string;
}

// ==================== Context ====================

const MultiStepFormContext = createContext<MultiStepFormContextValue | null>(null);

export function useMultiStepForm<T = Record<string, unknown>>() {
  const context = useContext(MultiStepFormContext);
  if (!context) {
    throw new Error('useMultiStepForm must be used within MultiStepForm');
  }
  return context as MultiStepFormContextValue<T>;
}

// ==================== 子组件 ====================

/**
 * 步骤指示器
 */
function StepIndicator({
  steps,
  currentStep,
  onStepClick,
  allowNavigation = true,
}: {
  steps: StepConfig[];
  currentStep: number;
  onStepClick?: (step: number) => void;
  allowNavigation?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      {steps.map((step, index) => {
        const isCompleted = index < currentStep;
        const isCurrent = index === currentStep;
        const isClickable = allowNavigation && (isCompleted || index === currentStep + 1);

        return (
          <React.Fragment key={step.id}>
            {/* Step Circle */}
            <button
              type="button"
              onClick={() => isClickable && onStepClick?.(index)}
              disabled={!isClickable}
              className={cn(
                'flex items-center gap-3 group transition-all',
                isClickable && 'cursor-pointer',
                !isClickable && 'cursor-default'
              )}
            >
              <div
                className={cn(
                  'w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300',
                  isCompleted && 'bg-primary text-primary-foreground',
                  isCurrent && 'bg-primary text-primary-foreground ring-4 ring-primary/20',
                  !isCompleted && !isCurrent && 'bg-muted text-muted-foreground',
                  isClickable && !isCurrent && 'group-hover:bg-primary/80 group-hover:text-primary-foreground'
                )}
              >
                {isCompleted ? (
                  <Check className="w-5 h-5" />
                ) : step.icon ? (
                  step.icon
                ) : (
                  <span className="text-sm font-medium">{index + 1}</span>
                )}
              </div>

              <div className="hidden md:block text-left">
                <p
                  className={cn(
                    'text-sm font-medium transition-colors',
                    (isCompleted || isCurrent) ? 'text-foreground' : 'text-muted-foreground'
                  )}
                >
                  {step.title}
                </p>
                {step.description && (
                  <p className="text-xs text-muted-foreground">
                    {step.description}
                  </p>
                )}
              </div>
            </button>

            {/* Connector Line */}
            {index < steps.length - 1 && (
              <div
                className={cn(
                  'flex-1 h-0.5 mx-4 transition-colors duration-300',
                  index < currentStep ? 'bg-primary' : 'bg-muted'
                )}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

/**
 * 紧凑型步骤指示器（移动端）
 */
function CompactStepIndicator({
  steps,
  currentStep,
}: {
  steps: StepConfig[];
  currentStep: number;
}) {
  return (
    <div className="flex items-center justify-center gap-2">
      {steps.map((_, index) => (
        <div
          key={index}
          className={cn(
            'w-2 h-2 rounded-full transition-all duration-300',
            index === currentStep && 'w-6 bg-primary',
            index < currentStep && 'bg-primary',
            index > currentStep && 'bg-muted'
          )}
        />
      ))}
    </div>
  );
}

/**
 * 步骤内容容器
 */
export function StepContent({ step, children, className }: StepContentProps) {
  const { currentStep } = useMultiStepForm();

  if (step !== currentStep) {
    return null;
  }

  return (
    <div className={cn(getEnterAnimationClass('slide-left', 'fast'), className)}>
      {children}
    </div>
  );
}

// ==================== 主组件 ====================

export function MultiStepForm<T extends Record<string, unknown>>({
  steps,
  initialData = {} as T,
  onSubmit,
  onStepChange,
  children,
  className,
  showProgress = true,
  showStepIndicator = true,
  allowSkip = false,
  submitLabel = '提交',
  nextLabel = '下一步',
  prevLabel = '上一步',
}: MultiStepFormProps<T>) {
  const [currentStep, setCurrentStep] = useState(0);
  const [formData, setFormData] = useState<T>(initialData);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const totalSteps = steps.length;
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === totalSteps - 1;
  const progress = ((currentStep + 1) / totalSteps) * 100;

  const updateFormData = useCallback((data: Partial<T>) => {
    setFormData((prev) => ({ ...prev, ...data }));
    // 清除相关错误
    const newErrors = { ...errors };
    Object.keys(data).forEach((key) => {
      delete newErrors[key];
    });
    setErrors(newErrors);
  }, [errors]);

  const goToStep = useCallback((step: number) => {
    if (step >= 0 && step < totalSteps) {
      setCurrentStep(step);
      onStepChange?.(step, formData);
    }
  }, [totalSteps, formData, onStepChange]);

  const nextStep = useCallback(async () => {
    const currentStepConfig = steps[currentStep];
    
    // 验证当前步骤
    if (currentStepConfig.validate) {
      try {
        const isValid = await currentStepConfig.validate();
        if (!isValid) {
          return;
        }
      } catch (error) {
        console.error('Validation error:', error);
        return;
      }
    }

    if (isLastStep) {
      // 提交表单
      setIsSubmitting(true);
      try {
        await onSubmit(formData);
      } catch (error) {
        console.error('Submit error:', error);
      } finally {
        setIsSubmitting(false);
      }
    } else {
      // 进入下一步
      const nextStepIndex = currentStep + 1;
      setCurrentStep(nextStepIndex);
      onStepChange?.(nextStepIndex, formData);
    }
  }, [currentStep, isLastStep, steps, formData, onSubmit, onStepChange]);

  const prevStep = useCallback(() => {
    if (!isFirstStep) {
      const prevStepIndex = currentStep - 1;
      setCurrentStep(prevStepIndex);
      onStepChange?.(prevStepIndex, formData);
    }
  }, [currentStep, isFirstStep, formData, onStepChange]);

  const contextValue = useMemo<MultiStepFormContextValue<T>>(
    () => ({
      currentStep,
      totalSteps,
      formData,
      updateFormData,
      goToStep,
      nextStep,
      prevStep,
      isFirstStep,
      isLastStep,
      isSubmitting,
      errors,
      setErrors,
    }),
    [
      currentStep,
      totalSteps,
      formData,
      updateFormData,
      goToStep,
      nextStep,
      prevStep,
      isFirstStep,
      isLastStep,
      isSubmitting,
      errors,
    ]
  );

  return (
    <MultiStepFormContext.Provider value={contextValue as MultiStepFormContextValue}>
      <div className={cn('space-y-6', className)}>
        {/* Progress Bar */}
        {showProgress && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">
                步骤 {currentStep + 1} / {totalSteps}
              </span>
              <span className="text-muted-foreground">
                {Math.round(progress)}% 完成
              </span>
            </div>
            <Progress value={progress} className="h-2" />
          </div>
        )}

        {/* Step Indicator */}
        {showStepIndicator && (
          <>
            {/* Desktop */}
            <div className="hidden md:block">
              <StepIndicator
                steps={steps}
                currentStep={currentStep}
                onStepClick={goToStep}
                allowNavigation={true}
              />
            </div>
            {/* Mobile */}
            <div className="md:hidden">
              <div className="text-center mb-2">
                <h3 className="font-medium">{steps[currentStep].title}</h3>
                {steps[currentStep].description && (
                  <p className="text-sm text-muted-foreground">
                    {steps[currentStep].description}
                  </p>
                )}
              </div>
              <CompactStepIndicator steps={steps} currentStep={currentStep} />
            </div>
          </>
        )}

        {/* Step Content */}
        <div className="min-h-[200px]">{children}</div>

        {/* Navigation Buttons */}
        <div className="flex items-center justify-between pt-4 border-t">
          <Button
            type="button"
            variant="outline"
            onClick={prevStep}
            disabled={isFirstStep || isSubmitting}
            className={cn(isFirstStep && 'invisible')}
          >
            <ChevronLeft className="w-4 h-4 mr-2" />
            {prevLabel}
          </Button>

          <div className="flex items-center gap-3">
            {allowSkip && !isLastStep && steps[currentStep].optional && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => goToStep(currentStep + 1)}
                disabled={isSubmitting}
              >
                跳过此步
              </Button>
            )}

            <Button
              type="button"
              onClick={nextStep}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  处理中...
                </>
              ) : isLastStep ? (
                submitLabel
              ) : (
                <>
                  {nextLabel}
                  <ChevronRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </MultiStepFormContext.Provider>
  );
}

// ==================== 表单字段辅助组件 ====================

interface FormFieldProps {
  name: string;
  label: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}

export function FormField({ name, label, required, children, className }: FormFieldProps) {
  const { errors } = useMultiStepForm();
  const error = errors[name];

  return (
    <div className={cn('space-y-2', className)}>
      <label className="text-sm font-medium">
        {label}
        {required && <span className="text-destructive ml-1">*</span>}
      </label>
      {children}
      {error && (
        <p className="text-sm text-destructive flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          {error}
        </p>
      )}
    </div>
  );
}

// ==================== 导出 ====================

export default MultiStepForm;