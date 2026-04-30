# Phase 2 v0.4 MVP 検証 — try8

**目的**: Phase 2 v0.3 で実装した 4 機能が研究ワークフローで end-to-end 動作することを実証する。

| 機能 | §spec | この try で検証する経路 |
|---|---|---|
| §5.1.1 Option A | 03b §3.6a.3 (`ParamAxis.target`) | `gridflow sweep` で metric-target axis を使う |
| §5.1.1 Option B | 03c §3.7.8 (`gridflow evaluate`) | YAML 形 + inline DSL 形の両方 |
| §5.1.2 column per-experiment metrics | 03b §3.6a.4 | SweepResult JSON を pandas で 1 行で読む |
| §5.1.3 CDL canonical input | 03b §3.5.4a | 同じ CDL YAML で OpenDSS と pandapower を駆動 |
| M5 SensitivityAnalyzer | 03b §3.7 | `gridflow evaluate --parameter-sweep` 経由 |

**シナリオ**: 4 バス放射状フィーダーで PV 注入を sweep し、metric 閾値を変えて感度分析。
OpenDSS は CI extra 必要なため optional。pandapower はあれば使う、なければ skip。
