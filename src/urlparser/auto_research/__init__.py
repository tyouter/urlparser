"""
urlparser Auto Research Framework

Inspired by Andrej Karpathy's auto research methodology:
automated, iterative, data-driven validation with clear acceptance criteria.

Architecture:
    1. DatasetBuilder: builds 500+ URL dataset from cubox exports + curated supplements
    2. AcceptanceCriteria: validates structural/content completeness per-platform
    3. EfficiencyBenchmark: measures parse throughput and latency
    4. ResearchRunner: orchestrates iterative research cycles with report generation

Acceptance Criteria (Strategy):
    - URL parse success rate > 99% across all platforms
    - Structural completeness: title + content + platform detected
    - Content completeness: min content length thresholds per platform
    - Platform coverage: ALL supported platforms must be tested
    - Test URL count: >= 500 unique URLs

Efficiency Criteria (Strategy):
    - Non-video URLs: >= 10 parses/minute
    - Video URLs: parse time <= video_duration / 10

Usage:
    python -m urlparser.auto_research run              # Full research cycle
    python -m urlparser.auto_research run --quick       # Quick cycle (50 URLs)
    python -m urlparser.auto_research dataset           # Build dataset only
    python -m urlparser.auto_research validate          # Validate dataset
    python -m urlparser.auto_research benchmark         # Efficiency benchmark only
"""

from .dataset import DatasetBuilder
from .acceptance import AcceptanceChecker
from .benchmark import EfficiencyBenchmark
from .runner import ResearchRunner

__all__ = [
    'DatasetBuilder',
    'AcceptanceChecker',
    'EfficiencyBenchmark',
    'ResearchRunner',
]
