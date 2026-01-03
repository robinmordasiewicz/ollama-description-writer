"""
Prompt engineering templates for length-constrained description generation.

Key principle: Prompts must constrain the model's thinking space so it naturally
produces output within limits - no truncation needed.
"""
from .models import DescriptionTier, ProductInput, TierConfig
from .config import get_tier_config


# System prompt establishing the technical writer persona
SYSTEM_PROMPT = """You are a technical documentation writer specializing in concise, accurate product descriptions.

RULES:
- Write factual, feature-focused content
- No marketing language, superlatives, or hyperbole
- No exclamation marks or emojis
- No markdown formatting
- Follow length constraints precisely
- Count characters mentally before responding"""


# Tier-specific length guidance to help model self-constrain
# Aligned with f5xc-api-enriched character limits
TIER_GUIDANCE = {
    DescriptionTier.SHORT: """LENGTH CALIBRATION for SHORT description:
- Target: {min_chars}-{max_chars} characters (approximately {word_budget})
- Structure: {structure}
- Start with noun, not verb (e.g., "Configuration for..." not "Configure...")
- Example (45 chars): "High-performance wireless mouse with 4000 DPI"
- Example (52 chars): "Load balancing service for HTTP traffic distribution"
- Omit articles (a, an, the) and filler words""",

    DescriptionTier.MEDIUM: """LENGTH CALIBRATION for MEDIUM description:
- Target: {min_chars}-{max_chars} characters (approximately {word_budget})
- Structure: {structure}
- Sentence 1: What it is and primary function
- Sentence 2: Key capability or use case
- Example (128 chars): "Wireless mouse with ergonomic design and Bluetooth 5.0. Features 4000 DPI optical sensor for precision control during extended use."
- Start with noun phrase, use active voice""",

    DescriptionTier.LONG: """LENGTH CALIBRATION for LONG description:
- Target: {min_chars}-{max_chars} characters (approximately {word_budget})
- Structure: {structure}
- CRITICAL: You MUST write at least {min_chars} characters. Short responses will be rejected.

REQUIRED CONTENT STRUCTURE (3 paragraphs):
1. Opening paragraph (~120 chars): Core product description and primary purpose
2. Middle paragraph (~150 chars): Technical specifications and key features
3. Closing paragraph (~100 chars): Use cases and target audience

EXAMPLE OUTPUT (425 characters - match this length):
"Mechanical keyboard with hot-swappable switches for customized typing experience. The aluminum frame provides durability while maintaining a compact profile suitable for desk setups.

Features per-key RGB backlighting with software control, dedicated media keys, and USB-C connectivity for universal compatibility.

Designed for users requiring responsive tactile feedback during extended typing sessions, whether for productivity or gaming applications."

Write a complete, detailed description. Too short = failure."""
}


# Main prompt template
PROMPT_TEMPLATE = """Generate a {tier} product description.

{tier_guidance}

PRODUCT DETAILS:
- Name: {product_name}
- Features: {features}
{category_line}

OUTPUT REQUIREMENTS:
- Return ONLY the description text
- No quotes, labels, or explanations
- No markdown or special formatting
- Must be {min_chars}-{max_chars} characters exactly
- Verify character count mentally before responding"""


def build_prompt(product: ProductInput, tier: DescriptionTier) -> str:
    """
    Build a length-constrained prompt for a specific tier.

    Args:
        product: Product to describe
        tier: Description tier (short/medium/long)

    Returns:
        Formatted prompt string
    """
    config = get_tier_config(tier)

    # Format tier-specific guidance with config values
    tier_guidance = TIER_GUIDANCE[tier].format(
        min_chars=config.min_chars,
        max_chars=config.max_chars,
        word_budget=config.word_budget,
        structure=config.structure
    )

    # Optional category line
    category_line = f"- Category: {product.category}" if product.category else ""

    return PROMPT_TEMPLATE.format(
        tier=tier.value.upper(),
        tier_guidance=tier_guidance,
        product_name=product.name,
        features=product.features_str(),
        category_line=category_line,
        min_chars=config.min_chars,
        max_chars=config.max_chars
    )


def get_system_prompt() -> str:
    """Get the system prompt for the technical writer persona."""
    return SYSTEM_PROMPT
