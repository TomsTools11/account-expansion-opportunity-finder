# Troubleshooting Guide

This guide covers common issues and their solutions when using the Insurance Agent Account Expansion Analyzer.

## Table of Contents

- [Connection Issues](#connection-issues)
- [Authentication Errors](#authentication-errors)
- [Data Quality Issues](#data-quality-issues)
- [Performance Problems](#performance-problems)
- [Analysis Issues](#analysis-issues)
- [Claude Desktop Integration](#claude-desktop-integration)

---

## Connection Issues

### Close CRM Connection Failed

**Symptoms:**
```
CloseAPIError: Connection failed to Close CRM API
```

**Causes & Solutions:**

1. **Network issues**
   - Check your internet connection
   - Verify Close CRM status at status.close.com

2. **Firewall blocking**
   - Ensure `api.close.com` is accessible
   - Check corporate firewall rules

3. **Timeout**
   - Increase timeout: `CLOSE_TIMEOUT_SECONDS=60`
   - Check for slow network conditions

### Google Sheets Connection Failed

**Symptoms:**
```
SheetsAPIError: Failed to connect to Google Sheets API
```

**Causes & Solutions:**

1. **Invalid credentials file**
   ```bash
   # Verify the file exists and is valid JSON
   cat $GOOGLE_SHEETS_CREDENTIALS_PATH | python -m json.tool
   ```

2. **API not enabled**
   - Go to Google Cloud Console
   - APIs & Services > Library
   - Search "Google Sheets API"
   - Click Enable

3. **Service account permissions**
   - Share the spreadsheet with the service account email
   - Grant "Editor" access

---

## Authentication Errors

### Close CRM Authentication Failed

**Symptoms:**
```
CloseAuthenticationError: API key invalid or expired
```

**Solutions:**

1. **Verify API key format**
   ```bash
   # Key should start with api_
   echo $CLOSE_API_KEY | head -c 4
   # Should output: api_
   ```

2. **Generate new key**
   - Log in to Close CRM
   - Settings > API Keys
   - Generate new key

3. **Check account permissions**
   - Ensure your Close account has API access
   - Contact Close support if needed

### Google Sheets Authentication Failed

**Symptoms:**
```
SheetsAuthenticationError: Invalid credentials
```

**Solutions:**

1. **Use absolute path**
   ```bash
   # Bad
   GOOGLE_SHEETS_CREDENTIALS_PATH=./credentials.json

   # Good
   GOOGLE_SHEETS_CREDENTIALS_PATH=/home/user/credentials.json
   ```

2. **Check file permissions**
   ```bash
   ls -la $GOOGLE_SHEETS_CREDENTIALS_PATH
   # Should be readable by current user
   ```

3. **Regenerate credentials**
   - Delete old key in Google Cloud Console
   - Create new service account key
   - Download fresh JSON file

---

## Data Quality Issues

### Agent Not Found

**Symptoms:**
```json
{"error": "Agent not found: lead_xyz123"}
```

**Solutions:**

1. **Verify lead ID**
   - Check the lead exists in Close CRM
   - Ensure correct ID format (starts with `lead_`)

2. **Check lead status**
   - Archived leads may not be accessible
   - Verify lead isn't deleted

### Missing Custom Fields

**Symptoms:**
```json
{"error": "insufficient_data", "missing_fields": ["contact_rate", "book_size"]}
```

**Solutions:**

1. **Add missing fields to Close CRM**
   - Go to Close CRM Settings > Custom Fields
   - Add required fields (see SETUP.md)

2. **Populate field values**
   - Update the agent's lead record
   - Ensure at least 60% data completeness

3. **Use fallback analysis**
   - Reduce `min_confidence` threshold
   - Accept lower-confidence recommendations

### Invalid Benchmark Data

**Symptoms:**
```
InvalidSheetSchemaError: Sheet 'Agent_Tiers' missing column 'Contact_Rate_Min'
```

**Solutions:**

1. **Check sheet structure**
   - Verify all required columns exist
   - Column headers must match exactly (case-sensitive)

2. **Restore from template**
   - See SETUP.md for expected sheet structure
   - Recreate tabs if corrupted

3. **Check for hidden columns**
   - Unhide all columns in Google Sheets
   - Remove any extra formatting

---

## Performance Problems

### Slow Batch Analysis

**Symptoms:**
- Batch analysis takes > 60 seconds for 100 agents
- Timeouts during batch operations

**Solutions:**

1. **Enable parallel processing**
   ```json
   {"parallel": true}
   ```

2. **Reduce batch size**
   - Use filters to narrow agent set
   - Analyze in smaller batches

3. **Increase workers**
   ```bash
   MAX_CONCURRENT_REQUESTS=8
   ```

4. **Check cache**
   - Don't use `use_cache: false` unless needed
   - Let cache warm up

### Rate Limit Exceeded

**Symptoms:**
```
CloseRateLimitError: Rate limit exceeded (429)
```

**Solutions:**

1. **Reduce request rate**
   ```bash
   RATE_LIMIT_PER_SECOND=5  # Lower than default 9
   ```

2. **Wait and retry**
   - Tool automatically retries with backoff
   - If persistent, wait 1 minute

3. **Use caching**
   - Don't bypass cache unnecessarily
   - Increase cache TTL if appropriate

### High Memory Usage

**Symptoms:**
- Process using > 500MB memory
- Out of memory errors

**Solutions:**

1. **Reduce cache size**
   ```bash
   MAX_AGENT_CACHE_ENTRIES=500  # Default 1000
   ```

2. **Process in batches**
   - Use smaller `top_n` values
   - Filter agents more aggressively

3. **Restart server**
   - Clear accumulated cache
   - Free up memory

---

## Analysis Issues

### No Opportunities Found

**Symptoms:**
```json
{"opportunities": [], "summary": {"total_opportunities": 0}}
```

**Causes & Solutions:**

1. **Agent already has all products**
   - Check agent's current product list
   - No cross-sell opportunities if fully diversified

2. **Confidence threshold too high**
   ```json
   {"min_confidence": 0.3}  // Lower from default 0.5
   ```

3. **Insufficient similar agents**
   - Need at least 10 similar agents
   - Broaden filters or wait for more data

4. **Agent profile too unique**
   - Very unusual combinations may not match peers
   - Use general benchmarks instead

### Low Confidence Scores

**Symptoms:**
- All opportunities have confidence < 0.5
- "Low" confidence level on everything

**Causes & Solutions:**

1. **Small peer group**
   - Few similar agents in database
   - Solution: Lower similarity threshold

2. **Missing benchmark patterns**
   - No historical cross-sell data
   - Solution: Run `refresh_benchmarks`

3. **Agent data incomplete**
   - Missing metrics reduce similarity matching
   - Solution: Fill in CRM custom fields

### Unrealistic Projections

**Symptoms:**
- Projected lift seems too high/low
- Projections don't match intuition

**Causes & Solutions:**

1. **Stale benchmarks**
   ```json
   // Refresh benchmarks
   {"force": true, "clear_agent_cache": true}
   ```

2. **Outlier peers**
   - A few high/low performers skewing median
   - Increasing min_similar_agents helps

3. **Market changes**
   - Benchmarks may be outdated
   - Update benchmark spreadsheet manually

---

## Claude Desktop Integration

### Server Not Starting

**Symptoms:**
- Claude shows "MCP server failed to start"
- No tools available in Claude

**Solutions:**

1. **Check command path**
   ```json
   {
     "command": "/absolute/path/to/venv/bin/expansion-analyzer"
   }
   ```

2. **Verify environment**
   ```json
   {
     "env": {
       "CLOSE_API_KEY": "api_xxx",
       "GOOGLE_SHEETS_CREDENTIALS_PATH": "/absolute/path/to/creds.json",
       "BENCHMARK_SHEET_ID": "your_sheet_id"
     }
   }
   ```

3. **Check server logs**
   ```bash
   # Run manually to see errors
   expansion-analyzer
   ```

### Tools Not Appearing

**Symptoms:**
- Server starts but tools not listed
- Claude doesn't recognize tool names

**Solutions:**

1. **Restart Claude Desktop**
   - Close completely and reopen
   - Config changes require restart

2. **Check config file syntax**
   ```bash
   # Validate JSON
   cat ~/.config/claude/claude_desktop_config.json | python -m json.tool
   ```

3. **Verify MCP version**
   - Ensure compatible MCP SDK version
   - Update if needed: `pip install --upgrade mcp`

### Tool Calls Failing

**Symptoms:**
- Tool invocation returns errors
- "Error calling tool" messages

**Solutions:**

1. **Check environment variables**
   - All required vars must be set
   - Use absolute paths

2. **Test server independently**
   ```bash
   # Test outside Claude first
   expansion-analyzer
   ```

3. **Enable debug logging**
   ```json
   {
     "env": {
       "LOG_LEVEL": "DEBUG"
     }
   }
   ```

---

## Getting Help

If you're still experiencing issues:

1. **Check logs**
   ```bash
   LOG_LEVEL=DEBUG expansion-analyzer 2>&1 | tee debug.log
   ```

2. **Run diagnostics**
   ```bash
   python -c "
   from src.integrations import CloseClient, SheetsClient
   print('Close:', CloseClient().test_connection())
   print('Sheets:', SheetsClient().test_connection())
   "
   ```

3. **File an issue**
   - Include error messages
   - Include relevant config (redact secrets)
   - Include steps to reproduce
