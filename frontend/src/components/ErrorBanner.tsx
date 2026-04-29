interface ErrorBannerProps {
  message: string;
  detail?: string;
  onDismiss?: () => void;
}

export function ErrorBanner({ message, detail, onDismiss }: ErrorBannerProps) {
  return (
    <div className="rounded-md bg-red-950 border border-red-800 p-3 flex items-start gap-3">
      <svg className="h-5 w-5 text-red-400 shrink-0 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
      </svg>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-red-300">{message}</p>
        {detail && (
          <p className="text-xs text-red-400 mt-0.5 break-all font-mono">{detail}</p>
        )}
      </div>

      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-red-400 hover:text-red-200 shrink-0 transition-colors"
          aria-label="Dismiss"
        >
          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
          </svg>
        </button>
      )}
    </div>
  );
}
