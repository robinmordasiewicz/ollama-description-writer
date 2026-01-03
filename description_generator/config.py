"""
Configuration for description tiers and generation settings.
"""
from .models import TierConfig, DescriptionTier

# Default vLLM server settings
DEFAULT_BASE_URL = "http://localhost:8000/v1"
DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_TOP_P = 0.9

# Tier configurations with length constraints and structural guidance
# Aligned with f5xc-api-enriched character limits for compatibility
TIER_CONFIGS: dict[DescriptionTier, TierConfig] = {
    DescriptionTier.SHORT: TierConfig(
        min_chars=35,
        max_chars=60,
        max_tokens=25,
        word_budget="5-10 words",
        structure="Single concise noun phrase"
    ),
    DescriptionTier.MEDIUM: TierConfig(
        min_chars=100,
        max_chars=150,
        max_tokens=60,
        word_budget="15-25 words",
        structure="1-2 complete sentences"
    ),
    DescriptionTier.LONG: TierConfig(
        min_chars=350,
        max_chars=500,
        max_tokens=200,
        word_budget="55-80 words",
        structure="2-3 focused paragraphs"
    ),
}


def get_tier_config(tier: DescriptionTier) -> TierConfig:
    """Get configuration for a specific tier."""
    return TIER_CONFIGS[tier]


def get_all_tiers() -> list[DescriptionTier]:
    """Get all available tiers."""
    return list(DescriptionTier)
