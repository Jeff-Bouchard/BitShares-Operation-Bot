# BOB: BitShares Operations Bot 🤖

BOB is a specialized AI assistant built on the ultra-lightweight `nanobot` framework, designed exclusively for interacting with the BitShares blockchain. 

BOB can understand natural language requests and construct complex BitShares operations for you. Instead of asking for your private keys, BOB securely generates `rawbitshares://` deeplinks so you can sign and broadcast transactions safely using your preferred wallet apps (like Beet).

## Core Features

- **Transfers**: Send assets to any BitShares account.
- **DEX Trading**: Place limit orders on the decentralized exchange with minimum receive protections.
- **Credit Offers**: Accept P2P credit deals and manage collateral.
- **Liquidity Pool Routing**: Find the most optimal jump-paths between assets using the built-in pool router skill.
- **Native Telegram Integration**: Talk to BOB directly from your phone.

## 🚀 Getting Started

BOB runs easily in Docker and connects directly to your Telegram bot.

### 1. Configure BOB

First, you need to set up your Telegram bot and choose an LLM provider (like OpenRouter).

1. Copy the example configuration file:
   ```bash
   cp config.json.example ~/.nanobot/config.json
   ```
2. Edit `~/.nanobot/config.json`:
   - Add your **OpenRouter API Key** (or another provider you prefer).
   - Add your **Telegram Bot Token** (get this from `@BotFather` on Telegram).
   - Add your **Telegram User ID** to the `allowFrom` list so only *you* can talk to BOB.

### 2. Run with Docker

Use Docker Compose to spin up BOB in the background:

```bash
docker-compose up -d
```

### 3. Start Chatting!

Open Telegram, find your bot, and try these commands:

- "BOB, what operations can you perform?"
- "Send 100 BTS to `init1`"
- "Sell 50 XBTSX.USDT for at least 0.05 BTC"
- "Accept credit offer `1.21.667` for 500 BTS using 1000 XBTSX.WRAM as collateral"
- "Find the best path to swap BTS for HONEST.MONEY"

BOB will respond with a summary of the operation and a `rawbitshares://` link. Tap the link on your device to open your wallet and confirm the transaction!

## Architecture Details

BOB relies on the `bitshares-ops` skill (located in `nanobot/skills/bitshares-ops/`). This skill contains:
- `ops.py`: The operation constructor and deeplink generator.
- `rpc_client.py`: A lightweight JSON-RPC client capable of querying multiple BitShares public nodes.

For testing without an active connection or keys, BOB includes a `--mock` mode in local CLI usage.
