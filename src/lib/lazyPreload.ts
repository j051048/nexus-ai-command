import React, { ComponentType, LazyExoticComponent, Suspense } from 'react';

// A factory that returns a Lazy component with an attached "preload" method
export function lazyWithPreload<T extends ComponentType<unknown>>(
    factory: () => Promise<{ default: T }>
): LazyExoticComponent<T> & { preload: () => Promise<{ default: T }> } {
    const Component = React.lazy(factory) as LazyExoticComponent<T> & { preload: unknown };
    Component.preload = factory;
    return Component as LazyExoticComponent<T> & { preload: () => Promise<{ default: T }> };
}

// Preload Helper for Sidebar
export const prefetchRoute = (component: { preload: () => Promise<unknown> }) => {
    if (component.preload) {
        component.preload();
    }
};

/**
 * Wraps a dynamic import with retry logic for handling chunk load failures
 * after new deployments. On final failure, triggers a page reload by default.
 *
 * @param reloadOnFailure - Set to false for non-critical components (e.g. GenUI)
 *   where a page reload would be disruptive. The error will still be thrown and
 *   can be caught by a React ErrorBoundary.
 */
export function lazyWithRetry<T extends ComponentType<unknown>>(
    factory: () => Promise<{ default: T }>,
    retries = 2,
    reloadOnFailure = true
): React.LazyExoticComponent<T> {
    return React.lazy(() => retryImport(factory, retries, reloadOnFailure));
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
            // Use a sessionStorage flag to prevent infinite reload loops
            const reloadKey = 'chunk-reload';
            const lastReload = sessionStorage.getItem(reloadKey);
            const now = Date.now();
            if (!lastReload || now - Number(lastReload) > 10000) {
                sessionStorage.setItem(reloadKey, String(now));
                window.location.reload();
            }
        }
        throw error;
    }
}
