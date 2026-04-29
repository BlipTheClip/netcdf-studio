import type { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

const VARIANT: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:   "bg-blue-600 hover:bg-blue-700 text-white disabled:bg-blue-800/60",
  secondary: "bg-slate-700 hover:bg-slate-600 text-slate-100 disabled:bg-slate-800",
  danger:    "bg-red-700 hover:bg-red-600 text-white disabled:bg-red-900",
  ghost:     "bg-transparent hover:bg-slate-700 text-slate-300 disabled:text-slate-600",
};

const SIZE: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-base",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={`
        inline-flex items-center gap-2 rounded-md font-medium transition-colors
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-slate-900
        disabled:cursor-not-allowed
        ${VARIANT[variant]} ${SIZE[size]} ${className}
      `}
      {...props}
    >
      {loading && (
        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
      )}
      {children}
    </button>
  );
}
