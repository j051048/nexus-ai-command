import { useEnhancedTheme } from '@/contexts/EnhancedThemeContext';

export const useChartTheme = () => {
  const { resolvedMode } = useEnhancedTheme();
  
  return {
    colors: resolvedMode === 'dark' 
      ? ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']
      : ['#7c3aed', '#0891b2', '#059669', '#d97706', '#dc2626'],
    grid: { stroke: resolvedMode === 'dark' ? '#374151' : '#e5e7eb' },
    text: { fill: resolvedMode === 'dark' ? '#9ca3af' : '#6b7280' },
  };
};
