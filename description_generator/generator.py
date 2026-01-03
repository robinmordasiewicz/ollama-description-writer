"""
Core generator for vLLM-based description generation.

Supports two modes:
1. Structured generation with ProductInput and tiers
2. Raw prompt generation (f5xc-style) with custom prompts and JSON schemas
"""
from openai import OpenAI
from typing import Optional, Any
import json
import logging
import re

from .models import (
    ProductInput,
    DescriptionTier,
    DescriptionResult,
    GenerationOutput,
    BatchOutput,
)
from .config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    get_tier_config,
    get_all_tiers,
)
from .prompts import build_prompt, get_system_prompt

logger = logging.getLogger(__name__)


class DescriptionGenerator:
    """
    Generate product descriptions using vLLM with intelligent prompt engineering.

    The generator uses carefully crafted prompts to constrain the model's output
    to specific length tiers without requiring post-processing truncation.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = DEFAULT_TOP_P,
        api_key: str = "EMPTY",
    ):
        """
        Initialize the generator.

        Args:
            base_url: vLLM server URL
            model: Model identifier
            temperature: Generation temperature (lower = more deterministic)
            top_p: Top-p sampling parameter
            api_key: API key (use "EMPTY" for local vLLM)
        """
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self._system_prompt = get_system_prompt()

    def generate_single(
        self,
        product: ProductInput,
        tier: DescriptionTier,
    ) -> DescriptionResult:
        """
        Generate a single description for a product and tier.

        Args:
            product: Product to describe
            tier: Description tier

        Returns:
            DescriptionResult with content and validation metadata
        """
        config = get_tier_config(tier)
        prompt = build_prompt(product, tier)

        logger.debug(f"Generating {tier.value} description for: {product.name}")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=config.max_tokens,
        )

        content = response.choices[0].message.content.strip()
        tokens_used = response.usage.total_tokens

        result = DescriptionResult.from_generation(
            tier=tier,
            content=content,
            config=config,
            tokens_used=tokens_used
        )

        logger.debug(
            f"Generated {tier.value}: {result.char_count} chars "
            f"(target: {result.target_range}, valid: {result.within_limits})"
        )

        return result

    def generate(
        self,
        product: ProductInput,
        tiers: Optional[list[DescriptionTier]] = None,
    ) -> GenerationOutput:
        """
        Generate descriptions for a product across specified tiers.

        Args:
            product: Product to describe
            tiers: List of tiers to generate (defaults to all)

        Returns:
            GenerationOutput with all descriptions and metadata
        """
        if tiers is None:
            tiers = get_all_tiers()

        descriptions = {}
        for tier in tiers:
            result = self.generate_single(product, tier)
            descriptions[tier.value] = result

        return GenerationOutput(
            product=product,
            descriptions=descriptions,
            model=self.model,
        )

    def batch_generate(
        self,
        products: list[ProductInput],
        tiers: Optional[list[DescriptionTier]] = None,
    ) -> BatchOutput:
        """
        Generate descriptions for multiple products.

        Args:
            products: List of products to describe
            tiers: List of tiers to generate (defaults to all)

        Returns:
            BatchOutput with all results
        """
        results = []
        for product in products:
            logger.info(f"Processing: {product.name}")
            result = self.generate(product, tiers)
            results.append(result)

        return BatchOutput(results=results)

    def generate_raw(
        self,
        prompt: str,
        schema: Optional[dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        timeout: int = 120,
    ) -> dict[str, str] | None:
        """
        Generate from a raw prompt with optional JSON schema enforcement.

        This method mimics the Claude Code CLI interface for compatibility
        with f5xc-api-enriched and similar projects.

        Args:
            prompt: The full prompt to send (can be 600+ lines)
            schema: JSON schema for structured output (e.g., {"short": "string", ...})
            system_prompt: Optional system prompt override
            max_tokens: Maximum tokens for generation
            timeout: Request timeout in seconds (not enforced by OpenAI client)

        Returns:
            Dictionary matching the schema, or None on error
        """
        # Build system prompt with JSON schema guidance
        sys_prompt = system_prompt or "You are generating descriptions. Respond ONLY with valid JSON."
        if schema:
            sys_prompt += f"\n\nYou MUST respond with JSON matching this exact schema:\n{json.dumps(schema, indent=2)}"
            sys_prompt += "\n\nDo not include any text before or after the JSON. No explanations."

        logger.debug(f"generate_raw: prompt length={len(prompt)}, schema={schema is not None}")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=max_tokens,
            )

            content = response.choices[0].message.content.strip()
            logger.debug(f"Raw response: {content[:200]}...")

            # Parse JSON response
            return self._parse_json_response(content, schema)

        except Exception as e:
            logger.error(f"generate_raw failed: {e}")
            return None

    def _parse_json_response(
        self,
        content: str,
        schema: Optional[dict[str, Any]] = None
    ) -> dict[str, str] | None:
        """
        Parse JSON from model response, handling common formatting issues.

        Args:
            content: Raw model output
            schema: Expected schema for validation

        Returns:
            Parsed dictionary or None on error
        """
        if not content:
            return None

        # Try to extract JSON from the response
        # Handle cases where model wraps JSON in markdown code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            content = json_match.group(1).strip()

        # Also handle cases where there's text before/after JSON
        # Look for the outermost { }
        brace_start = content.find('{')
        brace_end = content.rfind('}')
        if brace_start != -1 and brace_end != -1:
            content = content[brace_start:brace_end + 1]

        try:
            data = json.loads(content)

            # Validate against schema if provided
            if schema and "properties" in schema:
                required = schema.get("required", [])
                for key in required:
                    if key not in data:
                        logger.warning(f"Missing required key: {key}")
                        return None

            # Validate non-empty values (at least 3 words)
            non_empty = sum(
                1 for v in data.values()
                if isinstance(v, str) and len(v.split()) >= 3
            )
            if non_empty == 0:
                logger.warning("All values are empty or too short")
                return None

            return data

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.debug(f"Content was: {content[:500]}...")
            return None

    def test_connection(self) -> bool:
        """
        Test connection to the vLLM server.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            models = self.client.models.list()
            logger.info(f"Connected to vLLM. Available models: {[m.id for m in models.data]}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to vLLM: {e}")
            return False


def create_generator(
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    **kwargs
) -> DescriptionGenerator:
    """
    Factory function to create a generator instance.

    Args:
        base_url: vLLM server URL
        model: Model identifier
        **kwargs: Additional generator parameters

    Returns:
        Configured DescriptionGenerator instance
    """
    return DescriptionGenerator(base_url=base_url, model=model, **kwargs)
