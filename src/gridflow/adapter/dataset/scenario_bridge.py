"""Bridge from a :class:`DatasetTimeSeries` to a gridflow scenario pack.

Spec: ``docs/dataset_contribution.md`` (integration with existing
ScenarioPack flow).

The bridge does not modify the existing ScenarioPack types; it provides
helper functions that:
  * encode a DatasetSpec / DatasetTimeSeries reference into pack
    ``parameters`` (so an experiment can be replayed deterministically)
  * extract the ``DatasetTimeSeries`` channels into the data formats
    expected by an experiment (e.g. per-step active fraction)

Usage in try11 / future experiments:

  from gridflow.adapter.dataset import SyntheticLoader
  from gridflow.adapter.dataset.scenario_bridge import (
      pack_parameters_with_dataset, dataset_to_active_fraction,
  )

  spec = DatasetSpec(dataset_id="...", params=as_params({"seed": 0}))
  ts = SyntheticLoader().load(spec)
  active_fraction = dataset_to_active_fraction(ts, pool_size=200)
  params = pack_parameters_with_dataset(spec, ts.metadata, base_params={...})
"""

from __future__ import annotations

from gridflow.domain.dataset import DatasetMetadata, DatasetSpec, DatasetTimeSeries
from gridflow.domain.util.params import Params, as_params


def pack_parameters_with_dataset(
    spec: DatasetSpec,
    metadata: DatasetMetadata,
    base_params: Params | dict[str, object] | None = None,
) -> Params:
    """Encode dataset reference into the canonical pack parameters tuple.

    The output is suitable as ``PackMetadata.parameters`` and embeds:
      * dataset_id / dataset_sha256 / dataset_doi / dataset_license
        (= reproducibility provenance)
      * any ``base_params`` the caller wants to keep alongside

    Hashable / immutable per CLAUDE.md §0.1.
    """
    base = dict(as_params(base_params or {}))
    base.update(
        {
            "dataset_id": spec.dataset_id,
            "dataset_sha256": metadata.sha256,
            "dataset_doi": metadata.doi,
            "dataset_license": metadata.license.value,
            "dataset_resolution_seconds": metadata.time_resolution_seconds,
        }
    )
    if spec.time_range:
        base["dataset_time_range"] = f"{spec.time_range[0]}/{spec.time_range[1]}"
    return as_params(base)


def dataset_to_active_fraction(
    ts: DatasetTimeSeries,
    *,
    pool_size: int,
    count_channel: str = "aggregate_active_count",
) -> tuple[float, ...]:
    """Convert a DatasetTimeSeries to per-step active fraction.

    For VPP-availability traces, this is the natural way to feed real
    data into the existing ``trace_synthesizer.ChurnTrace`` shape.

    Args:
        ts: A loaded time series.
        pool_size: Total DER count (denominator).
        count_channel: Name of the channel containing per-step active count.

    Returns:
        Tuple of floats in [0, 1].
    """
    counts = ts.channel(count_channel)
    return tuple(min(1.0, max(0.0, c / pool_size)) for c in counts)


def dataset_to_active_count(
    ts: DatasetTimeSeries,
    count_channel: str = "aggregate_active_count",
) -> tuple[int, ...]:
    """Extract integer per-step active counts."""
    return tuple(round(v) for v in ts.channel(count_channel))
