from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trace_api_probe.carriers import Carrier, parse_carrier
from trace_api_probe.config import read_db_config
from trace_api_probe.db import ShipmentSample, fetch_latest_container
from trace_api_probe.providers import MissingCredentialError, provider_for


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从只读库取柜号并探测船司 Track & Trace API 原始返回")
    parser.add_argument("--carrier", required=True, help="试点船司: MAERSK / CMA_CGM / MSC，也可传数据库里的船司写法")
    parser.add_argument("--container", help="手动指定柜号；传入后不会从数据库取样本")
    parser.add_argument("--db-config", default="prod-db.yml", help="只读数据库配置文件路径，默认 prod-db.yml")
    args = parser.parse_args(argv)

    try:
        carrier = parse_carrier(args.carrier)
        sample = _resolve_sample(carrier, args.container, Path(args.db_config))
        print(_sample_message(carrier, sample), file=sys.stderr)

        raw = provider_for(carrier).fetch_raw(sample.container_no)
        print(json.dumps(raw, ensure_ascii=False, indent=2))
        return 0
    except MissingCredentialError as exc:
        print(f"无法调用 API：{exc}", file=sys.stderr)
        print("已停止：不会爬网页、不会伪造返回、不会写数据库。", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"执行失败：{exc}", file=sys.stderr)
        return 1


def _resolve_sample(carrier: Carrier, container_no: str | None, config_path: Path) -> ShipmentSample:
    if container_no:
        return ShipmentSample(
            id=0,
            shipping_company=carrier.value,
            container_no=container_no,
            update_time=None,
            create_time=None,
        )

    db_config = read_db_config(config_path)
    return fetch_latest_container(db_config, carrier)


def _sample_message(carrier: Carrier, sample: ShipmentSample) -> str:
    source = "命令行传入" if sample.id == 0 else f"只读库样本 id={sample.id}, shipping_company={sample.shipping_company}"
    return f"船司={carrier.value}, 柜号={sample.container_no}, 来源={source}"


if __name__ == "__main__":
    raise SystemExit(main())
