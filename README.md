# A.I.R.A. - Autonomous Investment Research Agent

An AI-powered financial analysis service that autonomously gathers market data, analyzes news sentiment, and generates investment research reports.

## What is AIRA?

AIRA is a backend service that acts like a tireless research assistant. You give it a stock ticker or company name, and it goes to work—fetching news articles, pulling financial data, analyzing sentiment, and synthesizing everything into a coherent analysis report. It can also watch stocks over time and alert you when something significant happens.

The interesting part is how it thinks. AIRA uses a reasoning pattern called ReAct (Reasoning + Acting), where it doesn't just execute a fixed script. Instead, it thinks about what information it needs, decides which tool to use, observes the results, and then thinks again about what to do next. This continues until it has gathered enough information to write a complete analysis.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI Application                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐     ┌──────────────────────────────────────────────┐    │
│   │   /analyze   │────▶│              Orchestrator                      │    │
│   │   /monitor   │     │  ┌──────────────────────────────────────┐    │    │
│   │   /alerts    │     │  │           ReAct Loop                  │    │    │
│   └──────────────┘     │  │  ┌────────┐  ┌─────────┐  ┌────────┐ │    │    │
│                        │  │  │ Think  │─▶│  Act    │─▶│Observe │ │    │    │
│                        │  │  └────────┘  └─────────┘  └────────┘ │    │    │
│                        │  │       ▲                        │      │    │    │
│                        │  │       └────────────────────────┘      │    │    │
│                        │  └──────────────────────────────────────┘    │    │
│                        │                    │                          │    │
│                        │                    ▼                          │    │
│                        │  ┌──────────────────────────────────────┐    │    │
│                        │  │          Reflection Layer             │    │    │
│                        │  │   (Quality Assessment & Refinement)   │    │    │
│                        │  └──────────────────────────────────────┘    │    │
│                        └──────────────────────────────────────────────┘    │
│                                            │                                │
│                                            ▼                                │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │                          Tool Registry                              │   │
│   ├────────────────┬────────────────┬─────────────────┬────────────────┤   │
│   │ News Retriever │ FinData Fetcher│ Sentiment       │ Ticker         │   │
│   │ (News API)     │ (Yahoo Finance)│ Analyzer        │ Extractor      │   │
│   │                │                │ (Gemini LLM)    │ (Gemini LLM)   │   │
│   └────────────────┴────────────────┴─────────────────┴────────────────┘   │
│                                            │                                │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │                        Storage Layer                                │   │
│   ├────────────────┬────────────────┬─────────────────┬────────────────┤   │
│   │   Job Store    │  Alert Store   │  News Store     │ Monitor Store  │   │
│   └────────────────┴────────────────┴─────────────────┴────────────────┘   │
│                                            │                                │
│                                            ▼                                │
│                                     ┌────────────┐                          │
│                                     │  SQLite    │                          │
│                                     │  Database  │                          │
│                                     └────────────┘                          │
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │                    APScheduler (Background Jobs)                    │   │
│   │              Periodic monitoring tasks for watched stocks           │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## How the Agent Thinks: ReAct + Reflection

### The ReAct Pattern

When you ask AIRA to analyze a stock, it doesn't just run a predetermined sequence of API calls. Instead, it engages in a reasoning loop:

1. **Think**: "I need to analyze Tesla. First, I should get recent news to understand what's happening with the company."

2. **Act**: Calls the `news_retriever` tool with query "TSLA"

3. **Observe**: Receives 5 news articles about Tesla's latest earnings and production numbers

4. **Think**: "I have news data now. To give a complete analysis, I need financial data—current price, market cap, and recent performance."

5. **Act**: Calls the `findata_fetcher` tool for TSLA

6. **Observe**: Gets current stock price, 52-week range, P/E ratio, quarterly earnings

7. **Think**: "Now I should analyze the sentiment of these news articles to understand market perception."

8. **Act**: Calls the `sentiment_analyzer` tool

9. **Observe**: Gets sentiment scores for each article

10. **Think**: "I have enough information. Time to synthesize a final analysis."

11. **Final Answer**: Produces a comprehensive report with sentiment score, key findings, and analysis summary

This loop continues until the agent decides it has gathered enough information (or hits the maximum step limit). Each step is logged, creating a traceable chain of reasoning.

### The Reflection Layer

After the ReAct loop produces an analysis, a reflection step sends the output back to the LLM with a prompt asking it to evaluate quality on a 0-1 scale. The LLM assesses completeness (were all tools used?), balance (positive and negative factors?), and specificity (actual data points cited?).

If the score falls below 0.7, the orchestrator retries the entire analysis. The LLM can also provide a refined summary to smooth out the original. This is essentially asking the LLM to grade its own homework—a soft quality gate rather than rigorous validation.

## Persistent Monitoring: How Alerts Work

AIRA can watch stocks over time. When you start a monitor, here's what happens:

1. **Scheduling**: APScheduler creates a background job that runs at your specified interval (e.g., every 6 hours)

2. **News Check**: Each run fetches the latest news articles for that ticker

3. **Deduplication**: Articles are hashed and compared against `seen_article_hashes`. Only truly new articles are considered.

4. **Significance Threshold**: If the number of new articles exceeds `MONITOR_MIN_ARTICLES` (default: 5), AIRA considers this "significant news"

5. **Triggered Analysis**: Significant news triggers a quick analysis (fewer ReAct steps, but with reflection) to assess the situation

6. **Proactive Alert**: The analysis is stored as a `PROACTIVE_ALERT` that you can retrieve via the `/alerts` endpoint

This design means AIRA won't spam you with alerts for every minor news blip. It waits until there's a meaningful volume of new information before bothering you.

## External APIs

AIRA integrates with three external services:

### Google Gemini (LLM)
Powers all the intelligent parts:
- Ticker extraction from natural language queries
- Sentiment analysis of news articles
- The ReAct reasoning loop
- Reflection and quality assessment

The `.env` file includes an API key that may work, but if you encounter rate limits or errors, you'll need your own key from [Google AI Studio](https://makersuite.google.com/app/apikey).

### News API
Fetches recent news articles about companies. Free tier allows 100 requests/day.
Get your key at [newsapi.org](https://newsapi.org/).

### Yahoo Finance (yfinance)
Retrieves stock prices, company info, and quarterly financials. This is a free API accessed through the `yfinance` Python package—no key required.

## Technology Stack

| Component | Technology | Why |
|-----------|------------|-----|
| Web Framework | FastAPI | Async support, automatic OpenAPI docs, Pydantic integration |
| Database | SQLite + aiosqlite | Zero-config, file-based, perfect for containerization |
| ORM | SQLAlchemy 2.0 (async) | Type-safe queries, automatic schema management |
| LLM | Google Gemini | Good balance of capability, speed, and cost |
| Scheduling | APScheduler | Lightweight, in-process job scheduling |
| HTTP Client | httpx | Modern async HTTP client |
| Stock Data | yfinance | Reliable free access to Yahoo Finance data |
| Validation | Pydantic | Data validation and settings management |

### Why SQLite?

For a project designed to run in containers, SQLite makes deployment trivial. No separate database server to configure, no connection strings to manage, no ports to expose. The database is just a file that lives in the container. For the scale of a personal research assistant, SQLite handles the workload perfectly well.

## Project Structure

```
AIRA/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Settings management from .env
│   │
│   ├── api/
│   │   └── routes.py           # API endpoints (/analyze, /monitor, etc.)
│   │
│   ├── agent/
│   │   ├── orchestrator.py     # High-level agent coordination
│   │   ├── react.py            # ReAct reasoning loop implementation
│   │   ├── reflection.py       # Quality assessment and refinement
│   │   └── prompts.py          # LLM prompt templates
│   │
│   ├── tools/
│   │   ├── base.py             # BaseTool abstract class
│   │   ├── registry.py         # Tool registration and execution
│   │   ├── news_retriever.py   # News API integration
│   │   ├── finData_fetcher.py  # Yahoo Finance integration
│   │   ├── sentiment_analyzer.py # LLM-based sentiment analysis
│   │   └── ticker_extractor.py # Company name to ticker resolution
│   │
│   ├── scheduler/
│   │   ├── scheduler.py        # APScheduler setup
│   │   └── tasks.py            # Monitoring background tasks
│   │
│   ├── storage/
│   │   ├── job_store.py        # Analysis job tracking
│   │   ├── alert_store.py      # Proactive alert storage
│   │   ├── news_store.py       # Article caching
│   │   └── monitor_state.py    # Monitor configuration
│   │
│   ├── database/
│   │   ├── connection.py       # Async SQLAlchemy setup
│   │   └── models.py           # Database models
│   │
│   ├── schemas/
│   │   ├── requests.py         # API request models
│   │   └── responses.py        # API response models
│   │
│   ├── services/
│   │   ├── llm.py              # Gemini API wrapper
│   │   └── ticker_extractor.py # Ticker extraction service
│   │
│   └── tests/
│       └── routes.py           # Test endpoints for individual tools
│
├── .env                        # Environment configuration
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container build instructions
└── README.md                   # You are here
```

## Setup and Installation

### Prerequisites
- Python 3.10+
- A Google API key for Gemini (optional—one is included that may work)
- A News API key (optional for basic testing)

### Local Development

1. **Clone the repository**
   ```bash
   cd AIRA
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment** (optional)

   Edit `.env` if you need to use your own API keys:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key
   NEWS_API_KEY=your_news_api_key
   ```

5. **Run the application**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 5127 --reload
   ```

6. **Open the API docs**

   Navigate to http://localhost:5127/docs

### Docker Deployment

```bash
# Build the image
docker build -t aira .

# Run the container
docker run -d -p 5127:5127 --name aira aira

# View logs
docker logs -f aira
```

The SQLite database will be created inside the container at `/app/aira.db`. To persist data across container restarts, mount a volume:

```bash
docker run -d -p 5127:5127 -v aira-data:/app --name aira aira
```

## API Endpoints

### Core Endpoints (prefix: `/api/v1`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/analyze` | POST | Submit analysis request |
| `/status/{job_id}` | GET | Check analysis job status |
| `/monitor_start` | POST | Start monitoring a ticker |
| `/monitor_stop` | POST | Stop monitoring a ticker |
| `/monitors` | GET | List all monitors |
| `/alerts` | GET | List all alerts |
| `/alerts/{alert_id}` | GET | Get specific alert |

### Test Endpoints (prefix: `/tests`)

These endpoints let you test individual tools in isolation:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ticker-extract` | POST | Test ticker extraction |
| `/news-search` | POST | Test news retrieval |
| `/sentiment-analyze` | POST | Test sentiment analysis |
| `/findata` | POST | Test financial data fetching |

## Usage Examples

### Analyze a Stock

```bash
curl -X POST http://localhost:5127/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "Analyze the near-term prospects of Tesla"}'
```

Response:
```json
{
  "success": true,
  "data": {
    "job_id": "abc123...",
    "status": "pending",
    "status_url": "/api/v1/status/abc123..."
  }
}
```

Then poll the status endpoint until complete:
```bash
curl http://localhost:5127/api/v1/status/abc123...
```

### Start Monitoring

```bash
curl -X POST http://localhost:5127/api/v1/monitor_start \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "interval_hours": 6}'
```

The `interval_hours` field accepts decimals (e.g., `0.1` = 6 minutes for testing).

### Check Alerts

```bash
curl http://localhost:5127/api/v1/alerts?ticker=AAPL
```

## Configuration

All configuration is managed through environment variables (see `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | (included) | Gemini API key |
| `NEWS_API_KEY` | (included) | News API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Default Gemini model |
| `GEMINI_REACT_MODEL` | `gemini-3-pro-preview` | Model for ReAct reasoning |
| `MONITOR_INTERVAL_HOURS` | `24` | Default monitoring interval |
| `MONITOR_MIN_ARTICLES` | `5` | Articles needed to trigger alert |
| `ANALYSIS_DAYS_BACK` | `7` | Days of news to fetch |
| `ANALYSIS_MAX_ARTICLES` | `5` | Max articles per analysis |
| `REFLECTION_ENABLED` | `true` | Enable/disable reflection layer |
| `REFLECTION_MIN_QUALITY_SCORE` | `0.7` | Minimum score to accept analysis |

## License

MIT
