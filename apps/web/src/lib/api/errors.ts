/** Every failure the data layer can surface, kept explicit so screens can react to the cause. */
export type ApiFailure =
  | "unreachable"
  | "timeout"
  | "cancelled"
  | "not_found"
  | "invalid_request"
  | "backend_error"
  | "invalid_response";

export class ApiError extends Error {
  readonly failure: ApiFailure;
  readonly status?: number;

  constructor(failure: ApiFailure, message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.failure = failure;
    this.status = status;
  }
}

export function isCancellation(error: unknown) {
  return error instanceof ApiError && error.failure === "cancelled";
}

const MESSAGES: Record<ApiFailure, string> = {
  unreachable: "The API could not be reached.",
  timeout: "The API did not respond in time.",
  cancelled: "The request was cancelled.",
  not_found: "That record does not exist.",
  invalid_request: "The API rejected these filters.",
  backend_error: "The API reported an internal error.",
  invalid_response: "The API returned a response this client cannot read.",
};

/** Message shown to a person; never includes the backend URL or response body. */
export function describeFailure(error: unknown) {
  if (error instanceof ApiError) return MESSAGES[error.failure];
  return "Something went wrong while loading this view.";
}

export function failureFromStatus(status: number): ApiFailure {
  if (status === 404) return "not_found";
  if (status === 422 || status === 400) return "invalid_request";
  return "backend_error";
}
