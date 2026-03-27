import time
import json
from json import dumps as json_dumps
from json import loads as json_loads
from random import shuffle
from websocket import create_connection as wss

NODES = [
    "wss://api.bts.mobi",
    "wss://api.61bts.com/ws",
    "wss://cloud.xbts.io/ws",
    "wss://eu.nodes.bitshares.ws",
    "wss://api.dex.trading",
]

class BitSharesRPC:
    def __init__(self, nodes=None):
        self.nodes = nodes or NODES
        self.rpc = None
        self.database_api = None
        self.history_api = None
        self.broadcast_api = None

    def connect(self):
        nodes = self.nodes[::]
        shuffle(nodes)
        for node in nodes:
            try:
                self.rpc = wss(node, timeout=5)
                # Get API handles
                self.database_api = self.query(["database", [], "database"])
                self.broadcast_api = self.query(["network_broadcast", [], "network_broadcast"])
                self.history_api = self.query(["history", [], "history"])
                print(f"Successfully connected to {node}!")
                return True
            except Exception as e:
                print(f"Failed to connect to {node}: {e}")
        return False

    def query(self, params, api_id=1):
        """
        params: [api_name, method_name, args]
        """
        query = json_dumps({
            "method": "call",
            "params": params,
            "jsonrpc": "2.0",
            "id": 1
        })
        self.rpc.send(query)
        ret = json_loads(self.rpc.recv())
        if "error" in ret:
            raise Exception(f"RPC Error: {ret['error']}")
        return ret.get("result")

    def get_objects(self, ids):
        return self.query([self.database_api, "get_objects", [ids]])

    def get_account_by_name(self, name):
        return self.query([self.database_api, "get_account_by_name", [name]])

    def get_asset_by_symbol(self, symbol):
        ret = self.query([self.database_api, "lookup_asset_symbols", [[symbol]]])
        return ret[0] if ret else None

    def get_dynamic_global_properties(self):
        return self.query([self.database_api, "get_dynamic_global_properties", []])

    def get_required_fees(self, operations, asset_id="1.3.0"):
        return self.query([self.database_api, "get_required_fees", [operations, asset_id]])

    def close(self):
        if self.rpc:
            self.rpc.close()

def get_client(mock=False):
    if mock:
        return MockRPC()
    client = BitSharesRPC()
    if client.connect():
        return client
    return None

class MockRPC:
    def connect(self): return True
    def get_objects(self, ids): return [{"id": i} for i in ids]
    def get_account_by_name(self, name): return {"id": "1.2.999", "name": name}
    def get_asset_by_symbol(self, symbol): return {"id": "1.3.0", "symbol": symbol, "precision": 5}
    def get_dynamic_global_properties(self):
        return {
            "head_block_number": 1234567,
            "head_block_id": "0012d68700000000000000000000000000000000",
            "time": "2026-03-22T12:00:00"
        }
    def get_required_fees(self, ops, asset): return [{"amount": 100, "asset_id": asset} for _ in ops]
    def close(self): pass
