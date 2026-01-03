"""
5-Layer validation system for generated descriptions.

Based on f5xc-api-enriched validation patterns:
1. Banned patterns (terminology, marketing language, CRUD verbs)
2. Self-referential check (descriptions shouldn't reference themselves)
3. Quality metrics (character limits, word count)
4. Circular definitions (shouldn't repeat field name)
5. Complete thought (grammatical completeness)
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from .models import DescriptionTier
from .config import get_tier_config


@dataclass
class ValidationResult:
    """Result of validating a single description."""
    is_valid: bool
    tier: DescriptionTier
    content: str
    char_count: int
    word_count: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def error_summary(self) -> str:
        """Human-readable error summary."""
        if not self.errors:
            return "Valid"
        return "; ".join(self.errors)


@dataclass
class BatchValidationResult:
    """Result of validating short/medium/long descriptions."""
    short: Optional[ValidationResult] = None
    medium: Optional[ValidationResult] = None
    long: Optional[ValidationResult] = None

    @property
    def all_valid(self) -> bool:
        """True if all present descriptions are valid."""
        results = [r for r in [self.short, self.medium, self.long] if r]
        return all(r.is_valid for r in results)

    @property
    def valid_count(self) -> int:
        """Number of valid descriptions."""
        results = [r for r in [self.short, self.medium, self.long] if r]
        return sum(1 for r in results if r.is_valid)

    @property
    def total_count(self) -> int:
        """Total number of descriptions validated."""
        return sum(1 for r in [self.short, self.medium, self.long] if r)


class DescriptionValidator:
    """
    5-layer validation for generated descriptions.

    Layers:
    1. BANNED_PATTERNS - Terminology and marketing language
    2. SELF_REFERENTIAL - Descriptions shouldn't reference themselves
    3. QUALITY_METRICS - Character and word count limits
    4. CIRCULAR_DEFINITION - Shouldn't just repeat the name
    5. COMPLETE_THOUGHT - Grammatical completeness
    """

    # Layer 1: Banned patterns
    BANNED_TERMS = [
        # Vendor/product names (case-insensitive)
        r'\bF5\b', r'\bXC\b', r'\bF5XC\b', r'\bDistributed Cloud\b',
        r'\bBIG-IP\b', r'\bNGINX\b', r'\bVolterra\b',

        # Marketing language
        r'\bworld-class\b', r'\bmarket-leading\b', r'\bcutting-edge\b',
        r'\bnext-generation\b', r'\bstate-of-the-art\b', r'\bseamless\b',
        r'\brobust\b', r'\bpowerful\b', r'\bcomprehensive\b',
        r'\binnovative\b', r'\bscalable\b', r'\bflexible\b',
        r'\bsimplifies\b', r'\bstreamlines\b', r'\bempowers\b',
        r'\bunparalleled\b', r'\bultimate\b', r'\bsuperior\b',

        # Superlatives
        r'\bbest\b', r'\bworst\b', r'\bmost\b', r'\bleast\b',
        r'\bfastest\b', r'\bslowest\b', r'\beasiest\b',

        # Filler phrases
        r'\bin order to\b', r'\bable to\b', r'\bhelps to\b',
        r'\ballows you to\b', r'\benables you to\b',
        r'\bdesigned to\b', r'\bused to\b',

        # Generic API terms (for API docs context)
        r'\bAPI\b', r'\bREST\b', r'\bEndpoint\b',
    ]

    # Layer 1: Banned verb prefixes (noun-first rule)
    BANNED_VERB_STARTS = [
        r'^Configure\b', r'^Manage\b', r'^Create\b', r'^Delete\b',
        r'^Update\b', r'^Get\b', r'^Set\b', r'^Enable\b',
        r'^Disable\b', r'^Add\b', r'^Remove\b', r'^Edit\b',
        r'^Modify\b', r'^Define\b', r'^Specify\b', r'^Select\b',
        r'^Use\b', r'^Apply\b', r'^View\b', r'^List\b',
        r'^This\b', r'^The\b', r'^A\b', r'^An\b',
    ]

    # Layer 2: Self-referential patterns
    SELF_REFERENTIAL = [
        r'\bthis field\b', r'\bthis property\b', r'\bthis setting\b',
        r'\bthis option\b', r'\bthis parameter\b', r'\bthis value\b',
        r'\bthe field\b', r'\bthe property\b', r'\bthe setting\b',
        r'\bspecifies the\b', r'\bdefines the\b', r'\bsets the\b',
        r'\bcontains the\b', r'\bholds the\b', r'\bstores the\b',
    ]

    def __init__(
        self,
        strict_mode: bool = False,
        custom_banned_terms: Optional[list[str]] = None,
    ):
        """
        Initialize validator.

        Args:
            strict_mode: If True, warnings become errors
            custom_banned_terms: Additional terms to ban
        """
        self.strict_mode = strict_mode
        self.banned_patterns = [re.compile(p, re.IGNORECASE) for p in self.BANNED_TERMS]
        self.verb_patterns = [re.compile(p, re.IGNORECASE) for p in self.BANNED_VERB_STARTS]
        self.self_ref_patterns = [re.compile(p, re.IGNORECASE) for p in self.SELF_REFERENTIAL]

        if custom_banned_terms:
            self.banned_patterns.extend([
                re.compile(rf'\b{re.escape(term)}\b', re.IGNORECASE)
                for term in custom_banned_terms
            ])

    def validate(
        self,
        content: str,
        tier: DescriptionTier,
        field_name: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate a single description against all 5 layers.

        Args:
            content: The description text
            tier: Description tier (short/medium/long)
            field_name: Optional field name for circular definition check

        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []

        content = content.strip()
        char_count = len(content)
        word_count = len(content.split())
        config = get_tier_config(tier)

        # Layer 1: Banned patterns
        for pattern in self.banned_patterns:
            if pattern.search(content):
                match = pattern.pattern.replace(r'\b', '').replace('\\', '')
                errors.append(f"Banned term: {match}")

        # Layer 1b: Verb-first check (noun-first rule)
        for pattern in self.verb_patterns:
            if pattern.match(content):
                match = pattern.pattern.replace('^', '').replace(r'\b', '')
                warnings.append(f"Starts with verb/article: {match}")

        # Layer 2: Self-referential check
        for pattern in self.self_ref_patterns:
            if pattern.search(content):
                match = pattern.pattern.replace(r'\b', '')
                warnings.append(f"Self-referential: {match}")

        # Layer 3: Quality metrics
        if char_count < config.min_chars:
            errors.append(f"Too short: {char_count} < {config.min_chars} chars")
        elif char_count > config.max_chars:
            errors.append(f"Too long: {char_count} > {config.max_chars} chars")

        min_words = 3
        if word_count < min_words:
            errors.append(f"Too few words: {word_count} < {min_words}")

        # Layer 4: Circular definition check
        if field_name:
            field_lower = field_name.lower().replace('_', ' ').replace('-', ' ')
            content_lower = content.lower()
            # Check if description is just the field name repeated
            if content_lower.startswith(field_lower) or content_lower == field_lower:
                errors.append(f"Circular definition: repeats field name '{field_name}'")

        # Layer 5: Complete thought check
        if not self._is_complete_thought(content):
            warnings.append("May not be a complete thought")

        # In strict mode, warnings become errors
        if self.strict_mode:
            errors.extend(warnings)
            warnings = []

        return ValidationResult(
            is_valid=len(errors) == 0,
            tier=tier,
            content=content,
            char_count=char_count,
            word_count=word_count,
            errors=errors,
            warnings=warnings,
        )

    def validate_batch(
        self,
        descriptions: dict[str, str],
        field_name: Optional[str] = None,
    ) -> BatchValidationResult:
        """
        Validate a batch of short/medium/long descriptions.

        Args:
            descriptions: Dict with keys 'short', 'medium', 'long'
            field_name: Optional field name for circular definition check

        Returns:
            BatchValidationResult with individual results
        """
        result = BatchValidationResult()

        tier_map = {
            'short': DescriptionTier.SHORT,
            'medium': DescriptionTier.MEDIUM,
            'long': DescriptionTier.LONG,
        }

        for key, tier in tier_map.items():
            if key in descriptions and descriptions[key]:
                validation = self.validate(descriptions[key], tier, field_name)
                setattr(result, key, validation)

        return result

    def _is_complete_thought(self, content: str) -> bool:
        """
        Check if content appears to be a complete grammatical thought.

        Basic heuristics:
        - Has reasonable length
        - Doesn't end mid-sentence (no trailing conjunctions, etc.)
        - Contains at least a noun-like structure
        """
        content = content.strip()

        # Too short to be complete
        if len(content) < 10:
            return False

        # Ends with incomplete markers
        incomplete_endings = [
            ' and', ' or', ' but', ' with', ' for', ' to',
            ' the', ' a', ' an', ' in', ' on', ' at',
        ]
        content_lower = content.lower()
        for ending in incomplete_endings:
            if content_lower.endswith(ending):
                return False

        # Starts with lowercase (likely fragment)
        if content[0].islower():
            return False

        return True


def validate_description(
    content: str,
    tier: DescriptionTier,
    strict: bool = False,
) -> ValidationResult:
    """
    Convenience function to validate a single description.

    Args:
        content: Description text
        tier: Description tier
        strict: If True, warnings become errors

    Returns:
        ValidationResult
    """
    validator = DescriptionValidator(strict_mode=strict)
    return validator.validate(content, tier)


def validate_descriptions(
    descriptions: dict[str, str],
    strict: bool = False,
) -> BatchValidationResult:
    """
    Convenience function to validate short/medium/long descriptions.

    Args:
        descriptions: Dict with 'short', 'medium', 'long' keys
        strict: If True, warnings become errors

    Returns:
        BatchValidationResult
    """
    validator = DescriptionValidator(strict_mode=strict)
    return validator.validate_batch(descriptions)
