import argparse
import json
import sys
from datetime import datetime, timedelta
from rpc_client import get_client

def get_tx_header(client):
    props = client.get_dynamic_global_properties()
    head_block_number = props["head_block_number"]
    head_block_id = props["head_block_id"]
    head_block_time = props["time"]

    ref_block_num = head_block_number & 0xFFFF
    # Get bytes 4-8 of head_block_id (8-16 in hex)
    import struct
    prefix_hex = head_block_id[8:16]
    # Little-endian uint32
    ref_block_prefix = struct.unpack("<I", bytes.fromhex(prefix_hex))[0]

    # Expiration: time + 120s
    exp_time = datetime.strptime(head_block_time, "%Y-%m-%dT%H:%M:%S")
    expiration = (exp_time + timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%S")

    return {
        "ref_block_num": ref_block_num,
        "ref_block_prefix": ref_block_prefix,
        "expiration": expiration
    }

def construct_tx(client, ops):
    header = get_tx_header(client)
    tx = {
        "ref_block_num": header["ref_block_num"],
        "ref_block_prefix": header["ref_block_prefix"],
        "expiration": header["expiration"],
        "operations": ops,
        "extensions": [],
        "signatures": []
    }
    return tx

def generate_deeplink(tx):
    import base64
    tx_json = json.dumps(tx)
    # BitShares deeplink format often uses beeteos://tx/base64(json)
    # or just the json string if handled by a specific app.
    # For now, we'll provide a clear instruction and the JSON.
    encoded = base64.b64encode(tx_json.encode()).decode()
    return f"beeteos://tx/{encoded}"

def main():
    parser = argparse.ArgumentParser(description="BOB BitShares Operations Tool")
    parser.add_argument("--op", required=True, choices=["transfer", "balance", "limit_order", "credit_accept", "credit_repay"])
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--from", dest="from_acct")
    parser.add_argument("--to", dest="to_acct")
    parser.add_argument("--amount", type=float)
    parser.add_argument("--asset", default="BTS")
    parser.add_argument("--target_asset", help="Target asset for limit orders")
    parser.add_argument("--min_receive", type=float, help="Min to receive for limit orders")
    parser.add_argument("--offer_id", help="Credit offer ID")
    parser.add_argument("--deal_id", help="Credit deal ID")
    parser.add_argument("--collateral", type=float)
    parser.add_argument("--collateral_asset", default="BTS")

    args = parser.parse_args()
    client = get_client(mock=args.mock)

    try:
        if args.op == "transfer":
            from_obj = client.get_account_by_name(args.from_acct)
            to_obj = client.get_account_by_name(args.to_acct)
            asset_obj = client.get_asset_by_symbol(args.asset)

            amount_int = int(args.amount * (10 ** asset_obj["precision"]))
            
            op = [0, {
                "fee": {"amount": 0, "asset_id": "1.3.0"},
                "from": from_obj["id"],
                "to": to_obj["id"],
                "amount": {"amount": amount_int, "asset_id": asset_obj["id"]},
                "extensions": []
            }]
            
            tx = construct_tx(client, [op])
            print(json.dumps({
                "status": "success",
                "operation": "transfer",
                "summary": f"Transfer {args.amount} {args.asset} from {args.from_acct} to {args.to_acct}",
                "tx": tx,
                "deeplink": generate_deeplink(tx)
            }, indent=2))

        elif args.op == "balance":
            acct_obj = client.get_account_by_name(args.from_acct)
            # In a real tool, we'd query balances here. For now, mock or simple response.
            print(json.dumps({
                "status": "success",
                "account": args.from_acct,
                "id": acct_obj["id"],
                "message": f"Balance for {args.from_acct} requested. (Mock environment: 1000.00 BTS)"
            }, indent=2))

        elif args.op == "limit_order":
            from_obj = client.get_account_by_name(args.from_acct)
            sell_asset = client.get_asset_by_symbol(args.asset)
            receive_asset = client.get_asset_by_symbol(args.target_asset)
            
            sell_amt = int(args.amount * (10 ** sell_asset["precision"]))
            recv_amt = int(args.min_receive * (10 ** receive_asset["precision"]))

            op = [1, {
                "fee": {"amount": 0, "asset_id": "1.3.0"},
                "seller": from_obj["id"],
                "amount_to_sell": {"amount": sell_amt, "asset_id": sell_asset["id"]},
                "min_to_receive": {"amount": recv_amt, "asset_id": receive_asset["id"]},
                "expiration": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S"),
                "fill_or_kill": False,
                "extensions": []
            }]
            
            tx = construct_tx(client, [op])
            print(json.dumps({
                "status": "success",
                "operation": "limit_order_create",
                "summary": f"Sell {args.amount} {args.asset} for at least {args.min_receive} {args.target_asset}",
                "tx": tx,
                "deeplink": generate_deeplink(tx)
            }, indent=2))

        elif args.op == "credit_accept":
            borrower = client.get_account_by_name(args.from_acct)
            # offer_id is 1.21.x
            # borrow_amount and collateral 
            # We'll assume the offer exists for now (real tool would verify)
            asset_obj = client.get_asset_by_symbol(args.asset)
            collateral_obj = client.get_asset_by_symbol(args.collateral_asset)

            op = [75, {
                "fee": {"amount": 0, "asset_id": "1.3.0"},
                "borrower": borrower["id"],
                "offer_id": args.offer_id,
                "borrow_amount": {"amount": int(args.amount * 10**asset_obj["precision"]), "asset_id": asset_obj["id"]},
                "collateral": {"amount": int(args.collateral * 10**collateral_obj["precision"]), "asset_id": collateral_obj["id"]},
                "max_fee_rate": 1000,
                "min_duration_seconds": 3600,
                "extensions": []
            }]
            
            tx = construct_tx(client, [op])
            print(json.dumps({
                "status": "success",
                "operation": "credit_offer_accept",
                "summary": f"Accept credit offer {args.offer_id} for {args.amount} {args.asset}",
                "tx": tx,
                "deeplink": generate_deeplink(tx)
            }, indent=2))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, indent=2))
    finally:
        client.close()

if __name__ == "__main__":
    main()
