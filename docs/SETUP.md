# Setup Guide

This guide walks you through setting up the Insurance Agent Account Expansion Analyzer from scratch.

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git (for cloning the repository)
- A Close CRM account with API access
- A Google Cloud account with Sheets API enabled

## Step 1: Install the Package

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/account-expansion-opportunity-finder.git
cd account-expansion-opportunity-finder

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .

# For development (includes test dependencies)
pip install -e ".[dev]"
```

### Verify Installation

```bash
# Check the command is available
expansion-analyzer --help

# Or run directly
python -c "from src.mcp.server import main; print('Import successful')"
```

## Step 2: Configure Close CRM

### Get Your API Key

1. Log in to Close CRM
2. Go to Settings (gear icon) > API Keys
3. Click "Generate New API Key"
4. Copy the key (starts with `api_`)

### Required Custom Fields

Ensure your Close CRM has these custom fields on leads:

| Field Name | Type | Purpose |
|------------|------|---------|
| `cf_product_lines` | Multi-select | Current insurance products |
| `cf_book_size` | Number | Annual premium volume ($) |
| `cf_agent_tenure` | Number | Months as agent |
| `cf_contact_rate` | Number | Contact rate percentage |
| `cf_quote_rate` | Number | Quote rate percentage |
| `cf_close_rate` | Number | Close rate percentage |
| `cf_monthly_leads` | Number | Average monthly lead volume |
| `cf_cac` | Number | Cost per acquisition ($) |
| `cf_region` | Text | Geographic region |
| `cf_agency_type` | Select | Independent/Captive/MGA |
| `cf_agent_tier` | Select | Performance tier |

### Test API Connection

```bash
# Quick connection test
curl -u your_api_key: https://api.close.com/api/v1/me/
```

## Step 3: Configure Google Sheets

### Create a Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the Google Sheets API:
   - Go to APIs & Services > Library
   - Search for "Google Sheets API"
   - Click Enable

4. Create a service account:
   - Go to IAM & Admin > Service Accounts
   - Click "Create Service Account"
   - Name it (e.g., "benchmark-reader")
   - Click Create and Continue
   - Skip role assignment (click Done)

5. Create a key:
   - Click on the service account you created
   - Go to Keys tab
   - Click Add Key > Create New Key
   - Select JSON format
   - Download and save securely

### Set Up the Benchmark Spreadsheet

1. Create a new Google Sheet
2. Share it with your service account email (found in the JSON key file)
3. Create these tabs with headers:

#### Tab 1: Agent_Tiers

| Tier | Contact_Rate_Min | Contact_Rate_Max | Quote_Rate_Min | Quote_Rate_Max | Close_Rate_Min | Close_Rate_Max | CAC_Min | CAC_Max | Lead_Volume_Min | Lead_Volume_Max |
|------|------------------|------------------|----------------|----------------|----------------|----------------|---------|---------|-----------------|-----------------|
| Top 10% | 55 | 70 | 35 | 50 | 25 | 40 | 25 | 60 | 150 | 300 |
| Top 25% | 45 | 55 | 25 | 35 | 18 | 25 | 50 | 90 | 100 | 150 |
| Average | 30 | 45 | 15 | 25 | 12 | 18 | 80 | 130 | 50 | 100 |
| Below Average | 20 | 30 | 10 | 15 | 6 | 12 | 120 | 180 | 25 | 50 |
| Bottom 10% | 10 | 20 | 5 | 10 | 2 | 6 | 160 | 250 | 10 | 25 |

#### Tab 2: Product_CAC

| Product | Organic_CAC | Inorganic_CAC | Blended_CAC | Avg_Annual_Premium | Source |
|---------|-------------|---------------|-------------|-------------------|--------|
| Auto | 203.52 | 305.28 | 244.22 | 950 | Focus Digital 2024 |
| Home | 140.72 | 211.08 | 168.86 | 1200 | Focus Digital 2024 |
| Life | 24.96 | 37.44 | 29.95 | 500 | Industry Avg |

#### Tab 3: Cross_Sell_Patterns

| Primary_Product | Added_Product | Avg_Lift_Pct | Adoption_Rate | Avg_Time_Months | Tier |
|-----------------|---------------|--------------|---------------|-----------------|------|
| Home | Auto | 35.2 | 0.68 | 6 | Top 25% |
| Auto | Home | 28.5 | 0.54 | 8 | Top 25% |

### Get the Spreadsheet ID

The spreadsheet ID is in the URL:
```
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit
```

## Step 4: Configure Environment Variables

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your values:
   ```bash
   # Required
   CLOSE_API_KEY=api_your_key_here
   GOOGLE_SHEETS_CREDENTIALS_PATH=/absolute/path/to/service-account.json
   BENCHMARK_SHEET_ID=your_spreadsheet_id

   # Optional (defaults shown)
   MIN_CONFIDENCE_THRESHOLD=0.5
   LOG_LEVEL=INFO
   ```

## Step 5: Verify Setup

### Test Connections

```bash
# Test Close CRM connection
python -c "
from src.integrations import CloseClient
client = CloseClient()
print('Connected!' if client.test_connection() else 'Connection failed')
"

# Test Google Sheets connection
python -c "
from src.integrations import SheetsClient
client = SheetsClient()
print('Connected!' if client.test_connection() else 'Connection failed')
"
```

### Run the Test Suite

```bash
# Run tests to verify everything works
pytest tests/ -v

# Run a quick smoke test
pytest tests/integration/ -v -k "test_connection"
```

### Start the Server

```bash
# Start in development mode
expansion-analyzer

# Or with verbose logging
LOG_LEVEL=DEBUG expansion-analyzer
```

## Step 6: Claude Desktop Integration

### Configure Claude Desktop

Add to your Claude Desktop config (usually `~/.config/claude/claude_desktop_config.json` on Linux or `%APPDATA%\claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "account-expansion": {
      "command": "/path/to/venv/bin/expansion-analyzer",
      "env": {
        "CLOSE_API_KEY": "api_your_key",
        "GOOGLE_SHEETS_CREDENTIALS_PATH": "/path/to/credentials.json",
        "BENCHMARK_SHEET_ID": "your_sheet_id"
      }
    }
  }
}
```

### Verify in Claude Desktop

1. Restart Claude Desktop
2. Open a new conversation
3. Ask Claude to list available tools
4. Try: "Analyze agent lead_abc123 for expansion opportunities"

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.

### Quick Fixes

**"Close CRM API key invalid"**
- Verify the key starts with `api_`
- Check the key hasn't expired
- Ensure you have API access in your Close plan

**"Google Sheets credentials not found"**
- Use absolute path in GOOGLE_SHEETS_CREDENTIALS_PATH
- Verify the JSON file exists and is readable
- Check file permissions

**"Spreadsheet not found"**
- Verify the BENCHMARK_SHEET_ID is correct
- Ensure the service account has Editor access to the sheet
- Check the sheet URL matches the ID

## Next Steps

- Review [API.md](API.md) for tool documentation
- Read [ALGORITHMS.md](ALGORITHMS.md) to understand the analysis methodology
- Run the performance test: `python scripts/performance_test.py`
