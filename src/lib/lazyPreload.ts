import React, { ComponentType, LazyExoticComponent, Suspense } from 'react';

// Lazy component type with optional preload method
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type PreloadableLazy<T extends ComponentType<any>> =
    LazyExoticComponent<T> & { preload: () => Promise<void> };

// A factory that returns a Lazy component with an attached "preload" method
export function lazyWithPreload<T extends ComponentType<unknown>>(
    factory: () => Promise<{ default: T }>
): PreloadableLazy<T> {
    const Component = React.lazy(factory) as PreloadableLazy<T>;
    Component.preload = () => factory().then(() => {});
    return Component;
}

// Preload Helper for Sidebar — accepts any component with a preload method
export const prefetchRoute = (component: { preload?: () => Promise<unknown> }) => {
    component.preload?.();
};

/**
 * Wraps a dynamic import with retry logic for handling chunk load failures
 * after new deployments. On final failure, triggers a page reload by default.
 * Also exposes a `.preload()` method for eager loading on hover.
 *
 * @param reloadOnFailure - Set to false for non-critical components (e.g. GenUI)
 *   where a page reload would be disruptive. The error will still be thrown and
 *   can be caught by a React ErrorBoundary.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function lazyWithRetry<T extends ComponentType<any>>(
    factory: () => Promise<{ default: T }>,
    retries = 2,
    reloadOnFailure = true
): PreloadableLazy<T> {
    const Component = React.lazy(() => retryImport(factory, retries, reloadOnFailure)) as PreloadableLazy<T>;
    // preload calls factory directly (no retry needed for preload — it's best-effort)
    Component.preload = () => factory().then(() => {});
    return Component;
}

async function retryImport<T>(
    factory: () => Promise<T>,
    retries: number,
    reloadOnFailure: boolean
): Promise<T> {
    try {
        return await factory();
    } catch (error) {
        if (retries > 0) {
            // Wait briefly then retry
            await new Promise(r => setTimeout(r, 1000));
            return retryImport(factory, retries - 1, reloadOnFailure);
        }
        // All retries failed — reload only if enabled (route-level components)
        if (reloadOnFailure) {
            triggerReload();
        }

        // Attach a custom flag to the error to help ErrorBoundaries distinguish it
        (error as any).isChunkLoadError = true;
        throw error;
    }
}

function triggerReload() {
    // Use a sessionStorage flag to prevent infinite reload loops
    const reloadKey = 'chunk-reload';
    const lastReload = sessionStorage.getItem(reloadKey);
    const now = Date.now();
    if (!lastReload || now - Number(lastReload) > 10000) {
        sessionStorage.setItem(reloadKey, String(now));
        window.location.reload();
    }
}
