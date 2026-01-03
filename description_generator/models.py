"""
Pydantic models for structured input/output.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
from datetime import datetime


class DescriptionTier(str, Enum):
    """Available description length tiers."""
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class ProductInput(BaseModel):
    """Input schema for a product to describe."""
    name: str = Field(..., min_length=1, description="Product name")
    features: list[str] = Field(..., min_length=1, description="List of product features")
    category: Optional[str] = Field(None, description="Product category for context")

    @field_validator('features')
    @classmethod
    def features_not_empty(cls, v: list[str]) -> list[str]:
        if not v or all(f.strip() == "" for f in v):
            raise ValueError("At least one non-empty feature is required")
        return [f.strip() for f in v if f.strip()]

    def features_str(self) -> str:
        """Return features as a comma-separated string."""
        return ", ".join(self.features)


class TierConfig(BaseModel):
    """Configuration for a description tier."""
    min_chars: int = Field(..., gt=0, description="Minimum character count")
    max_chars: int = Field(..., gt=0, description="Maximum character count")
    max_tokens: int = Field(..., gt=0, description="Maximum tokens for generation")
    word_budget: str = Field(..., description="Approximate word count guidance")
    structure: str = Field(..., description="Structural guidance for the tier")

    @property
    def char_range(self) -> str:
        """Return character range as string."""
        return f"{self.min_chars}-{self.max_chars}"


class DescriptionResult(BaseModel):
    """Result of generating a single description."""
    tier: DescriptionTier
    content: str
    char_count: int
    within_limits: bool
    target_range: str
    tokens_used: int

    @classmethod
    def from_generation(
        cls,
        tier: DescriptionTier,
        content: str,
        config: TierConfig,
        tokens_used: int
    ) -> "DescriptionResult":
        """Create result from generation output."""
        char_count = len(content)
        within_limits = config.min_chars <= char_count <= config.max_chars
        return cls(
            tier=tier,
            content=content,
            char_count=char_count,
            within_limits=within_limits,
            target_range=config.char_range,
            tokens_used=tokens_used
        )


class GenerationOutput(BaseModel):
    """Complete output for a product's descriptions."""
    product: ProductInput
    descriptions: dict[str, DescriptionResult]
    model: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    all_valid: bool = False

    def model_post_init(self, __context) -> None:
        """Calculate all_valid after initialization."""
        if self.descriptions:
            self.all_valid = all(d.within_limits for d in self.descriptions.values())


class BatchInput(BaseModel):
    """Input schema for batch processing."""
    products: list[ProductInput] = Field(..., min_length=1)
    tiers: list[DescriptionTier] = Field(
        default=[DescriptionTier.SHORT, DescriptionTier.MEDIUM, DescriptionTier.LONG]
    )
    settings: Optional[dict] = Field(default=None, description="Optional generation settings")


class BatchOutput(BaseModel):
    """Output schema for batch processing."""
    results: list[GenerationOutput]
    total_products: int
    all_valid: bool
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def model_post_init(self, __context) -> None:
        """Calculate aggregates after initialization."""
        self.total_products = len(self.results)
        self.all_valid = all(r.all_valid for r in self.results)
