import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY


# --- Settings ---
WATCH_WALLET = ""   # paste target wallet here
MY_WALLET = ""      # your funder address
SECRET_KEY = ""     # your private key — do NOT commit
SIG_MODE = 1  # 0 = EOA, 1 = Magic/email, 2 = browser proxy

WAGER_USD = 1
PREVIEW_ONLY = False


# --- Endpoints ---
ENDPOINTS = {
    "data": "https://data-api.polymarket.com",
    "clob": "https://clob.polymarket.com",
    "gamma": "https://gamma-api.polymarket.com",
}


def fetch_display_name(addr):
    r = requests.get(f"{ENDPOINTS['gamma']}/public-profile", params={"address": addr})
    r.raise_for_status()
    data = r.json()
    fallback = addr[:10] + "..."
    return data.get("name") or data.get("pseudonym") or fallback


def fetch_open_positions(addr):
    r = requests.get(
        f"{ENDPOINTS['data']}/positions",
        params={"user": addr, "sizeThreshold": 0},
    )
    r.raise_for_status()
    return r.json()


def fetch_most_recent_buy(addr):
    r = requests.get(
        f"{ENDPOINTS['data']}/activity",
        params={"user": addr, "limit": 20},
    )
    r.raise_for_status()
    for item in r.json():
        is_trade = item.get("type") == "TRADE"
        is_buy = item.get("side") == "BUY"
        if is_trade and is_buy:
            return item
    return None


def position_exists(positions, condition_id, outcome_idx):
    needle = (condition_id, outcome_idx)
    haystack = {(p["conditionId"], p["outcomeIndex"]) for p in positions}
    return needle in haystack


def build_clob_client():
    c = ClobClient(
        ENDPOINTS["clob"],
        key=SECRET_KEY,
        chain_id=137,
        signature_type=SIG_MODE,
        funder=MY_WALLET,
    )
    c.set_api_creds(c.derive_api_key())
    return c


def submit_market_buy(c, asset_id, usd_amount):
    args = MarketOrderArgs(
        token_id=asset_id,
        amount=usd_amount,
        side=BUY,
        order_type=OrderType.FOK,
    )
    signed = c.create_market_order(args)
    c.post_order(signed, OrderType.FOK)


def run():
    name = fetch_display_name(WATCH_WALLET)

    print()
    print("-" * 60)
    print(f"Tracking: {name}")
    print(f"Stake per trade: ${WAGER_USD}")
    print(f"Mode: {'PREVIEW' if PREVIEW_ONLY else 'LIVE'}")
    print("-" * 60)
    print()

    print("Step 1: Pulling latest trade from target wallet")
    trade = fetch_most_recent_buy(WATCH_WALLET)
    if trade is None:
        print("  Nothing recent to mirror.")
        return

    market = trade["title"][:50]
    side = trade["outcome"]
    qty = trade["size"]
    px = trade["price"]

    print(f"  Market: {market}")
    print(f"  Bought: {qty:.1f} {side} @ {px * 100:.1f}c")

    print()
    print("Step 2: Reviewing your portfolio")
    mine = fetch_open_positions(MY_WALLET)
    if len(mine) > 0:
        print("  Currently holding:")
        for p in mine:
            print(f"    > {p['title'][:40]}: {p['outcome']}")
    else:
        print("  Portfolio is empty.")

    if position_exists(mine, trade["conditionId"], trade["outcomeIndex"]):
        print("  Already exposed to this market, skipping.")
        return

    print("  No overlap. Continuing.")

    print()
    print("Step 3: Executing")
    client = build_clob_client()
    if PREVIEW_ONLY:
        print(f"  [PREVIEW] would purchase ${WAGER_USD:.2f} of {side}")
    else:
        submit_market_buy(client, trade["asset"], WAGER_USD)
        print(f"  Filled: ${WAGER_USD:.2f} of {side}")


if __name__ == "__main__":
    try:
        run()
    except requests.HTTPError as err:
        code = err.response.status_code
        body = err.response.text
        print(f"\nAPI error {code}: {body}")
    except Exception as err:
        print(f"\nFailure: {err}")
