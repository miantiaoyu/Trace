from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from trace_api_probe.carriers import Carrier, parse_carrier
from trace_api_probe.config import read_db_config
from trace_api_probe.db import ShipmentSample, fetch_pending_shipments, fetch_recent_shipments
from trace_api_probe.headway import persist_headway
from trace_api_probe.result_status import PARTIAL_STATUSES, SKIPPED_STATUSES, SUCCESS_STATUSES
from trace_api_probe.runtime import DetailRecorder, RunLock, RunRecorder
from trace_api_probe.tracking import TrackingOptions, query_samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从只读库读取最近订单并按船司查询柜号轨迹")
    parser.add_argument("--carrier", help="只查询指定船司；不传则查询最近订单中的全部船司")
    parser.add_argument("--container", help="手动指定柜号；必须同时传 --carrier")
    parser.add_argument(
        "--environment",
        choices=("test", "prod"),
        default=None,
        help="运行环境，默认读取 TRACE_ENV 或 prod；用于选择 test-db.yml/prod-db.yml",
    )
    parser.add_argument("--db-config", help="只读数据库配置文件路径；传入后优先于环境默认路径")
    parser.add_argument("--days", type=_positive_int, default=7, help="查询最近多少天，默认 7")
    parser.add_argument(
        "--limit",
        type=_nonnegative_int,
        default=20,
        help="最多查询多少个去重柜号，默认 20；传 0 表示不限制",
    )
    parser.add_argument("--headless", action="store_true", help="网页路线使用无界面浏览器")
    parser.add_argument(
        "--browser-channel",
        choices=("chromium", "msedge"),
        default="chromium",
        help="网页路线使用的浏览器通道，默认 chromium",
    )
    parser.add_argument("--timeout-seconds", type=_positive_float, help="覆盖船司默认查询超时，单位秒")
    parser.add_argument("--max-attempts", type=_positive_int, help="覆盖船司默认最大尝试次数")
    parser.add_argument("--min-interval-seconds", type=_nonnegative_float, help="覆盖船司默认最小访问间隔，单位秒")
    parser.add_argument("--lock-file", default=".trace-api-probe.lock", help="防止定时任务重叠的锁文件路径")
    parser.add_argument("--lock-timeout-seconds", type=_nonnegative_float, default=0, help="等待任务锁的秒数，默认立即失败")
    parser.add_argument("--run-log", help="可选的脱敏 JSONL 运行日志路径")
    parser.add_argument("--detail-log", help="可选的逐条诊断 JSONL 日志路径；不保存 raw 原始响应")
    parser.add_argument("--health-state", help="可选的船司连续失败状态文件路径")
    parser.add_argument("--alert-threshold", type=_positive_int, default=3, help="连续多少轮无成功结果后告警，默认 3")
    parser.add_argument("--summary-only", action="store_true", help="只输出脱敏查询汇总，不输出柜号和 raw 原始响应")
    parser.add_argument("--persist", action="store_true", help="将最新查询快照写入 oms.headway")
    args = parser.parse_args(argv)
    environment = args.environment or os.environ.get("TRACE_ENV", "prod")
    if environment not in {"test", "prod"}:
        parser.error("TRACE_ENV 必须是 test 或 prod")
    config_path = Path(args.db_config) if args.db_config else Path(f"{environment}-db.yml")

    try:
        with RunLock(Path(args.lock_file), timeout_seconds=args.lock_timeout_seconds):
            carrier = parse_carrier(args.carrier) if args.carrier else None
            samples = _resolve_samples(
                carrier=carrier,
                container_no=args.container,
                config_path=config_path,
                environment=environment,
                persist=args.persist,
                days=args.days,
                limit=args.limit,
            )
            report = _build_report(
                samples=samples,
                days=args.days,
                limit=args.limit,
                carrier=carrier,
                environment=environment,
                persist=args.persist,
                options=TrackingOptions(
                    headless=args.headless,
                    browser_channel=args.browser_channel,
                    timeout_seconds=args.timeout_seconds,
                    max_attempts=args.max_attempts,
                    min_interval_seconds=args.min_interval_seconds,
                ),
            )
            recorder = RunRecorder(
                log_path=Path(args.run_log) if args.run_log else None,
                health_state_path=Path(args.health_state) if args.health_state else None,
                alert_threshold=args.alert_threshold,
            )
            report["alerts"] = recorder.record(report)
            if args.persist:
                report["persistence"] = persist_headway(
                    read_db_config(config_path),
                    environment=environment,
                    samples=samples,
                    results=report["results"],
                )
            DetailRecorder(log_path=Path(args.detail_log) if args.detail_log else None).record(
                report,
                samples=samples,
                persist=args.persist,
            )
            for alert in report["alerts"]:
                print(f"告警：{alert['message']}", file=sys.stderr)
        _print_json(report, summary_only=args.summary_only)
        return 0 if report["summary"]["failed"] == 0 and report["summary"]["partial"] == 0 else 1
    except Exception as exc:
        print(f"执行失败：{exc}", file=sys.stderr)
        return 1


def _resolve_samples(
    *,
    carrier: Carrier | None,
    container_no: str | None,
    config_path: Path,
    environment: str,
    persist: bool,
    days: int,
    limit: int,
) -> list[ShipmentSample]:
    if container_no and not carrier:
        raise ValueError("手动指定柜号时必须同时传 --carrier")
    if container_no:
        return [
            ShipmentSample(
            id=0,
            shipping_company=carrier.value,
            container_no=container_no,
            update_time=None,
            create_time=None,
            )
        ]

    db_config = read_db_config(config_path)
    if persist:
        return fetch_pending_shipments(db_config, environment=environment, days=days, carrier=carrier, limit=limit)
    return fetch_recent_shipments(db_config, days=days, carrier=carrier, limit=limit)


def _build_report(
    *,
    samples: list[ShipmentSample],
    days: int,
    limit: int,
    carrier: Carrier | None,
    options: TrackingOptions,
    environment: str = "prod",
    persist: bool = False,
) -> dict[str, object]:
    results = query_samples(samples, options=options)
    success = sum(result["status"] in SUCCESS_STATUSES for result in results)
    partial = sum(result["status"] in PARTIAL_STATUSES for result in results)
    skipped = sum(result["status"] in SKIPPED_STATUSES for result in results)
    failed = len(results) - success - partial - skipped
    return {
        "query": {
            "source": "trobs.po_cabinet_combination",
            "read_only": not persist,
            "persist": persist,
            "days": days,
            "limit": limit,
            "carrier": carrier.value if carrier else None,
            "environment": environment,
            "count": len(samples),
        },
        "summary": {
            "total": len(results),
            "success": success,
            "partial": partial,
            "skipped": skipped,
            "failed": failed,
        },
        "results": results,
    }


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是大于 0 的整数")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("必须是大于等于 0 的整数")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是大于 0 的数字")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("必须是大于等于 0 的数字")
    return parsed


def _print_json(value: object, *, summary_only: bool = False) -> None:
    if summary_only and isinstance(value, dict):
        value = {
            "query": value.get("query", {}),
            "summary": value.get("summary", {}),
            "alerts": value.get("alerts", []),
            "persistence": value.get("persistence", {}),
        }
    payload = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")


if __name__ == "__main__":
    raise SystemExit(main())
