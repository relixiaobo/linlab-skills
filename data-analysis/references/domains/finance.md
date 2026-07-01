# Domain: Finance

Use for market data, company fundamentals, portfolio/risk analytics, earnings, macro data, and screening.

## Core Concepts

- Price series need adjustment status: raw, split-adjusted, dividend-adjusted, total return.
- Returns should specify simple vs log return.
- Time alignment matters: market close, timezone, trading calendar, reporting lag.
- Fundamentals need period type: quarterly, annual, trailing twelve months.
- Currency and share class must be explicit.

## Common Analyses

- Return and volatility.
- Drawdown.
- Correlation and beta.
- Factor exposure.
- Valuation multiples.
- Earnings surprise.
- Screening by liquidity, market cap, sector, and quality filters.

## Pitfalls

- Lookahead bias from using future fundamentals.
- Survivorship bias in symbol universes.
- Mixing fiscal and calendar periods.
- Comparing unadjusted prices across splits.
- Treating backtest output as live performance.

## Reporting

Always state data vendor/source, timestamp, adjustment basis, universe, and whether outputs are investment advice. Prefer analytical language over recommendations unless explicitly requested and permitted.

