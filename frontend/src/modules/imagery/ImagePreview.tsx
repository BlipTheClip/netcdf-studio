import { useState } from "react";
import { Spinner } from "@/components/Spinner";

interface ImagePreviewProps {
  path: string | null;
  loading?: boolean;
  error?: string | null;
  label?: string;
}

/** Convert an absolute OS path to a file:// URL usable in Electron's renderer. */
function toFileUrl(p: string): string {
  const fwd = p.replace(/\\/g, "/");
  // Windows absolute path: D:/foo → file:///D:/foo
  // Unix absolute path:    /foo   → file:///foo
  return fwd.match(/^[A-Za-z]:\//) ? `file:///${fwd}` : `file://${fwd}`;
}

export function ImagePreview({ path, loading = false, error = null, label }: ImagePreviewProps) {
  const [imgError, setImgError] = useState(false);

  // Reset img error when path changes
  const key = path ?? "empty";

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500">
        <Spinner size="lg" label="Rendering…" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-sm text-center space-y-2">
          <div className="text-3xl select-none">⚠</div>
          <p className="text-sm text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  if (!path) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-600 text-sm select-none">
        {label ?? "Configure the form and click Render to generate an image."}
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-start p-4 gap-2 overflow-auto">
      {imgError ? (
        <div className="text-center space-y-2">
          <div className="text-3xl select-none">🖼</div>
          <p className="text-sm text-red-400">Could not load image from disk.</p>
          <p className="text-xs text-slate-500 font-mono break-all">{path}</p>
        </div>
      ) : (
        <>
          <img
            key={key}
            src={toFileUrl(path)}
            alt="Rendered output"
            className="max-w-full rounded-lg shadow-lg border border-slate-700"
            onError={() => setImgError(true)}
            onLoad={() => setImgError(false)}
          />
          <p className="text-xs text-slate-500 font-mono break-all text-center">{path}</p>
        </>
      )}
    </div>
  );
}
