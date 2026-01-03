"""
Result tracking for iterative prompt engineering.

Tracks generation results in a matrix format to support multi-phase
prompt optimization with TODO lists and experiment tracking.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from .models import GenerationOutput, DescriptionTier


class ExperimentRun(BaseModel):
    """Single experiment run with prompt configuration and results."""
    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    prompt_version: str = Field(default="v1")
    model: str
    temperature: float
    results: list[GenerationOutput]

    # Aggregate metrics
    total_generations: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    validity_rate: float = 0.0

    # Per-tier metrics
    tier_metrics: dict[str, dict] = Field(default_factory=dict)

    def model_post_init(self, __context) -> None:
        """Calculate metrics after initialization."""
        self._calculate_metrics()

    def _calculate_metrics(self) -> None:
        """Calculate aggregate and per-tier metrics."""
        tier_stats = {tier.value: {"valid": 0, "invalid": 0, "char_counts": []}
                      for tier in DescriptionTier}

        for result in self.results:
            for tier_name, desc in result.descriptions.items():
                if desc.within_limits:
                    tier_stats[tier_name]["valid"] += 1
                    self.valid_count += 1
                else:
                    tier_stats[tier_name]["invalid"] += 1
                    self.invalid_count += 1
                tier_stats[tier_name]["char_counts"].append(desc.char_count)
                self.total_generations += 1

        if self.total_generations > 0:
            self.validity_rate = self.valid_count / self.total_generations

        # Calculate per-tier metrics
        for tier_name, stats in tier_stats.items():
            total = stats["valid"] + stats["invalid"]
            if total > 0:
                chars = stats["char_counts"]
                self.tier_metrics[tier_name] = {
                    "valid": stats["valid"],
                    "invalid": stats["invalid"],
                    "validity_rate": stats["valid"] / total,
                    "avg_chars": sum(chars) / len(chars) if chars else 0,
                    "min_chars": min(chars) if chars else 0,
                    "max_chars": max(chars) if chars else 0,
                }


class ExperimentMatrix(BaseModel):
    """
    Matrix tracking multiple experiment runs for prompt optimization.

    Supports:
    - Tracking multiple prompt versions
    - Comparing results across iterations
    - Identifying best-performing configurations
    """
    project_name: str = "description_generator"
    runs: list[ExperimentRun] = Field(default_factory=list)
    best_run_id: Optional[str] = None
    best_validity_rate: float = 0.0

    def add_run(self, run: ExperimentRun) -> None:
        """Add an experiment run and update best metrics."""
        self.runs.append(run)
        if run.validity_rate > self.best_validity_rate:
            self.best_validity_rate = run.validity_rate
            self.best_run_id = run.run_id

    def get_run(self, run_id: str) -> Optional[ExperimentRun]:
        """Get a specific run by ID."""
        for run in self.runs:
            if run.run_id == run_id:
                return run
        return None

    def get_comparison_table(self) -> list[dict]:
        """
        Generate a comparison table of all runs.

        Returns:
            List of dicts with run metrics for tabular display
        """
        table = []
        for run in self.runs:
            row = {
                "run_id": run.run_id,
                "prompt_version": run.prompt_version,
                "model": run.model,
                "temperature": run.temperature,
                "total": run.total_generations,
                "valid": run.valid_count,
                "invalid": run.invalid_count,
                "validity_rate": f"{run.validity_rate:.1%}",
                "timestamp": run.timestamp[:19],
            }
            # Add per-tier validity rates
            for tier in DescriptionTier:
                if tier.value in run.tier_metrics:
                    rate = run.tier_metrics[tier.value]["validity_rate"]
                    row[f"{tier.value}_rate"] = f"{rate:.1%}"
            table.append(row)
        return table

    def save(self, path: Path) -> None:
        """Save matrix to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: Path) -> "ExperimentMatrix":
        """Load matrix from JSON file."""
        if not path.exists():
            return cls()
        with open(path) as f:
            data = json.load(f)
        return cls.model_validate(data)


class ResultTracker:
    """
    High-level interface for tracking experiment results.

    Usage:
        tracker = ResultTracker("results/experiments.json")
        run = tracker.start_run("v2", model="Qwen/Qwen2.5-7B-Instruct", temperature=0.3)
        # ... run experiments and add results ...
        tracker.finish_run(run, results)
        tracker.save()
    """

    def __init__(self, path: str = "results/experiment_matrix.json"):
        self.path = Path(path)
        self.matrix = ExperimentMatrix.load(self.path)

    def start_run(
        self,
        prompt_version: str,
        model: str,
        temperature: float,
    ) -> str:
        """
        Start a new experiment run.

        Returns:
            Run ID for the new experiment
        """
        run_id = f"run_{len(self.matrix.runs) + 1:03d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return run_id

    def finish_run(
        self,
        run_id: str,
        prompt_version: str,
        model: str,
        temperature: float,
        results: list[GenerationOutput],
    ) -> ExperimentRun:
        """
        Finish an experiment run with results.

        Args:
            run_id: ID from start_run
            prompt_version: Version identifier for the prompt
            model: Model used
            temperature: Temperature setting
            results: Generation results

        Returns:
            Completed ExperimentRun
        """
        run = ExperimentRun(
            run_id=run_id,
            prompt_version=prompt_version,
            model=model,
            temperature=temperature,
            results=results,
        )
        self.matrix.add_run(run)
        return run

    def save(self) -> None:
        """Save the experiment matrix to disk."""
        self.matrix.save(self.path)

    def print_comparison(self) -> None:
        """Print comparison table of all runs."""
        table = self.matrix.get_comparison_table()
        if not table:
            print("No experiment runs recorded yet.")
            return

        # Print header
        headers = list(table[0].keys())
        print("\n" + "=" * 100)
        print("EXPERIMENT MATRIX")
        print("=" * 100)
        print(" | ".join(f"{h:>12}" for h in headers))
        print("-" * 100)

        # Print rows
        for row in table:
            print(" | ".join(f"{str(v):>12}" for v in row.values()))

        print("=" * 100)
        print(f"Best run: {self.matrix.best_run_id} ({self.matrix.best_validity_rate:.1%} validity)")
