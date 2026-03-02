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
 * after new deployments. On final failure, triggers a page reload.
 */
export function lazyWithRetry<T extends ComponentType<unknown>>(
    factory: () => Promise<{ default: T }>,
    retries = 2
): React.LazyExoticComponent<T> {
    return React.lazy(() => retryImport(factory, retries));
}

async function retryImport<T>(
    factory: () => Promise<T>,
    retries: number
): Promise<T> {
    try {
        return await factory();
    } catch (error) {
        if (retries > 0) {
            // Wait briefly then retry
            await new Promise(r => setTimeout(r, 1000));
            return retryImport(factory, retries - 1);
        }
        // All retries failed — likely a new deployment, reload the page
        // Use a sessionStorage flag to prevent infinite reload loops
        const reloadKey = 'chunk-reload';
        const lastReload = sessionStorage.getItem(reloadKey);
        const now = Date.now();
        if (!lastReload || now - Number(lastReload) > 10000) {
            sessionStorage.setItem(reloadKey, String(now));
            window.location.reload();
        }
        throw error;
    }
}
