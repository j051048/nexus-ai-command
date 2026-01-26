import React, { ComponentType, LazyExoticComponent, Suspense } from 'react';

// A factory that returns a Lazy component with an attached "preload" method
export function lazyWithPreload<T extends ComponentType<any>>(
    factory: () => Promise<{ default: T }>
): LazyExoticComponent<T> & { preload: () => Promise<{ default: T }> } {
    const Component = React.lazy(factory) as LazyExoticComponent<T> & { preload: unknown };
    Component.preload = factory;
    return Component as LazyExoticComponent<T> & { preload: () => Promise<{ default: T }> };
}

// Preload Helper for Sidebar
export const prefetchRoute = (component: { preload: () => Promise<any> }) => {
    if (component.preload) {
        component.preload();
    }
};
