import { AlertCircle, Loader2 } from "lucide-react";

export function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-line bg-white/95 px-5 py-4 text-sm font-semibold text-muted shadow-board">
      <Loader2 className="animate-spin text-accent" size={18} aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorBlock({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-red-200 bg-red-50 px-5 py-4 text-sm font-semibold text-red-800 shadow-board">
      <AlertCircle size={18} aria-hidden="true" />
      {message}
    </div>
  );
}
