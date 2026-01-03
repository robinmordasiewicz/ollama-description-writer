#!/usr/bin/env python3
"""
Description Generator using vLLM with Qwen2.5-7B-Instruct
Generates short/medium/long product descriptions with style constraints.

Usage:
    python description_generator.py

Requirements:
    - vLLM server running: vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000
    - pip install openai
"""

from openai import OpenAI
from typing import Literal

# vLLM OpenAI-compatible client
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="EMPTY"
)

MODEL = "Qwen/Qwen2.5-7B-Instruct"

# Description tier configurations
TIER_CONFIG = {
    "short": {
        "max_tokens": 50,
        "char_target": "50-100",
        "prompt_template": (
            "Write a concise product description in exactly ONE sentence, "
            "under 100 characters.\n"
            "Product: {product_name}\n"
            "Features: {features}\n"
            "Output format: Single sentence, no markdown, no quotes."
        )
    },
    "medium": {
        "max_tokens": 150,
        "char_target": "150-300",
        "prompt_template": (
            "Write a product description in 2-3 sentences (150-300 characters total).\n"
            "Product: {product_name}\n"
            "Features: {features}\n"
            "Style: Professional, feature-focused, no marketing fluff.\n"
            "Output format: Plain text, no markdown."
        )
    },
    "long": {
        "max_tokens": 400,
        "char_target": "500-1000",
        "prompt_template": (
            "Write a comprehensive product description in 3-5 paragraphs "
            "(500-1000 characters total).\n"
            "Product: {product_name}\n"
            "Features: {features}\n"
            "Include: Key features, benefits, use cases.\n"
            "Style: Technical documentation, clear structure.\n"
            "Output format: Plain text with clear paragraph breaks."
        )
    }
}

SYSTEM_PROMPT = (
    "You are a technical documentation writer. "
    "Follow length constraints exactly. "
    "Write clear, professional prose without marketing language. "
    "Never use emojis, exclamation marks, or superlatives."
)


def generate_description(
    product_name: str,
    features: str,
    tier: Literal["short", "medium", "long"] = "medium",
    temperature: float = 0.3
) -> dict:
    """
    Generate a product description using the vLLM server.

    Args:
        product_name: Name of the product
        features: Comma-separated list of features
        tier: Description length tier (short/medium/long)
        temperature: Generation temperature (lower = more deterministic)

    Returns:
        dict with 'content', 'char_count', 'tier', 'tokens_used'
    """
    config = TIER_CONFIG[tier]
    prompt = config["prompt_template"].format(
        product_name=product_name,
        features=features
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=config["max_tokens"],
        top_p=0.9
    )

    content = response.choices[0].message.content.strip()

    return {
        "content": content,
        "char_count": len(content),
        "tier": tier,
        "target_chars": config["char_target"],
        "tokens_used": response.usage.total_tokens
    }


def generate_all_tiers(product_name: str, features: str) -> dict:
    """Generate descriptions for all tiers."""
    results = {}
    for tier in ["short", "medium", "long"]:
        results[tier] = generate_description(product_name, features, tier)
    return results


def main():
    """Demo: Generate descriptions for a sample product."""
    product = "ErgoMax Pro Wireless Mouse"
    features = "Bluetooth 5.0, ergonomic design, 4000 DPI sensor, silent clicks, USB-C charging"

    print("=" * 60)
    print("vLLM Description Generator Demo")
    print(f"Model: {MODEL}")
    print("=" * 60)
    print(f"\nProduct: {product}")
    print(f"Features: {features}")
    print("-" * 60)

    results = generate_all_tiers(product, features)

    for tier, data in results.items():
        print(f"\n[{tier.upper()}] ({data['char_count']} chars, target: {data['target_chars']})")
        print("-" * 40)
        print(data["content"])
        print(f"Tokens used: {data['tokens_used']}")

    print("\n" + "=" * 60)
    print("Server running at: http://localhost:8000")
    print("Stop with: Ctrl+C on the vLLM server terminal")


if __name__ == "__main__":
    main()
