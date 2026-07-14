from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable


class QueryTimeoutError(TimeoutError):
    pass


@dataclass(frozen=True)
class QueryPolicy:
    min_interval_seconds: float = 3.0
    timeout_seconds: float = 75.0
    max_attempts: int = 2

    def __post_init__(self) -> None:
        if self.min_interval_seconds < 0:
            raise ValueError("单船司最小间隔不能小于 0")
        if self.timeout_seconds <= 0:
            raise ValueError("查询超时必须大于 0")
        if self.max_attempts <= 0:
            raise ValueError("最大尝试次数必须大于 0")


QueryRunner = Callable[[str, Callable[[str, object], object], str, object, float], object]


class QueryExecutor:
    """集中执行单柜查询，限制同船司频率并只重试可恢复故障。"""

    def __init__(
        self,
        *,
        runner: QueryRunner | None = None,
        use_subprocess: bool = True,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._runner = runner or (_run_with_subprocess_timeout if use_subprocess else _run_direct)
        self._clock = clock
        self._sleep = sleep
        self._last_started_at: dict[str, float] = {}

    def execute(
        self,
        carrier: str,
        adapter: Callable[[str, object], object],
        container: str,
        options: object,
        policy: QueryPolicy,
    ) -> tuple[object, dict[str, object]]:
        attempts = 0
        started_at = self._clock()
        for attempt in range(1, policy.max_attempts + 1):
            attempts = attempt
            self._respect_interval(carrier, policy.min_interval_seconds)
            self._last_started_at[carrier] = self._clock()
            try:
                result = self._runner(
                    carrier,
                    adapter,
                    container,
                    options,
                    policy.timeout_seconds,
                )
                return result, {
                    "attempts": attempts,
                    "timeout_seconds": policy.timeout_seconds,
                    "elapsed_seconds": round(self._clock() - started_at, 3),
                }
            except QueryTimeoutError as exc:
                if attempt == policy.max_attempts:
                    _attach_failure_metadata(exc, attempts, self._clock() - started_at)
                    raise
            except Exception as exc:
                if not _is_transient_error(exc) or attempt == policy.max_attempts:
                    _attach_failure_metadata(exc, attempts, self._clock() - started_at)
                    raise

        raise AssertionError("查询尝试流程不应到达这里")

    def _respect_interval(self, carrier: str, interval: float) -> None:
        last_started_at = self._last_started_at.get(carrier)
        if last_started_at is None:
            return
        remaining = interval - (self._clock() - last_started_at)
        if remaining > 0:
            self._sleep(remaining)


def _run_with_subprocess_timeout(
    carrier: str,
    adapter: Callable[[str, object], object],
    container: str,
    options: object,
    timeout_seconds: float,
) -> object:
    """由独立 Python 子进程执行 Provider；超时会终止浏览器或网络请求。"""
    del adapter
    command = [
        sys.executable,
        "-m",
        "trace_api_probe.worker",
        "--carrier",
        carrier,
        "--container",
        container,
        "--browser-channel",
        str(getattr(options, "browser_channel", "chromium")),
    ]
    if getattr(options, "headless", False):
        command.append("--headless")
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise QueryTimeoutError(f"查询超过 {timeout_seconds:g} 秒，已终止本次 Provider 进程") from exc
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or f"退出码: {completed.returncode}"
        raise RuntimeError(message)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Provider 子进程未返回有效 JSON") from exc


def _run_direct(
    carrier: str,
    adapter: Callable[[str, object], object],
    container: str,
    options: object,
    timeout_seconds: float,
) -> object:
    del carrier, timeout_seconds
    return adapter(container, options)


def _is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "timeout",
            "temporarily",
            "connection reset",
            "connection aborted",
            "连接失败",
            "无法连接",
            "查询超时",
            "未返回追踪结果",
            "未返回轨迹数据",
            "浏览器启动或页面访问失败",
            "http 429",
            "http 500",
            "http 502",
            "http 503",
            "http 504",
        )
    )


def _attach_failure_metadata(exc: BaseException | None, attempts: int, elapsed_seconds: float) -> None:
    if exc is None:
        return
    try:
        setattr(exc, "query_attempts", attempts)
        setattr(exc, "query_elapsed_seconds", round(elapsed_seconds, 3))
    except Exception:
        return
