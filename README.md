# Insurance Agent Account Expansion Analyzer

An MCP (Model Context Protocol) server that identifies revenue growth opportunities for insurance agents by comparing their current product mix and performance metrics against benchmark data from top performers.

## Overview

This tool integrates with Close CRM for agent account data and Google Sheets for benchmark storage, providing actionable recommendations with projected revenue lift.

### Business Value

- **Revenue Growth**: Identifies cross-sell and upsell opportunities by showing agents what similar high performers sell
- **Data-Driven Decisions**: Replaces gut feelings with concrete benchmarks from 5 performance tiers (Top 10%, Top 25%, Average, Below Average, Bottom 10%)
- **Prioritized Action**: Scores opportunities 0-100 based on confidence, potential lift, and agent readiness
- **Time Savings**: Automates analysis that would take hours manually, surfacing insights in seconds

### Example Output

```
Agent currently sells Home-only with $45K annual premium. Similar agents in Top 25%
tier who added Auto see average 35% revenue lift ($15.8K). Contact rate 50% suggests
strong client relationships—high confidence opportunity.
```

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Close CRM API key
- Google Cloud service account with Sheets API access
- Benchmark data spreadsheet set up in Google Sheets

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/account-expansion-opportunity-finder.git
cd account-expansion-opportunity-finder

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# For development
pip install -e ".[dev]"
```

### Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your credentials:
   ```bash
   CLOSE_API_KEY=api_your_key_here
   GOOGLE_SHEETS_CREDENTIALS_PATH=/path/to/service-account.json
   BENCHMARK_SHEET_ID=your_spreadsheet_id_here
   ```

See [docs/SETUP.md](docs/SETUP.md) for detailed setup instructions.

### Running the Server

```bash
# Start the MCP server
expansion-analyzer

# Or run directly
python -m src.mcp.server
```

### Claude Desktop Integration

Add to your Claude Desktop configuration file (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "account-expansion": {
      "command": "expansion-analyzer",
      "env": {
        "CLOSE_API_KEY": "your_api_key",
        "GOOGLE_SHEETS_CREDENTIALS_PATH": "/path/to/credentials.json",
        "BENCHMARK_SHEET_ID": "your_sheet_id"
      }
    }
  }
}
```

## Available Tools

### analyze_agent_account

Analyzes a single agent account against benchmarks to identify expansion opportunities.

```python
{
    "agent_id": "lead_xyz789",  # Required: Close CRM lead ID
    "min_confidence": 0.5,       # Optional: Minimum confidence threshold
    "max_opportunities": 5       # Optional: Maximum opportunities to return
}
```

### batch_expansion_analysis

Analyzes multiple agents and returns a prioritized list of expansion opportunities.

```python
{
    "top_n": 20,                           # Number of top opportunities to return
    "filter_tiers": ["Top 25%", "Average"], # Filter by performance tiers
    "min_tenure_months": 12,               # Minimum agent tenure
    "min_premium_volume": 25000            # Minimum book size
}
```

### get_benchmark_summary

Retrieves current benchmark data for reference.

```python
{
    "include_tiers": true,
    "include_products": true,
    "include_cross_sell": true,
    "tier_filter": "Top 25%"  # Optional: Filter to specific tier
}
```

### refresh_benchmarks

Refreshes benchmark data from Google Sheets and optionally clears caches.

```python
{
    "force": true,           # Force refresh even if cache is valid
    "clear_agent_cache": true # Also clear the agent data cache
}
```

See [docs/API.md](docs/API.md) for complete API documentation.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Desktop                          │
└─────────────────────────┬───────────────────────────────────┘
                          │ MCP Protocol
┌─────────────────────────▼───────────────────────────────────┐
│                      MCP Server                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Tool Router │  │  Validator  │  │  Response Formatter │  │
│  └──────┬──────┘  └─────────────┘  └─────────────────────┘  │
└─────────┼───────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────┐
│                    Analysis Engine                           │
│  ┌────────────────┐  ┌─────────────┐  ┌────────────────┐    │
│  │   Similarity   │  │ Projections │  │    Scoring     │    │
│  │    Matcher     │  │   Engine    │  │    Engine      │    │
│  └────────────────┘  └─────────────┘  └────────────────┘    │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Data Layer                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Close CRM   │  │   Google    │  │       Cache         │  │
│  │   Client    │  │   Sheets    │  │      (LRU)          │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘  │
└─────────┼────────────────┼──────────────────────────────────┘
          │                │
    ┌─────▼─────┐    ┌─────▼─────┐
    │ Close CRM │    │  Google   │
    │    API    │    │  Sheets   │
    └───────────┘    └───────────┘
```

## Development

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_similarity.py -v

# Run integration tests
pytest tests/integration/ -v
```

### Code Quality

```bash
# Lint with ruff
ruff check src/ tests/

# Type check with mypy
mypy src/

# Format code
ruff format src/ tests/
```

### Performance Testing

```bash
# Run performance tests (100 agents)
python scripts/performance_test.py --agents 100

# Run with 500 agents
python scripts/performance_test.py --agents 500 --iterations 3
```

## Documentation

- [Setup Guide](docs/SETUP.md) - Detailed setup instructions
- [API Reference](docs/API.md) - Complete tool documentation
- [Algorithms](docs/ALGORITHMS.md) - Analysis methodology explained
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

## Performance Targets

| Metric | Target | Typical |
|--------|--------|---------|
| Single agent analysis | < 2s | ~500ms |
| Batch 100 agents | < 60s | ~15s |
| Batch 500 agents | < 2min | ~60s |
| Memory usage | < 500MB | ~200MB |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass with `pytest`
5. Submit a pull request

## Support

For issues and feature requests, please use the GitHub issue tracker.
