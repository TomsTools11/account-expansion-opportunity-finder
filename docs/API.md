# API Reference

This document provides complete documentation for all MCP tools available in the Insurance Agent Account Expansion Analyzer.

## Tool Overview

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `analyze_agent_account` | Analyze single agent for opportunities | `agent_id` |
| `batch_expansion_analysis` | Batch analyze multiple agents | None |
| `get_benchmark_summary` | Retrieve benchmark data | None |
| `refresh_benchmarks` | Refresh cached benchmark data | None |

---

## analyze_agent_account

Analyzes a single agent account against benchmarks to identify expansion opportunities.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "description": "Close CRM lead ID (e.g., 'lead_xyz789')"
    },
    "min_confidence": {
      "type": "number",
      "description": "Minimum confidence score (0-1) to include opportunities",
      "default": 0.5,
      "minimum": 0,
      "maximum": 1
    },
    "max_opportunities": {
      "type": "integer",
      "description": "Maximum number of opportunities to return",
      "default": 5,
      "minimum": 1,
      "maximum": 20
    },
    "include_tier_progression": {
      "type": "boolean",
      "description": "Include tier progression opportunities",
      "default": true
    }
  },
  "required": ["agent_id"]
}
```

### Output Schema

```json
{
  "agent": {
    "id": "string",
    "name": "string",
    "current_products": ["string"],
    "annual_premium_volume": "number",
    "tenure_months": "integer",
    "performance_tier": "string"
  },
  "opportunities": [
    {
      "rank": "integer",
      "type": "string",
      "recommended_product": "string|null",
      "projected_lift": {
        "dollars": "number",
        "percentage": "number"
      },
      "confidence": {
        "level": "string",
        "score": "number"
      },
      "priority_score": "number",
      "message": "string",
      "peer_analysis": {
        "similar_agent_count": "integer",
        "avg_revenue": "number"
      },
      "readiness": {
        "indicators": ["string"],
        "barriers": ["string"]
      },
      "tier_progression": {
        "current": "string",
        "target": "string"
      }
    }
  ],
  "summary": {
    "total_opportunities": "integer",
    "total_projected_lift": "number",
    "highest_confidence": "number",
    "top_recommendation": "string"
  },
  "benchmark_context": {
    "current_tier": "string",
    "peer_group_size": "integer",
    "peer_avg_revenue": "number",
    "readiness_score": "number"
  }
}
```

### Example

**Request:**
```json
{
  "agent_id": "lead_abc123",
  "min_confidence": 0.6,
  "max_opportunities": 3
}
```

**Response:**
```json
{
  "agent": {
    "id": "lead_abc123",
    "name": "John Smith Insurance Agency",
    "current_products": ["Home"],
    "annual_premium_volume": 45000,
    "tenure_months": 24,
    "performance_tier": "Top 25%"
  },
  "opportunities": [
    {
      "rank": 1,
      "type": "Add Product",
      "recommended_product": "Auto",
      "projected_lift": {
        "dollars": 15750,
        "percentage": 35.0
      },
      "confidence": {
        "level": "High",
        "score": 0.82
      },
      "priority_score": 87,
      "message": "Agent currently sells Home-only with $45K annual premium. Similar Top 25% agents who added Auto see average 35% revenue lift ($15.8K). Agent has strong contact rate (50%) and 2+ years tenure—high confidence opportunity.",
      "peer_analysis": {
        "similar_agent_count": 47,
        "avg_revenue": 60800
      },
      "readiness": {
        "indicators": [
          "Contact rate 50% (above tier average)",
          "Tenure 24 months (established relationships)"
        ],
        "barriers": []
      },
      "tier_progression": {
        "current": "Top 25%",
        "target": "Top 10%"
      }
    }
  ],
  "summary": {
    "total_opportunities": 1,
    "total_projected_lift": 15750,
    "highest_confidence": 0.82,
    "top_recommendation": "Auto"
  },
  "benchmark_context": {
    "current_tier": "Top 25%",
    "peer_group_size": 47,
    "peer_avg_revenue": 60800,
    "readiness_score": 0.85
  }
}
```

---

## batch_expansion_analysis

Analyzes multiple agents and returns a prioritized list of expansion opportunities.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "top_n": {
      "type": "integer",
      "description": "Number of top opportunities to return",
      "default": 20,
      "minimum": 1,
      "maximum": 100
    },
    "min_confidence": {
      "type": "number",
      "description": "Minimum confidence score (0-1)",
      "default": 0.5,
      "minimum": 0,
      "maximum": 1
    },
    "filter_tiers": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Filter by performance tiers",
      "enum_values": ["Top 10%", "Top 25%", "Average", "Below Average", "Bottom 10%"]
    },
    "filter_products": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Filter to agents with these products"
    },
    "filter_missing_products": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Filter to agents missing these products"
    },
    "min_tenure_months": {
      "type": "integer",
      "description": "Minimum agent tenure in months",
      "minimum": 0
    },
    "max_tenure_months": {
      "type": "integer",
      "description": "Maximum agent tenure in months",
      "minimum": 0
    },
    "min_premium_volume": {
      "type": "number",
      "description": "Minimum annual premium volume ($)",
      "minimum": 0
    },
    "max_premium_volume": {
      "type": "number",
      "description": "Maximum annual premium volume ($)",
      "minimum": 0
    },
    "parallel": {
      "type": "boolean",
      "description": "Use parallel processing for faster analysis",
      "default": true
    }
  },
  "required": []
}
```

### Output Schema

```json
{
  "summary": {
    "total_agents_analyzed": "integer",
    "total_opportunities_found": "integer",
    "agents_with_opportunities": "integer",
    "opportunities_per_agent": "number"
  },
  "aggregate_metrics": {
    "total_projected_lift": "number",
    "avg_confidence_score": "number",
    "avg_priority_score": "number"
  },
  "priority_distribution": {
    "high_priority": "integer",
    "medium_priority": "integer",
    "low_priority": "integer"
  },
  "most_common_product": "string",
  "top_opportunities": [
    {
      "rank": "integer",
      "agent": {
        "id": "string",
        "name": "string"
      },
      "type": "string",
      "recommended_product": "string",
      "projected_lift": {
        "dollars": "number",
        "percentage": "number"
      },
      "confidence": {
        "level": "string",
        "score": "number"
      },
      "priority_score": "number",
      "message": "string",
      "peer_analysis": {
        "similar_agent_count": "integer",
        "avg_revenue": "number"
      }
    }
  ]
}
```

### Example

**Request:**
```json
{
  "top_n": 10,
  "filter_tiers": ["Top 25%", "Average"],
  "min_tenure_months": 12,
  "min_premium_volume": 25000
}
```

**Response:**
```json
{
  "summary": {
    "total_agents_analyzed": 85,
    "total_opportunities_found": 156,
    "agents_with_opportunities": 72,
    "opportunities_per_agent": 1.83
  },
  "aggregate_metrics": {
    "total_projected_lift": 892500,
    "avg_confidence_score": 0.68,
    "avg_priority_score": 64.2
  },
  "priority_distribution": {
    "high_priority": 18,
    "medium_priority": 45,
    "low_priority": 93
  },
  "most_common_product": "Auto",
  "top_opportunities": [
    {
      "rank": 1,
      "agent": {
        "id": "lead_top1",
        "name": "Premier Insurance Group"
      },
      "type": "Add Product",
      "recommended_product": "Auto",
      "projected_lift": {
        "dollars": 28500,
        "percentage": 42.5
      },
      "confidence": {
        "level": "High",
        "score": 0.89
      },
      "priority_score": 94,
      "message": "High-performing Home-only agent with $67K book. Top 10% potential with Auto addition.",
      "peer_analysis": {
        "similar_agent_count": 52,
        "avg_revenue": 95600
      }
    }
  ]
}
```

---

## get_benchmark_summary

Retrieves current benchmark data for reference without performing analysis.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "include_tiers": {
      "type": "boolean",
      "description": "Include tier benchmark data",
      "default": true
    },
    "include_products": {
      "type": "boolean",
      "description": "Include product benchmark data",
      "default": true
    },
    "include_cross_sell": {
      "type": "boolean",
      "description": "Include cross-sell pattern data",
      "default": true
    },
    "tier_filter": {
      "type": "string",
      "description": "Filter to a specific tier",
      "enum": ["Top 10%", "Top 25%", "Average", "Below Average", "Bottom 10%"]
    }
  },
  "required": []
}
```

### Output Schema

```json
{
  "tier_benchmarks": [
    {
      "tier": "string",
      "contact_rate": {"min": "number", "max": "number", "avg": "number"},
      "quote_rate": {"min": "number", "max": "number", "avg": "number"},
      "close_rate": {"min": "number", "max": "number", "avg": "number"},
      "cac": {"min": "number", "max": "number", "avg": "number"},
      "lead_volume": {"min": "integer", "max": "integer", "avg": "number"}
    }
  ],
  "product_benchmarks": [
    {
      "product": "string",
      "organic_cac": "number",
      "inorganic_cac": "number",
      "blended_cac": "number"
    }
  ],
  "cross_sell_patterns": [
    {
      "primary_product": "string",
      "added_product": "string",
      "avg_lift_pct": "number",
      "adoption_rate": "number",
      "avg_time_months": "integer"
    }
  ],
  "last_refresh": "string (ISO 8601 datetime)"
}
```

### Example

**Request:**
```json
{
  "include_tiers": true,
  "include_products": true,
  "tier_filter": "Top 25%"
}
```

**Response:**
```json
{
  "tier_benchmarks": [
    {
      "tier": "Top 25%",
      "contact_rate": {"min": 45.0, "max": 55.0, "avg": 50.0},
      "quote_rate": {"min": 25.0, "max": 35.0, "avg": 30.0},
      "close_rate": {"min": 18.0, "max": 25.0, "avg": 21.5},
      "cac": {"min": 50.0, "max": 90.0, "avg": 70.0},
      "lead_volume": {"min": 100, "max": 150, "avg": 125}
    }
  ],
  "product_benchmarks": [
    {
      "product": "Auto",
      "organic_cac": 203.52,
      "inorganic_cac": 305.28,
      "blended_cac": 244.22
    },
    {
      "product": "Home",
      "organic_cac": 140.72,
      "inorganic_cac": 211.08,
      "blended_cac": 168.86
    }
  ],
  "last_refresh": "2025-12-10T12:30:00Z"
}
```

---

## refresh_benchmarks

Refreshes benchmark data from Google Sheets and optionally clears caches.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "force": {
      "type": "boolean",
      "description": "Force refresh even if cache is still valid",
      "default": false
    },
    "clear_agent_cache": {
      "type": "boolean",
      "description": "Also clear the agent data cache",
      "default": false
    }
  },
  "required": []
}
```

### Output Schema

```json
{
  "success": "boolean",
  "last_refresh": "string (ISO 8601 datetime)",
  "tier_count": "integer",
  "product_count": "integer",
  "pattern_count": "integer",
  "agents_cache_cleared": "boolean",
  "error": "string (only if success is false)"
}
```

### Example

**Request:**
```json
{
  "force": true,
  "clear_agent_cache": true
}
```

**Response:**
```json
{
  "success": true,
  "last_refresh": "2025-12-10T14:45:00Z",
  "tier_count": 5,
  "product_count": 5,
  "pattern_count": 8,
  "agents_cache_cleared": true
}
```

---

## Error Responses

All tools return errors in a consistent format:

```json
{
  "error": "Error message describing what went wrong",
  "error_type": "error_category",
  "details": {}
}
```

### Common Error Types

| Type | Description | Resolution |
|------|-------------|------------|
| `not_found` | Agent or resource not found | Verify the ID is correct |
| `validation_error` | Invalid input parameters | Check input against schema |
| `api_error` | External API failure | Retry or check credentials |
| `insufficient_data` | Not enough data for analysis | Wait for more agent data |
| `rate_limited` | API rate limit exceeded | Wait and retry |

### Example Error Response

```json
{
  "error": "Agent not found: lead_nonexistent",
  "error_type": "not_found",
  "agent_id": "lead_nonexistent"
}
```

---

## Rate Limits and Performance

- **Close CRM**: 600 requests/minute (tool uses 9 req/sec with backoff)
- **Single agent analysis**: ~500ms average
- **Batch analysis (100 agents)**: ~15-30 seconds
- **Benchmark refresh**: ~2-5 seconds

### Caching

- Agent data is cached for 5 minutes by default
- Benchmark data is cached for 1 hour by default
- Use `refresh_benchmarks` with `force: true` to clear caches
