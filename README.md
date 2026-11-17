# Hedge Simulation

An AI-driven multi-agent hedge fund simulation platform. This project simulates an autonomous investment committee where specialized AI agents—inspired by legendary investors and analytical disciplines—collaborate to analyze market data, evaluate risk, and execute trading strategies.

> **Disclaimer**: This project is strictly for **educational, experimental, and research purposes**. It does not execute real-world trades or provide financial advice.

---

## Architecture Overview

The system models a complete investment firm pipeline through collaborative agents:

### 1. Investment Personas
- **Warren Buffett**: Focuses on high-quality businesses with strong economic moats and fair prices.
- **Charlie Munger**: Emphasizes durable competitive advantages and avoiding mistakes.
- **Ben Graham**: Deep value investing with strict margin of safety requirements.
- **Aswath Damodaran**: Disciplined narrative and numbers valuation.
- **Peter Lynch**: Searches for fast-growing businesses in everyday markets.
- **Michael Burry**: Contrarian deep-value search for mispriced securities.
- **Cathie Wood**: High-conviction disruptive innovation and high-growth technologies.
- **Stanley Druckenmiller**: Macro-driven asymmetric upside opportunities.
- **Bill Ackman**: Activist investment theses with operational catalysts.
- **Phil Fisher**: Scuttlebutt qualitative growth analysis.
- **Mohnish Pabrai**: Low-risk, high-uncertainty Dhandho investing.
- **Rakesh Jhunjhunwala**: High-conviction compounders and growth trajectories.

### 2. Analytical & Execution Agents
- **Valuation Agent**: Calculates intrinsic fair value metrics and discounts.
- **Sentiment Agent**: Processes news, market psychology, and social sentiment.
- **Fundamentals Agent**: Analyzes financial statements, balance sheets, and cash flows.
- **Technicals Agent**: Computes momentum, moving averages, and technical indicators.
- **Risk Manager**: Dynamically manages position sizing and volatility caps.
- **Portfolio Manager**: Synthesizes all agent signals into final capital allocation orders.

---

## Tech Stack

- **Backend**: FastAPI (Python 3.11), SQLAlchemy, SQLite, Uvicorn, Server-Sent Events (SSE)
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Radix UI, Lucide Icons
- **Simulation & Core**: LangChain, Pydantic, Pandas, NumPy, Poetry
- **LLM Support**: Local (Ollama) and Cloud (OpenAI, Anthropic, Groq, DeepSeek, Azure)
- **Security**: Fernet encryption for API keys at rest, path traversal safeguards, secure CORS policies

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- [Poetry](https://python-poetry.org/) (Python package manager)
- (Optional) [Ollama](https://ollama.ai/) for running local LLMs

### 1. Clone & Setup Environment

```bash
git clone https://github.com/ikhlashilmi/Hedge-Simulation.git
cd Hedge-Simulation
```

Copy the example environment file and configure your keys:

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```ini
# At least one LLM provider is required (or run locally via Ollama)
OPENAI_API_KEY=your-openai-api-key
# GROQ_API_KEY=your-groq-api-key
# ANTHROPIC_API_KEY=your-anthropic-api-key

# Financial data provider (Free data available for AAPL, GOOGL, MSFT, NVDA, TSLA)
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

### 2. Python Dependencies

```bash
poetry install
```

---

## Running the Application

### Option A: Web Application (Full-Stack)

1. **Start the Backend API Server**:
   ```bash
   poetry run uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Start the Frontend UI**:
   ```bash
   cd app/frontend
   npm install
   npm run dev
   ```

   Open your browser at `http://localhost:5173`.

### Option B: Command Line Interface (CLI)

Run the multi-agent decision cycle directly in your terminal:

```bash
# Run with default cloud LLM
poetry run python src/main.py --ticker AAPL,MSFT,NVDA

# Run with local models via Ollama
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama

# Specify historical date ranges
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
```

### Option C: Backtesting Engine

Evaluate agent strategies against historical market data:

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-06-01
```

The backtester calculates:
- Total Return & Benchmark Comparison
- Sharpe Ratio & Sortino Ratio
- Maximum Drawdown (MDD)
- Trade-by-trade portfolio log

---

## Project Structure

```
Hedge-Simulation/
├── app/
│   ├── backend/          # FastAPI server, database repositories, API routes
│   └── frontend/         # React + Vite web dashboard and flow visualizer
├── src/
│   ├── agents/           # Specialized investor and analytical agent personas
│   ├── backtesting/      # Backtesting execution engine and financial metrics
│   ├── data/             # Thread-safe cache and market data models
│   ├── tools/            # Market data APIs and financial fetchers
│   └── utils/            # Progress streaming, LLM client wrappers, helpers
├── docker/               # Production Dockerfile and container configuration
├── pyproject.toml        # Poetry dependencies and project metadata
└── README.md
```

---

## License

This project is licensed under the [MIT License](LICENSE).
