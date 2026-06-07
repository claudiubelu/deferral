# Error handling

When a cleanup itself raises, `deferral` gives you three built-in strategies, mixable per scope or per cleanup.

| Handler | Behaviour |
|---------|-----------|
| `LOG` *(default)* | Log the exception, swallow it, continue running remaining cleanups. |
| `IGNORE` | Silently swallow. Useful for best-effort cleanups where errors are expected. |
| `RAISE` | Collect the exception; after all cleanups run, re-raise it. Multiple failures become a `BaseExceptionGroup`. |

## Scope-level vs per-cleanup

Set the handler once on the decorator to apply it to every cleanup in that function, then override per cleanup as needed:

```python
from deferral import defer_scope, defer, IGNORE, RAISE

# scope-level: all cleanups in this function default to RAISE
@defer_scope(on_error=RAISE)
def strict_setup():
    defer(must_not_fail)
    defer(also_must_not_fail)

# per-cleanup override: one cleanup is exempt, others inherit the scope default
@defer_scope(on_error=RAISE)
def mixed_setup():
    defer(must_succeed, on_error=RAISE)
    defer(best_effort, on_error=IGNORE)   # allowed to fail silently
```

**Key guarantee:** if the function body raises *and* a cleanup also raises, the body exception always propagates. Cleanup exceptions in that case are logged regardless of their handler. Your original error is never silently swapped out.

## Ignoring expected exceptions

For cleanups that routinely raise predictable exceptions (e.g., "already deleted"), use `ignore_exceptions`:

```python
@defer_scope
def cleanup_temp_file(path):
    defer(os.remove, path, ignore_exceptions=FileNotFoundError)  # idempotent; fine if already gone
```

Accepts a single exception type or a tuple of types, same as `except`.

## Custom error handlers

Any callable that takes a `BaseException` and returns `None` works as a handler. Use this to plug into your own error tracking:

```python
import sentry_sdk
from deferral import defer_scope, defer

def report_and_swallow(exc: BaseException) -> None:
    sentry_sdk.capture_exception(exc)

@defer_scope(on_error=report_and_swallow)
def deploy():
    defer(teardown_blue_env)
    defer(close_tunnel)
```

Per-cleanup overrides accept custom handlers too:

```python
@defer_scope
def process():
    defer(noisy_cleanup, on_error=report_and_swallow)
    defer(quiet_cleanup, on_error=deferral.IGNORE)
```

If the handler itself raises, both the original cleanup exception and the handler exception are collected and re-raised as a `BaseExceptionGroup`.

`ErrorHandler` and `ExceptTypes` are exported for type annotations:

```python
from deferral import ErrorHandler, ExceptTypes

def my_handler(exc: BaseException) -> None: ...       # ErrorHandler
ignore: ExceptTypes = (FileNotFoundError, OSError)    # ExceptTypes
```

## Changing the global default

```python
from deferral import set_default_error_handler, RAISE

set_default_error_handler(RAISE)  # strictest mode for the whole process
```
