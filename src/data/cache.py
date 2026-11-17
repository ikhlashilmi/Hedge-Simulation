import threading
from typing import Any


def _is_iso_date(value: str) -> bool:
    return len(value) == 10 and value[4] == "-" and value[7] == "-" and value.replace("-", "").isdigit()


class Cache:
    """Thread-safe in-memory cache for API responses with per-ticker range slicing."""

    def __init__(self):
        self._lock = threading.RLock()
        self._prices_cache: dict[str, list[dict[str, Any]]] = {}
        self._prices_by_ticker: dict[str, list[dict[str, Any]]] = {}
        self._prices_ranges: dict[str, list[tuple[str, str]]] = {}

        self._financial_metrics_cache: dict[str, list[dict[str, Any]]] = {}
        self._fm_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._fm_coverages: dict[tuple[str, str], list[tuple[str, int, int]]] = {}

        self._line_items_cache: dict[str, list[dict[str, Any]]] = {}

        self._insider_trades_cache: dict[str, list[dict[str, Any]]] = {}
        self._insider_by_ticker: dict[str, list[dict[str, Any]]] = {}
        self._insider_ranges: dict[str, list[tuple[str, str, int, int]]] = {}

        self._company_news_cache: dict[str, list[dict[str, Any]]] = {}
        self._news_by_ticker: dict[str, list[dict[str, Any]]] = {}
        self._news_ranges: dict[str, list[tuple[str, str, int, int]]] = {}

    def _merge_data(self, existing: list[dict] | None, new_data: list[dict], key_field: str) -> list[dict]:
        """Merge existing and new data, avoiding duplicates based on a key field."""
        if not existing:
            return list(new_data)

        existing_keys = {item[key_field] for item in existing if key_field in item}
        merged = existing.copy()
        merged.extend([item for item in new_data if item.get(key_field) not in existing_keys])
        return merged

    @staticmethod
    def _merge_unique(existing: list[dict] | None, new_data: list[dict], key_fn) -> list[dict]:
        if not existing:
            return list(new_data)
        existing_keys = {key_fn(item) for item in existing}
        merged = existing.copy()
        for item in new_data:
            k = key_fn(item)
            if k not in existing_keys:
                existing_keys.add(k)
                merged.append(item)
        return merged

    @staticmethod
    def _parse_prices_key(key: str) -> tuple[str, str, str] | None:
        parts = key.rsplit("_", 2)
        if len(parts) == 3 and _is_iso_date(parts[1]) and _is_iso_date(parts[2]):
            return parts[0], parts[1], parts[2]
        return None

    @staticmethod
    def _parse_fm_key(key: str) -> tuple[str, str, str, int] | None:
        parts = key.rsplit("_", 3)
        if len(parts) == 4 and _is_iso_date(parts[2]) and parts[3].isdigit():
            return parts[0], parts[1], parts[2], int(parts[3])
        return None

    @staticmethod
    def _parse_window_key(key: str) -> tuple[str, str, str, int] | None:
        parts = key.rsplit("_", 3)
        if (
            len(parts) == 4
            and (parts[1] == "none" or _is_iso_date(parts[1]))
            and _is_iso_date(parts[2])
            and parts[3].isdigit()
        ):
            return parts[0], parts[1], parts[2], int(parts[3])
        return None

    @staticmethod
    def _add_interval(intervals: list[tuple[str, str]], start: str, end: str) -> list[tuple[str, str]]:
        updated = sorted(intervals + [(start, end)])
        merged: list[tuple[str, str]] = []
        for s, e in updated:
            if not merged or s > merged[-1][1]:
                merged.append((s, e))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        return merged

    def get_prices(self, ticker: str) -> list[dict[str, Any]] | None:
        """Get cached price data if available (supports range-slicing from wider entries)."""
        with self._lock:
            if ticker in self._prices_cache:
                return self._prices_cache[ticker]

            parsed = self._parse_prices_key(ticker)
            if not parsed:
                return None
            sym, req_start, req_end = parsed
            for cov_start, cov_end in self._prices_ranges.get(sym, []):
                if cov_start <= req_start and req_end <= cov_end:
                    rows = [
                        row for row in self._prices_by_ticker.get(sym, [])
                        if req_start <= str(row.get("time", ""))[:10] <= req_end
                    ]
                    rows.sort(key=lambda r: str(r.get("time", "")))
                    return rows
            return None

    def set_prices(self, ticker: str, data: list[dict[str, Any]]):
        """Append new price data to cache and index by ticker for range slicing."""
        with self._lock:
            self._prices_cache[ticker] = self._merge_data(self._prices_cache.get(ticker), data, key_field="time")
            parsed = self._parse_prices_key(ticker)
            if parsed:
                sym, start_date, end_date = parsed
                self._prices_by_ticker[sym] = self._merge_data(
                    self._prices_by_ticker.get(sym), data, key_field="time"
                )
                self._prices_ranges[sym] = self._add_interval(
                    self._prices_ranges.get(sym, []), start_date, end_date
                )

    def get_financial_metrics(self, ticker: str) -> list[dict[str, Any]] | None:
        """Get cached financial metrics if available (supports slicing by end_date/limit)."""
        with self._lock:
            if ticker in self._financial_metrics_cache:
                return self._financial_metrics_cache[ticker]

            parsed = self._parse_fm_key(ticker)
            if not parsed:
                return None
            sym, period, req_end, req_limit = parsed
            for cov_end, cov_limit, cov_count in self._fm_coverages.get((sym, period), []):
                if cov_end >= req_end:
                    filtered = [
                        m for m in self._fm_by_key.get((sym, period), [])
                        if str(m.get("report_period", ""))[:10] <= req_end
                    ]
                    filtered.sort(key=lambda m: str(m.get("report_period", "")), reverse=True)
                    if cov_count < cov_limit or len(filtered) >= req_limit:
                        return filtered[:req_limit]
            return None

    def set_financial_metrics(self, ticker: str, data: list[dict[str, Any]]):
        """Append new financial metrics to cache and index by (ticker, period)."""
        with self._lock:
            self._financial_metrics_cache[ticker] = self._merge_data(
                self._financial_metrics_cache.get(ticker), data, key_field="report_period"
            )
            parsed = self._parse_fm_key(ticker)
            if parsed:
                sym, period, end_date, limit = parsed
                key = (sym, period)
                self._fm_by_key[key] = self._merge_data(
                    self._fm_by_key.get(key), data, key_field="report_period"
                )
                self._fm_coverages.setdefault(key, []).append((end_date, limit, len(data)))

    def get_line_items(self, ticker: str) -> list[dict[str, Any]] | None:
        """Get cached line items if available."""
        with self._lock:
            return self._line_items_cache.get(ticker)

    def set_line_items(self, ticker: str, data: list[dict[str, Any]]):
        """Append new line items to cache."""
        with self._lock:
            self._line_items_cache[ticker] = self._merge_data(
                self._line_items_cache.get(ticker), data, key_field="report_period"
            )

    def get_insider_trades(self, ticker: str) -> list[dict[str, Any]] | None:
        """Get cached insider trades if available (supports date-range slicing)."""
        with self._lock:
            if ticker in self._insider_trades_cache:
                return self._insider_trades_cache[ticker]

            parsed = self._parse_window_key(ticker)
            if not parsed:
                return None
            sym, req_start, req_end, req_limit = parsed
            if req_start == "none":
                return None
            for cov_start, cov_end, cov_limit, cov_count in self._insider_ranges.get(sym, []):
                if cov_start != "none" and cov_start <= req_start and req_end <= cov_end:
                    rows = [
                        t for t in self._insider_by_ticker.get(sym, [])
                        if req_start <= str(t.get("filing_date", ""))[:10] <= req_end
                    ]
                    if cov_count < cov_limit or len(rows) >= req_limit:
                        return rows[:req_limit]
            return None

    def set_insider_trades(self, ticker: str, data: list[dict[str, Any]]):
        """Append new insider trades to cache."""
        with self._lock:
            self._insider_trades_cache[ticker] = self._merge_data(
                self._insider_trades_cache.get(ticker), data, key_field="filing_date"
            )
            parsed = self._parse_window_key(ticker)
            if parsed:
                sym, start_str, end_date, limit = parsed
                self._insider_by_ticker[sym] = self._merge_unique(
                    self._insider_by_ticker.get(sym),
                    data,
                    key_fn=lambda t: (
                        t.get("filing_date"),
                        t.get("transaction_date"),
                        t.get("name"),
                        t.get("transaction_shares"),
                    ),
                )
                self._insider_ranges.setdefault(sym, []).append((start_str, end_date, limit, len(data)))

    def get_company_news(self, ticker: str) -> list[dict[str, Any]] | None:
        """Get cached company news if available (supports date-range slicing)."""
        with self._lock:
            if ticker in self._company_news_cache:
                return self._company_news_cache[ticker]

            parsed = self._parse_window_key(ticker)
            if not parsed:
                return None
            sym, req_start, req_end, req_limit = parsed
            if req_start == "none":
                return None
            for cov_start, cov_end, cov_limit, cov_count in self._news_ranges.get(sym, []):
                if cov_start != "none" and cov_start <= req_start and req_end <= cov_end:
                    rows = [
                        n for n in self._news_by_ticker.get(sym, [])
                        if req_start <= str(n.get("date", ""))[:10] <= req_end
                    ]
                    if cov_count < cov_limit or len(rows) >= req_limit:
                        return rows[:req_limit]
            return None

    def set_company_news(self, ticker: str, data: list[dict[str, Any]]):
        """Append new company news to cache."""
        with self._lock:
            self._company_news_cache[ticker] = self._merge_data(
                self._company_news_cache.get(ticker), data, key_field="date"
            )
            parsed = self._parse_window_key(ticker)
            if parsed:
                sym, start_str, end_date, limit = parsed
                self._news_by_ticker[sym] = self._merge_unique(
                    self._news_by_ticker.get(sym),
                    data,
                    key_fn=lambda n: (n.get("date"), n.get("url"), n.get("title")),
                )
                self._news_ranges.setdefault(sym, []).append((start_str, end_date, limit, len(data)))


# Global cache instance
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache
