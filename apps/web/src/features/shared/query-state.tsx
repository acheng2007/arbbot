"use client";
import type { ReactNode } from "react";
import { describeFailure } from "@/lib/api/errors";
import { ErrorState, LoadingState } from "@/components/states";

type Props = {
  isPending: boolean;
  error: unknown;
  loadingLabel: string;
  onRetry?: () => void;
  children: ReactNode;
};

/**
 * Renders loading and failure states consistently. Nothing partial is shown
 * during a failure, so a stale success view can never be mistaken for current
 * data.
 */
export function QueryState({
  isPending,
  error,
  loadingLabel,
  onRetry,
  children,
}: Props) {
  if (error)
    return (
      <ErrorState
        title="This view could not be loaded"
        description={describeFailure(error)}
        onRetry={onRetry}
      />
    );
  if (isPending) return <LoadingState label={loadingLabel} />;
  return <>{children}</>;
}
