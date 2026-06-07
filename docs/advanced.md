# Advanced usage

## Passing arguments to cleanups

`defer`, `defer_on_error`, and `defer_on_success` forward positional and keyword arguments directly to the cleanup callable:

```python
@deferred
def build(src_dir, dst_dir):
    defer(shutil.copy2, src_dir, "/tmp/backup", follow_symlinks=False)
    defer(subprocess.run, ["make", "clean"], check=False, cwd=src_dir)
```

`on_error` and `ignore_exceptions` are keyword-only on `defer` itself and are never forwarded to the callable. If your cleanup function happens to have a parameter named `on_error` or `ignore_exceptions`, wrap it in a lambda:

```python
defer(lambda: my_cleanup(on_error=True))
```

## Async support

`@deferred` works on `async def` functions without any changes:

```python
@deferred
async def fetch_and_store(url):
    session = await create_session()
    defer(session.close)

    data = await session.get(url)
    defer_on_success(cache.store, url, data)
    return data
```

## Thread and async safety

Each thread and each asyncio task has its own independent defer stack, implemented via [`ContextVar`](https://docs.python.org/3/library/contextvars.html). Nested and recursive `@deferred` calls each get their own stack - `defer()` always targets the innermost decorated function.

```python
@deferred
def inner():
    defer(print, "inner cleanup")

@deferred
def outer():
    defer(print, "outer - runs last")
    inner()
    defer(print, "this runs before outer")
```

No locks. No globals. No surprises.

## Why not a context manager?

`with` is fine for resources that already implement `__enter__`/`__exit__`, and multiple resources can share a single level with the comma syntax. Where it breaks down:

- **Conditional cleanup.** There's no `with`-native equivalent of `defer_on_error` or `defer_on_success`. You end up with a flag variable and a `finally` block.
- **Cleanup that isn't a context manager.** Not every API gives you one. `defer` works with any callable.

`contextlib.ExitStack` covers all of these cases but at the cost of boilerplate. `defer` is the lighter path: one line, no nesting, no restructuring.

## Comparison with Go's `defer`

If you've used Go, this will feel familiar. The main differences:

| | Go `defer` | `deferral` |
|--|------------|------------|
| Scope | Always runs on function exit | `defer` / `defer_on_error` / `defer_on_success` |
| Cleanup errors | Ignored | Configurable: `LOG` / `IGNORE` / `RAISE` |
| Async | N/A | Full `async def` support |
| Thread safety | Goroutine-local | Thread- and task-local via `ContextVar` |
