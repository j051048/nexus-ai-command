/**
 * Stable VMD hook facade.
 *
 * Domain hooks live in focused modules; this barrel preserves the existing
 * public import path so feature pages can migrate independently.
 */
export * from './vmd/clues';
export * from './vmd/dashboard';
export * from './vmd/models';
export * from './vmd/tasks';
export * from './vmd/types';
