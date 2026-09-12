"""
MCP Server for FinFlow AI - Financial Interface Generator
Provides tools for financial data retrieval and analysis.
Uses the official MCP Python SDK v1 FastMCP server.
"""

import json
import random
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP

server = FastMCP("finflow-financial-tools")


# ─── MCP Tool Definitions (using .tool() decorator) ──────────────────────────

@server.tool()
def get_stock_quote(symbol: str) -> str:
    """
    Get a simulated real-time stock quote for a given ticker symbol.
    Returns price, change, volume, and market cap as JSON.
    """
    base_prices = {
        "AAPL": 189.50, "MSFT": 415.20, "GOOGL": 175.80, "AMZN": 198.40,
        "META": 502.30, "NVDA": 875.60, "TSLA": 248.90, "JPM": 198.70,
        "BAC": 38.20, "GS": 512.40, "BTC": 67450.00, "ETH": 3820.00,
        "CEMEX": 8.45, "AMXL": 15.30, "WALMEX": 87.20, "GFNORTEO": 145.80,
    }
    price = base_prices.get(symbol.upper(), random.uniform(50, 500))
    change_pct = random.uniform(-5, 5)
    change = price * change_pct / 100
    result = {
        "symbol": symbol.upper(),
        "price": round(price + change * random.uniform(0.8, 1.2), 2),
        "change": round(change, 2),
        "change_percent": round(change_pct, 2),
        "volume": random.randint(1_000_000, 50_000_000),
        "market_cap": f"{random.uniform(100, 3000):.1f}B",
        "high_52w": round(price * 1.35, 2),
        "low_52w": round(price * 0.65, 2),
        "timestamp": datetime.now().isoformat(),
    }
    return json.dumps(result)


@server.tool()
def get_portfolio_summary(holdings: list[str]) -> str:
    """
    Get a portfolio summary with total value, gains/losses, and position allocation.
    holdings: list of ticker symbols e.g. ['AAPL', 'MSFT', 'GOOGL']
    """
    positions = []
    total_value = 0.0
    total_cost = 0.0

    for symbol in holdings:
        data = json.loads(get_stock_quote(symbol))
        price = data["price"]
        shares = random.randint(5, 200)
        cost_basis = price * random.uniform(0.75, 1.25)
        value = price * shares
        gain = (price - cost_basis) * shares
        total_value += value
        total_cost += cost_basis * shares
        positions.append({
            "symbol": symbol.upper(),
            "shares": shares,
            "current_price": price,
            "cost_basis": round(cost_basis, 2),
            "market_value": round(value, 2),
            "unrealized_gain": round(gain, 2),
            "gain_percent": round((price / cost_basis - 1) * 100, 2),
            "weight": 0.0,
        })

    for p in positions:
        p["weight"] = round(p["market_value"] / total_value * 100, 2)

    result = {
        "total_market_value": round(total_value, 2),
        "total_cost_basis": round(total_cost, 2),
        "total_unrealized_gain": round(total_value - total_cost, 2),
        "total_return_percent": round((total_value / total_cost - 1) * 100, 2),
        "positions": positions,
        "as_of": datetime.now().isoformat(),
    }
    return json.dumps(result)


@server.tool()
def get_market_indices() -> str:
    """
    Get current values for major market indices: S&P 500, NASDAQ, Dow Jones, IPC Mexico, FTSE 100.
    """
    indices = {
        "SP500":  {"name": "S&P 500",    "base": 5432.10},
        "NASDAQ": {"name": "NASDAQ",     "base": 17580.50},
        "DOW":    {"name": "Dow Jones",  "base": 41250.80},
        "IPC":    {"name": "IPC Mexico", "base": 53840.20},
        "FTSE":   {"name": "FTSE 100",   "base": 8320.40},
    }
    result = {}
    for key, idx in indices.items():
        change_pct = random.uniform(-2, 2)
        change = idx["base"] * change_pct / 100
        result[key] = {
            "name": idx["name"],
            "value": round(idx["base"] + change, 2),
            "change": round(change, 2),
            "change_percent": round(change_pct, 2),
        }
    return json.dumps(result)


@server.tool()
def analyze_credit_risk(
    annual_income: float,
    requested_amount: float,
    credit_score: int,
    employment_years: float,
    existing_debt: float,
) -> str:
    """
    Analyze credit risk for a loan application.
    Returns risk score (0-100), recommendation (APPROVE/DECLINE/CONDITIONAL_APPROVE), and risk factors.
    """
    debt_to_income = (existing_debt + requested_amount * 0.05) / annual_income
    loan_to_income = requested_amount / annual_income
    score = 100
    factors = []

    if credit_score >= 750: score += 20
    elif credit_score >= 700: score += 10
    elif credit_score >= 650: score -= 10
    else:
        score -= 30
        factors.append({"factor": "Credit Score", "impact": "HIGH", "note": f"Score {credit_score} is below preferred threshold of 650"})

    if debt_to_income < 0.30: score += 15
    elif debt_to_income < 0.43: score += 5
    else:
        score -= 25
        factors.append({"factor": "Debt-to-Income", "impact": "HIGH", "note": f"DTI of {debt_to_income:.1%} exceeds 43% threshold"})

    if employment_years >= 2: score += 10
    elif employment_years < 1:
        score -= 15
        factors.append({"factor": "Employment", "impact": "MEDIUM", "note": "Less than 1 year at current employer"})

    if loan_to_income > 5:
        score -= 20
        factors.append({"factor": "Loan Amount", "impact": "MEDIUM", "note": f"Requested amount is {loan_to_income:.1f}x annual income"})

    score = max(0, min(100, score))
    if score >= 75: recommendation, risk_level = "APPROVE", "LOW"
    elif score >= 55: recommendation, risk_level = "CONDITIONAL_APPROVE", "MEDIUM"
    else: recommendation, risk_level = "DECLINE", "HIGH"

    result = {
        "risk_score": score,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "debt_to_income_ratio": round(debt_to_income, 4),
        "loan_to_income_ratio": round(loan_to_income, 2),
        "risk_factors": factors,
        "suggested_interest_rate": round(5.5 + (100 - score) * 0.15, 2),
        "analysis_date": datetime.now().isoformat(),
    }
    return json.dumps(result)


@server.tool()
def get_historical_prices(symbol: str, days: int = 30) -> str:
    """
    Get simulated historical OHLCV price data for a stock symbol, suitable for chart rendering.
    """
    base_prices = {
        "AAPL": 189.50, "MSFT": 415.20, "GOOGL": 175.80,
        "NVDA": 875.60, "TSLA": 248.90, "BTC": 67450.00,
    }
    base = base_prices.get(symbol.upper(), 150.0)
    data = []
    current = base * random.uniform(0.85, 0.95)

    for i in range(days, 0, -1):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_change = current * random.uniform(-0.04, 0.04)
        open_p = current
        close_p = current + daily_change
        high_p = max(open_p, close_p) * random.uniform(1.0, 1.02)
        low_p = min(open_p, close_p) * random.uniform(0.98, 1.0)
        data.append({
            "date": date,
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": random.randint(5_000_000, 80_000_000),
        })
        current = close_p

    result = {
        "symbol": symbol.upper(),
        "period_days": days,
        "data": data,
        "start_price": data[0]["close"],
        "end_price": data[-1]["close"],
        "total_return": round((data[-1]["close"] / data[0]["close"] - 1) * 100, 2),
    }
    return json.dumps(result)


@server.tool()
def get_financial_news(category: str = "markets") -> str:
    """
    Get simulated financial news headlines with sentiment scores.
    category options: markets, crypto, economy, mexico
    """
    news_db = {
        "markets": [
            {"title": "S&P 500 Reaches New All-Time High Amid Tech Rally", "sentiment": "positive", "source": "Reuters"},
            {"title": "Federal Reserve Signals Rate Cut Timeline for Q4", "sentiment": "positive", "source": "Bloomberg"},
            {"title": "Global Markets Mixed as Geopolitical Tensions Rise", "sentiment": "neutral", "source": "FT"},
            {"title": "Institutional Investors Rotate from Growth to Value Stocks", "sentiment": "neutral", "source": "WSJ"},
        ],
        "crypto": [
            {"title": "Bitcoin Surges Past $67,000 on ETF Inflow Momentum", "sentiment": "positive", "source": "CoinDesk"},
            {"title": "Ethereum Upgrade Reduces Transaction Fees by 40%", "sentiment": "positive", "source": "Decrypt"},
            {"title": "Regulatory Clarity Boosts Institutional Crypto Adoption", "sentiment": "positive", "source": "Bloomberg"},
        ],
        "mexico": [
            {"title": "Banxico Holds Rate at 11% Amid Inflation Concerns", "sentiment": "neutral", "source": "El Financiero"},
            {"title": "IPC Alcanza Maximo de 6 Meses por Nearshoring", "sentiment": "positive", "source": "Expansion"},
            {"title": "PEMEX Reporta Reduccion en Deuda Neta", "sentiment": "positive", "source": "BMV"},
            {"title": "Grupo Financiero Banorte Supera Estimados de Utilidades", "sentiment": "positive", "source": "Milenio"},
        ],
        "economy": [
            {"title": "US GDP Growth Revised Upward to 3.1% for Q2", "sentiment": "positive", "source": "BEA"},
            {"title": "Unemployment Rate Holds Steady at 3.8%", "sentiment": "neutral", "source": "BLS"},
            {"title": "Core Inflation Cools to 2.6%, Nearing Fed Target", "sentiment": "positive", "source": "CPI Report"},
        ],
    }
    items = list(news_db.get(category, news_db["markets"]))
    for item in items:
        item["published_at"] = (datetime.now() - timedelta(hours=random.randint(1, 24))).strftime("%Y-%m-%dT%H:%M:%S")
    return json.dumps(items)


@server.tool()
def calculate_compound_interest(
    principal: float,
    annual_rate: float,
    years: int,
    compounds_per_year: int = 12,
    monthly_contribution: float = 0.0,
) -> str:
    """
    Calculate compound interest growth with optional monthly contributions.
    Returns final balance, total contributions, interest earned, and yearly breakdown.
    """
    yearly_data = []
    balance = principal

    for year in range(1, years + 1):
        for _ in range(compounds_per_year):
            balance = balance * (1 + annual_rate / 100 / compounds_per_year)
            balance += monthly_contribution
        yearly_data.append({
            "year": year,
            "balance": round(balance, 2),
            "contributions": round(principal + monthly_contribution * 12 * year, 2),
            "interest_earned": round(balance - principal - monthly_contribution * 12 * year, 2),
        })

    total_contributions = principal + monthly_contribution * 12 * years
    result = {
        "final_balance": round(balance, 2),
        "total_contributions": round(total_contributions, 2),
        "total_interest_earned": round(balance - total_contributions, 2),
        "return_on_investment": round((balance / total_contributions - 1) * 100, 2),
        "yearly_breakdown": yearly_data,
    }
    return json.dumps(result)


@server.tool()
def get_forex_rates(base_currency: str = "USD") -> str:
    """
    Get simulated foreign exchange rates relative to a base currency.
    Supports: USD, EUR, MXN, GBP, JPY, CAD, AUD, CHF, CNY, BRL
    """
    usd_rates = {
        "EUR": 0.9245, "GBP": 0.7892, "JPY": 149.82, "MXN": 17.45,
        "CAD": 1.3621, "AUD": 1.5234, "CHF": 0.8921, "CNY": 7.2340,
        "BRL": 5.0123, "ARS": 900.50, "CLP": 935.20, "COP": 4150.30,
    }

    def noise(x):
        return round(x * random.uniform(0.995, 1.005), 4)

    if base_currency.upper() == "USD":
        rates = {k: noise(v) for k, v in usd_rates.items()}
    else:
        base_rate = usd_rates.get(base_currency.upper(), 1.0)
        rates = {k: round(noise(v) / base_rate, 4) for k, v in usd_rates.items() if k != base_currency.upper()}
        rates["USD"] = round(1 / base_rate, 4)

    result = {
        "base": base_currency.upper(),
        "timestamp": datetime.now().isoformat(),
        "rates": rates,
    }
    return json.dumps(result)


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server.run(transport="stdio")
