# deferral

[![Release](https://img.shields.io/github/v/release/claudiubelu/deferral)](https://img.shields.io/github/v/release/claudiubelu/deferral)
[![Build status](https://img.shields.io/github/actions/workflow/status/claudiubelu/deferral/main.yml?branch=main)](https://github.com/claudiubelu/deferral/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/claudiubelu/deferral/branch/main/graph/badge.svg)](https://codecov.io/gh/claudiubelu/deferral)
[![Commit activity](https://img.shields.io/github/commit-activity/m/claudiubelu/deferral)](https://img.shields.io/github/commit-activity/m/claudiubelu/deferral)
[![License](https://img.shields.io/github/license/claudiubelu/deferral)](https://img.shields.io/github/license/claudiubelu/deferral)

**Python's missing `defer`. Cleanup code where it belongs, right next to the resource that needs cleaning up.**

---

## Has this ever happened to you?

You crack open your Python project and the *Star Wars* opening crawl starts playing in your head, because the code is so deeply nested it looks *center-aligned*. Each `try/finally` block shunts your actual logic four more spaces to the right, until the function body is a thin column floating in the middle of the screen, and a long method genuinely resembles that yellow text drifting toward a galaxy far, far away... just like your sanity.

Does adding *one more* nesting level make your soul quietly leave the room? Do you need to wrap 200 lines of someone else's code in a `try/finally` for some small cleanup, but you dread inflating every `git blame` line with your name, for a change that adds *zero* logical value? Do you dread backporting bugfixes, because you *know* that the code shifted and indented so much that the merge conflict looks like a murder scene you have to now investigate?

Wouldn't it be preferable if some calls were **deferrable**?

```python
# before: your soul, slowly departing
def provision(name):
    conn = db.connect()
    try:
        lock = acquire_lock(name)
        try:
            tmp = tempfile.mkdtemp()
            try:
                result = do_work(conn, lock, tmp)
                notify_success(name)
                return result
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        finally:
            release_lock(lock)
    finally:
        conn.close()
```

```python
# after: your faith in humanity, gently returning
from deferral import deferred, defer, defer_on_success

@deferred
def provision(name):
    conn = db.connect()
    defer(conn.close)

    lock = acquire_lock(name)
    defer(release_lock, lock)

    tmp = tempfile.mkdtemp()
    defer(shutil.rmtree, tmp, ignore_errors=True)

    result = do_work(conn, lock, tmp)
    defer_on_success(notify_success, name)
    return result
```

Each cleanup lives *right next to the thing it cleans up*. No extra indentation. No restructuring the entire function. No phantom `git blame` entries. And when the function exits - success or failure - everything runs in reverse order, just like Go's `defer`.

---

## Installation

```bash
pip install deferral
```

Python 3.7 – 3.14. No dependencies on 3.11+; uses the [`exceptiongroup`](https://pypi.org/project/exceptiongroup/) backport on 3.7 – 3.10.

---

## Core API

### `@deferred` - the decorator

Wrap any function (sync or async) with `@deferred` to enable `defer()` calls inside it. Transparent: preserves the function's name, docstring, and signature.

```python
from deferral import deferred, defer

@deferred
def my_function():
    defer(print, "cleanup")
    print("work")
# prints: work, then cleanup
```

Can be used with arguments to configure the error handler for the whole scope:

```python
from deferral import deferred, RAISE

@deferred(on_error=RAISE)
def my_function():
    ...
```

---

### `defer(fn)` - always runs

Registers `fn` to run when the enclosing `@deferred` function exits, whether it succeeds or raises. Multiple calls run in **LIFO order** (last registered, first executed), just like `finally` blocks and Go's `defer`.

```python
@deferred
def setup():
    a = open_resource_a()
    defer(a.close)           # runs third

    b = open_resource_b()
    defer(b.close)           # runs second

    c = open_resource_c()
    defer(c.close)           # runs first
```

---

### `defer_on_error(fn)` - runs only on failure

Like Zig's `errdefer` or D's `scope(failure)`. The cleanup runs only if the function exits with an exception. Useful for rolling back partial state.

```python
@deferred
def create_user(name):
    user = db.insert_user(name)
    defer_on_error(db.delete_user, user.id)  # rollback on failure

    send_welcome_email(user)  # if this raises, the user is deleted
    return user               # if this returns, the user is kept
```

---

### `defer_on_success(fn)` - runs only on success

The mirror image, like D's `scope(success)`. Runs only when the function returns cleanly.

```python
@deferred
def complete_order(order_id):
    result = process_payment(order_id)
    defer_on_success(notify_warehouse, order_id)  # only if payment succeeded
    return result
```

---

### Mixing them all

All three variants share a single LIFO queue and interleave naturally:

```python
@deferred
def transfer_funds(src, dst, amount):
    tx = db.begin()
    defer(tx.close)  # always close the transaction

    debit(src, amount)
    defer_on_error(credit, src, amount)  # rollback debit on failure

    credit(dst, amount)
    defer_on_error(debit, dst, amount)   # rollback credit on failure

    defer_on_success(tx.commit)  # commit only on full success
```

---

## Further reading

Full API reference, error handling strategies, async and thread safety — **[claudiubelu.github.io/deferral](https://claudiubelu.github.io/deferral/)**.

---

## License

MIT. See [LICENSE](LICENSE).
