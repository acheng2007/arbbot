from datetime import datetime
from typing import Protocol

from pydantic import TypeAdapter

from arbbot.fees.models import FeeRequest, FeeResult, FeeUnavailable


class FeeProvider(Protocol):
    async def quote(self, request: FeeRequest, *, as_of: datetime) -> FeeResult:
        """Return an explicit unavailable result when policy is unsupported or stale."""
        ...


async def quote_fees(
    provider: FeeProvider | None, request: FeeRequest, *, as_of: datetime
) -> FeeResult:
    """Validate provider boundaries; failures never become an implicit zero fee."""
    request = FeeRequest.model_validate(request)
    unavailable = FeeUnavailable(request=request, as_of=as_of, reason="unsupported")
    if provider is None:
        return unavailable
    try:
        result = await provider.quote(request, as_of=as_of)
    except Exception:
        # Raw provider exceptions may contain credentials or response bodies.
        # Cancellation is a BaseException and deliberately propagates.
        return FeeUnavailable(request=request, as_of=as_of, reason="provider_error")
    try:
        result = TypeAdapter(FeeResult).validate_python(result)
        if result.request != request or result.as_of != as_of:
            raise ValueError("Fee quote is bound to a different request or time")
    except (ValueError, TypeError):
        return FeeUnavailable(request=request, as_of=as_of, reason="invalid_quote")
    return result
