/**
 * P2 UX Enhancement: Language Selector
 * 语言选择器组件
 */

import React from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Globe, Check, ChevronDown } from 'lucide-react';
import { useTranslation, Locale, localeConfigs } from '@/lib/i18n';

// ==================== Dropdown 版本 ====================

interface LanguageSelectorDropdownProps {
  className?: string;
  showLabel?: boolean;
  align?: 'start' | 'center' | 'end';
}

export function LanguageSelectorDropdown({
  className,
  showLabel = false,
  align = 'end',
}: LanguageSelectorDropdownProps) {
  const { locale, setLocale, locales, t } = useTranslation();
  const currentLocale = localeConfigs[locale];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size={showLabel ? 'default' : 'icon'} className={className}>
          <Globe className="w-4 h-4" />
          {showLabel && (
            <>
              <span className="ml-2">{currentLocale.nativeName}</span>
              <ChevronDown className="w-4 h-4 ml-1" />
            </>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={align} className="w-48">
        <DropdownMenuLabel>{t('settings.language')}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {locales.map((loc) => (
          <DropdownMenuItem
            key={loc.code}
            onClick={() => setLocale(loc.code)}
            className="cursor-pointer"
          >
            <span className="mr-2 text-lg">{loc.flag}</span>
            <span className="flex-1">{loc.nativeName}</span>
            {locale === loc.code && <Check className="w-4 h-4 text-primary" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// ==================== Select 版本 ====================

interface LanguageSelectorSelectProps {
  className?: string;
  label?: string;
}

export function LanguageSelectorSelect({ className, label }: LanguageSelectorSelectProps) {
  const { locale, setLocale, locales } = useTranslation();

  return (
    <div className={cn('space-y-2', className)}>
      {label && <label className="text-sm font-medium">{label}</label>}
      <Select value={locale} onValueChange={(value) => setLocale(value as Locale)}>
        <SelectTrigger className="w-full">
          <SelectValue>
            <span className="flex items-center gap-2">
              <span className="text-lg">{localeConfigs[locale].flag}</span>
              <span>{localeConfigs[locale].nativeName}</span>
            </span>
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {locales.map((loc) => (
            <SelectItem key={loc.code} value={loc.code}>
              <span className="flex items-center gap-2">
                <span className="text-lg">{loc.flag}</span>
                <span>{loc.nativeName}</span>
                <span className="text-xs text-muted-foreground">({loc.name})</span>
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

// ==================== Inline 版本 ====================

interface LanguageSelectorInlineProps {
  className?: string;
}

export function LanguageSelectorInline({ className }: LanguageSelectorInlineProps) {
  const { locale, setLocale, locales } = useTranslation();

  return (
    <div className={cn('flex items-center gap-1', className)}>
      {locales.map((loc) => (
        <button
          key={loc.code}
          onClick={() => setLocale(loc.code)}
          className={cn(
            'px-2 py-1 text-sm rounded-md transition-all',
            locale === loc.code
              ? 'bg-primary text-primary-foreground'
              : 'hover:bg-muted text-muted-foreground hover:text-foreground'
          )}
        >
          <span className="mr-1">{loc.flag}</span>
          <span className="hidden sm:inline">{loc.code.split('-')[0].toUpperCase()}</span>
        </button>
      ))}
    </div>
  );
}

// ==================== 导出 ====================

export { LanguageSelectorDropdown as LanguageSelector };
export default LanguageSelectorDropdown;