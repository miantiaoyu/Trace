import unittest

from trace_api_probe.execution import QueryExecutor, QueryPolicy, QueryTimeoutError


class QueryExecutorTests(unittest.TestCase):
    def test_retries_a_timeout_then_returns_result(self) -> None:
        attempts = []

        def runner(carrier, adapter, container, options, timeout_seconds):
            attempts.append((container, timeout_seconds))
            if len(attempts) == 1:
                raise QueryTimeoutError("查询超时")
            return {"container": container}

        executor = QueryExecutor(runner=runner, clock=lambda: 10.0, sleep=lambda seconds: None)

        result, metadata = executor.execute(
            carrier="YANG_MING",
            adapter=lambda container, options: {"container": container},
            container="YMMU7349033",
            options=object(),
            policy=QueryPolicy(min_interval_seconds=0, timeout_seconds=12, max_attempts=2),
        )

        self.assertEqual(result, {"container": "YMMU7349033"})
        self.assertEqual(metadata["attempts"], 2)
        self.assertEqual(attempts, [("YMMU7349033", 12), ("YMMU7349033", 12)])

    def test_does_not_retry_non_transient_failure(self) -> None:
        attempts = []

        def runner(carrier, adapter, container, options, timeout_seconds):
            attempts.append(container)
            raise RuntimeError("查询参数无效")

        executor = QueryExecutor(runner=runner, clock=lambda: 10.0, sleep=lambda seconds: None)

        with self.assertRaisesRegex(RuntimeError, "查询参数无效"):
            executor.execute(
                carrier="CMA_CGM",
                adapter=lambda container, options: None,
                container="CMAU4616180",
                options=object(),
                policy=QueryPolicy(min_interval_seconds=0, timeout_seconds=12, max_attempts=3),
            )

        self.assertEqual(attempts, ["CMAU4616180"])

    def test_waits_before_repeating_same_carrier(self) -> None:
        now = [0.0]
        sleeps = []

        def sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        executor = QueryExecutor(runner=lambda carrier, adapter, container, options, timeout: {"container": container}, clock=lambda: now[0], sleep=sleep)
        policy = QueryPolicy(min_interval_seconds=3, timeout_seconds=12, max_attempts=1)

        executor.execute("HMM", lambda container, options: None, "HMMU4706485", object(), policy)
        executor.execute("HMM", lambda container, options: None, "HMMU4706486", object(), policy)

        self.assertEqual(sleeps, [3])

    def test_retries_provider_chinese_timeout_message(self) -> None:
        attempts = []

        def runner(carrier, adapter, container, options, timeout_seconds):
            attempts.append(container)
            if len(attempts) == 1:
                raise RuntimeError("HMM 官网在 60 秒内未返回追踪结果")
            return {"container": container}

        executor = QueryExecutor(runner=runner, clock=lambda: 10.0, sleep=lambda seconds: None)
        result, metadata = executor.execute(
            "HMM",
            lambda container, options: None,
            "HMMU0000001",
            object(),
            QueryPolicy(min_interval_seconds=0, timeout_seconds=90, max_attempts=2),
        )

        self.assertEqual(result["container"], "HMMU0000001")
        self.assertEqual(metadata["attempts"], 2)

    def test_final_failure_contains_attempt_metadata(self) -> None:
        now = [0.0]

        def runner(carrier, adapter, container, options, timeout_seconds):
            now[0] += 2
            raise RuntimeError("连接失败")

        executor = QueryExecutor(runner=runner, clock=lambda: now[0], sleep=lambda seconds: None)

        with self.assertRaises(RuntimeError) as raised:
            executor.execute(
                "HMM",
                lambda container, options: None,
                "HMMU0000001",
                object(),
                QueryPolicy(min_interval_seconds=0, timeout_seconds=90, max_attempts=2),
            )

        self.assertEqual(raised.exception.query_attempts, 2)
        self.assertEqual(raised.exception.query_elapsed_seconds, 4)

    def test_retry_uses_exponential_backoff_jitter_and_rate_limit(self) -> None:
        attempts = []
        now = [0.0]
        sleeps = []

        def runner(carrier, adapter, container, options, timeout_seconds):
            attempts.append(container)
            if len(attempts) < 3:
                raise RuntimeError("连接失败")
            return {"container": container}

        def sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        executor = QueryExecutor(
            runner=runner,
            clock=lambda: now[0],
            sleep=sleep,
            random_value=lambda: 0.5,
        )
        policy = QueryPolicy(
            min_interval_seconds=3,
            timeout_seconds=10,
            max_attempts=3,
            backoff_base_seconds=2,
            backoff_max_seconds=10,
            jitter_seconds=2,
        )

        _, metadata = executor.execute("HMM", lambda container, options: None, "HMMU0000001", object(), policy)

        self.assertEqual(sleeps, [3, 5])
        self.assertEqual(metadata["retry_delays_seconds"], [3, 5])


if __name__ == "__main__":
    unittest.main()
