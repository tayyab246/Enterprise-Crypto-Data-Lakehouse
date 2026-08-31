import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Security, Query, Depends, status
from fastapi.security import APIKeyHeader
from supabase import create_client, Client
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="Secure Crypto Gateway API", version="1.1.0")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header.")
    
    # ERROR HANDLING: Wrap auth query in try/except
    try:
        response = supabase.table("api_keys").select("client_name, is_active").eq("key_value", api_key).execute()
    except Exception as e:
        logger.error(f"Database authentication error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal authentication error.")
    
    if not response.data or not response.data[0].get("is_active"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or inactive API Key.")
    
    return response.data[0]

class CreateKeyRequest(BaseModel):
    client_name: str

@app.post("/api/v1/keys/generate", status_code=status.HTTP_201_CREATED)
def generate_api_key(body: CreateKeyRequest, admin: dict = Depends(verify_api_key)):
    try:
        new_key = f"crypto_live_{secrets.token_urlsafe(32)}"
        supabase.table("api_keys").insert({
            "key_value": new_key,
            "client_name": body.client_name,
            "is_active": True
        }).execute()
        return {"status": "success", "client_name": body.client_name, "api_key": new_key}
    except Exception as e:
        logger.error(f"Failed to generate key: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to provision API key.")
@app.get("/api/v1/crypto/range")
def get_crypto_range(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    coin_id: str = Query("bitcoin"),
    client: dict = Depends(verify_api_key)
):
    try:
        now_utc = datetime.now(timezone.utc)
        retention_limit = (now_utc - timedelta(days=1095)).date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else now_utc.date()
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else end_date_obj - timedelta(days=30)

        if start_date_obj < retention_limit:
            start_date_obj = retention_limit

        start_iso = datetime.combine(start_date_obj, datetime.min.time(), tzinfo=timezone.utc).isoformat()
        end_iso = datetime.combine(end_date_obj, datetime.max.time(), tzinfo=timezone.utc).isoformat()

        response = (
            supabase.table("crypto_metrics")
            .select("coin_id, datetime_utc, price, market_cap, total_volume")
            .eq("coin_id", coin_id)
            .gte("datetime_utc", start_iso)
            .lte("datetime_utc", end_iso)
            .order("datetime_utc", desc=False)
            .execute()
        )

        # DATA CLEANING: Ensure no null prices are passed to consumers
        cleaned_data = [row for row in response.data if row.get("price") is not None]

        return {
            "status": "success",
            "authenticated_as": client.get("client_name"),
            "count": len(cleaned_data),
            "data": cleaned_data
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    except Exception as e:
        logger.error(f"Database fetch error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while retrieving crypto metrics.")
