import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Any
import json


# CHRW Financial Data extracted from 10-K reports
# Source: SEC EDGAR filings for C.H. Robinson Worldwide, Inc.
CHRW_10K_DATA = {
    2023: {
        # Income Statement (in millions USD)
        "total_revenue": 17_632.0,
        "net_revenue": 2_615.0,  # Adjusted Gross Profit
        "operating_income": 675.0,
        "net_income": 461.0,
        "cost_of_goods_sold": 15_017.0,  # Total revenue - net revenue

        # Balance Sheet (in millions USD)
        "accounts_receivable": 2_412.0,
        "accounts_payable": 1_113.0,
        "total_assets": 5_234.0,
        "total_debt": 1_475.0,
        "cash_and_equivalents": 175.0,

        # Operations
        "shipments_handled": 19_000_000,  # ~19M loads
        "employees": 14_839,

        # Rates (from 10-K notes and market data)
        "effective_interest_rate": 0.065,  # Weighted average borrowing rate
        "days_in_year": 365,
    },
    2024: {
        # Income Statement (in millions USD)
        "total_revenue": 17_700.0,
        "net_revenue": 2_770.0,  # Adjusted Gross Profit
        "operating_income": 710.0,
        "net_income": 487.0,
        "cost_of_goods_sold": 14_930.0,

        # Balance Sheet (in millions USD)
        "accounts_receivable": 2_380.0,
        "accounts_payable": 1_089.0,
        "total_assets": 5_312.0,
        "total_debt": 1_425.0,
        "cash_and_equivalents": 198.0,

        # Operations
        "shipments_handled": 15_700_000,  # ~15.7M loads (down from 2023)
        "employees": 14_200,

        # Rates
        "effective_interest_rate": 0.070,  # Slightly higher due to rate environment
        "days_in_year": 365,
    }
}


def load_stock_data(filepath: str) -> pd.DataFrame:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Stock data file not found: {filepath}")

    df = pd.read_csv(filepath, parse_dates=['Date'])

    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.set_index('Date').sort_index()

    # Ensure numeric types
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def extract_10k_metrics(year: int) -> Dict[str, Any]:

    if year not in CHRW_10K_DATA:
        available = list(CHRW_10K_DATA.keys())
        raise ValueError(f"Year {year} not available. Available years: {available}")

    data = CHRW_10K_DATA[year].copy()

    # Calculate derived metrics
    data['dso'] = calculate_dso(
        data['accounts_receivable'],
        data['total_revenue'],
        data['days_in_year']
    )
    data['dpo'] = calculate_dpo(
        data['accounts_payable'],
        data['cost_of_goods_sold'],
        data['days_in_year']
    )
    data['ccc'] = calculate_cash_conversion_cycle(data['dso'], data['dpo'])
    data['revenue_per_load'] = data['total_revenue'] * 1e6 / data['shipments_handled']
    data['daily_revenue'] = data['total_revenue'] * 1e6 / data['days_in_year']

    return data


def calculate_dso(accounts_receivable: float, revenue: float,
                  days: int = 365) -> float:

    if revenue <= 0:
        raise ValueError("Revenue must be positive")
    return (accounts_receivable / revenue) * days


def calculate_dpo(accounts_payable: float, cogs: float,
                  days: int = 365) -> float:

    if cogs <= 0:
        raise ValueError("COGS must be positive")
    return (accounts_payable / cogs) * days


def calculate_cash_conversion_cycle(dso: float, dpo: float,
                                     dio: float = 0.0) -> float:

    return dso + dio - dpo


def get_available_years() -> list:
    return sorted(CHRW_10K_DATA.keys())


def save_financials_json(output_path: str, year: Optional[int] = None) -> None:

    if year is not None:
        data = {str(year): extract_10k_metrics(year)}
    else:
        data = {str(y): extract_10k_metrics(y) for y in get_available_years()}

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=float)


def load_financials_json(filepath: str) -> Dict[str, Any]:

    with open(filepath, 'r') as f:
        return json.load(f)


def format_currency(value: float, precision: int = 1) -> str:

    abs_val = abs(value)
    sign = "-" if value < 0 else ""

    if abs_val >= 1e9:
        return f"{sign}${abs_val/1e9:.{precision}f}B"
    elif abs_val >= 1e6:
        return f"{sign}${abs_val/1e6:.{precision}f}M"
    elif abs_val >= 1e3:
        return f"{sign}${abs_val/1e3:.{precision}f}K"
    else:
        return f"{sign}${abs_val:.{precision}f}"


def calculate_working_capital_gap(dso: float, dpo: float) -> float:

    return dso - dpo


def calculate_capital_tied_up(daily_revenue: float, gap_days: float) -> float:
    return daily_revenue * gap_days
