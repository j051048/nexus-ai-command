export const tokens = {
  shadow: {
    sm: 'var(--shadow-card)',
    DEFAULT: 'var(--shadow-card)',
    md: 'var(--shadow-card)',
    lg: 'var(--shadow-elevated)',
    xl: 'var(--shadow-elevated)',
    /** @deprecated Compatibility only. New surfaces must use elevation. */
    glow: 'var(--shadow-card)',
  },
  transition: {
    fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
    base: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
    slow: '300ms cubic-bezier(0.4, 0, 0.2, 1)',
  },
  zIndex: {
    dropdown: 1000,
    sticky: 1020,
    fixed: 1030,
    modalBackdrop: 1040,
    modal: 1050,
    popover: 1060,
    tooltip: 1070,
  }
};
