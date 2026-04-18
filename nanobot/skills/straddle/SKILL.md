---
name: straddle
description: Place symmetric buy/sell limit orders straddling a market price on the BitShares DEX.
metadata: {"nanobot":{"emoji":"📊","requires":{"bins":["python3"]}}}
---

# Straddle Limit Orders

This skill places **two simultaneous limit orders** on the BitShares DEX — one buy below and one sell above a market price — straddling it by a configurable spread percentage. It's a market-making primitive for creating symmetric exposure.

## Usage

```bash
python3 /path/to/skill/straddle.py --account ACCOUNT --market MARKET --spread PCT --size AMOUNT [--price OVERRIDE] [--cancel ORDER_IDS]
```

### Required Arguments
- `--account`: BitShares account name (resolved on-chain to `1.2.x`)
- `--spread`: Half-spread as percentage (e.g. `2.0` for ±2% around price)
- `--size`: Order size in base asset units per side (e.g. `10000` = 10,000 BTS)

### Optional Arguments
- `--market`: Market pair (default: `BTS/XBTSX.USDT`)
- `--price`: Override the auto-fetched market price
- `--cancel`: Comma-separated `1.7.x` order IDs to cancel in the same transaction

### Examples
- Place a basic straddle: `python3 straddle.py --account johnr --spread 2.0 --size 10000`
- With specific price: `python3 straddle.py --account myaccount --spread 3.0 --size 50000 --price 0.0015`
- Cancel and replace: `python3 straddle.py --account myaccount --spread 2.0 --size 10000 --cancel 1.7.12345,1.7.12346`

## Output Format (JSON)

```json
{
  "status": "success",
  "operation": "straddle_limit_orders",
  "account": "johnr",
  "market": "BTS/XBTSX.USDT",
  "market_price": 0.0012,
  "buy_price": 0.001176,
  "sell_price": 0.001224,
  "spread_pct": 2.0,
  "summary": "Straddle on BTS/XBTSX.USDT: BUY 10000 BTS @ 0.00117600 | SELL 10000 BTS @ 0.00122400 (±2.0% spread)",
  "tx": { ... },
  "deeplink": "rawbitshares://tx/..."
}
```

## Internal Notes
- All pairs are quoted in XBTSX.USDT (`1.3.5589`, precision 6)
- Orders expire after 24 hours
- The tool generates unsigned transactions — it never broadcasts
- Always offer the `deeplink` to the user for wallet signing
