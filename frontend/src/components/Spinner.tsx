interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  label?: string;
}

const SIZE = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-10 w-10" };

export function Spinner({ size = "md", label }: SpinnerProps) {
  return (
    <div className="flex flex-col items-center gap-2">
      <svg className={`${SIZE[size]} animate-spin text-blue-500`} viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
      {label && <span className="text-sm text-slate-400">{label}</span>}
    </div>
  );
}
