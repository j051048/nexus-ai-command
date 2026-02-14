import React from 'react';

interface IllustrationProps {
  className?: string;
}

/**
 * EmptyInboxIllustration - default type
 * An open empty inbox/box with decorative lines
 */
export function EmptyInboxIllustration({ className }: IllustrationProps) {
  return (
    <svg
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Background circle */}
      <circle cx="60" cy="60" r="50" fill="currentColor" opacity="0.06" />
      {/* Box body */}
      <rect
        x="30" y="50" width="60" height="35" rx="4"
        stroke="currentColor" strokeWidth="2.5" opacity="0.5"
      />
      {/* Box front flap - gives depth */}
      <path
        d="M30 50 L45 35 L75 35 L90 50"
        stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" opacity="0.7"
      />
      {/* Box left flap */}
      <path d="M30 50 L45 35" stroke="currentColor" strokeWidth="2.5" opacity="0.4" />
      {/* Box right flap */}
      <path d="M90 50 L75 35" stroke="currentColor" strokeWidth="2.5" opacity="0.4" />
      {/* Inner divider line */}
      <line x1="30" y1="60" x2="90" y2="60" stroke="currentColor" strokeWidth="1.5" opacity="0.2" />
      {/* Decorative floating lines - represent emptiness */}
      <line x1="50" y1="25" x2="55" y2="20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.25" />
      <line x1="60" y1="22" x2="60" y2="16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.2" />
      <line x1="70" y1="25" x2="65" y2="20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.25" />
      {/* Small dots for decoration */}
      <circle cx="45" cy="95" r="2" fill="currentColor" opacity="0.15" />
      <circle cx="75" cy="92" r="1.5" fill="currentColor" opacity="0.12" />
    </svg>
  );
}

/**
 * NoSearchResultsIllustration - search type
 * A magnifying glass with a question mark and scattered dots
 */
export function NoSearchResultsIllustration({ className }: IllustrationProps) {
  return (
    <svg
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Background circle */}
      <circle cx="60" cy="60" r="50" fill="currentColor" opacity="0.06" />
      {/* Magnifying glass circle */}
      <circle
        cx="52" cy="50" r="22"
        stroke="currentColor" strokeWidth="2.5" opacity="0.5"
      />
      {/* Magnifying glass handle */}
      <line
        x1="68" y1="66" x2="85" y2="83"
        stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity="0.6"
      />
      {/* Question mark inside the glass */}
      <path
        d="M46 43 C46 38 50 35 54 35 C58 35 61 38 61 42 C61 45 58 46 55 48 L55 52"
        stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.7"
      />
      {/* Question mark dot */}
      <circle cx="55" cy="58" r="1.8" fill="currentColor" opacity="0.7" />
      {/* Scattered dots around */}
      <circle cx="28" cy="35" r="2" fill="currentColor" opacity="0.15" />
      <circle cx="82" cy="38" r="1.5" fill="currentColor" opacity="0.12" />
      <circle cx="35" cy="78" r="1.5" fill="currentColor" opacity="0.1" />
      <circle cx="88" cy="55" r="2" fill="currentColor" opacity="0.15" />
      <circle cx="22" cy="60" r="1" fill="currentColor" opacity="0.1" />
      <circle cx="78" cy="25" r="1" fill="currentColor" opacity="0.1" />
    </svg>
  );
}

/**
 * ErrorIllustration - error type
 * A warning triangle with a lightning bolt
 */
export function ErrorIllustration({ className }: IllustrationProps) {
  return (
    <svg
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Background circle */}
      <circle cx="60" cy="60" r="50" fill="currentColor" opacity="0.06" />
      {/* Warning triangle */}
      <path
        d="M60 28 L88 80 L32 80 Z"
        stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" opacity="0.5"
      />
      {/* Exclamation line */}
      <line
        x1="60" y1="45" x2="60" y2="62"
        stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity="0.7"
      />
      {/* Exclamation dot */}
      <circle cx="60" cy="70" r="2" fill="currentColor" opacity="0.7" />
      {/* Lightning bolt next to triangle */}
      <path
        d="M82 35 L78 48 L83 48 L77 62"
        stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.35"
      />
      {/* Crack lines at bottom */}
      <line x1="40" y1="90" x2="50" y2="88" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.15" />
      <line x1="70" y1="88" x2="80" y2="90" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.15" />
      {/* Small alert dots */}
      <circle cx="35" cy="40" r="1.5" fill="currentColor" opacity="0.12" />
      <circle cx="92" cy="70" r="1.5" fill="currentColor" opacity="0.12" />
    </svg>
  );
}

/**
 * NoDataIllustration - no-data type
 * An empty folder with a small leaf (empty but alive)
 */
export function NoDataIllustration({ className }: IllustrationProps) {
  return (
    <svg
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Background circle */}
      <circle cx="60" cy="60" r="50" fill="currentColor" opacity="0.06" />
      {/* Folder back */}
      <path
        d="M28 42 L28 82 C28 84 30 86 32 86 L88 86 C90 86 92 84 92 82 L92 48 C92 46 90 44 88 44 L58 44 L52 36 L32 36 C30 36 28 38 28 40 Z"
        stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" opacity="0.5"
      />
      {/* Folder tab */}
      <path
        d="M28 42 L52 36"
        stroke="currentColor" strokeWidth="1.5" opacity="0.3"
      />
      {/* Inner line suggesting emptiness */}
      <line x1="40" y1="65" x2="80" y2="65" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.15" />
      <line x1="45" y1="72" x2="75" y2="72" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.1" />
      {/* Small leaf - sign of life */}
      <path
        d="M78 30 C78 30 82 22 90 20 C90 20 88 28 82 32"
        stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" opacity="0.35"
      />
      {/* Leaf vein */}
      <path
        d="M80 30 C83 26 86 23 89 21"
        stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.2"
      />
      {/* Stem */}
      <line x1="78" y1="30" x2="76" y2="36" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      {/* Dots */}
      <circle cx="35" cy="95" r="1.5" fill="currentColor" opacity="0.1" />
      <circle cx="85" cy="95" r="2" fill="currentColor" opacity="0.12" />
    </svg>
  );
}

/**
 * NoPermissionIllustration - no-permission type
 * A lock with a shield
 */
export function NoPermissionIllustration({ className }: IllustrationProps) {
  return (
    <svg
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Background circle */}
      <circle cx="60" cy="60" r="50" fill="currentColor" opacity="0.06" />
      {/* Shield shape */}
      <path
        d="M60 25 L85 38 L85 62 C85 75 72 88 60 95 C48 88 35 75 35 62 L35 38 Z"
        stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" opacity="0.4"
      />
      {/* Lock body */}
      <rect
        x="48" y="55" width="24" height="18" rx="3"
        stroke="currentColor" strokeWidth="2.5" opacity="0.6"
      />
      {/* Lock shackle */}
      <path
        d="M52 55 L52 47 C52 42 56 38 60 38 C64 38 68 42 68 47 L68 55"
        stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" opacity="0.5"
      />
      {/* Keyhole */}
      <circle cx="60" cy="63" r="2.5" fill="currentColor" opacity="0.6" />
      <path d="M60 65 L60 69" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
      {/* Decorative rays from shield */}
      <line x1="30" y1="30" x2="35" y2="35" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.15" />
      <line x1="90" y1="30" x2="85" y2="35" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.15" />
      {/* Dots */}
      <circle cx="25" cy="55" r="1.5" fill="currentColor" opacity="0.1" />
      <circle cx="95" cy="55" r="1.5" fill="currentColor" opacity="0.1" />
    </svg>
  );
}
