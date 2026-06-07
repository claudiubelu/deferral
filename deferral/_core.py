# Copyright 2026 Claudiu Belu
#
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
import functools
import logging
import sys
from contextvars import ContextVar
from typing import Any, Callable, TypeVar, Union

if sys.version_info >= (3, 11):
    from builtins import BaseExceptionGroup
else:
    from exceptiongroup import BaseExceptionGroup

_logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])


class _Sentinel:
    def __init__(self, name: str) -> None:
        self._name = name

    def __repr__(self) -> str:
        return f"deferral.{self._name}"


def LOG(exc: BaseException) -> None:
    """Log the exception and continue running remaining deferred cleanups."""
    _logger.exception("deferral cleanup raised an exception", exc_info=exc)


def IGNORE(exc: BaseException) -> None:
    """Silently swallow the exception and continue running remaining deferred cleanups."""


RAISE = _Sentinel("RAISE")

ErrorHandler = Union[Callable[[BaseException], None], _Sentinel]

_default_error_handler: ErrorHandler = LOG

ExceptTypes = type[BaseException] | tuple[type[BaseException], ...]

# (cleanup_fn, args, kwargs, run_on_success, run_on_error, per_defer_on_error_override, ignore_exceptions)
_DeferEntry = tuple[
    Callable[..., Any],
    tuple[Any, ...],
    dict[str, Any],
    bool,
    bool,
    ErrorHandler | None,
    tuple[type[BaseException], ...],
]

_defer_stack: ContextVar[list[_DeferEntry] | None] = ContextVar(
    "_defer_stack", default=None
)


def set_default_error_handler(handler: ErrorHandler) -> None:
    """Set the module-level default error handler for deferred cleanups that raise."""
    global _default_error_handler
    _default_error_handler = handler


def _normalize_ignore(
    ignore_exceptions: ExceptTypes | None,
) -> tuple[type[BaseException], ...]:
    if ignore_exceptions is None:
        return ()

    if isinstance(ignore_exceptions, tuple):
        return ignore_exceptions

    return (ignore_exceptions,)


def _register(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    run_on_success: bool,
    run_on_error: bool,
    on_error: ErrorHandler | None,
    ignore_exceptions: tuple[type[BaseException], ...],
) -> None:
    stack = _defer_stack.get()
    if stack is None:
        raise RuntimeError("defer() called outside of a @deferred function")

    stack.append((
        fn,
        args,
        kwargs,
        run_on_success,
        run_on_error,
        on_error,
        ignore_exceptions,
    ))


def defer(
    fn: Callable[..., Any],
    *args: Any,
    on_error: ErrorHandler | None = None,
    ignore_exceptions: ExceptTypes | None = None,
    **kwargs: Any,
) -> None:
    """Schedule fn to run when the enclosing @deferred function exits, whether it succeeds or fails."""
    _register(
        fn, args, kwargs, True, True, on_error, _normalize_ignore(ignore_exceptions)
    )


def defer_on_error(
    fn: Callable[..., Any],
    *args: Any,
    on_error: ErrorHandler | None = None,
    ignore_exceptions: ExceptTypes | None = None,
    **kwargs: Any,
) -> None:
    """Schedule fn to run only if the enclosing @deferred function exits with an exception."""
    _register(
        fn, args, kwargs, False, True, on_error, _normalize_ignore(ignore_exceptions)
    )


def defer_on_success(
    fn: Callable[..., Any],
    *args: Any,
    on_error: ErrorHandler | None = None,
    ignore_exceptions: ExceptTypes | None = None,
    **kwargs: Any,
) -> None:
    """Schedule fn to run only if the enclosing @deferred function returns successfully."""
    _register(
        fn, args, kwargs, True, False, on_error, _normalize_ignore(ignore_exceptions)
    )


def _handle_cleanup_error(
    exc: BaseException,
    handler: ErrorHandler,
    raise_exceptions: list[BaseException],
) -> None:
    if isinstance(handler, _Sentinel):
        raise_exceptions.append(exc)
        return

    try:
        handler(exc)
    except BaseException as handler_exc:
        raise_exceptions.append(exc)
        raise_exceptions.append(handler_exc)


def _run_defers(
    entries: list[_DeferEntry],
    succeeded: bool,
    scope_handler: ErrorHandler,
) -> None:
    raise_exceptions: list[BaseException] = []

    for (
        fn,
        args,
        kwargs,
        run_on_success,
        run_on_error,
        per_defer_handler,
        ignore_exceptions,
    ) in reversed(entries):
        if (succeeded and not run_on_success) or (not succeeded and not run_on_error):
            continue

        handler = scope_handler
        if per_defer_handler is not None:
            handler = per_defer_handler

        try:
            fn(*args, **kwargs)
        except ignore_exceptions as exc:
            _logger.debug("deferral cleanup ignored expected exception", exc_info=exc)
        except BaseException as exc:
            _handle_cleanup_error(exc, handler, raise_exceptions)

    if not raise_exceptions:
        return

    if not succeeded:
        for deferred_exc in raise_exceptions:
            _logger.exception(
                "deferral cleanup raised an exception (body already failed)",
                exc_info=deferred_exc,
            )
        return

    if len(raise_exceptions) == 1:
        raise raise_exceptions[0]

    raise BaseExceptionGroup("deferred cleanups raised exceptions", raise_exceptions)


def deferred(
    fn: _F | None = None,
    *,
    on_error: ErrorHandler | None = None,
) -> _F | Callable[[_F], _F]:
    """Decorator that enables defer(), defer_on_error(), and defer_on_success() inside a function.

    Can be used with or without arguments:

        @deferred
        def fn(): ...

        @deferred(on_error=RAISE)
        def fn(): ...
    """

    def decorator(func: _F) -> _F:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                handler = on_error if on_error is not None else _default_error_handler
                entries: list[_DeferEntry] = []
                token = _defer_stack.set(entries)
                succeeded = False

                try:
                    result = await func(*args, **kwargs)
                    succeeded = True
                    return result
                finally:
                    _defer_stack.reset(token)
                    _run_defers(entries, succeeded, handler)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            handler = on_error if on_error is not None else _default_error_handler
            entries: list[_DeferEntry] = []
            token = _defer_stack.set(entries)
            succeeded = False

            try:
                result = func(*args, **kwargs)
                succeeded = True
                return result
            finally:
                _defer_stack.reset(token)
                _run_defers(entries, succeeded, handler)

        return wrapper  # type: ignore[return-value]

    if fn is not None:
        return decorator(fn)

    return decorator
