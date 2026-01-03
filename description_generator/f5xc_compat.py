"""
f5xc-api-enriched compatibility module.

Provides f5xc-specific prompt patterns, banned terms, synonym replacements,
and integration helpers for migrating from Claude Code CLI to local vLLM.
"""
import json
from typing import Optional


# f5xc-specific banned terms (50+ patterns from original)
F5XC_BANNED_TERMS = [
    # Vendor names
    "F5", "XC", "F5XC", "Distributed Cloud", "BIG-IP", "NGINX", "Volterra",
    "Anthropic", "Claude", "OpenAI", "GPT",

    # Generic API terms
    "API", "REST", "RESTful", "Endpoint", "Request", "Response",
    "JSON", "XML", "HTTP", "HTTPS",

    # Marketing language
    "world-class", "market-leading", "cutting-edge", "next-generation",
    "state-of-the-art", "seamless", "robust", "powerful", "comprehensive",
    "innovative", "scalable", "flexible", "enterprise-grade", "best-in-class",
    "industry-leading", "mission-critical", "turnkey", "holistic",

    # Superlatives
    "best", "worst", "most", "least", "fastest", "slowest", "easiest",
    "simplest", "hardest", "greatest", "ultimate", "superior", "optimal",

    # Filler phrases
    "in order to", "able to", "helps to", "allows you to", "enables you to",
    "designed to", "used to", "intended to", "meant to", "serves to",
    "aims to", "seeks to", "provides the ability to",

    # Self-referential
    "this field", "this property", "this setting", "this option",
    "this parameter", "this value", "the field", "the property",

    # Vague terms
    "various", "multiple", "several", "many", "some", "certain",
    "appropriate", "relevant", "necessary", "required", "specific",
]

# CRUD verbs to avoid starting descriptions (noun-first rule)
F5XC_BANNED_VERB_STARTS = [
    "Configure", "Manage", "Create", "Delete", "Update", "Get", "Set",
    "Enable", "Disable", "Add", "Remove", "Edit", "Modify", "Define",
    "Specify", "Select", "Use", "Apply", "View", "List", "Show",
    "Enter", "Input", "Provide", "Submit", "Save", "Load", "Read",
    "Write", "Execute", "Run", "Start", "Stop", "Restart",
]

# Synonym replacements for cleaner descriptions
F5XC_SYNONYMS = {
    # Technical synonyms
    "API endpoint": "service interface",
    "REST API": "web service",
    "JSON object": "data structure",
    "HTTP request": "service call",
    "HTTP response": "service response",

    # Marketing to technical
    "seamless integration": "compatible connection",
    "robust solution": "reliable system",
    "powerful feature": "capability",
    "comprehensive suite": "tool set",
    "scalable architecture": "distributed design",

    # Verb to noun transformations
    "Configure": "Configuration for",
    "Manage": "Management of",
    "Enable": "Control to enable",
    "Disable": "Control to disable",
    "Create": "Creation of",
    "Delete": "Deletion of",
    "Update": "Update to",
}


# JSON schema matching Claude Code CLI output
DESCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "short": {"type": "string"},
        "medium": {"type": "string"},
        "long": {"type": "string"},
    },
    "required": ["short", "medium", "long"],
}


def get_f5xc_system_prompt() -> str:
    """
    Get the f5xc-compatible system prompt for description generation.

    Returns:
        System prompt string for vLLM
    """
    banned_list = ", ".join(F5XC_BANNED_TERMS[:20])  # Truncate for brevity

    return f"""You are a technical documentation writer for enterprise software.

STRICT RULES:
1. Write factual, feature-focused content only
2. Start every description with a NOUN, never a verb
3. Use active voice, present tense
4. No marketing language, superlatives, or hyperbole
5. No exclamation marks, emojis, or markdown
6. No vendor names or product branding
7. No self-referential language ("this field", "this setting")

BANNED TERMS (partial list):
{banned_list}...

OUTPUT FORMAT:
Respond ONLY with valid JSON matching this schema:
{json.dumps(DESCRIPTION_SCHEMA, indent=2)}

CHARACTER LIMITS (strict):
- short: 35-60 characters
- medium: 100-150 characters
- long: 350-500 characters

Count characters carefully. Do not exceed limits."""


def build_f5xc_prompt(
    field_name: str,
    field_type: str,
    context: Optional[str] = None,
    existing_description: Optional[str] = None,
    parent_object: Optional[str] = None,
) -> str:
    """
    Build a prompt matching f5xc-api-enriched style.

    Args:
        field_name: Name of the API field (e.g., "load_balancer_config")
        field_type: Type of the field (e.g., "object", "string", "boolean")
        context: Additional context about the field
        existing_description: Any existing description to improve
        parent_object: Parent object name for context

    Returns:
        Formatted prompt string
    """
    prompt_parts = [
        f"Generate descriptions for the API field: {field_name}",
        f"Field type: {field_type}",
    ]

    if parent_object:
        prompt_parts.append(f"Parent object: {parent_object}")

    if context:
        prompt_parts.append(f"Context: {context}")

    if existing_description:
        prompt_parts.append(f"Existing description (improve this): {existing_description}")

    prompt_parts.extend([
        "",
        "REQUIREMENTS:",
        "- SHORT: 35-60 chars, single noun phrase",
        "- MEDIUM: 100-150 chars, 1-2 sentences",
        "- LONG: 350-500 chars, 2-3 paragraphs",
        "",
        "- Start with noun (e.g., 'Configuration for...' not 'Configure...')",
        "- No marketing language or superlatives",
        "- No vendor names (F5, NGINX, etc.)",
        "- Active voice, present tense",
        "",
        "Return ONLY valid JSON with short, medium, long keys.",
    ])

    return "\n".join(prompt_parts)


def apply_synonyms(text: str) -> str:
    """
    Apply synonym replacements to clean up generated text.

    Args:
        text: Raw generated text

    Returns:
        Text with synonyms applied
    """
    result = text
    for original, replacement in F5XC_SYNONYMS.items():
        # Case-insensitive replacement
        import re
        pattern = re.compile(re.escape(original), re.IGNORECASE)
        result = pattern.sub(replacement, result)
    return result


def noun_first_transform(text: str) -> str:
    """
    Transform verb-first descriptions to noun-first.

    Args:
        text: Description that may start with a verb

    Returns:
        Transformed description starting with noun
    """
    for verb in F5XC_BANNED_VERB_STARTS:
        if text.startswith(verb + " "):
            # Apply transformation based on verb
            if verb in F5XC_SYNONYMS:
                return text.replace(verb + " ", F5XC_SYNONYMS[verb] + " ", 1)
            # Generic transformation: "Verb X" -> "X configuration"
            remainder = text[len(verb) + 1:]
            return f"{remainder.capitalize()} configuration"

    return text


class F5XCAdapter:
    """
    Adapter for f5xc-api-enriched workflow compatibility.

    Provides methods matching the original call_claude() interface.
    """

    def __init__(self, generator):
        """
        Initialize adapter with a DescriptionGenerator instance.

        Args:
            generator: DescriptionGenerator instance
        """
        self.generator = generator
        self.system_prompt = get_f5xc_system_prompt()

    def generate(
        self,
        field_name: str,
        field_type: str = "string",
        context: Optional[str] = None,
        existing_description: Optional[str] = None,
        parent_object: Optional[str] = None,
        max_retries: int = 3,
        strict_validation: bool = False,
    ) -> dict[str, str] | None:
        """
        Generate descriptions in f5xc-compatible format.

        Args:
            field_name: API field name
            field_type: Field type
            context: Additional context
            existing_description: Existing description to improve
            parent_object: Parent object name
            max_retries: Number of retry attempts
            strict_validation: If True, require all tiers within limits

        Returns:
            Dict with short/medium/long keys, or None on failure
        """
        prompt = build_f5xc_prompt(
            field_name=field_name,
            field_type=field_type,
            context=context,
            existing_description=existing_description,
            parent_object=parent_object,
        )

        best_result = None
        best_valid_count = 0

        for attempt in range(max_retries):
            result = self.generator.generate_raw(
                prompt=prompt,
                schema=DESCRIPTION_SCHEMA,
                system_prompt=self.system_prompt,
                max_tokens=500,
            )

            if result:
                # Apply post-processing
                result = self._post_process(result)
                valid_count = self._count_valid(result)

                # Track best result
                if valid_count > best_valid_count:
                    best_result = result
                    best_valid_count = valid_count

                # Return immediately if all valid or strict mode satisfied
                if valid_count == 3:
                    return result
                if strict_validation and self._validate_lengths(result):
                    return result

        # Return best result found (even if not all tiers valid)
        return best_result

    def _post_process(self, result: dict[str, str]) -> dict[str, str]:
        """Apply synonym replacements and noun-first transforms."""
        processed = {}
        for key, value in result.items():
            if isinstance(value, str):
                value = apply_synonyms(value)
                value = noun_first_transform(value)
                processed[key] = value.strip()
            else:
                processed[key] = value
        return processed

    def _count_valid(self, result: dict[str, str]) -> int:
        """Count how many tiers are within character limits."""
        limits = {
            'short': (35, 60),
            'medium': (100, 150),
            'long': (350, 500),
        }
        count = 0
        for key, (min_len, max_len) in limits.items():
            if key in result:
                length = len(result[key])
                if min_len <= length <= max_len:
                    count += 1
        return count

    def _validate_lengths(self, result: dict[str, str]) -> bool:
        """Check if all descriptions meet character limits."""
        limits = {
            'short': (35, 60),
            'medium': (100, 150),
            'long': (350, 500),
        }

        for key, (min_len, max_len) in limits.items():
            if key in result:
                length = len(result[key])
                if length < min_len or length > max_len:
                    return False

        return True
