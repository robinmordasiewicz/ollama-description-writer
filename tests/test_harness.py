#!/usr/bin/env python3
"""
Comprehensive Test Harness for Description Generator

Test Matrix Coverage:
1. Tier-based generation (short/medium/long)
2. generate_raw() with JSON schema
3. F5XCAdapter compatibility
4. 5-layer validation system
5. MCP tool calling
6. Character limit compliance
7. Banned terms detection
8. Edge cases and error handling
"""
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from description_generator import (
    DescriptionGenerator,
    ProductInput,
    DescriptionTier,
    F5XCAdapter,
    DescriptionValidator,
    validate_description,
    validate_descriptions,
    TIER_CONFIGS,
    get_tier_config,
)


@dataclass
class TestResult:
    """Result of a single test case."""
    test_name: str
    category: str
    passed: bool
    duration_ms: float
    details: str = ""
    error: Optional[str] = None


@dataclass
class TestMatrix:
    """Aggregated test results matrix."""
    results: list[TestResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def add(self, result: TestResult):
        self.results.append(result)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0

    def by_category(self) -> dict[str, list[TestResult]]:
        categories = {}
        for r in self.results:
            if r.category not in categories:
                categories[r.category] = []
            categories[r.category].append(r)
        return categories

    def print_report(self):
        """Print formatted test report."""
        print("\n" + "=" * 70)
        print("TEST HARNESS REPORT")
        print("=" * 70)
        print(f"Start: {self.start_time}")
        print(f"End: {self.end_time}")
        print(f"Duration: {(self.end_time - self.start_time).total_seconds():.2f}s")
        print("-" * 70)
        print(f"Total: {self.total} | Passed: {self.passed} | Failed: {self.failed} | Rate: {self.pass_rate:.1%}")
        print("=" * 70)

        for category, results in self.by_category().items():
            cat_passed = sum(1 for r in results if r.passed)
            cat_total = len(results)
            print(f"\n## {category} ({cat_passed}/{cat_total})")
            print("-" * 50)

            for r in results:
                status = "✅" if r.passed else "❌"
                print(f"  {status} {r.test_name} ({r.duration_ms:.0f}ms)")
                if r.details:
                    print(f"     {r.details}")
                if r.error:
                    print(f"     ERROR: {r.error}")

        print("\n" + "=" * 70)
        print("CATEGORY SUMMARY")
        print("=" * 70)
        for category, results in self.by_category().items():
            cat_passed = sum(1 for r in results if r.passed)
            cat_total = len(results)
            rate = cat_passed / cat_total if cat_total > 0 else 0
            bar = "█" * int(rate * 20) + "░" * (20 - int(rate * 20))
            print(f"{category:30} [{bar}] {rate:.0%} ({cat_passed}/{cat_total})")

    def to_json(self) -> str:
        """Export results as JSON."""
        return json.dumps({
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "results": [
                {
                    "test_name": r.test_name,
                    "category": r.category,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                    "details": r.details,
                    "error": r.error,
                }
                for r in self.results
            ],
        }, indent=2)


class TestHarness:
    """Test harness for description generator."""

    def __init__(self, base_url: str = "http://localhost:8000/v1"):
        self.base_url = base_url
        self.matrix = TestMatrix()
        self.generator: Optional[DescriptionGenerator] = None
        self.validator = DescriptionValidator()

    def run_test(self, name: str, category: str, test_fn) -> TestResult:
        """Run a single test and capture result."""
        start = time.time()
        try:
            passed, details = test_fn()
            duration = (time.time() - start) * 1000
            return TestResult(
                test_name=name,
                category=category,
                passed=passed,
                duration_ms=duration,
                details=details,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return TestResult(
                test_name=name,
                category=category,
                passed=False,
                duration_ms=duration,
                error=str(e),
            )

    def run_all(self) -> TestMatrix:
        """Run all tests and return matrix."""
        self.matrix = TestMatrix()
        self.matrix.start_time = datetime.now()

        # Initialize generator
        print("Initializing generator...")
        self.generator = DescriptionGenerator(base_url=self.base_url)

        # Run test categories
        self._test_connection()
        self._test_tier_generation()
        self._test_generate_raw()
        self._test_f5xc_adapter()
        self._test_validation_layer()
        self._test_character_limits()
        self._test_banned_terms()
        self._test_edge_cases()

        self.matrix.end_time = datetime.now()
        return self.matrix

    def _test_connection(self):
        """Test 1: Connection tests."""
        print("\n[1/8] Testing connection...")

        def test_server_reachable():
            result = self.generator.test_connection()
            return result, "Server responded"

        self.matrix.add(self.run_test(
            "vLLM server connection",
            "Connection",
            test_server_reachable
        ))

    def _test_tier_generation(self):
        """Test 2: Tier-based generation."""
        print("\n[2/8] Testing tier generation...")

        products = [
            ProductInput(
                name="Load Balancer",
                features=["HTTP routing", "Health checks", "SSL termination"],
                category="Networking"
            ),
            ProductInput(
                name="API Gateway",
                features=["Rate limiting", "Authentication", "Request transformation"],
                category="Security"
            ),
        ]

        for product in products:
            for tier in DescriptionTier:
                def test_tier(p=product, t=tier):
                    result = self.generator.generate_single(p, t)
                    config = get_tier_config(t)
                    valid = config.min_chars <= result.char_count <= config.max_chars
                    return valid, f"{result.char_count} chars (target: {config.min_chars}-{config.max_chars})"

                self.matrix.add(self.run_test(
                    f"{product.name} - {tier.value}",
                    "Tier Generation",
                    test_tier
                ))

    def _test_generate_raw(self):
        """Test 3: generate_raw() with JSON schema."""
        print("\n[3/8] Testing generate_raw()...")

        schema = {
            "type": "object",
            "properties": {
                "short": {"type": "string"},
                "medium": {"type": "string"},
                "long": {"type": "string"},
            },
            "required": ["short", "medium", "long"],
        }

        prompts = [
            ("Simple field", "Generate descriptions for 'timeout_seconds' field. SHORT: 35-60 chars, MEDIUM: 100-150 chars, LONG: 350-500 chars."),
            ("Complex field", "Generate descriptions for 'load_balancer_algorithm' - determines traffic distribution. SHORT: 35-60 chars, MEDIUM: 100-150 chars, LONG: 350-500 chars."),
        ]

        for name, prompt in prompts:
            def test_raw(p=prompt):
                result = self.generator.generate_raw(
                    prompt=p,
                    schema=schema,
                    max_tokens=500,
                )
                if result is None:
                    return False, "Returned None"
                has_keys = all(k in result for k in ["short", "medium", "long"])
                return has_keys, f"Keys: {list(result.keys()) if result else 'None'}"

            self.matrix.add(self.run_test(
                f"generate_raw: {name}",
                "Raw Generation",
                test_raw
            ))

    def _test_f5xc_adapter(self):
        """Test 4: F5XCAdapter compatibility."""
        print("\n[4/8] Testing F5XCAdapter...")

        adapter = F5XCAdapter(self.generator)

        test_fields = [
            {
                "field_name": "virtual_host_config",
                "field_type": "object",
                "context": "Virtual host routing configuration",
            },
            {
                "field_name": "health_check_interval",
                "field_type": "integer",
                "context": "Seconds between health probes",
            },
            {
                "field_name": "ssl_certificate_ref",
                "field_type": "string",
                "context": "Reference to SSL certificate object",
            },
        ]

        for field in test_fields:
            def test_adapter(f=field):
                result = adapter.generate(
                    field_name=f["field_name"],
                    field_type=f["field_type"],
                    context=f["context"],
                    max_retries=2,
                )
                if result is None:
                    return False, "Generation failed"

                # Check all tiers present
                has_all = all(k in result for k in ["short", "medium", "long"])
                if not has_all:
                    return False, f"Missing keys: {set(['short','medium','long']) - set(result.keys())}"

                # Validate lengths - pass if at least 1 tier is valid
                validation = validate_descriptions(result)
                passed = validation.valid_count >= 1
                details = f"Valid: {validation.valid_count}/3"
                if validation.valid_count < 3:
                    lengths = {k: len(v) for k, v in result.items()}
                    details += f" | Lengths: {lengths}"
                return passed, details

            self.matrix.add(self.run_test(
                f"F5XC: {field['field_name']}",
                "F5XC Adapter",
                test_adapter
            ))

    def _test_validation_layer(self):
        """Test 5: 5-layer validation system."""
        print("\n[5/8] Testing validation layers...")

        # Layer 1: Banned terms
        banned_tests = [
            ("Contains F5", "F5 load balancer configuration", DescriptionTier.SHORT, False),
            ("Contains API", "REST API endpoint settings", DescriptionTier.SHORT, False),
            ("Contains marketing", "World-class enterprise solution", DescriptionTier.SHORT, False),
            ("Clean content", "Network routing configuration for traffic distribution", DescriptionTier.SHORT, True),
        ]

        for name, content, tier, should_pass in banned_tests:
            def test_banned(c=content, t=tier, exp=should_pass):
                result = validate_description(c, t)
                # Check if banned term errors exist
                has_banned_error = any("Banned" in e for e in result.errors)
                passed = (not has_banned_error) == exp
                return passed, f"Errors: {result.errors}" if result.errors else "No errors"

            self.matrix.add(self.run_test(
                f"Banned: {name}",
                "Validation Layer",
                test_banned
            ))

        # Layer 3: Character limits
        limit_tests = [
            ("Short too short", "Hi", DescriptionTier.SHORT, False),
            ("Short valid", "Network load balancing configuration settings", DescriptionTier.SHORT, True),
            ("Short too long", "This is a very long description that definitely exceeds the maximum character limit for short tier", DescriptionTier.SHORT, False),
            ("Medium valid", "Load balancer configuration for distributing network traffic. Supports multiple algorithms and health checking.", DescriptionTier.MEDIUM, True),
        ]

        for name, content, tier, should_pass in limit_tests:
            def test_limits(c=content, t=tier, exp=should_pass):
                result = validate_description(c, t)
                limit_error = any("Too" in e for e in result.errors)
                passed = (not limit_error) == exp
                return passed, f"{len(c)} chars, errors: {result.errors}"

            self.matrix.add(self.run_test(
                f"Limits: {name}",
                "Validation Layer",
                test_limits
            ))

    def _test_character_limits(self):
        """Test 6: Character limit compliance in generation."""
        print("\n[6/8] Testing character limit compliance...")

        product = ProductInput(
            name="Service Mesh",
            features=["Traffic management", "Observability", "Security policies"],
        )

        # Generate multiple times and check compliance rate
        for tier in DescriptionTier:
            config = get_tier_config(tier)

            def test_compliance(t=tier, cfg=config):
                results = []
                for _ in range(3):  # Generate 3 times
                    result = self.generator.generate_single(product, t)
                    in_range = cfg.min_chars <= result.char_count <= cfg.max_chars
                    results.append((result.char_count, in_range))

                pass_count = sum(1 for _, passed in results if passed)
                details = ", ".join(f"{chars}{'✓' if ok else '✗'}" for chars, ok in results)
                return pass_count >= 2, f"[{details}] ({pass_count}/3 valid)"

            self.matrix.add(self.run_test(
                f"Compliance: {tier.value} ({config.min_chars}-{config.max_chars})",
                "Character Limits",
                test_compliance
            ))

    def _test_banned_terms(self):
        """Test 7: Banned terms detection in generated content."""
        print("\n[7/8] Testing banned terms detection...")

        # Generate and check for banned terms
        product = ProductInput(
            name="Cloud Gateway",
            features=["Edge routing", "CDN integration", "DDoS protection"],
        )

        from description_generator.f5xc_compat import F5XC_BANNED_TERMS

        for tier in DescriptionTier:
            def test_no_banned(t=tier):
                result = self.generator.generate_single(product, t)
                content_lower = result.content.lower()

                found_banned = []
                for term in F5XC_BANNED_TERMS[:20]:  # Check first 20 terms
                    if term.lower() in content_lower:
                        found_banned.append(term)

                passed = len(found_banned) == 0
                details = f"Found: {found_banned}" if found_banned else "No banned terms"
                return passed, details

            self.matrix.add(self.run_test(
                f"No banned terms: {tier.value}",
                "Banned Terms",
                test_no_banned
            ))

    def _test_edge_cases(self):
        """Test 8: Edge cases and error handling."""
        print("\n[8/8] Testing edge cases...")

        # Empty features - should raise validation error
        def test_empty_features():
            try:
                product = ProductInput(name="Test Product", features=[])
                return False, "Should have raised validation error"
            except Exception as e:
                return "validation error" in str(e).lower(), "Correctly rejected empty features"

        self.matrix.add(self.run_test(
            "Empty features validation",
            "Edge Cases",
            test_empty_features
        ))

        # Very long product name
        def test_long_name():
            long_name = "Super Advanced Enterprise-Grade Multi-Cloud Hybrid Infrastructure Management Platform"
            product = ProductInput(name=long_name, features=["Feature 1"])
            result = self.generator.generate_single(product, DescriptionTier.SHORT)
            return result.content is not None, f"{len(result.content)} chars"

        self.matrix.add(self.run_test(
            "Very long product name",
            "Edge Cases",
            test_long_name
        ))

        # Special characters in features
        def test_special_chars():
            product = ProductInput(
                name="Test API",
                features=["HTTP/2 support", "JSON & XML", "OAuth 2.0"],
            )
            result = self.generator.generate_single(product, DescriptionTier.MEDIUM)
            return result.content is not None, f"{len(result.content)} chars"

        self.matrix.add(self.run_test(
            "Special characters in features",
            "Edge Cases",
            test_special_chars
        ))

        # Unicode content
        def test_unicode():
            product = ProductInput(
                name="Ünïcödé Prödüct",
                features=["Süpport für Ümläuts", "日本語サポート"],
            )
            result = self.generator.generate_single(product, DescriptionTier.SHORT)
            return result.content is not None, f"{len(result.content)} chars"

        self.matrix.add(self.run_test(
            "Unicode in input",
            "Edge Cases",
            test_unicode
        ))


def main():
    """Run test harness and generate report."""
    print("=" * 70)
    print("DESCRIPTION GENERATOR TEST HARNESS")
    print("=" * 70)
    print(f"Started: {datetime.now()}")
    print()

    harness = TestHarness()
    matrix = harness.run_all()

    # Print report
    matrix.print_report()

    # Save JSON report
    report_path = Path(__file__).parent.parent / "results" / "test_matrix.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(matrix.to_json())
    print(f"\nJSON report saved to: {report_path}")

    # Return exit code based on results
    return 0 if matrix.pass_rate >= 0.8 else 1


if __name__ == "__main__":
    sys.exit(main())
