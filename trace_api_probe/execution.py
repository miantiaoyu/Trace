from __future__ import annotations

import json
import queue
import random
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable


class QueryTimeoutError(TimeoutError):
    pass


class ProviderProcessError(RuntimeError):
    def __init__(self, message: str, *, provider_error_type: str | None = None) -> None:
        super().__init__(message)
        self.provider_error_type = provider_error_type
        self.provider_error_message = message


@dataclass(frozen=True)
class QueryPolicy:
    min_interval_seconds: float = 3.0
    timeout_seconds: float = 75.0
    max_attempts: int = 2
    backoff_base_seconds: float = 2.0
    backoff_max_seconds: float = 30.0
    jitter_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.min_interval_seconds < 0:
            raise ValueError("单船司最小间隔不能小于 0")
        if self.timeout_seconds <= 0:
            raise ValueError("查询超时必须大于 0")
        if self.max_attempts <= 0:
            raise ValueError("最大尝试次数必须大于 0")
        if self.backoff_base_seconds < 0 or self.backoff_max_seconds < 0 or self.jitter_seconds < 0:
            raise ValueError("退避和抖动参数不能小于 0")


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
        random_value: Callable[[], float] = random.random,
    ) -> None:
        self._worker_client = ProviderWorkerClient() if runner is None and use_subprocess else None
        self._runner = runner or (self._worker_client.run if self._worker_client else _run_direct)
        self._clock = clock
        self._sleep = sleep
        self._random_value = random_value
        self._last_started_at: dict[str, float] = {}

    def close_provider(self) -> None:
        if self._worker_client is not None:
            self._worker_client.close()

    def execute(
        self,
        carrier: str,
        adapter: Callable[[str, object], object],
        container: str,
        options: object,
        policy: QueryPolicy,
    ) -> tuple[object, dict[str, object]]:
        attempts = 0
        retry_delays: list[float] = []
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
                    "retry_delays_seconds": retry_delays,
                }
            except QueryTimeoutError as exc:
                if attempt == policy.max_attempts:
                    _attach_failure_metadata(exc, attempts, self._clock() - started_at, retry_delays)
                    raise
                retry_delays.append(self._wait_before_retry(carrier, attempt, policy))
            except Exception as exc:
                if not _is_transient_error(exc) or attempt == policy.max_attempts:
                    _attach_failure_metadata(exc, attempts, self._clock() - started_at, retry_delays)
                    raise
                retry_delays.append(self._wait_before_retry(carrier, attempt, policy))

        raise AssertionError("查询尝试流程不应到达这里")

    def _respect_interval(self, carrier: str, interval: float) -> None:
        last_started_at = self._last_started_at.get(carrier)
        if last_started_at is None:
            return
        remaining = interval - (self._clock() - last_started_at)
        if remaining > 0:
            self._sleep(remaining)

    def _wait_before_retry(self, carrier: str, attempt: int, policy: QueryPolicy) -> float:
        backoff = min(policy.backoff_base_seconds * (2 ** (attempt - 1)), policy.backoff_max_seconds)
        jitter = self._random_value() * policy.jitter_seconds
        last_started_at = self._last_started_at.get(carrier)
        interval_remaining = 0.0
        if last_started_at is not None:
            interval_remaining = max(0.0, policy.min_interval_seconds - (self._clock() - last_started_at))
        delay = max(interval_remaining, backoff + jitter)
        if delay > 0:
            self._sleep(delay)
        return round(delay, 3)


class ProviderWorkerClient:
    """同一船司复用一个 Provider 子进程，同时保留单柜硬超时。"""

    def __init__(
        self,
        *,
        popen_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
    ) -> None:
        self._popen_factory = popen_factory
        self._process: subprocess.Popen[str] | None = None
        self._worker_key: tuple[str, bool, str] | None = None

    def run(
        self,
        carrier: str,
        adapter: Callable[[str, object], object],
        container: str,
        options: object,
        timeout_seconds: float,
    ) -> object:
        del adapter
        key = (
            carrier,
            bool(getattr(options, "headless", False)),
            str(getattr(options, "browser_channel", "chromium")),
        )
        self._ensure_worker(key)
        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise RuntimeError("Provider 子进程未正确启动")

        try:
            process.stdin.write(json.dumps({"container": container}, ensure_ascii=False) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            details = self._worker_details()
            self.close()
            raise RuntimeError(f"Provider 子进程连接已断开: {details}") from exc

        response_queue: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)

        def read_response() -> None:
            try:
                response_queue.put(process.stdout.readline())
            except BaseException as exc:  # pragma: no cover - defensive pipe handling
                response_queue.put(exc)

        threading.Thread(target=read_response, daemon=True).start()
        try:
            response = response_queue.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            self.close()
            raise QueryTimeoutError(f"查询超过 {timeout_seconds:g} 秒，已终止本次 Provider 进程") from exc

        if isinstance(response, BaseException):
            self.close()
            raise RuntimeError(f"读取 Provider 子进程响应失败: {response}") from response
        if not response:
            details = self._worker_details()
            self.close()
            raise RuntimeError(f"Provider 子进程提前退出: {details}")
        try:
            payload = json.loads(response)
        except json.JSONDecodeError as exc:
            self.close()
            raise RuntimeError(f"Provider 子进程未返回有效 JSON: {response[:300]}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Provider 子进程响应不是 JSON 对象")
        if payload.get("ok") is True:
            return payload.get("result")
        error_type = str(payload.get("error_type") or "") or None
        message = str(payload.get("message") or "Provider 查询失败")
        raise ProviderProcessError(message, provider_error_type=error_type)

    def close(self) -> None:
        process = self._process
        self._process = None
        self._worker_key = None
        if process is None:
            return
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def _ensure_worker(self, key: tuple[str, bool, str]) -> None:
        if self._process is not None and self._process.poll() is None and self._worker_key == key:
            return
        self.close()
        carrier, headless, browser_channel = key
        command = [
            sys.executable,
            "-m",
            "trace_api_probe.worker",
            "--serve",
            "--carrier",
            carrier,
            "--browser-channel",
            browser_channel,
        ]
        if headless:
            command.append("--headless")
        self._process = self._popen_factory(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._worker_key = key

    def _worker_details(self) -> str:
        process = self._process
        if process is None:
            return "进程不存在"
        if process.poll() is None or process.stderr is None:
            return "进程仍在运行但未返回结果"
        return process.stderr.read().strip() or f"退出码 {process.returncode}"


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


def _attach_failure_metadata(
    exc: BaseException | None,
    attempts: int,
    elapsed_seconds: float,
    retry_delays: list[float],
) -> None:
    if exc is None:
        return
    try:
        setattr(exc, "query_attempts", attempts)
        setattr(exc, "query_elapsed_seconds", round(elapsed_seconds, 3))
        setattr(exc, "query_retry_delays_seconds", retry_delays)
    except Exception:
        return


def _parse_worker_error(raw_message: str) -> tuple[str | None, str]:
    message = raw_message.strip()
    first_line = next((line.strip() for line in message.splitlines() if line.strip()), "")
    match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):\s*(.*)$", first_line)
    if not match:
        return None, message
    error_type = match.group(1)
    detail = match.group(2).strip()
    return error_type, detail or message
