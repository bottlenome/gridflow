"""Paper / data export adapters (AS-5: publication productivity)."""

from gridflow.adapter.export.loaders import (
    comparison_table_from_benchmark_report,
    load_comparison_table_json,
)
from gridflow.adapter.export.paper import (
    CaptionRenderer,
    CsvDataRenderer,
    LatexTableRenderer,
    MatplotlibScriptRenderer,
    PaperArtifactRenderer,
    PaperExporter,
)

__all__ = [
    "CaptionRenderer",
    "CsvDataRenderer",
    "LatexTableRenderer",
    "MatplotlibScriptRenderer",
    "PaperArtifactRenderer",
    "PaperExporter",
    "comparison_table_from_benchmark_report",
    "load_comparison_table_json",
]
