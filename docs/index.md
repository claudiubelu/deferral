# deferral

**Python's missing `defer`. Cleanup code where it belongs, right next to the resource that needs cleaning up.**

For the full pitch and quick-start examples, see the [README](https://github.com/claudiubelu/deferral#readme).

## Navigation

- **[Error handling](error-handling.md)**: `LOG`, `IGNORE`, `RAISE`; custom handlers; per-scope and per-cleanup overrides; ignoring expected exceptions.
- **[Advanced](advanced.md)**: passing arguments to cleanups, async support, thread safety, comparison with Go's `defer`, and why `defer` beats nested `with` blocks.
- **[API reference](modules.md)**: full docstring reference for every public symbol.
