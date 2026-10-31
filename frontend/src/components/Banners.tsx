import { CircleX, Info, TriangleAlert, X } from 'lucide-react';

interface BannerProps {
  kind: 'error' | 'warning' | 'info';
  children: React.ReactNode;
  onDismiss?: () => void;
}

const ICONS = { error: CircleX, warning: TriangleAlert, info: Info } as const;

export function Banner({ kind, children, onDismiss }: BannerProps) {
  const Icon = ICONS[kind];
  return (
    <div className={`banner banner--${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <Icon size={16} aria-hidden="true" />
      <div className="banner__body">{children}</div>
      {onDismiss && (
        <button type="button" className="banner__close" onClick={onDismiss} aria-label="Dismiss">
          <X size={16} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

export function ResultsSkeleton() {
  return (
    <div className="skeleton-stack" aria-busy="true" aria-label="Loading results">
      <div className="skeleton skeleton--card" />
      <div className="skeleton skeleton--row" />
      <div className="skeleton skeleton--row" />
      <div className="skeleton skeleton--row" />
    </div>
  );
}
