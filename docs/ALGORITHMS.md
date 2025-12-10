# Analysis Algorithms

This document explains the methodology behind the Insurance Agent Account Expansion Analyzer's recommendation engine.

## Overview

The analyzer uses four main algorithms to identify and prioritize expansion opportunities:

1. **Agent Similarity Matching** - Finding comparable agents
2. **Revenue Lift Projection** - Estimating potential revenue increase
3. **Agent Readiness Assessment** - Evaluating ability to succeed
4. **Opportunity Scoring** - Prioritizing recommendations

## 1. Agent Similarity Matching

### Goal

Find agents with similar characteristics to the target agent to establish a peer group for revenue lift projections.

### Algorithm: Weighted Cosine Similarity

Agents are represented as feature vectors, and similarity is calculated using cosine similarity with weighted features.

### Feature Vector Construction

```python
def create_agent_vector(agent):
    features = []

    # Product mix (one-hot encoding) - Weight: 40%
    products = ["Auto", "Home", "Life", "Health", "Renters",
                "Medicare", "Commercial Property", "Commercial Auto"]
    product_vector = [1 if p in agent.current_products else 0 for p in products]
    features.extend([x * 0.4 for x in product_vector])

    # Performance tier (ordinal encoding) - Weight: 25%
    tier_map = {"Bottom 10%": 1, "Below Average": 2, "Average": 3,
                "Top 25%": 4, "Top 10%": 5}
    tier_value = tier_map.get(agent.performance_tier, 3) / 5.0
    features.append(tier_value * 0.25)

    # Tenure band (normalized) - Weight: 15%
    tenure_normalized = min(agent.tenure_months / 60.0, 1.0)  # Cap at 5 years
    features.append(tenure_normalized * 0.15)

    # Book size band (log-normalized) - Weight: 20%
    book_normalized = min(log10(agent.annual_premium_volume + 1) / 6.0, 1.0)
    features.append(book_normalized * 0.20)

    return features
```

### Similarity Calculation

```python
def cosine_similarity(vec_a, vec_b):
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    magnitude_a = sqrt(sum(a * a for a in vec_a))
    magnitude_b = sqrt(sum(b * b for b in vec_b))

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)
```

### Similarity Thresholds

| Similarity Score | Confidence Level | Description |
|-----------------|------------------|-------------|
| > 0.75 | High | Very similar agents |
| 0.60 - 0.75 | Medium | Comparable agents |
| 0.50 - 0.60 | Low | Some similarity |
| ≤ 0.50 | Excluded | Too different |

---

## 2. Revenue Lift Projection

### Goal

Estimate the revenue increase if an agent adds a specific product, based on similar agents who have that product.

### Algorithm: Median Lift from Peer Group

1. **Find peer agents** who are similar and have the target product
2. **Calculate median revenue** of peers with the product
3. **Compare to peers without** the product
4. **Apply cross-sell pattern** lift percentage if available

### Projection Formula

```python
def project_revenue_lift(target_agent, similar_agents, product_to_add, benchmarks):
    # Get agents with the target product
    agents_with_product = [a for a in similar_agents
                          if product_to_add in a.current_products]

    # Get agents without the product for comparison
    agents_without_product = [a for a in similar_agents
                             if product_to_add not in a.current_products]

    # Check for cross-sell pattern from benchmarks
    pattern = benchmarks.get_cross_sell_pattern(
        primary_product=target_agent.primary_product,
        added_product=product_to_add
    )

    if pattern:
        # Use benchmark lift percentage
        lift_pct = pattern.avg_revenue_lift_pct
    else:
        # Calculate from peer data
        median_with = median([a.annual_premium_volume for a in agents_with_product])
        median_without = median([a.annual_premium_volume for a in agents_without_product])
        lift_pct = ((median_with - median_without) / median_without) * 100

    # Apply lift to target agent's current revenue
    projected_lift_dollars = target_agent.annual_premium_volume * (lift_pct / 100.0)

    return projected_lift_dollars, lift_pct
```

### Confidence Calculation

Confidence depends on multiple factors:

```python
def calculate_confidence(sample_size, similarity_avg, pattern_adoption_rate, agent_readiness):
    # Sample size factor (diminishing returns after 50)
    size_factor = min(sample_size / 50.0, 1.0)

    # Combine factors with weights
    confidence = (
        size_factor * 0.30 +           # 30% weight
        similarity_avg * 0.30 +        # 30% weight
        pattern_adoption_rate * 0.20 + # 20% weight
        agent_readiness * 0.20         # 20% weight
    )

    return min(confidence, 1.0)
```

---

## 3. Agent Readiness Assessment

### Goal

Determine if an agent is ready to successfully expand their product offerings.

### Readiness Factors

| Factor | Weight | High Score Criteria |
|--------|--------|---------------------|
| Tenure | 25% | ≥24 months |
| Contact Rate | 25% | ≥10% above tier average |
| Close Rate | 20% | ≥10% above tier average |
| Book Size | 15% | ≥$50,000 |
| Lead Volume | 15% | ≥tier average |

### Readiness Scoring

```python
def assess_readiness(agent, benchmarks):
    score = 0.0
    max_score = 100.0
    indicators = []
    barriers = []

    tier_benchmark = benchmarks.get_tier(agent.performance_tier)
    tier_avg_contact = (tier_benchmark.contact_rate_range[0] +
                        tier_benchmark.contact_rate_range[1]) / 2

    # Factor 1: Tenure (25 points)
    if agent.tenure_months >= 24:
        score += 25
        indicators.append(f"Tenure {agent.tenure_months} months (established)")
    elif agent.tenure_months >= 12:
        score += 15
        indicators.append(f"Tenure {agent.tenure_months} months (growing)")
    else:
        barriers.append(f"New agent ({agent.tenure_months} months)")

    # Factor 2: Contact Rate (25 points)
    if agent.contact_rate >= tier_avg_contact * 1.1:
        score += 25
        indicators.append(f"Contact rate {agent.contact_rate}% (above tier avg)")
    elif agent.contact_rate >= tier_avg_contact:
        score += 15
    else:
        barriers.append(f"Contact rate {agent.contact_rate}% (below tier avg)")

    # ... similar for other factors

    return score / max_score, indicators, barriers
```

### Readiness Indicators (Examples)

**Positive Indicators:**
- "Contact rate 50% (above tier average 45%)"
- "Tenure 24 months (established relationships)"
- "Book size $60K (solid cross-sell base)"
- "Lead volume 120/month (capacity for growth)"

**Barriers:**
- "Contact rate 25% (below tier average 45%)"
- "New agent (6 months tenure)"
- "Low lead volume (30/month vs tier avg 80)"

---

## 4. Opportunity Scoring

### Goal

Rank opportunities 0-100 for prioritization across multiple agents.

### Scoring Formula

```python
def score_opportunity(opportunity, agent, benchmarks):
    # Component 1: Lift Potential (50% weight)
    lift_pct = (opportunity.projected_revenue_lift / agent.annual_premium_volume) * 100
    lift_score = min(lift_pct / 50.0, 1.0) * 50  # Cap at 50% lift = max score

    # Component 2: Confidence (30% weight)
    confidence_score = opportunity.confidence_score * 30

    # Component 3: Agent Readiness (20% weight)
    readiness_score = assess_readiness(agent, benchmarks) * 20

    total_score = lift_score + confidence_score + readiness_score

    return int(round(total_score))
```

### Score Interpretation

| Score | Priority | Action |
|-------|----------|--------|
| 90-100 | Immediate | Very high confidence and impact - act now |
| 75-89 | High | Strong opportunity - prioritize |
| 60-74 | Medium | Good opportunity with some uncertainty |
| 50-59 | Lower | Consider after higher-priority items |
| <50 | Low | May not be worth pursuing |

---

## Performance Tiers

The system uses five performance tiers based on industry benchmarks:

| Tier | Contact Rate | Quote Rate | Close Rate | CAC | Lead Volume |
|------|-------------|------------|------------|-----|-------------|
| Top 10% | 55-70% | 35-50% | 25-40% | $25-60 | 150-300/mo |
| Top 25% | 45-55% | 25-35% | 18-25% | $50-90 | 100-150/mo |
| Average | 30-45% | 15-25% | 12-18% | $80-130 | 50-100/mo |
| Below Average | 20-30% | 10-15% | 6-12% | $120-180 | 25-50/mo |
| Bottom 10% | 10-20% | 5-10% | 2-6% | $160-250 | 10-25/mo |

---

## Cross-Sell Patterns

The system uses historical data to identify successful cross-sell patterns:

| Primary Product | Added Product | Avg Lift | Adoption Rate | Avg Time |
|----------------|---------------|----------|---------------|----------|
| Home | Auto | 35% | 65% | 6 months |
| Auto | Home | 28% | 55% | 8 months |
| Auto | Life | 15% | 30% | 12 months |
| Home | Life | 12% | 25% | 14 months |

---

## Accuracy and Validation

### Validation Approach

1. **Historical Backtesting**: Compare predictions to actual outcomes for agents who added products
2. **A/B Testing**: Track recommendation acceptance rates
3. **Lift Accuracy**: Target ≤20% variance from projected vs actual lift

### Confidence Calibration

The confidence scores are calibrated so that:
- **High confidence (>0.75)**: ~80% of predictions should be within 20% of actual
- **Medium confidence (0.55-0.75)**: ~65% within 20%
- **Low confidence (<0.55)**: ~50% within 20%

---

## Limitations

1. **Data Quality Dependency**: Analysis is only as good as the CRM data
2. **Historical Bias**: Patterns based on past performance may not predict future results
3. **Market Changes**: External factors not captured in the model
4. **Small Sample Sizes**: Less reliable for unique agent profiles

### Mitigations

- Require minimum 10 similar agents for projections
- Fall back to general benchmarks when peer data is insufficient
- Display confidence levels prominently
- Recommend regular benchmark refreshes
