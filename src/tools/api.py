import datetime
import logging
import os
import pandas as pd
import requests
import time

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyFactsResponse,
)

logger = logging.getLogger(__name__)

# Global cache instance
_cache = get_cache()

DEFAULT_REQUEST_TIMEOUT = 30.0


def _get_headers(api_key: str | None = None) -> dict:
    """Build request headers including FINANCIAL_DATASETS_API_KEY when present."""
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key
    return headers


def _make_api_request(
    url: str,
    headers: dict,
    method: str = "GET",
    json_data: dict = None,
    max_retries: int = 3,
    timeout: float | None = None,
) -> requests.Response:
    """
    Make an API request with rate limiting handling and moderate backoff.
    """
    request_kwargs = {"headers": headers}
    if timeout is not None:
        request_kwargs["timeout"] = timeout

    for attempt in range(max_retries + 1):  # +1 for initial attempt
        if method.upper() == "POST":
            response = requests.post(url, json=json_data, **request_kwargs)
        else:
            response = requests.get(url, **request_kwargs)

        if response.status_code == 429 and attempt < max_retries:
            # Linear backoff: 60s, 90s, 120s, 150s...
            delay = 60 + (30 * attempt)
            print(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
            time.sleep(delay)
            continue

        # Return the response (whether success, other errors, or final 429)
        return response


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """Fetch price data from cache or API."""
    cache_key = f"{ticker}_{start_date}_{end_date}"

    if (cached_data := _cache.get_prices(cache_key)) is not None:
        return [Price(**price) for price in cached_data]

    headers = _get_headers(api_key)
    url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    response = _make_api_request(url, headers, timeout=DEFAULT_REQUEST_TIMEOUT)
    if response.status_code != 200:
        return []

    try:
        price_response = PriceResponse(**response.json())
        prices = price_response.prices
    except Exception as e:
        logger.warning("Failed to parse prices for %s: %s", ticker, e)
        return []

    if not prices:
        return []

    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """Fetch financial metrics from cache or API."""
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"

    if (cached_data := _cache.get_financial_metrics(cache_key)) is not None:
        return [FinancialMetrics(**metric) for metric in cached_data]

    headers = _get_headers(api_key)
    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    response = _make_api_request(url, headers, timeout=DEFAULT_REQUEST_TIMEOUT)
    if response.status_code != 200:
        return []

    try:
        metrics_response = FinancialMetricsResponse(**response.json())
        financial_metrics = metrics_response.financial_metrics
    except Exception as e:
        logger.warning("Failed to parse financial metrics for %s: %s", ticker, e)
        return []

    if not financial_metrics:
        return []

    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
    return financial_metrics


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """Fetch line items from cache or API."""
    cache_key = f"{ticker}_{'_'.join(sorted(line_items))}_{period}_{end_date}_{limit}"
    if (cached_data := _cache.get_line_items(cache_key)) is not None:
        return [LineItem(**item) for item in cached_data][:limit]

    headers = _get_headers(api_key)
    url = "https://api.financialdatasets.ai/financials/search/line-items"

    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    response = _make_api_request(url, headers, method="POST", json_data=body, timeout=DEFAULT_REQUEST_TIMEOUT)
    if response.status_code != 200:
        return []

    try:
        data = response.json()
        response_model = LineItemResponse(**data)
        search_results = response_model.search_results
    except Exception as e:
        logger.warning("Failed to parse line items for %s: %s", ticker, e)
        return []
    if not search_results:
        return []

    _cache.set_line_items(cache_key, [item.model_dump() for item in search_results])
    return search_results[:limit]


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or API."""
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"

    if (cached_data := _cache.get_insider_trades(cache_key)) is not None:
        return [InsiderTrade(**trade) for trade in cached_data]

    headers = _get_headers(api_key)
    all_trades = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        url += f"&limit={limit}"

        response = _make_api_request(url, headers, timeout=DEFAULT_REQUEST_TIMEOUT)
        if response.status_code != 200:
            break

        try:
            data = response.json()
            response_model = InsiderTradeResponse(**data)
            insider_trades = response_model.insider_trades
        except Exception as e:
            logger.warning("Failed to parse insider trades for %s: %s", ticker, e)
            break

        if not insider_trades:
            break

        all_trades.extend(insider_trades)

        if not start_date or len(insider_trades) < limit:
            break

        current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]
        if current_end_date <= start_date:
            break

    if not all_trades:
        return []

    _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in all_trades])
    return all_trades


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """Fetch company news from cache or API."""
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"

    if (cached_data := _cache.get_company_news(cache_key)) is not None:
        return [CompanyNews(**news) for news in cached_data]

    headers = _get_headers(api_key)
    all_news = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
        if start_date:
            url += f"&start_date={start_date}"
        url += f"&limit={limit}"

        response = _make_api_request(url, headers, timeout=DEFAULT_REQUEST_TIMEOUT)
        if response.status_code != 200:
            break

        try:
            data = response.json()
            response_model = CompanyNewsResponse(**data)
            company_news = response_model.news
        except Exception as e:
            logger.warning("Failed to parse company news for %s: %s", ticker, e)
            break

        if not company_news:
            break

        all_news.extend(company_news)

        if not start_date or len(company_news) < limit:
            break

        current_end_date = min(news.date for news in company_news).split("T")[0]
        if current_end_date <= start_date:
            break

    if not all_news:
        return []

    _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
    return all_news


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """Fetch market cap from the API."""
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        headers = _get_headers(api_key)
        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        response = _make_api_request(url, headers, timeout=DEFAULT_REQUEST_TIMEOUT)
        if response.status_code != 200:
            logger.warning("Error fetching company facts: %s - %s", ticker, response.status_code)
            return None

        try:
            data = response.json()
            response_model = CompanyFactsResponse(**data)
            return response_model.company_facts.market_cap
        except Exception as e:
            logger.warning("Failed to parse company facts for %s: %s", ticker, e)
            return None

    financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
    if not financial_metrics:
        return None

    market_cap = financial_metrics[0].market_cap
    return market_cap or None


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    if not prices:
        return pd.DataFrame(columns=["open", "close", "high", "low", "volume"])
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
