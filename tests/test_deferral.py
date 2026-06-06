# Copyright 2026 Claudiu Belu
#
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
import sys
import threading
from typing import Any
from unittest import mock

import testtools

import deferral
import deferral._core
from deferral._core import _defer_stack

if sys.version_info >= (3, 11):
    from builtins import BaseExceptionGroup
else:
    from exceptiongroup import BaseExceptionGroup


def _raise(exc: BaseException) -> None:
    raise exc


class DeferTests(testtools.TestCase):
    def test_defer_runs_on_success(self):
        calls: list[str] = []

        @deferral.deferred
        def fn() -> None:
            deferral.defer(lambda: calls.append("lish"))
            calls.append("foo")

        fn()

        self.assertEqual(["foo", "lish"], calls)

    def test_defer_runs_on_error(self):
        calls: list[str] = []

        @deferral.deferred
        def fn() -> None:
            deferral.defer(lambda: calls.append("delish"))
            raise Exception("al code still breaks sometimes")

        self.assertRaises(Exception, fn)
        self.assertEqual(["delish"], calls)

    def test_defer_lifo_order(self):
        calls: list[str] = []

        @deferral.deferred
        def fn() -> None:
            deferral.defer(lambda: calls.append("Dante"))
            deferral.defer(lambda: calls.append("ness"))
            calls.append("foo")
            deferral.defer(lambda: calls.append("lish"))

        fn()

        self.assertEqual(["foo", "lish", "ness", "Dante"], calls)

    def test_defer_outside_deferred_raises(self):
        self.assertRaises(RuntimeError, deferral.defer, lambda: None)

    def test_deferred_with_args(self):
        @deferral.deferred(on_error=deferral.IGNORE)
        def fn() -> str:
            return "foo"

        self.assertEqual("foo", fn())

    def test_defer_on_error_skipped_on_success(self):
        calls: list[str] = []

        @deferral.deferred
        def fn() -> None:
            deferral.defer_on_error(lambda: calls.append("lish"))

        fn()

        self.assertEqual([], calls)

    def test_defer_on_error_runs_on_error(self):
        calls: list[str] = []

        @deferral.deferred
        def fn() -> None:
            deferral.defer_on_error(lambda: calls.append("lish"))
            raise Exception("You thought it was a return, but it was me, Dio!")

        self.assertRaises(Exception, fn)
        self.assertEqual(["lish"], calls)

    def test_defer_on_success_runs_on_success(self):
        calls: list[str] = []

        @deferral.deferred
        def fn() -> None:
            deferral.defer_on_success(lambda: calls.append("lish"))

        fn()

        self.assertEqual(["lish"], calls)

    def test_defer_on_success_skipped_on_error(self):
        calls: list[str] = []

        @deferral.deferred
        def fn() -> None:
            deferral.defer_on_success(lambda: calls.append("lish"))
            raise Exception("al questions at work or school")

        self.assertRaises(Exception, fn)
        self.assertEqual([], calls)

    def test_all_defers_run_even_if_one_raises(self):
        calls: list[str] = []

        @deferral.deferred
        def fn() -> None:
            deferral.defer(lambda: calls.append("lish"))
            deferral.defer(lambda: calls.append("foo"))
            deferral.defer(lambda: _raise(Exception("the unexpected")))

        # the default exception handler on defer errorr is LOG, which swallows the
        # cleanup exception; fn completes normally.
        fn()

        self.assertEqual(["foo", "lish"], calls)

    def test_deferred_stack_cleared_after_call(self):
        @deferral.deferred
        def fn() -> None:
            deferral.defer(lambda: None)

        fn()

        self.assertIsNone(_defer_stack.get())

    def test_deferred_stack_cleared_after_error(self):
        @deferral.deferred
        def fn() -> None:
            deferral.defer(lambda: None)
            raise Exception("al coding practices")

        self.assertRaises(Exception, fn)
        self.assertIsNone(_defer_stack.get())

    def test_nested_deferred(self):
        outer_calls: list[str] = []
        inner_calls: list[str] = []

        @deferral.deferred
        def inner() -> None:
            deferral.defer(lambda: inner_calls.append("great"))
            deferral.defer(lambda: inner_calls.append("the"))

        @deferral.deferred
        def outer() -> None:
            deferral.defer(lambda: outer_calls.append("tender"))
            inner()
            deferral.defer(lambda: outer_calls.append("pre"))

        outer()

        self.assertEqual(["the", "great"], inner_calls)
        self.assertEqual(["pre", "tender"], outer_calls)

    def test_recursive_deferred(self):
        calls: list[int] = []

        @deferral.deferred
        def fn(n: int) -> None:
            deferral.defer(lambda: calls.append(-n))
            calls.append(n)

            if n > 0:
                fn(n - 1)

        fn(2)

        self.assertEqual([2, 1, 0, 0, -1, -2], calls)

    def test_deferred_preserves_return_value(self):
        @deferral.deferred
        def fn() -> str:
            deferral.defer(lambda: None)
            return "foo"

        self.assertEqual("foo", fn())

    def test_deferred_preserves_function_metadata(self):
        @deferral.deferred
        def the_world() -> None:  # ZA WARUDO
            """Stops time."""

        self.assertEqual("the_world", the_world.__name__)
        self.assertEqual("Stops time.", the_world.__doc__)

    def test_mixed_defer_types_lifo_order(self):
        calls: list[str] = []

        @deferral.deferred
        def fn() -> None:
            deferral.defer(lambda: calls.append("ploy"))
            deferral.defer_on_success(lambda: calls.append("lish"))
            deferral.defer(lambda: calls.append("foo"))
            deferral.defer_on_error(lambda: calls.append("what a"))

        fn()

        # defer_on_error skipped; rest run in reverse: foo, lish, ploy
        self.assertEqual(["foo", "lish", "ploy"], calls)


class AsyncDeferralTests(testtools.TestCase):
    def _run(self, coro: Any) -> Any:
        return asyncio.run(coro)

    def test_async_defer_runs_on_success(self):
        calls: list[str] = []

        @deferral.deferred
        async def fn() -> None:
            deferral.defer(lambda: calls.append("lish"))
            calls.append("foo")

        self._run(fn())
        self.assertEqual(["foo", "lish"], calls)

    def test_async_defer_runs_on_error(self):
        calls: list[str] = []

        @deferral.deferred
        async def fn() -> None:
            deferral.defer(lambda: calls.append("lish"))
            raise Exception("al code still breaks sometimes")

        self.assertRaises(Exception, self._run, fn())
        self.assertEqual(["lish"], calls)

    def test_async_defer_lifo_order(self):
        calls: list[str] = []

        @deferral.deferred
        async def fn() -> None:
            deferral.defer(lambda: calls.append("code"))
            deferral.defer(lambda: calls.append("lish"))
            deferral.defer(lambda: calls.append("foo"))

        self._run(fn())
        self.assertEqual(["foo", "lish", "code"], calls)

    def test_async_defer_on_error_skipped_on_success(self):
        calls: list[str] = []

        @deferral.deferred
        async def fn() -> None:
            deferral.defer_on_error(lambda: calls.append("lish"))

        self._run(fn())

        self.assertEqual([], calls)

    def test_async_defer_on_error_runs_on_error(self):
        calls: list[str] = []

        @deferral.deferred
        async def fn() -> None:
            deferral.defer_on_error(lambda: calls.append("lish"))
            raise Exception("You thought it was an await, but it was me, Dio!")

        self.assertRaises(Exception, self._run, fn())
        self.assertEqual(["lish"], calls)

    def test_async_defer_on_success_runs_on_success(self):
        calls: list[str] = []

        @deferral.deferred
        async def fn() -> None:
            deferral.defer_on_success(lambda: calls.append("lish"))

        self._run(fn())

        self.assertEqual(["lish"], calls)

    def test_async_defer_on_success_skipped_on_error(self):
        calls: list[str] = []

        @deferral.deferred
        async def fn() -> None:
            deferral.defer_on_success(lambda: calls.append("lish"))
            raise Exception("Async Dio strikes again!")

        self.assertRaises(Exception, self._run, fn())
        self.assertEqual([], calls)

    def test_async_all_defers_run_even_if_one_raises(self):
        calls: list[str] = []

        @deferral.deferred
        async def fn() -> None:
            deferral.defer(lambda: calls.append("lish"))
            deferral.defer(lambda: calls.append("foo"))
            deferral.defer(
                lambda: _raise(Exception("Nobody expects the Spanish Inquisition!"))
            )

        self._run(fn())

        self.assertEqual(["foo", "lish"], calls)

    def test_async_deferred_stack_cleared_after_call(self):
        @deferral.deferred
        async def fn() -> None:
            deferral.defer(lambda: None)

        self._run(fn())

        self.assertIsNone(_defer_stack.get())

    def test_async_deferred_stack_cleared_after_error(self):
        @deferral.deferred
        async def fn() -> None:
            deferral.defer(lambda: None)
            raise Exception("I've made a huge mistake.")

        self.assertRaises(Exception, self._run, fn())
        self.assertIsNone(_defer_stack.get())

    def test_async_nested_deferred(self):
        outer_calls: list[str] = []
        inner_calls: list[str] = []

        @deferral.deferred
        async def inner() -> None:
            deferral.defer(lambda: inner_calls.append("ender"))
            deferral.defer(lambda: inner_calls.append("bart"))

        @deferral.deferred
        async def outer() -> None:
            deferral.defer(lambda: outer_calls.append("tender"))
            await inner()
            deferral.defer(lambda: outer_calls.append("bar"))

        self._run(outer())

        self.assertEqual(["bart", "ender"], inner_calls)
        self.assertEqual(["bar", "tender"], outer_calls)

    def test_async_recursive_deferred(self):
        calls: list[int] = []

        @deferral.deferred
        async def fn(n: int) -> None:
            deferral.defer(lambda: calls.append(-n))
            calls.append(n)

            if n > 0:
                await fn(n - 1)

        self._run(fn(2))

        self.assertEqual([2, 1, 0, 0, -1, -2], calls)

    def test_async_mixed_defer_types_lifo_order(self):
        calls: list[str] = []

        @deferral.deferred
        async def fn() -> None:
            deferral.defer(lambda: calls.append("ploy"))
            deferral.defer_on_success(lambda: calls.append("lish"))
            deferral.defer(lambda: calls.append("foo"))
            deferral.defer_on_error(lambda: calls.append("what a"))

        self._run(fn())

        # defer_on_error skipped; rest run in reverse: foo, lish, ploy
        self.assertEqual(["foo", "lish", "ploy"], calls)


class ErrorHandlerTests(testtools.TestCase):
    def test_raise_handler_raises_after_all_defers_run(self):
        calls: list[str] = []

        @deferral.deferred
        def fn() -> None:
            deferral.defer_on_success(
                lambda: calls.append("lish"),
                on_error=deferral.RAISE,
            )
            deferral.defer(lambda: calls.append("foo"), on_error=deferral.RAISE)
            deferral.defer(
                lambda: _raise(Exception("I am inevitable.")),
                on_error=deferral.RAISE,
            )

        self.assertRaises(Exception, fn)

        # all three defers ran
        self.assertEqual(["foo", "lish"], calls)

    def test_raise_handler_multiple_failures_raises_exception_group(self):
        @deferral.deferred
        def fn() -> None:
            deferral.defer(
                lambda: _raise(Exception("You shall not pass!")),
                on_error=deferral.RAISE,
            )
            deferral.defer(
                lambda: _raise(Exception("One does not simply raise into Mordor.")),
                on_error=deferral.RAISE,
            )

        exc = self.assertRaises(BaseException, fn)

        self.assertIsInstance(exc, BaseExceptionGroup)

    def test_ignore_handler_swallows_exception(self):
        calls: list[str] = []

        @deferral.deferred
        def fn() -> None:
            deferral.defer(lambda: calls.append("foo"), on_error=deferral.IGNORE)
            deferral.defer(
                lambda: _raise(
                    Exception("These aren't the exceptions you're looking for."),
                ),
                on_error=deferral.IGNORE,
            )

        fn()

        self.assertEqual(["foo"], calls)

    def test_log_handler_logs_and_continues(self):
        @deferral.deferred
        def fn() -> None:
            deferral.defer(
                lambda: _raise(Exception("This is fine.")),
                on_error=deferral.LOG,
            )

        with mock.patch.object(deferral._core._logger, "exception") as mock_log:
            fn()  # should not raise
            mock_log.assert_called_once()

    def test_body_exception_propagates_when_defer_also_raises(self):
        @deferral.deferred
        def fn() -> None:
            deferral.defer(
                lambda: _raise(Exception("I'll be back.")),
                on_error=deferral.RAISE,
            )
            raise ValueError("the original sin")

        # The deferred exception should be logged.
        with mock.patch.object(deferral._core._logger, "exception") as mock_log:
            exc = self.assertRaises(ValueError, fn)

            self.assertEqual("the original sin", str(exc))
            mock_log.assert_called_once()

    def test_scope_level_error_handler(self):
        calls: list[str] = []

        @deferral.deferred(on_error=deferral.IGNORE)
        def fn() -> None:
            deferral.defer(lambda: calls.append("lish"), on_error=deferral.RAISE)
            deferral.defer(lambda: _raise(Exception("Winter is coming.")))

        # scope handler is IGNORE, so no raise
        fn()

        self.assertEqual(["lish"], calls)

    def test_per_defer_handler_overrides_scope_handler(self):
        @deferral.deferred(on_error=deferral.IGNORE)
        def fn() -> None:
            deferral.defer(
                lambda: _raise(Exception("I'm the captain now.")),
                on_error=deferral.RAISE,
            )

        self.assertRaises(Exception, fn)

    def test_broken_custom_handler_preserves_original_cleanup_exception(self):
        cleanup_exc = Exception("I am inevitable.")
        handler_exc = Exception("And I am Iron Man.")

        def broken_handler(exc: BaseException) -> None:
            raise handler_exc

        @deferral.deferred
        def fn() -> None:
            deferral.defer(
                lambda: _raise(cleanup_exc),
                on_error=broken_handler,
            )

        exc = self.assertRaises(BaseExceptionGroup, fn)

        self.assertIn(cleanup_exc, exc.exceptions)
        self.assertIn(handler_exc, exc.exceptions)

    def test_set_default_error_handler(self):
        original = deferral._core._default_error_handler
        try:
            deferral.set_default_error_handler(deferral.IGNORE)

            @deferral.deferred
            def fn() -> None:
                deferral.defer(lambda: _raise(Exception("Why so serious?")))

            # should not raise, new default is IGNORE
            fn()
        finally:
            deferral.set_default_error_handler(original)


class ThreadSafetyTests(testtools.TestCase):
    def test_threads_have_independent_defer_stacks(self):
        barrier = threading.Barrier(4)
        results: dict = {}

        @deferral.deferred
        def fn(thread_id: str) -> None:
            deferral.defer(lambda: results.update({thread_id: thread_id}))
            barrier.wait()  # all stacks live at the same time

        threads = [
            threading.Thread(target=fn, args=(tid,))
            for tid in ["foo", "lish", "bar", "tender"]
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(
            {"foo": "foo", "lish": "lish", "bar": "bar", "tender": "tender"}, results
        )

    def test_concurrent_deferred_calls_do_not_interfere(self):
        barrier = threading.Barrier(4)
        calls: list[str] = []
        lock = threading.Lock()

        @deferral.deferred
        def fn(value: str) -> None:
            def append() -> None:
                with lock:
                    calls.append(value)

            deferral.defer(lambda: None)  # register something
            barrier.wait()  # all threads reach this point before any returns
            deferral.defer(append)

        threads = [
            threading.Thread(target=fn, args=(v,))
            for v in ["foo", "lish", "bar", "tender"]
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sorted(["foo", "lish", "bar", "tender"]), sorted(calls))
