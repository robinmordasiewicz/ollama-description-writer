"""
Description Generator - Deterministic product description generation using vLLM.

This package provides a programmatic toolchain for generating technical documentation
descriptions in three tiers (short/medium/long) with intelligent prompt engineering
that constrains output length at generation time.

Usage:
    from description_generator import DescriptionGenerator, ProductInput, DescriptionTier

    # Create generator
    gen = DescriptionGenerator()

    # Generate for a product
    product = ProductInput(name="Wireless Mouse", features=["Bluetooth", "Ergonomic"])
    result = gen.generate(product)

    # Access results
    print(result.descriptions["short"].content)
    print(result.model_dump_json(indent=2))
"""

from .models import (
    ProductInput,
    DescriptionTier,
    DescriptionResult,
    GenerationOutput,
    BatchInput,
    BatchOutput,
    TierConfig,
)
from .generator import DescriptionGenerator, create_generator
from .config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    TIER_CONFIGS,
    get_tier_config,
    get_all_tiers,
)
from .prompts import build_prompt, get_system_prompt
from .tracking import ResultTracker, ExperimentMatrix, ExperimentRun
from .validation import (
    DescriptionValidator,
    ValidationResult,
    BatchValidationResult,
    validate_description,
    validate_descriptions,
)
from .f5xc_compat import (
    F5XCAdapter,
    DESCRIPTION_SCHEMA,
    F5XC_BANNED_TERMS,
    F5XC_SYNONYMS,
    get_f5xc_system_prompt,
    build_f5xc_prompt,
    apply_synonyms,
    noun_first_transform,
)

__version__ = "0.2.0"

__all__ = [
    # Models
    "ProductInput",
    "DescriptionTier",
    "DescriptionResult",
    "GenerationOutput",
    "BatchInput",
    "BatchOutput",
    "TierConfig",
    # Generator
    "DescriptionGenerator",
    "create_generator",
    # Config
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "TIER_CONFIGS",
    "get_tier_config",
    "get_all_tiers",
    # Prompts
    "build_prompt",
    "get_system_prompt",
    # Tracking
    "ResultTracker",
    "ExperimentMatrix",
    "ExperimentRun",
    # Validation
    "DescriptionValidator",
    "ValidationResult",
    "BatchValidationResult",
    "validate_description",
    "validate_descriptions",
    # f5xc Compatibility
    "F5XCAdapter",
    "DESCRIPTION_SCHEMA",
    "F5XC_BANNED_TERMS",
    "F5XC_SYNONYMS",
    "get_f5xc_system_prompt",
    "build_f5xc_prompt",
    "apply_synonyms",
    "noun_first_transform",
]
