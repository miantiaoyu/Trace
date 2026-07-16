from __future__ import annotations


SUCCESS_STATUSES = frozenset({"success"})
PARTIAL_STATUSES = frozenset({"partial_success"})
SKIPPED_STATUSES = frozenset({"source_data_error", "route_unavailable", "unsupported_carrier"})
