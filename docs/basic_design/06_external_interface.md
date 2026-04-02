# 第6章 外部インターフェース設計

本章では、gridflow の外部インターフェース（Connector、Plugin API、コンテナ間 IPC）の設計仕様を定義する。Power System Workflow Engine として Python 3.11+ / Docker 環境で動作する各インターフェースの Protocol、時間管理方式、拡張レベルを示す。

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-01 | 初版作成 |

---

## 6.1 外部IF一覧

| # | インターフェース名 | 種別 | 方向 | 関連要求 |
|---|---|---|---|---|
| IF-01 | ConnectorInterface | Python Protocol | gridflow ↔ 外部シミュレータ | REQ-F-007, REQ-Q-004 |
| IF-02 | Plugin API (L1) | YAML 設定 | ユーザ → gridflow | REQ-F-006 |
| IF-03 | Plugin API (L2) | Python Protocol | ユーザ → gridflow | REQ-F-006 |
| IF-04 | Plugin API (L3) | Python Protocol | ユーザ → gridflow | REQ-F-006 |
| IF-05 | Plugin API (L4) | ソースフォーク | ユーザ → gridflow | REQ-F-006 |
| IF-06 | DataExporter | Python Protocol | gridflow → 外部ツール | REQ-Q-009 |
| IF-07 | Notebook Bridge HTTP API | REST (HTTP) | Jupyter ↔ gridflow | REQ-F-007, REQ-Q-009 |

---

## 6.2 Connector インターフェース仕様

### 6.2.1 ConnectorInterface Protocol

外部シミュレーションツール（OpenDSS、pandapower、HELICS、Grid2Op 等）を統一的に扱うための Protocol。Clean Architecture の Interface Adapters 層に位置する。

```python
from typing import Protocol, Any
from dataclasses import dataclass


@dataclass(frozen=True)
class StepResult:
    """1 ステップの実行結果。"""
    status: str          # "success" | "warning" | "error"
    data: dict[str, Any] # CDL 準拠の出力データ
    elapsed_ms: float    # 実行時間（ミリ秒）


@dataclass(frozen=True)
class HealthStatus:
    """Connector の稼働状態。"""
    healthy: bool
    message: str


class ConnectorInterface(Protocol):
    """外部シミュレータとの統一インターフェース。"""

    def initialize(self, config: dict[str, Any]) -> None:
        """Connector を初期化する。設定を受け取りシミュレータへの接続を確立する。"""
        ...

    def execute(self, step: int, context: dict[str, Any]) -> StepResult:
        """指定ステップを実行し、結果を返す。"""
        ...

    def health_check(self) -> HealthStatus:
        """Connector の稼働状態を返す。"""
        ...

    def teardown(self) -> None:
        """リソースを解放し、シミュレータとの接続を切断する。"""
        ...
```

### 6.2.2 DataTranslator Protocol

Connector 内部で CDL との相互変換を担う Protocol。

```python
from typing import Protocol, Any
from gridflow.cdl import CanonicalData


class DataTranslator(Protocol):
    """ツール固有フォーマットと CDL 間の変換を担う。"""

    def to_canonical(self, raw: Any) -> CanonicalData:
        """ツール固有データを CDL 形式に変換する。"""
        ...

    def from_canonical(self, data: CanonicalData) -> Any:
        """CDL 形式をツール固有データに変換する。"""
        ...
```

### 6.2.3 時間管理方式

Connector の種別に応じて 3 つの時間管理方式を定義する。Orchestrator がステップ管理戦略を切り替える。

| 方式 | 対象 Connector | 時間制御の主体 | 説明 |
|---|---|---|---|
| Orchestrator-driven | OpenDSS, pandapower | Orchestrator | Orchestrator が各ステップのタイミングを決定し、Connector に `step` を渡す。シミュレータは受動的に実行する。 |
| Federation-driven | HELICS | HELICS Co-sim | HELICS のフェデレーション時間管理に従う。Orchestrator は HELICS Broker の時間進行を監視し、同期ポイントで CDL データを交換する。 |
| Environment-driven | Grid2Op | Grid2Op Environment | Grid2Op の Environment が時間進行を管理する。Orchestrator は `env.step(action)` の戻り値から状態を取得し、CDL に変換する。 |

---

## 6.3 Plugin API 仕様

段階的カスタマイズレベル（L1-L4）に応じた拡張インターフェースを定義する（`REQ-F-006`）。

### 6.3.1 L1: 設定変更（YAML）

YAML ファイルの編集のみで動作パラメータを変更する。コード変更不要。

```yaml
# config/simulation.yaml
simulation:
  solver: pandapower
  max_steps: 96
  time_resolution_min: 15
  convergence_tolerance: 1.0e-6

metrics:
  - name: voltage_deviation
    threshold: 0.05
  - name: thermal_overload
    threshold: 1.0
```

### 6.3.2 L2: プラグイン開発（Python Protocol）

MetricCalculator Protocol を実装し、カスタムメトリクスや制御ロジックを追加する。PluginRegistry に登録して利用する。

```python
from typing import Protocol, Any
from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    """計算結果メトリクス。"""
    name: str
    value: float
    unit: str
    metadata: dict[str, Any]


class MetricCalculator(Protocol):
    """カスタムメトリクス計算の Protocol。"""

    def calculate(self, data: dict[str, Any]) -> Metric:
        """CDL データからメトリクスを計算する。"""
        ...


# --- 利用例 ---

class VoltageDeviationCalculator:
    """電圧逸脱率を計算するカスタムメトリクス。"""

    def calculate(self, data: dict[str, Any]) -> Metric:
        voltages = data["bus_voltages"]
        nominal = data.get("nominal_voltage", 1.0)
        max_dev = max(abs(v - nominal) / nominal for v in voltages)
        return Metric(
            name="voltage_deviation",
            value=max_dev,
            unit="pu",
            metadata={"bus_count": len(voltages)},
        )


# PluginRegistry への登録
from gridflow.plugin import PluginRegistry

registry = PluginRegistry()
registry.register_metric("voltage_deviation", VoltageDeviationCalculator())
```

### 6.3.3 L3: 新規 Connector 実装

ConnectorInterface Protocol を実装し、新しいシミュレーションツールを統合する。

```python
from typing import Any
from gridflow.connector import ConnectorInterface, StepResult, HealthStatus


class CustomSimulatorConnector:
    """カスタムシミュレータ用 Connector 実装例。"""

    def __init__(self) -> None:
        self._client: Any = None

    def initialize(self, config: dict[str, Any]) -> None:
        host = config["host"]
        port = config["port"]
        self._client = connect_to_simulator(host, port)

    def execute(self, step: int, context: dict[str, Any]) -> StepResult:
        raw_result = self._client.run_step(step, context)
        return StepResult(
            status="success",
            data=self._translate(raw_result),
            elapsed_ms=raw_result.elapsed,
        )

    def health_check(self) -> HealthStatus:
        alive = self._client is not None and self._client.ping()
        return HealthStatus(healthy=alive, message="OK" if alive else "Not connected")

    def teardown(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def _translate(self, raw: Any) -> dict[str, Any]:
        """ツール固有結果を CDL 準拠 dict に変換する。"""
        return {"bus_voltages": raw.voltages, "line_flows": raw.flows}
```

### 6.3.4 L4: ソース改変（フォーク）

リポジトリをフォークし、コア機能を直接変更する。Orchestrator のスケジューリングロジックや CDL スキーマの拡張など、Protocol では吸収できない変更が対象となる。

---

## 6.4 Docker コンテナ間 IPC 仕様

### 6.4.1 共有ボリューム（CDL ファイル）

Orchestrator コンテナと Connector コンテナ間で CDL データファイルを受け渡すために、Docker 共有ボリュームを使用する。

| 項目 | 仕様 |
|---|---|
| マウントパス | `/data` |
| ファイル形式 | JSON / Parquet |
| ディレクトリ構造 | `/data/cdl/{experiment_id}/{step}/` |
| アクセス制御 | Orchestrator: read/write、Connector: read/write（自身のステップのみ） |

### 6.4.2 Notebook Bridge HTTP API

Jupyter Notebook から gridflow の機能にアクセスするための REST API。Orchestrator コンテナ内でホストされる。

| 項目 | 仕様 |
|---|---|
| ポート | 8080 |
| プロトコル | HTTP/1.1 (REST) |
| データ形式 | JSON |
| 認証 | トークンベース（Jupyter トークンと共有） |

**エンドポイント一覧**:

| メソッド | パス | 説明 |
|---|---|---|
| `GET` | `/api/v1/scenarios` | Scenario Pack 一覧取得 |
| `POST` | `/api/v1/scenarios/{id}/run` | 実験実行の開始 |
| `GET` | `/api/v1/experiments/{id}/status` | 実験実行状態の取得 |
| `GET` | `/api/v1/experiments/{id}/results` | 実験結果の取得（CDL 形式） |
| `GET` | `/api/v1/health` | ヘルスチェック |

---

## 関連要求トレーサビリティ

| 要求 ID | 要求名 | 本章での対応箇所 |
|---|---|---|
| REQ-F-006 | 段階的カスタムレイヤー | 6.3 Plugin API 仕様 |
| REQ-F-007 | Connector 統合 | 6.2 Connector インターフェース仕様 |
| REQ-Q-004 | 拡張性 | 6.2, 6.3（Protocol ベース設計） |
| REQ-Q-009 | データエクスポート容易性 | 6.4 Docker コンテナ間 IPC 仕様 |
