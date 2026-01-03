"""
Command-line interface for the description generator.
"""
import argparse
import json
import sys
import logging
from pathlib import Path
from typing import Optional

from .models import ProductInput, DescriptionTier, BatchInput
from .generator import DescriptionGenerator
from .config import DEFAULT_MODEL, DEFAULT_BASE_URL, DEFAULT_TEMPERATURE
from .tracking import ResultTracker


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )


def parse_tiers(tier_strings: Optional[list[str]]) -> list[DescriptionTier]:
    """Parse tier strings to enum values."""
    if not tier_strings:
        return list(DescriptionTier)
    return [DescriptionTier(t.lower()) for t in tier_strings]


def load_config(config_path: str) -> BatchInput:
    """Load batch configuration from JSON file."""
    with open(config_path) as f:
        data = json.load(f)
    return BatchInput.model_validate(data)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="description_generator",
        description="Generate product descriptions using vLLM with length-constrained prompts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single product, all tiers
  python -m description_generator --name "Wireless Mouse" --features "Bluetooth" "Ergonomic"

  # Specific tiers only
  python -m description_generator --name "Mouse" --features "Wireless" --tiers short medium

  # Batch from config file
  python -m description_generator --config products.json --output results.json

  # With experiment tracking
  python -m description_generator --config products.json --track --prompt-version v2
        """
    )

    # Input options (mutually exclusive: direct input vs config file)
    input_group = parser.add_argument_group("Input Options")
    input_group.add_argument(
        "--name", "-n",
        help="Product name (for single product mode)"
    )
    input_group.add_argument(
        "--features", "-f",
        nargs="+",
        help="Product features (for single product mode)"
    )
    input_group.add_argument(
        "--category", "-c",
        help="Product category (optional)"
    )
    input_group.add_argument(
        "--config",
        help="Path to JSON config file for batch processing"
    )

    # Generation options
    gen_group = parser.add_argument_group("Generation Options")
    gen_group.add_argument(
        "--tiers", "-t",
        nargs="+",
        choices=["short", "medium", "long"],
        help="Tiers to generate (default: all)"
    )
    gen_group.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        help=f"Model identifier (default: {DEFAULT_MODEL})"
    )
    gen_group.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"vLLM server URL (default: {DEFAULT_BASE_URL})"
    )
    gen_group.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help=f"Generation temperature (default: {DEFAULT_TEMPERATURE})"
    )

    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    output_group.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: True)"
    )
    output_group.add_argument(
        "--compact",
        action="store_true",
        help="Compact JSON output (overrides --pretty)"
    )

    # Tracking options
    track_group = parser.add_argument_group("Experiment Tracking")
    track_group.add_argument(
        "--track",
        action="store_true",
        help="Enable experiment tracking"
    )
    track_group.add_argument(
        "--prompt-version",
        default="v1",
        help="Prompt version identifier for tracking"
    )
    track_group.add_argument(
        "--track-file",
        default="results/experiment_matrix.json",
        help="Experiment tracking file path"
    )
    track_group.add_argument(
        "--show-matrix",
        action="store_true",
        help="Show experiment comparison matrix and exit"
    )

    # Other options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test vLLM server connection and exit"
    )

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Handle show-matrix command
    if args.show_matrix:
        tracker = ResultTracker(args.track_file)
        tracker.print_comparison()
        return 0

    # Create generator
    generator = DescriptionGenerator(
        base_url=args.base_url,
        model=args.model,
        temperature=args.temperature,
    )

    # Handle test-connection
    if args.test_connection:
        if generator.test_connection():
            print("Connection successful!")
            return 0
        else:
            print("Connection failed!", file=sys.stderr)
            return 1

    # Determine input mode
    if args.config:
        # Batch mode from config file
        logger.info(f"Loading config from: {args.config}")
        batch_input = load_config(args.config)
        products = batch_input.products
        tiers = batch_input.tiers
    elif args.name and args.features:
        # Single product mode
        products = [ProductInput(
            name=args.name,
            features=args.features,
            category=args.category
        )]
        tiers = parse_tiers(args.tiers)
    else:
        parser.error("Either --config or (--name and --features) is required")
        return 1

    # Generate descriptions
    logger.info(f"Generating descriptions for {len(products)} product(s)")
    results = []
    for product in products:
        logger.info(f"Processing: {product.name}")
        result = generator.generate(product, tiers)
        results.append(result)

        # Log validation status
        for tier_name, desc in result.descriptions.items():
            status = "OK" if desc.within_limits else "OVER"
            logger.info(
                f"  {tier_name}: {desc.char_count} chars "
                f"(target: {desc.target_range}) [{status}]"
            )

    # Handle experiment tracking
    if args.track:
        tracker = ResultTracker(args.track_file)
        run_id = tracker.start_run(
            args.prompt_version,
            args.model,
            args.temperature
        )
        run = tracker.finish_run(
            run_id=run_id,
            prompt_version=args.prompt_version,
            model=args.model,
            temperature=args.temperature,
            results=results
        )
        tracker.save()
        logger.info(f"Tracked experiment run: {run_id} (validity: {run.validity_rate:.1%})")

    # Prepare output
    if len(results) == 1:
        output_data = results[0].model_dump()
    else:
        output_data = {
            "results": [r.model_dump() for r in results],
            "total_products": len(results),
            "all_valid": all(r.all_valid for r in results),
        }

    # Format output
    indent = None if args.compact else 2
    output_json = json.dumps(output_data, indent=indent, ensure_ascii=False)

    # Write output
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output_json)
        logger.info(f"Output written to: {args.output}")
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
