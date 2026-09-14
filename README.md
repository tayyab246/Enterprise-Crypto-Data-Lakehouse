# 📊 Enterprise Crypto Data Lakehouse & Secure API

A 100% free-tier, serverless data pipeline and analytics platform designed to extract, store, process, and serve multi-asset cryptocurrency metrics. This project demonstrates an end-to-end data engineering lifecycle, from automated ingestion to secure API distribution and interactive data visualization.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badges_black_white.svg)](https://enterprise-crypto-data-lakehouse.streamlit.app)

---

## 🏗️ System Architecture & Topography

This pipeline is built entirely on free-tier, serverless infrastructure, requiring no billing profiles. 

| Subsystem | Technology Choice | Purpose & Constraints |
| :--- | :--- | :--- |
| **Ingestion Engine** | GitHub Actions | Automated CRON job execution (2,000 free minutes/mo) pulling from source APIs. |
| **Processing Logic** | Python 3.10+ | Handles data extraction, normalization, and pushing data to the warehouse. |
| **Data Warehouse** | Supabase (Postgres) | 500MB Free tier database for storing historical metrics permanently. |
| **API Gateway** | Render + FastAPI | Serves as a robust middle-layer for data querying and access control. |
| **Visualization** | Streamlit Cloud | Frontend dashboard connected to APIs/DB natively, hosted entirely free. |

**Architecture Data Flow:**
1. **Trigger & Extract:** GitHub Actions runs on a schedule (e.g., 6:00 AM daily), requesting data from external APIs like CoinGecko.
2. **Load & Store:** Python scripts push sanitized records securely into the Supabase Postgres database. *(The daily insertion query prevents Supabase from automatically pausing the database after 7 days of inactivity).*
3. **Serve:** A FastAPI gateway on Render securely connects to Supabase and exposes standardized endpoints. *(Note: Render spins down the free web service after 15 minutes of inactivity; the first request may experience a 30-50 second cold start latency).*
4. **Consume:** The Streamlit dashboard queries the FastAPI endpoints and database to visualize parameters interactively.

---

## 📸 Dashboard Showcase

*(**Note to recruiter/reviewer:** The live dashboard is gated to protect database limits. Below are screenshots of the internal views.)*

### 1. Single Asset Analysis (Price & Volume Profile)
![Single Asset Analysis](./dashboard_preview2.png)

### 2. Comprehensive Market Comparison Suite
![Market Comparison](./dashboard_preview1.png)

---

## 🚀 Key Engineering Features

*   **Automated Data Governance:** Implements a rolling 3-year data retention purge to ensure the database stays within the 500MB storage limit.
*   **Data Cleaning:** Python extraction scripts handle network timeouts, validate JSON responses, and filter out null or negative financial records.
*   **Secure API Authentication:** The FastAPI gateway restricts access via custom `X-API-Key` headers, backed by cryptographic token generation.
*   **Advanced Analytics:** The Streamlit dashboard engineers on-the-fly KPIs like *Trading Velocity (Volume/Market Cap %)* and *Market Cap Dominance Share*.

---

## 🔐 Security & Local Setup

**Security Note:** For security purposes, all production API keys, database credentials, and service role keys have been removed from this public repository. Database connections require injected environment variables established directly in the hosting environment's secure panel.

To run this pipeline locally, you must create a `.env` file in the root directory and supply your own credentials. 

**1. Create a `.env` file based on this template:**
```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SUPABASE_ANON_KEY=your_supabase_anon_key
COINGECKO_API_KEY=your_coingecko_api_key_if_applicable
```

**2. Install Dependencies:**
```cmd
pip install -r requirements.txt
```

**3. Run the API Gateway Locally:**
```cmd
uvicorn main:app --host 0.0.0.0 --port 8000
```

*(If deploying to Render, the build command is ```pip install -r requirements.txt ```and the start command is ```uvicorn main:app --host 0.0.0.0 --port $PORT```).*

**4. Run the Streamlit Dashboard:**
```cmd
streamlit run app.py
```

## 📡 API Usage & Test Drive
**Once the FastAPI server is running, you can test the secure endpoints using curl.**

**1. Generate a New Client API Key:**
```cmd
curl -X POST "http://localhost:8000/api/v1/keys/generate" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your_master_admin_key" \
     -d '{"client_name": "Test Client"}'
```

**2. Fetch Crypto Metrics using the Generated Key:**

```cmd
curl -X GET "http://localhost:8000/api/v1/crypto/range?start_date=2026-01-01&coin_id=bitcoin" \
     -H "X-API-Key: crypto_live_your_generated_key_here"
```
