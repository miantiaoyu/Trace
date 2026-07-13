from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from trace_api_probe.carriers import Carrier, normalize_carrier
from trace_api_probe.db import ShipmentSample


class UnsupportedTrackingError(RuntimeError):
    """船司已识别，但当前没有可稳定执行的自动查询路线。"""


@dataclass(frozen=True)
class TrackingOptions:
    headless: bool = False
    browser_channel: str = "chromium"


TrackingAdapter = Callable[[str, TrackingOptions], object]


@dataclass(frozen=True)
class CarrierRoute:
    name: str
    description: str
    adapter: TrackingAdapter | None


def _yang_ming(container: str, options: TrackingOptions) -> object:
    from crawler_lab.yang_ming_probe import fetch_tracking

    return fetch_tracking(container)


def _sm_line(container: str, options: TrackingOptions) -> object:
    from crawler_lab.sm_line_probe import fetch_tracking

    return fetch_tracking(container)


def _evergreen(container: str, options: TrackingOptions) -> object:
    from crawler_lab.evergreen_probe import fetch_tracking

    return fetch_tracking(container)


def _browser_dom(carrier: Carrier, container: str, options: TrackingOptions) -> object:
    from crawler_lab.browser_dom_probe import fetch_tracking

    return fetch_tracking(carrier.value, container)


def _cosco(container: str, options: TrackingOptions) -> object:
    return _browser_dom(Carrier.COSCO, container, options)


def _one(container: str, options: TrackingOptions) -> object:
    return _browser_dom(Carrier.ONE, container, options)


def _maersk(container: str, options: TrackingOptions) -> object:
    from crawler_lab.maersk_probe import fetch_tracking

    return fetch_tracking(container)


def _msc(container: str, options: TrackingOptions) -> object:
    from crawler_lab.msc_probe import fetch_tracking

    return fetch_tracking(
        container,
        headless=options.headless,
        browser_channel=options.browser_channel,
    )


def _wan_hai(container: str, options: TrackingOptions) -> object:
    from crawler_lab.wan_hai_probe import fetch_tracking

    return fetch_tracking(
        container,
        headless=options.headless,
        browser_channel=options.browser_channel,
    )


def _hmm(container: str, options: TrackingOptions) -> object:
    from crawler_lab.hmm_probe import fetch_tracking

    return fetch_tracking(
        container,
        headless=options.headless,
        browser_channel=options.browser_channel,
    )


def _official_api(carrier: Carrier, container: str, options: TrackingOptions) -> object:
    from trace_api_probe.providers import provider_for

    return provider_for(carrier).fetch_raw(container)


def _cma_cgm(container: str, options: TrackingOptions) -> object:
    return _official_api(Carrier.CMA_CGM, container, options)


ROUTES: Mapping[Carrier, CarrierRoute] = {
    Carrier.YANG_MING: CarrierRoute("yang_ming_json", "阳明官网公开 JSON", _yang_ming),
    Carrier.SM_LINE: CarrierRoute("sm_line_json", "SM Line 官网会话 JSON", _sm_line),
    Carrier.EVERGREEN: CarrierRoute("evergreen_html", "长荣官网表单 HTML", _evergreen),
    Carrier.COSCO: CarrierRoute("cosco_dom", "COSCO 官网结构化 DOM", _cosco),
    Carrier.ONE: CarrierRoute("one_dom", "ONE 官网结构化 DOM", _one),
    Carrier.MAERSK: CarrierRoute("maersk_browser_json", "马士基官网页面 JSON", _maersk),
    Carrier.MSC: CarrierRoute("msc_browser_json", "MSC 官网页面 JSON", _msc),
    Carrier.WAN_HAI: CarrierRoute("wan_hai_form_html", "万海官网会话表单 HTML", _wan_hai),
    Carrier.HMM: CarrierRoute("hmm_browser_html", "HMM 官网有界浏览器 HTML", _hmm),
    Carrier.CMA_CGM: CarrierRoute("cma_cgm_official_api", "CMA CGM 官方 API（需要凭证）", _cma_cgm),
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

    def __init__(self, routes: Mapping[Carrier, CarrierRoute] | None = None) -> None:
        self._routes = routes or ROUTES

    def query(self, sample: ShipmentSample, options: TrackingOptions | None = None) -> dict[str, object]:
        options = options or TrackingOptions()
        carrier = normalize_carrier(sample.shipping_company)
        result = _sample_metadata(sample, carrier)
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
        try:
            raw = route.adapter(sample.container_no, options)
        except Exception as exc:
            result.update(
                status="query_failed",
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            return result

        result.update(status="success", raw=raw)
        return result


def query_samples(
    samples: list[ShipmentSample],
    *,
    options: TrackingOptions | None = None,
    router: TrackingRouter | None = None,
) -> list[dict[str, object]]:
    active_router = router or TrackingRouter()
    return [active_router.query(sample, options) for sample in samples]


def _sample_metadata(sample: ShipmentSample, carrier: Carrier | None) -> dict[str, object]:
    return {
        "sample_id": sample.id,
        "shipping_company": sample.shipping_company,
        "carrier": carrier.value if carrier else None,
        "container": sample.container_no,
        "update_time": sample.update_time,
        "create_time": sample.create_time,
    }
