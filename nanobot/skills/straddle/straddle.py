#!/usr/bin/env python3
"""
Straddle Limit Orders — BOBv2 Standalone CLI Skill

Places two simultaneous limit_order_create operations (op_type 1) straddling
a market price by a configurable spread percentage. Self-contained script
with its own RPC client, price fetching, and transaction assembly.

All trading pairs are quoted in XBTSX.USDT (1.3.5589, precision 6).

Usage:
    python3 straddle.py --account johnr --market BTS/XBTSX.USDT --spread 2.0 --size 10000
    python3 straddle.py --account johnr --spread 3.0 --size 50000 --price 0.0015
    python3 straddle.py --account johnr --spread 2.0 --size 10000 --cancel 1.7.12345,1.7.12346
"""

import argparse
import json
import sys
import struct
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request

# ── Constants ────────────────────────────────────────────────────────────────

QUOTE_ASSET_ID = "1.3.5589"
QUOTE_PRECISION = 6
ORDER_EXPIRY_SECONDS = 86400  # 24 hours

NODES = [
    "wss://api.bts.mobi/ws",
    "wss://dex.iobanker.com/ws",
    "wss://node.xbts.io/ws",
]

# ── Asset Registry ───────────────────────────────────────────────────────────

ASSET_REGISTRY = {
    "BTS/XBTSX.USDT": {
        "base_asset_id": "1.3.0",
        "base_precision": 5,
        "base_symbol": "BTS",
        "coinpaprika_id": "bts-bitshares",
    },
}

# ── Minimal RPC Client ──────────────────────────────────────────────────────

class RPC:
    """Minimal BitShares WebSocket RPC client."""

    def __init__(self, nodes=None):
        self.nodes = nodes or NODES
        self.ws = None
        self.db_api = None

    def connect(self):
        from websocket import create_connection
        from random import shuffle
        nodes = self.nodes[:]
        shuffle(nodes)
        for node in nodes:
            try:
                self.ws = create_connection(node, timeout=10)
                self.db_api = self._call(1, "database", [])
                print(f"[+] Connected to {node}", file=sys.stderr)
                return True
            except Exception as e:
                print(f"[-] Failed: {node}: {e}", file=sys.stderr)
        return False

    def _call(self, api_id, method, params):
        payload = json.dumps({
            "method": "call",
            "params": [api_id, method, params],
            "jsonrpc": "2.0",
            "id": 1
        })
        self.ws.send(payload)
        resp = json.loads(self.ws.recv())
        if "error" in resp:
            raise Exception(f"RPC Error: {resp['error']}")
        return resp.get("result")

    def db(self, method, params):
        return self._call(self.db_api, method, params)

    def get_account_by_name(self, name):
        return self.db("get_account_by_name", [name])

    def get_dynamic_global_properties(self):
        return self.db("get_dynamic_global_properties", [])

    def get_limit_orders(self, base_id, quote_id, limit=100):
        return self.db("get_limit_orders", [base_id, quote_id, limit])

    def close(self):
        if self.ws:
            self.ws.close()


# ── Price Fetching ───────────────────────────────────────────────────────────

FALLBACK_PRICES = {"BTS": 0.0012, "BTC": 73000.0, "XAUT": 4800.0, "XRP": 2.74}


def fetch_usd_price(coin_id):
    """Fetch USD price from Coinpaprika."""
    url = f"https://api.coinpaprika.com/v1/tickers/{coin_id}"
    try:
        req = Request(url, headers={"User-Agent": "straddle-bob/1.0"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        usd = data.get("quotes", {}).get("USD", {}).get("price")
        if not isinstance(usd, (int, float)) or usd <= 0:
            raise ValueError("bad price")
        return usd
    except Exception:
        return None


# ── Transaction Building ────────────────────────────────────────────────────

def get_tx_header(rpc):
    """Build transaction header from chain state."""
    props = rpc.get_dynamic_global_properties()
    ref_block_num = props["head_block_number"] & 0xFFFF
    prefix_hex = props["head_block_id"][8:16]
    ref_block_prefix = struct.unpack("<I", bytes.fromhex(prefix_hex))[0]
    expiration = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "ref_block_num": ref_block_num,
        "ref_block_prefix": ref_block_prefix,
        "expiration": expiration,
    }


def build_limit_order_op(seller_id, sell_amount, sell_asset_id, receive_amount, receive_asset_id, expiration):
    """Build a limit_order_create operation (op_type 1)."""
    return [1, {
        "fee": {"amount": 0, "asset_id": "1.3.0"},
        "seller": seller_id,
        "amount_to_sell": {"amount": sell_amount, "asset_id": sell_asset_id},
        "min_to_receive": {"amount": receive_amount, "asset_id": receive_asset_id},
        "expiration": expiration,
        "fill_or_kill": False,
        "extensions": []
    }]


def build_cancel_op(account_id, order_id):
    """Build a limit_order_cancel operation (op_type 2)."""
    return [2, {
        "fee": {"amount": 0, "asset_id": "1.3.0"},
        "fee_paying_account": account_id,
        "order": order_id,
        "extensions": []
    }]


def generate_deeplink(tx):
    """Generate a rawbitshares:// deep link from a transaction."""
    import base64
    tx_json = json.dumps(tx)
    encoded = base64.b64encode(tx_json.encode()).decode()
    return f"rawbitshares://tx/{encoded}"


# ── Main Logic ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BOB Straddle Limit Orders Tool")
    parser.add_argument("--account", required=True, help="BitShares account name (resolved on-chain)")
    parser.add_argument("--market", default="BTS/XBTSX.USDT", help="Market key (e.g. BTS/XBTSX.USDT)")
    parser.add_argument("--spread", type=float, required=True, help="Half-spread percentage (e.g. 2.0 for ±2%%)")
    parser.add_argument("--size", type=float, required=True, help="Order size in base asset units per side")
    parser.add_argument("--price", type=float, default=None, help="Override market price")
    parser.add_argument("--cancel", type=str, default=None, help="Comma-separated order IDs to cancel (1.7.x)")
    parser.add_argument("--mock", action="store_true", help="Use mock RPC (for testing)")
    args = parser.parse_args()

    # ── Validate inputs ──
    if args.market not in ASSET_REGISTRY:
        print(json.dumps({"status": "error", "message": f"Unknown market: {args.market}. Supported: {list(ASSET_REGISTRY.keys())}"}))
        sys.exit(1)
    if args.spread <= 0 or args.spread > 50:
        print(json.dumps({"status": "error", "message": f"spread must be in (0, 50], got {args.spread}"}))
        sys.exit(1)
    if args.size <= 0:
        print(json.dumps({"status": "error", "message": f"size must be > 0, got {args.size}"}))
        sys.exit(1)

    entry = ASSET_REGISTRY[args.market]
    base_precision = entry["base_precision"]

    # ── Connect to chain ──
    rpc = RPC()
    if not rpc.connect():
        print(json.dumps({"status": "error", "message": "Failed to connect to any BitShares node"}))
        sys.exit(1)

    try:
        # ── Resolve account ──
        acct = rpc.get_account_by_name(args.account)
        if not acct:
            print(json.dumps({"status": "error", "message": f"Account '{args.account}' not found on-chain"}))
            sys.exit(1)
        account_id = acct["id"]

        # ── Get market price ──
        market_price = args.price
        if market_price is None:
            coin_id = entry.get("coinpaprika_id")
            if coin_id:
                market_price = fetch_usd_price(coin_id)
            if not market_price:
                fallback_key = entry["base_symbol"]
                market_price = FALLBACK_PRICES.get(fallback_key)
                print(f"[!] Using fallback price for {fallback_key}: {market_price}", file=sys.stderr)
            if not market_price or market_price <= 0:
                print(json.dumps({"status": "error", "message": "Could not fetch market price and no fallback available"}))
                sys.exit(1)

        # ── Calculate prices ──
        mp = Decimal(str(market_price))
        spread = Decimal(str(args.spread))
        buy_price = mp * (1 - spread / 100)
        sell_price = mp * (1 + spread / 100)
        size = Decimal(str(args.size))

        # Buy side: spend USDT, receive base
        buy_sell_raw = int(round(size * buy_price * Decimal(10 ** QUOTE_PRECISION)))
        buy_recv_raw = int(round(size * Decimal(10 ** base_precision)))

        # Sell side: spend base, receive USDT
        sell_sell_raw = int(round(size * Decimal(10 ** base_precision)))
        sell_recv_raw = int(round(size * sell_price * Decimal(10 ** QUOTE_PRECISION)))

        # Underflow check
        for name, val in [("buy_sell", buy_sell_raw), ("buy_recv", buy_recv_raw),
                          ("sell_sell", sell_sell_raw), ("sell_recv", sell_recv_raw)]:
            if val < 1:
                print(json.dumps({"status": "error", "message": f"PrecisionUnderflow: {name} rounds to 0. Increase --size."}))
                sys.exit(1)

        # ── Order expiration ──
        order_exp = (datetime.now(timezone.utc) + timedelta(seconds=ORDER_EXPIRY_SECONDS)).strftime("%Y-%m-%dT%H:%M:%S")

        # ── Build operations ──
        ops = []
        cancelled = []

        # Cancel ops (if requested)
        if args.cancel:
            for oid in args.cancel.split(","):
                oid = oid.strip()
                if oid.startswith("1.7."):
                    ops.append(build_cancel_op(account_id, oid))
                    cancelled.append(oid)

        # Buy op
        buy_op = build_limit_order_op(
            account_id, buy_sell_raw, QUOTE_ASSET_ID,
            buy_recv_raw, entry["base_asset_id"], order_exp
        )
        ops.append(buy_op)

        # Sell op
        sell_op = build_limit_order_op(
            account_id, sell_sell_raw, entry["base_asset_id"],
            sell_recv_raw, QUOTE_ASSET_ID, order_exp
        )
        ops.append(sell_op)

        # ── Assemble transaction ──
        header = get_tx_header(rpc)
        tx = {
            "ref_block_num": header["ref_block_num"],
            "ref_block_prefix": header["ref_block_prefix"],
            "expiration": header["expiration"],
            "operations": ops,
            "extensions": [],
            "signatures": []
        }

        deeplink = generate_deeplink(tx)

        result = {
            "status": "success",
            "operation": "straddle_limit_orders",
            "account": args.account,
            "account_id": account_id,
            "market": args.market,
            "market_price": float(mp),
            "buy_price": float(buy_price),
            "sell_price": float(sell_price),
            "spread_pct": args.spread,
            "order_size": args.size,
            "summary": (
                f"Straddle on {args.market}: "
                f"BUY {args.size} {entry['base_symbol']} @ {float(buy_price):.8f} | "
                f"SELL {args.size} {entry['base_symbol']} @ {float(sell_price):.8f} "
                f"(±{args.spread}% spread)"
            ),
            "cancelled_orders": cancelled,
            "operation_count": len(ops),
            "tx": tx,
            "deeplink": deeplink,
        }

        print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, indent=2))
    finally:
        rpc.close()


if __name__ == "__main__":
    main()
