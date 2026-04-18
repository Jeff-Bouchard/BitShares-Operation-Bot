---
name: bitshares-ops
description: General BitShares blockchain operations (Transfer, DEX Orders, Credit Offers).
metadata: {"nanobot":{"emoji":"🤖","requires":{"bins":["python3"]}}}
---

# BitShares Operations (BOB)

This skill allows BOB to perform various operations on the BitShares blockchain, including sending assets, placing limit orders on the DEX, and managing P2P credit offers.

## Usage Examples

- **Transfer**: "BOB, send 100 BTS to account `init1`"
- **Balance**: "BOB, what's the balance of account `my-account`?"
- **Limit Order**: "BOB, sell 50 XBTSX.USDT for at least 0.05 BTC"
- **Credit Offer**: "BOB, accept credit offer `1.21.667` for 500 BTS with 1000 XBTSX.WRAM collateral"

## Tools

### General Operations Tool

Use `ops.py` to construct operations and generate `rawbitshares://` deeplinks.

```bash
python3 /path/to/skill/ops.py --op OPERATION [args]
```

#### Supported Operations:
- `transfer`: Requires `--from`, `--to`, `--amount`, `--asset`.
- `balance`: Requires `--from`.
- `limit_order`: Requires `--from`, `--amount`, `--asset`, `--target_asset`, `--min_receive`.
- `credit_accept`: Requires `--from`, `--amount`, `--asset`, `--offer_id`, `--collateral`, `--collateral_asset`.

#### Output Format (JSON):
The tool outputs a JSON object containing a `summary`, the full `tx` (transaction JSON), and a `deeplink`.

```json
{
  "status": "success",
  "operation": "transfer",
  "summary": "Transfer 10.0 BTS from account1 to account2",
  "tx": { ... },
  "deeplink": "rawbitshares://tx/..."
}
```

## Internal Note
Always offer a `rawbitshares://` deeplink when an operation is requested. 
If `--mock` is used, the output will use placeholder data for block headers and account IDs.
