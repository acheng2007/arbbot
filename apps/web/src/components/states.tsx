import { CircleAlert, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
export function LoadingState({
  label = "Loading workspace",
}: {
  label?: string;
}) {
  return (
    <div
      role="status"
      className="flex items-center gap-3 rounded-lg border border-border bg-card p-6 text-muted-foreground"
    >
      <LoaderCircle
        aria-hidden="true"
        className="size-5 motion-safe:animate-spin"
      />
      {label}
    </div>
  );
}
export function ErrorState({
  title = "Unable to load this view",
  description = "Please try again in a moment.",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-destructive/30 bg-card p-6"
    >
      <div className="flex items-center gap-3 text-destructive">
        <CircleAlert aria-hidden="true" className="size-5" />
        <h2 className="font-semibold">{title}</h2>
      </div>
      <p className="mt-3 text-sm text-muted-foreground">{description}</p>
      {onRetry && (
        <Button className="mt-5" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-lg border border-dashed border-border p-8">
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
        {description}
      </p>
    </div>
  );
}
export function StaleNotice({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="status"
      className="rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
    >
      {children}
    </p>
  );
}
