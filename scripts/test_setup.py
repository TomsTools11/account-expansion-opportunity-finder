#!/usr/bin/env python3
"""Test script to verify local setup and connections."""

import sys
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()


def test_close_crm():
    """Test Close CRM connection."""
    print("=" * 50)
    print("Testing Close CRM Connection...")
    print("=" * 50)

    try:
        from src.integrations import CloseClient
        client = CloseClient()

        if client.test_connection():
            print("✓ Close CRM: Connected successfully!")

            # Try to fetch some agents
            print("\nFetching agents from Close CRM...")
            agents = client.fetch_all_agents(max_agents=5)
            print(f"✓ Found {len(agents)} agents")

            if agents:
                print("\nSample agent:")
                agent = agents[0]
                print(f"  - ID: {agent.id}")
                print(f"  - Name: {agent.name}")
                print(f"  - Products: {agent.current_products}")
                print(f"  - Premium Volume: ${agent.annual_premium_volume:,.2f}")
                print(f"  - Tier: {agent.performance_tier}")

            return True
        else:
            print("✗ Close CRM: Connection failed")
            return False

    except Exception as e:
        print(f"✗ Close CRM Error: {e}")
        return False


def test_google_sheets():
    """Test Google Sheets connection."""
    print("\n" + "=" * 50)
    print("Testing Google Sheets Connection...")
    print("=" * 50)

    try:
        from src.integrations import SheetsClient
        client = SheetsClient()

        if client.test_connection():
            print("✓ Google Sheets: Connected successfully!")

            # Try to load benchmarks
            print("\nLoading benchmark data...")
            benchmarks = client.load_benchmarks(use_cache=False)

            print(f"✓ Loaded {len(benchmarks.tiers)} performance tiers")
            print(f"✓ Loaded {len(benchmarks.products)} product benchmarks")
            print(f"✓ Loaded {len(benchmarks.cross_sell_patterns)} cross-sell patterns")

            if benchmarks.tiers:
                print("\nPerformance Tiers:")
                for tier in benchmarks.tiers:
                    print(f"  - {tier.tier_name.value}: Contact {tier.contact_rate_range[0]}-{tier.contact_rate_range[1]}%")

            if benchmarks.products:
                print("\nProduct Benchmarks:")
                for product in benchmarks.products:
                    print(f"  - {product.product}: CAC ${product.blended_cac:.2f}")

            return True
        else:
            print("✗ Google Sheets: Connection failed")
            return False

    except Exception as e:
        print(f"✗ Google Sheets Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_analysis_engine():
    """Test the analysis engine with real data."""
    print("\n" + "=" * 50)
    print("Testing Analysis Engine...")
    print("=" * 50)

    try:
        from src.integrations import CloseClient, SheetsClient
        from src.analysis import create_analysis_engine

        # Load data
        close_client = CloseClient()
        sheets_client = SheetsClient()

        print("Loading agents and benchmarks...")
        agents = close_client.fetch_all_agents(max_agents=20)
        benchmarks = sheets_client.load_benchmarks()

        if not agents:
            print("✗ No agents found - cannot test analysis")
            return False

        print(f"✓ Loaded {len(agents)} agents")

        # Create engine and analyze
        engine = create_analysis_engine(benchmarks, min_confidence=0.3)

        # Single agent analysis
        print(f"\nAnalyzing agent: {agents[0].name}...")
        result = engine.analyze_single_agent(agents[0], agents)

        print(f"✓ Found {len(result.opportunities)} opportunities")

        if result.opportunities:
            print("\nTop Opportunity:")
            opp = result.opportunities[0]
            print(f"  - Type: {opp.opportunity_type.value}")
            print(f"  - Product: {opp.recommended_product or 'N/A'}")
            print(f"  - Projected Lift: ${opp.projected_revenue_lift:,.2f}")
            print(f"  - Confidence: {opp.confidence_level.value} ({opp.confidence_score:.2f})")
            print(f"  - Priority Score: {opp.priority_score}")

        # Batch analysis
        print(f"\nRunning batch analysis on {len(agents)} agents...")
        batch_result = engine.analyze_batch(agents, top_n=5)

        print(f"✓ Analyzed {batch_result.total_agents_analyzed} agents")
        print(f"✓ Found {batch_result.total_opportunities_found} total opportunities")
        print(f"✓ Total projected lift: ${batch_result.summary_stats.get('total_projected_lift', 0):,.2f}")

        return True

    except Exception as e:
        print(f"✗ Analysis Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "#" * 60)
    print("#  Insurance Agent Account Expansion Analyzer - Setup Test  #")
    print("#" * 60)

    results = {
        "Close CRM": test_close_crm(),
        "Google Sheets": test_google_sheets(),
    }

    # Only test analysis if both connections work
    if all(results.values()):
        results["Analysis Engine"] = test_analysis_engine()

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    all_passed = True
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 All tests passed! Your setup is complete.")
        print("\nYou can now use the MCP server:")
        print("  expansion-analyzer")
        print("\nOr test with Claude Desktop by adding to your config.")
    else:
        print("Some tests failed. Please check the errors above.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
