import os
import requests
import logging
import time
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

# Setup basic logging for error tracking
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_and_store_daily_crypto():
    # Restricted to the top 3 coins to respect the 500MB DB limit
    target_coins = ["bitcoin", "ethereum", "tether"]
    
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(hours=24)
    
    from_ts = int(start_dt.timestamp())
    to_ts = int(end_dt.timestamp())
    
    headers = {"accept": "application/json"}
    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY

    for coin_id in target_coins:
        base_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
        params = {"vs_currency": "usd", "from": from_ts, "to": to_ts}
        
        # ERROR HANDLING: Catch network errors and bad HTTP responses
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Network or API Error for {coin_id}: {e}")
            time.sleep(5)
            continue
            
        # ERROR HANDLING: Ensure response is valid JSON
        try:
            raw_json = response.json()
        except ValueError as e:
            logger.error(f"Failed to parse JSON response for {coin_id}: {e}")
            time.sleep(5)
            continue
            
        prices = raw_json.get("prices", [])
        market_caps = raw_json.get("market_caps", [])
        total_volumes = raw_json.get("total_volumes", [])
        
        records = []
        for i in range(len(prices)):
            try:
                ts_ms = prices[i][0]
                price = prices[i][1]
                
                # DATA CLEANING: Skip records with invalid, zero, or negative prices
                if price is None or price <= 0:
                    logger.warning(f"Invalid price data {price} at timestamp {ts_ms} for {coin_id}. Skipping.")
                    continue
                    
                dt_utc = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
                
                # DATA CLEANING: Fallback to 0.0 if market cap or volume is missing/null
                m_cap = market_caps[i][1] if i < len(market_caps) and market_caps[i][1] is not None else 0.0
                vol = total_volumes[i][1] if i < len(total_volumes) and total_volumes[i][1] is not None else 0.0
                
                records.append({
                    "coin_id": coin_id,
                    "timestamp_ms": ts_ms,
                    "datetime_utc": dt_utc,
                    "price": price,
                    "market_cap": m_cap,
                    "total_volume": vol
                })
            except Exception as e:
                logger.error(f"Error parsing record at index {i} for {coin_id}: {e}")
                continue
                
        if not records:
            logger.warning(f"No valid records found for {coin_id} after data cleaning. Exiting current loop.")
            time.sleep(5)
            continue
            
        # ERROR HANDLING: Catch database connection/insertion issues
        try:
            supabase.table("crypto_metrics").upsert(records, on_conflict="coin_id, timestamp_ms").execute()
            logger.info(f"Successfully processed {len(records)} records for {coin_id}.")
        except Exception as e:
            logger.error(f"Supabase database operation failed for {coin_id}: {e}")
            
        # Sleep to avoid hitting CoinGecko rate limits across coins
        time.sleep(5)
        
    # ERROR HANDLING: Ensure purge operations are wrapped to prevent pipeline failure
    try:
        purge_cutoff = (now_utc - timedelta(days=1095)).isoformat()
        supabase.table("crypto_metrics").delete().lt("datetime_utc", purge_cutoff).execute()
        logger.info("Successfully enforced 3-year data purge.")
    except Exception as e:
        logger.error(f"Supabase database purge failed: {e}")

if __name__ == "__main__":
    fetch_and_store_daily_crypto()
