from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from trace_api_probe.carriers import Carrier, normalize_carrier
from trace_api_probe.container_numbers import normalize_container_number
from trace_api_probe.db import ShipmentSample
from trace_api_probe.execution import QueryExecutor, QueryPolicy
from trace_api_probe.normalization import empty_tracking_summary, normalize_tracking


class UnsupportedTrackingError(RuntimeError):
    """船司已识别，但当前没有可稳定执行的自动查询路线。"""


@dataclass(frozen=True)
class TrackingOptions:
    headless: bool = False
    browser_channel: str = "chromium"
    timeout_seconds: float | None = None
    max_attempts: int | None = None
    min_interval_seconds: float | None = None


TrackingAdapter = Callable[[str, TrackingOptions], object]

DEFAULT_POLICY = QueryPolicy(min_interval_seconds=0, timeout_seconds=75, max_attempts=1)


@dataclass(frozen=True)
class CarrierRoute:
    name: str
    description: str
    adapter: TrackingAdapter | None
    policy: QueryPolicy = DEFAULT_POLICY


HTTP_POLICY = QueryPolicy(min_interval_seconds=30, timeout_seconds=45, max_attempts=2)
DOM_POLICY = QueryPolicy(min_interval_seconds=60, timeout_seconds=60, max_attempts=2)
BROWSER_POLICY = QueryPolicy(min_interval_seconds=90, timeout_seconds=90, max_attempts=2)
WAN_HAI_POLICY = QueryPolicy(min_interval_seconds=120, timeout_seconds=120, max_attempts=1)
HMM_POLICY = QueryPolicy(
    min_interval_seconds=120,
    timeout_seconds=240,
    max_attempts=2,
    backoff_base_seconds=180,
    backoff_max_seconds=300,
    jitter_seconds=60,
)


def _yang_ming(container: str, options: TrackingOptions) -> object:
    from trace_api_probe.providers.yang_ming_probe import fetch_tracking

    return fetch_tracking(container)


def _sm_line(container: str, options: TrackingOptions) -> object:
    from trace_api_probe.providers.sm_line_probe import fetch_tracking

    return fetch_tracking(container)


def _evergreen(container: str, options: TrackingOptions) -> object:
    from trace_api_probe.providers.evergreen_probe import fetch_tracking

    return fetch_tracking(container)


def _browser_dom(carrier: Carrier, container: str, options: TrackingOptions) -> object:
    from trace_api_probe.providers.browser_dom_probe import fetch_tracking

    return fetch_tracking(carrier.value, container)


def _cosco(container: str, options: TrackingOptions) -> object:
    return _browser_dom(Carrier.COSCO, container, options)


def _one(container: str, options: TrackingOptions) -> object:
    return _browser_dom(Carrier.ONE, container, options)


def _maersk(container: str, options: TrackingOptions) -> object:
    from trace_api_probe.providers.maersk_probe import fetch_tracking

    return fetch_tracking(container)


def _msc(container: str, options: TrackingOptions) -> object:
    from trace_api_probe.providers.msc_probe import fetch_tracking

    return fetch_tracking(
        container,
        headless=options.headless,
        browser_channel=options.browser_channel,
    )


def _wan_hai(container: str, options: TrackingOptions) -> object:
    from trace_api_probe.providers.wan_hai_probe import fetch_tracking

    return fetch_tracking(
        container,
        headless=options.headless,
        browser_channel=options.browser_channel,
    )


def _hmm(container: str, options: TrackingOptions) -> object:
    from trace_api_probe.providers.hmm_probe import fetch_tracking

    return fetch_tracking(
        container,
        headless=options.headless,
        browser_channel=options.browser_channel,
    )


ROUTES: Mapping[Carrier, CarrierRoute] = {
    Carrier.YANG_MING: CarrierRoute("yang_ming_json", "阳明官网公开 JSON", _yang_ming, HTTP_POLICY),
    Carrier.SM_LINE: CarrierRoute("sm_line_json", "SM Line 官网会话 JSON", _sm_line, HTTP_POLICY),
    Carrier.EVERGREEN: CarrierRoute("evergreen_html", "长荣官网表单 HTML", _evergreen, HTTP_POLICY),
    Carrier.COSCO: CarrierRoute("cosco_dom", "COSCO 官网结构化 DOM", _cosco, DOM_POLICY),
    Carrier.ONE: CarrierRoute("one_dom", "ONE 官网结构化 DOM", _one, DOM_POLICY),
    Carrier.MAERSK: CarrierRoute("maersk_browser_json", "马士基官网页面 JSON", _maersk, BROWSER_POLICY),
    Carrier.MSC: CarrierRoute("msc_browser_json", "MSC 官网页面 JSON", _msc, BROWSER_POLICY),
    Carrier.WAN_HAI: CarrierRoute("wan_hai_form_html", "万海官网会话表单 HTML", _wan_hai, WAN_HAI_POLICY),
    Carrier.HMM: CarrierRoute("hmm_browser_html", "HMM 官网有界浏览器 HTML", _hmm, HMM_POLICY),
    Carrier.CMA_CGM: CarrierRoute("cma_cgm_unavailable", "CMA CGM 当前没有可执行的网页查询路线", None),
    Carrier.APL: CarrierRoute("apl_unavailable", "APL 当前没有稳定的直接查询路线", None),
    Carrier.OOCL: CarrierRoute("oocl_unavailable", "OOCL 当前受 Cloudflare 人机验证限制", None),
    Carrier.ZIM: CarrierRoute("zim_unavailable", "ZIM 当前受 Cloudflare 访问限制", None),
    Carrier.TS_LINES: CarrierRoute("ts_lines_unavailable", "TS Lines 查询需要人工验证码", None),
    Carrier.HAPAG_LLOYD: CarrierRoute("hapag_lloyd_unavailable", "Hapag-Lloyd 当前受 Cloudflare 访问限制", None),
    Carrier.KMTC: CarrierRoute("kmtc_unavailable", "KMTC 当前受 Akamai 访问限制", None),
    Carrier.SEA_LEAD: CarrierRoute("sea_lead_unavailable", "SeaLead 当前官网追踪服务维护", None),
}


class TrackingRouter:
    """把数据库样本路由到船司适配器，并返回统一结果信封。"""

    def __init__(
        self,
        routes: Mapping[Carrier, CarrierRoute] | None = None,
        executor: QueryExecutor | None = None,
    ) -> None:
        self._routes = routes or ROUTES
        self._executor = executor or QueryExecutor(use_subprocess=routes is None)

    def close_provider(self) -> None:
        self._executor.close_provider()

    def query(self, sample: ShipmentSample, options: TrackingOptions | None = None) -> dict[str, object]:
        options = options or TrackingOptions()
        carrier = normalize_carrier(sample.shipping_company)
        result = _sample_metadata(sample, carrier)
        if sample.source_error:
            result.update(status="source_data_error", route="source_validation", error=sample.source_error)
            return result

        try:
            container_no = normalize_container_number(sample.container_no)
        except ValueError as exc:
            result.update(status="source_data_error", route="source_validation", error=str(exc))
            return result
        result["container"] = container_no

        if carrier is None:
            result.update(
                status="unsupported_carrier",
                route="unknown",
                error=f"无法识别数据库船司: {sample.shipping_company}",
            )
            return result

        route = self._routes.get(carrier)
        result.update(carrier=carrier.value)
        if route is None or route.adapter is None:
            result.update(
                status="route_unavailable",
                route=route.name if route else "unregistered",
                route_description=route.description if route else "未注册船司路线",
                error=route.description if route else f"未注册船司路线: {carrier.value}",
            )
            return result

        result.update(route=route.name, route_description=route.description)
        policy = _effective_policy(route.policy, options)
        try:
            raw, execution = self._executor.execute(
                carrier.value,
                route.adapter,
                container_no,
                options,
                policy,
            )
        except Exception as exc:
            result.update(
                status="query_failed",
                execution={
                    "attempts": getattr(exc, "query_attempts", 1),
                    "timeout_seconds": policy.timeout_seconds,
                    "elapsed_seconds": getattr(exc, "query_elapsed_seconds", None),
                    "retry_delays_seconds": getattr(exc, "query_retry_delays_seconds", []),
                },
                error={
                    "type": getattr(exc, "provider_error_type", None) or type(exc).__name__,
                    "message": getattr(exc, "provider_error_message", None) or str(exc),
                },
            )
            return result

        try:
            normalized = normalize_tracking(carrier, container_no, raw)
        except Exception as exc:
            result.update(
                status="partial_success",
                execution=execution,
                normalized=empty_tracking_summary(carrier, container_no),
                raw=raw,
                error={
                    "stage": "normalization",
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
            return result

        result.update(status="success", execution=execution, normalized=normalized, raw=raw)
        return result


def query_samples(
    samples: list[ShipmentSample],
    *,
    options: TrackingOptions | None = None,
    router: TrackingRouter | None = None,
) -> list[dict[str, object]]:
    active_router = router or TrackingRouter()
    grouped_indices: dict[str, list[int]] = {}
    for index, sample in enumerate(samples):
        carrier = normalize_carrier(sample.shipping_company)
        key = carrier.value if carrier else f"UNKNOWN:{sample.shipping_company}"
        grouped_indices.setdefault(key, []).append(index)

    results: list[dict[str, object] | None] = [None] * len(samples)
    for indices in grouped_indices.values():
        try:
            for index in indices:
                sample = samples[index]
                try:
                    results[index] = active_router.query(sample, options)
                except Exception as exc:
                    carrier = normalize_carrier(sample.shipping_company)
                    result = _sample_metadata(sample, carrier)
                    result.update(
                        status="internal_error",
                        route="unknown",
                        error={
                            "stage": "routing",
                            "type": type(exc).__name__,
                            "message": str(exc),
                        },
                    )
                    results[index] = result
        finally:
            close_provider = getattr(active_router, "close_provider", None)
            if callable(close_provider):
                close_provider()
    if any(result is None for result in results):  # pragma: no cover - defensive batch invariant
        raise AssertionError("批量查询结果未与全部输入样本对应")
    return [result for result in results if result is not None]


def _sample_metadata(sample: ShipmentSample, carrier: Carrier | None) -> dict[str, object]:
    return {
        "sample_id": sample.id,
        "shipping_company": sample.shipping_company,
        "carrier": carrier.value if carrier else None,
        "container": sample.container_no,
        "update_time": sample.update_time,
        "create_time": sample.create_time,
        "consolidation_no": sample.consolidation_no,
        "erp_order_count": sample.erp_order_count,
    }


def _effective_policy(policy: QueryPolicy, options: TrackingOptions) -> QueryPolicy:
    return QueryPolicy(
        min_interval_seconds=(
            options.min_interval_seconds if options.min_interval_seconds is not None else policy.min_interval_seconds
        ),
        timeout_seconds=options.timeout_seconds if options.timeout_seconds is not None else policy.timeout_seconds,
        max_attempts=options.max_attempts if options.max_attempts is not None else policy.max_attempts,
        backoff_base_seconds=policy.backoff_base_seconds,
        backoff_max_seconds=policy.backoff_max_seconds,
        jitter_seconds=policy.jitter_seconds,
    )


def fetch_raw_for_carrier(carrier: Carrier, container: str, options: TrackingOptions) -> object:
    route = ROUTES.get(carrier)
    if route is None or route.adapter is None:
        raise UnsupportedTrackingError(f"{carrier.value} 没有可执行的查询路线")
    return route.adapter(container, options)
