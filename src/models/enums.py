"""Enum definitions for the Insurance Agent Account Expansion Analyzer."""

from enum import Enum


class ProductType(str, Enum):
    """Insurance product types tracked in the system."""

    AUTO = "Auto"
    HOME = "Home"
    LIFE = "Life"
    HEALTH = "Health"
    RENTERS = "Renters"
    MEDICARE = "Medicare"
    COMMERCIAL_PROPERTY = "Commercial Property"
    COMMERCIAL_AUTO = "Commercial Auto"

    @classmethod
    def values(cls) -> list[str]:
        """Return all product type values as strings."""
        return [p.value for p in cls]


class PerformanceTier(str, Enum):
    """Agent performance tier classifications."""

    TOP_10 = "Top 10%"
    TOP_25 = "Top 25%"
    AVERAGE = "Average"
    BELOW_AVERAGE = "Below Average"
    BOTTOM_10 = "Bottom 10%"

    @classmethod
    def from_percentile(cls, percentile: float) -> "PerformanceTier":
        """Determine tier from a percentile ranking (0-100, higher is better)."""
        if percentile >= 90:
            return cls.TOP_10
        elif percentile >= 75:
            return cls.TOP_25
        elif percentile >= 25:
            return cls.AVERAGE
        elif percentile >= 10:
            return cls.BELOW_AVERAGE
        else:
            return cls.BOTTOM_10

    @property
    def ordinal(self) -> int:
        """Return ordinal value for tier comparison (higher is better)."""
        tier_order = {
            self.BOTTOM_10: 1,
            self.BELOW_AVERAGE: 2,
            self.AVERAGE: 3,
            self.TOP_25: 4,
            self.TOP_10: 5,
        }
        return tier_order[self]


class AgencyType(str, Enum):
    """Type of insurance agency."""

    INDEPENDENT = "Independent"
    CAPTIVE = "Captive"
    MGA = "MGA"  # Managing General Agent


class OpportunityType(str, Enum):
    """Types of expansion opportunities."""

    ADD_PRODUCT = "Add Product"
    IMPROVE_CONVERSION = "Improve Conversion"
    INCREASE_VOLUME = "Increase Volume"


class ConfidenceLevel(str, Enum):
    """Confidence level classifications for opportunities."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INSUFFICIENT_DATA = "Insufficient Data"

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        """Determine confidence level from a numeric score (0-1)."""
        if score > 0.75:
            return cls.HIGH
        elif score > 0.55:
            return cls.MEDIUM
        elif score > 0:
            return cls.LOW
        else:
            return cls.INSUFFICIENT_DATA


class BenchmarkSection(str, Enum):
    """Sections of benchmark data that can be requested."""

    TIERS = "tiers"
    PRODUCTS = "products"
    CROSS_SELL = "cross_sell"
    CONVERSION_RATES = "conversion_rates"
    ALL = "all"
