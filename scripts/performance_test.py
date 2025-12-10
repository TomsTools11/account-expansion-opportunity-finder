#!/usr/bin/env python3
"""Performance test script for the analysis engine.

Usage:
    python scripts/performance_test.py [--agents N] [--iterations N] [--parallel]

Options:
    --agents N       Number of agents to generate (default: 100)
    --iterations N   Number of test iterations (default: 3)
    --parallel       Use parallel processing (default: enabled)
    --no-parallel    Disable parallel processing
"""

import argparse
import random
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Add src to path for imports
sys.path.insert(0, ".")

from src.analysis import create_analysis_engine
from src.models import (
    Agent,
    BenchmarkData,
    BenchmarkTier,
    CrossSellPattern,
    PerformanceTier,
    ProductBenchmark,
)


@dataclass
class PerformanceResult:
    """Performance test result."""
    agent_count: int
    total_time_seconds: float
    avg_time_per_agent_ms: float
    opportunities_found: int
    parallel: bool


def create_benchmark_data() -> BenchmarkData:
    """Create comprehensive benchmark data for testing."""
    return BenchmarkData(
        tiers=[
            BenchmarkTier(
                tier_name=PerformanceTier.TOP_10,
                contact_rate_range=(55.0, 70.0),
                quote_rate_range=(35.0, 50.0),
                close_rate_range=(25.0, 40.0),
                cac_range=(25.0, 60.0),
                lead_volume_range=(150, 300),
            ),
            BenchmarkTier(
                tier_name=PerformanceTier.TOP_25,
                contact_rate_range=(45.0, 55.0),
                quote_rate_range=(25.0, 35.0),
                close_rate_range=(18.0, 25.0),
                cac_range=(50.0, 90.0),
                lead_volume_range=(100, 150),
            ),
            BenchmarkTier(
                tier_name=PerformanceTier.AVERAGE,
                contact_rate_range=(30.0, 45.0),
                quote_rate_range=(15.0, 25.0),
                close_rate_range=(12.0, 18.0),
                cac_range=(80.0, 130.0),
                lead_volume_range=(50, 100),
            ),
            BenchmarkTier(
                tier_name=PerformanceTier.BELOW_AVERAGE,
                contact_rate_range=(20.0, 30.0),
                quote_rate_range=(10.0, 15.0),
                close_rate_range=(6.0, 12.0),
                cac_range=(120.0, 180.0),
                lead_volume_range=(25, 50),
            ),
            BenchmarkTier(
                tier_name=PerformanceTier.BOTTOM_10,
                contact_rate_range=(10.0, 20.0),
                quote_rate_range=(5.0, 10.0),
                close_rate_range=(2.0, 6.0),
                cac_range=(160.0, 250.0),
                lead_volume_range=(10, 25),
            ),
        ],
        products=[
            ProductBenchmark(product="Auto", organic_cac=203.52, inorganic_cac=305.28, blended_cac=244.22),
            ProductBenchmark(product="Home", organic_cac=140.72, inorganic_cac=211.08, blended_cac=168.86),
            ProductBenchmark(product="Life", organic_cac=24.96, inorganic_cac=37.44, blended_cac=29.95),
            ProductBenchmark(product="Health", organic_cac=150.00, inorganic_cac=225.00, blended_cac=180.00),
            ProductBenchmark(product="Renters", organic_cac=50.00, inorganic_cac=75.00, blended_cac=60.00),
        ],
        cross_sell_patterns=[
            CrossSellPattern(primary_product="Home", added_product="Auto", avg_revenue_lift_pct=35.0, adoption_rate=0.65, avg_time_to_add_months=6),
            CrossSellPattern(primary_product="Auto", added_product="Home", avg_revenue_lift_pct=28.0, adoption_rate=0.55, avg_time_to_add_months=8),
            CrossSellPattern(primary_product="Auto", added_product="Life", avg_revenue_lift_pct=15.0, adoption_rate=0.30, avg_time_to_add_months=12),
            CrossSellPattern(primary_product="Home", added_product="Life", avg_revenue_lift_pct=12.0, adoption_rate=0.25, avg_time_to_add_months=14),
            CrossSellPattern(primary_product="Auto", added_product="Renters", avg_revenue_lift_pct=8.0, adoption_rate=0.20, avg_time_to_add_months=4),
        ],
    )


def generate_agents(count: int) -> list[Agent]:
    """Generate synthetic agents for testing.

    Creates a realistic distribution of agents across different tiers and product mixes.
    """
    agents = []
    products_list = ["Auto", "Home", "Life", "Health", "Renters"]

    tier_distribution = {
        PerformanceTier.TOP_10: 0.10,
        PerformanceTier.TOP_25: 0.15,
        PerformanceTier.AVERAGE: 0.50,
        PerformanceTier.BELOW_AVERAGE: 0.15,
        PerformanceTier.BOTTOM_10: 0.10,
    }

    tier_metrics = {
        PerformanceTier.TOP_10: {"contact": (55, 70), "close": (25, 40), "volume": (80000, 150000)},
        PerformanceTier.TOP_25: {"contact": (45, 55), "close": (18, 25), "volume": (50000, 80000)},
        PerformanceTier.AVERAGE: {"contact": (30, 45), "close": (12, 18), "volume": (25000, 50000)},
        PerformanceTier.BELOW_AVERAGE: {"contact": (20, 30), "close": (6, 12), "volume": (10000, 25000)},
        PerformanceTier.BOTTOM_10: {"contact": (10, 20), "close": (2, 6), "volume": (5000, 10000)},
    }

    for i in range(count):
        # Select tier based on distribution
        tier = random.choices(
            list(tier_distribution.keys()),
            weights=list(tier_distribution.values()),
        )[0]

        metrics = tier_metrics[tier]

        # Generate product mix (1-3 products)
        num_products = random.choices([1, 2, 3], weights=[0.40, 0.40, 0.20])[0]
        current_products = random.sample(products_list, num_products)

        agent = Agent(
            id=f"lead_{i:06d}",
            name=f"Agent {i:06d}",
            email=f"agent{i}@example.com",
            phone=f"+1-555-{i:07d}"[:15],
            current_products=current_products,
            annual_premium_volume=random.uniform(*metrics["volume"]),
            tenure_months=random.randint(6, 120),
            region=random.choice(["Northeast", "Southeast", "Midwest", "Southwest", "West"]),
            contact_rate=random.uniform(*metrics["contact"]),
            quote_rate=random.uniform(10, 50),
            close_rate=random.uniform(*metrics["close"]),
            monthly_lead_volume=random.randint(20, 200),
            performance_tier=tier,
        )
        agents.append(agent)

    return agents


def run_batch_test(
    engine,
    agents: list[Agent],
    parallel: bool = True,
) -> PerformanceResult:
    """Run a single batch analysis test and return results."""
    start = time.perf_counter()

    result = engine.analyze_batch(
        agents=agents,
        top_n=50,
        parallel=parallel,
        max_workers=4 if parallel else 1,
    )

    elapsed = time.perf_counter() - start

    return PerformanceResult(
        agent_count=len(agents),
        total_time_seconds=elapsed,
        avg_time_per_agent_ms=(elapsed / len(agents)) * 1000,
        opportunities_found=result.total_opportunities_found,
        parallel=parallel,
    )


def run_single_agent_tests(
    engine,
    agents: list[Agent],
    sample_count: int = 10,
) -> list[float]:
    """Run single agent analysis tests and return timing data."""
    times = []
    sample_agents = random.sample(agents, min(sample_count, len(agents)))

    for agent in sample_agents:
        start = time.perf_counter()
        engine.analyze_single_agent(agent, agents)
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)  # Convert to ms

    return times


def print_report(
    batch_results: list[PerformanceResult],
    single_times: list[float],
    agent_count: int,
):
    """Print the performance test report."""
    print("\n" + "=" * 60)
    print("PERFORMANCE TEST REPORT")
    print("=" * 60)
    print(f"\nTimestamp: {datetime.now().isoformat()}")
    print(f"Agent Count: {agent_count}")

    # Batch Analysis Results
    print("\n--- Batch Analysis ---")
    for result in batch_results:
        mode = "Parallel" if result.parallel else "Sequential"
        print(f"\n{mode} Mode:")
        print(f"  Total Time: {result.total_time_seconds:.2f}s")
        print(f"  Avg per Agent: {result.avg_time_per_agent_ms:.2f}ms")
        print(f"  Opportunities Found: {result.opportunities_found}")

    # Compare parallel vs sequential
    parallel_times = [r.total_time_seconds for r in batch_results if r.parallel]
    sequential_times = [r.total_time_seconds for r in batch_results if not r.parallel]

    if parallel_times and sequential_times:
        speedup = statistics.mean(sequential_times) / statistics.mean(parallel_times)
        print(f"\nParallel Speedup: {speedup:.2f}x")

    # Single Agent Results
    print("\n--- Single Agent Analysis ---")
    print(f"  Sample Size: {len(single_times)}")
    print(f"  Mean Time: {statistics.mean(single_times):.2f}ms")
    print(f"  Median Time: {statistics.median(single_times):.2f}ms")
    print(f"  Min Time: {min(single_times):.2f}ms")
    print(f"  Max Time: {max(single_times):.2f}ms")
    if len(single_times) > 1:
        print(f"  Std Dev: {statistics.stdev(single_times):.2f}ms")

    # Performance Targets
    print("\n--- Performance Targets ---")
    batch_avg = statistics.mean([r.total_time_seconds for r in batch_results if r.parallel])
    single_avg = statistics.mean(single_times)

    targets = [
        (f"Batch {agent_count} agents < 60s", batch_avg < 60.0, batch_avg),
        ("Single agent < 2000ms", single_avg < 2000, single_avg),
        ("Avg per agent < 500ms", batch_avg / agent_count * 1000 < 500, batch_avg / agent_count * 1000),
    ]

    for name, passed, value in targets:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: {value:.2f}")

    print("\n" + "=" * 60)

    # Return overall pass/fail
    return all(passed for _, passed, _ in targets)


def main():
    """Run the performance tests."""
    parser = argparse.ArgumentParser(description="Performance test for analysis engine")
    parser.add_argument("--agents", type=int, default=100, help="Number of agents")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations")
    parser.add_argument("--parallel", dest="parallel", action="store_true", default=True)
    parser.add_argument("--no-parallel", dest="parallel", action="store_false")
    args = parser.parse_args()

    print(f"Generating {args.agents} synthetic agents...")
    agents = generate_agents(args.agents)

    print("Creating analysis engine...")
    benchmarks = create_benchmark_data()
    engine = create_analysis_engine(benchmarks, min_confidence=0.3)

    print(f"Running {args.iterations} batch test iterations...")
    batch_results = []

    # Warm-up run
    print("  Warm-up run...")
    run_batch_test(engine, agents[:10], parallel=args.parallel)

    for i in range(args.iterations):
        print(f"  Iteration {i + 1}/{args.iterations}...")

        # Parallel test
        if args.parallel:
            result = run_batch_test(engine, agents, parallel=True)
            batch_results.append(result)

        # Sequential test (for comparison)
        result = run_batch_test(engine, agents, parallel=False)
        batch_results.append(result)

    print("Running single agent analysis tests...")
    single_times = run_single_agent_tests(engine, agents, sample_count=20)

    passed = print_report(batch_results, single_times, args.agents)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
