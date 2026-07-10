from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from trace_api_probe.carriers import Carrier


class MissingCredentialError(RuntimeError):
    def __init__(self, carrier: Carrier, missing_names: list[str]) -> None:
        self.carrier = carrier
        self.missing_names = missing_names
        super().__init__(f"{carrier.value} 缺少 API 凭证: {', '.join(missing_names)}")


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    headers: Mapping[str, str]


class TrackTraceProvider:
    carrier: Carrier
    default_base_url: str
    base_url_env: str

    def fetch_raw(self, container_no: str) -> object:
        config = self._config_from_env()
        url = _with_query(config.base_url, {"equipmentReference": container_no})
        request = Request(url, headers=dict(config.headers), method="GET")

        try:
            with urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                return _parse_json(body)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{self.carrier.value} API 返回 HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(f"{self.carrier.value} API 请求失败: {exc.reason}") from exc

    def _config_from_env(self) -> ProviderConfig:
        raise NotImplementedError


class MaerskProvider(TrackTraceProvider):
    carrier = Carrier.MAERSK
    default_base_url = "https://api.maersk.com/track-and-trace/events"
    base_url_env = "MAERSK_TRACK_TRACE_URL"

    def _config_from_env(self) -> ProviderConfig:
        base_url = os.getenv(self.base_url_env, self.default_base_url)
        api_key = os.getenv("MAERSK_API_KEY")
        client_id = os.getenv("MAERSK_CLIENT_ID")
        bearer_token = os.getenv("MAERSK_BEARER_TOKEN")

        if not api_key and not client_id:
            raise MissingCredentialError(self.carrier, ["MAERSK_API_KEY 或 MAERSK_CLIENT_ID"])

        headers = {"Accept": "application/json"}
        if api_key:
            headers["Consumer-Key"] = api_key
        if client_id:
            headers["Consumer-Key"] = client_id
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        return ProviderConfig(base_url=base_url, headers=headers)


class CmaCgmProvider(TrackTraceProvider):
    carrier = Carrier.CMA_CGM
    default_base_url = "https://apis.cma-cgm.net/operation/trackandtrace/v1/events"
    base_url_env = "CMA_CGM_TRACK_TRACE_URL"

    def _config_from_env(self) -> ProviderConfig:
        base_url = os.getenv(self.base_url_env, self.default_base_url)
        api_key = os.getenv("CMA_CGM_API_KEY")
        bearer_token = os.getenv("CMA_CGM_BEARER_TOKEN")

        if not api_key:
            raise MissingCredentialError(self.carrier, ["CMA_CGM_API_KEY"])

        headers = {
            "Accept": "application/json",
            "Ocp-Apim-Subscription-Key": api_key,
        }
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        return ProviderConfig(base_url=base_url, headers=headers)


class MscProvider(TrackTraceProvider):
    carrier = Carrier.MSC
    default_base_url = "https://api.tech.msc.com/trackandtrace/v2/events"
    base_url_env = "MSC_TRACK_TRACE_URL"

    def _config_from_env(self) -> ProviderConfig:
        base_url = os.getenv(self.base_url_env, self.default_base_url)
        api_key = os.getenv("MSC_API_KEY")
        bearer_token = os.getenv("MSC_BEARER_TOKEN")

        if not api_key:
            raise MissingCredentialError(self.carrier, ["MSC_API_KEY"])

        headers = {
            "Accept": "application/json",
            "Ocp-Apim-Subscription-Key": api_key,
        }
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        return ProviderConfig(base_url=base_url, headers=headers)


def provider_for(carrier: Carrier) -> TrackTraceProvider:
    providers: dict[Carrier, type[TrackTraceProvider]] = {
        Carrier.MAERSK: MaerskProvider,
        Carrier.CMA_CGM: CmaCgmProvider,
        Carrier.MSC: MscProvider,
    }
    return providers[carrier]()


def _with_query(base_url: str, params: Mapping[str, str]) -> str:
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"


def _parse_json(body: str) -> object:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw_text": body}
