# 第4章 CLI インターフェース設計

本章では、gridflow の主要ユーザーインターフェースである CLI のコマンド体系、入出力仕様、および Notebook Bridge のプログラマティックインターフェースを定義する。IPA の画面設計に相当する章であり、CLI ベースのツールに読み替えて構成する。

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-01 | 初版作成 |

---

## 4.1 コマンド体系一覧

**関連要求:** REQ-F-005（CLI + Notebook Bridge）、REQ-Q-002（初回利用効率）

| コマンド | サブコマンド | 説明 | 関連 UC | 関連 REQ |
|---|---|---|---|---|
| `gridflow run` | — | Scenario Pack を実行する | UC-01 | REQ-F-001, REQ-F-002 |
| `gridflow scenario` | `create` | テンプレートから新規 Scenario Pack を作成 | UC-02 | REQ-F-001 |
| | `list` | Registry 内の Scenario Pack を一覧表示 | UC-02 | REQ-F-001 |
| | `clone` | 既存 Pack を複製 | UC-02 | REQ-F-001 |
| | `validate` | Scenario Pack の設定を検証 | UC-02 | REQ-F-001 |
| | `register` | Registry に登録 | UC-02 | REQ-F-001 |
| `gridflow benchmark` | `run` | 実験結果を評価指標で採点 | UC-03 | REQ-F-004 |
| | `compare` | 複数実験の比較表を生成 | UC-03 | REQ-F-004 |
| | `export` | 評価結果をエクスポート | UC-03 | REQ-F-004, REQ-Q-006 |
| `gridflow status` | — | 環境・コンポーネントの状態確認 | UC-04 | REQ-F-002 |
| `gridflow logs` | — | 実行ログの確認 | UC-05 | REQ-Q-008 |
| `gridflow trace` | — | 実行パイプラインのトレース表示 | UC-05 | REQ-Q-008 |
| `gridflow metrics` | — | KPI メトリクスの確認 | UC-05 | REQ-Q-008 |
| `gridflow debug` | — | エラー原因の特定・中間データ検査 | UC-06 | REQ-Q-008 |
| `gridflow results` | `show` | 実験結果の表示 | UC-09 | REQ-F-003 |
| | `export` | 結果データのエクスポート | UC-09 | REQ-F-003, REQ-Q-006 |
| `gridflow update` | — | gridflow のアップデート | UC-08 | — |

---

## 4.2 コマンド別 入出力仕様

### 4.2.1 `gridflow run`

```
gridflow run <scenario-pack> [OPTIONS]
```

| 引数/オプション | 型 | 説明 | デフォルト |
|---|---|---|---|
| `<scenario-pack>` | str | Scenario Pack の ID または名前 | （必須） |
| `--seed` | int | 乱数 seed の上書き | Pack 内定義値 |
| `--from-step` | str | 指定ステップから再開（UC-06 連携） | なし |
| `--batch` | str | バッチパラメータファイル | なし |
| `--output` | path | 結果出力先ディレクトリ | `./results/` |
| `--format` | choice | 出力形式: `json` / `text` | `text` |

**標準出力（text モード）:**

```
[gridflow] Loading scenario pack: microgrid-baseline-v1
[gridflow] Validating configuration... OK
[gridflow] Initializing connectors: OpenDSS... OK
[gridflow] Executing step 1/3: power_flow_run (00:00:12)
[gridflow] Executing step 2/3: metrics_calc (00:00:02)
[gridflow] Executing step 3/3: store_results (00:00:01)

✓ Experiment completed successfully
  Experiment ID: exp-20260401-001
  Duration: 00:00:15
  Results: ./results/exp-20260401-001/
```

**標準出力（json モード）:**

```json
{
  "status": "success",
  "experiment_id": "exp-20260401-001",
  "duration_ms": 15234,
  "results_path": "./results/exp-20260401-001/",
  "steps": [
    {"name": "power_flow_run", "status": "success", "duration_ms": 12100},
    {"name": "metrics_calc", "status": "success", "duration_ms": 2034},
    {"name": "store_results", "status": "success", "duration_ms": 1100}
  ]
}
```

**終了コード:**

| コード | 意味 |
|---|---|
| 0 | 正常完了 |
| 1 | 実行エラー（EXEC / CONN / DATA） |
| 2 | 設定エラー（CONF） |
| 3 | システムエラー（SYS） |

### 4.2.2 `gridflow scenario`

```
gridflow scenario create <name> [--template <template>]
gridflow scenario list [--filter <keyword>] [--format json|text]
gridflow scenario clone <source> <new-name>
gridflow scenario validate <name>
gridflow scenario register <name> [--version <version>]
```

| サブコマンド | 主な出力 |
|---|---|
| `create` | テンプレートからのスケルトン生成。作成先ディレクトリパスを表示 |
| `list` | Pack 名、バージョン、登録日時、説明の一覧表 |
| `clone` | 複製先の Pack パスを表示 |
| `validate` | 検証結果（OK / エラー一覧）を表示 |
| `register` | 登録完了メッセージ（Pack ID、バージョン）を表示 |

### 4.2.3 `gridflow benchmark`

```
gridflow benchmark run <experiment-ids...> [--metrics <metrics>]
gridflow benchmark compare <experiment-ids...> [--format json|text|latex]
gridflow benchmark export <experiment-ids...> --format <csv|json|parquet|latex>
```

| サブコマンド | 主な出力 |
|---|---|
| `run` | 各実験の評価指標値を表形式で表示 |
| `compare` | 複数実験の比較表。`--format latex` で LaTeX テーブル出力（REQ-Q-011） |
| `export` | エクスポート先ファイルパスを表示 |

### 4.2.4 `gridflow status`

```
gridflow status [--format json|text]
```

**出力例:**

```
gridflow v0.1.0

Components:
  Orchestrator    ● running
  Registry        ● running  (3 packs registered)
  OpenDSS         ● healthy
  HELICS          ○ not configured

Experiments:
  Running: 0
  Completed: 5
```

### 4.2.5 `gridflow logs` / `gridflow trace` / `gridflow metrics`

```
gridflow logs [--experiment <id>] [--level info|warn|error|debug] [--tail <n>]
gridflow trace <experiment-id>
gridflow metrics [--format json|text]
```

| コマンド | 出力内容 |
|---|---|
| `logs` | 構造化ログ（タイムスタンプ、コンポーネント、レベル、メッセージ） |
| `trace` | 実行パイプラインの各ステップの時系列表示（名前、時間、状態） |
| `metrics` | KPI 計測値（セットアップ時間、コマンド数、実験成功率等） |

### 4.2.6 `gridflow results`

```
gridflow results show <experiment-id> [--format json|text]
gridflow results export <experiment-id> --format <csv|json|parquet> [--output <path>]
gridflow results export <experiment-id> --format paper [--output <path>]
```

`--format paper` は PaperExporter を使用し、LaTeX 表形式 + matplotlib 用データを出力する（REQ-Q-006、REQ-Q-011）。

---

## 4.3 Notebook Bridge インターフェース仕様

**関連要求:** REQ-F-005

Notebook Bridge は軽量 HTTP API 経由で gridflow コアと通信し、Jupyter Notebook / Python スクリプトからプログラマティックにアクセスする。

### Python API

```python
import gridflow

# 接続
gf = gridflow.connect()  # localhost:8080 に接続

# Scenario Pack 管理
packs = gf.scenario.list()
pack = gf.scenario.clone("baseline-v1", "my-experiment")

# 実験実行
result = gf.run("my-experiment", seed=42)
print(result.status)          # "success"
print(result.experiment_id)   # "exp-20260401-002"
print(result.duration_ms)     # 15234

# 結果取得
df = result.to_dataframe()    # pandas DataFrame
timeseries = result.timeseries("voltage_bus_1")

# ベンチマーク
comparison = gf.benchmark.compare([
    "exp-20260401-001",
    "exp-20260401-002",
])
comparison.to_latex()          # LaTeX 表形式文字列
comparison.to_dataframe()      # pandas DataFrame

# エクスポート
result.export("csv", output="./export/")
result.export("paper", output="./paper_data/")
```

### 設計方針

- Notebook Bridge は CLI と同等の操作を提供する（REQ-F-005）
- 戻り値は構造化オブジェクトとし、`.to_dataframe()` / `.to_dict()` で変換可能
- 内部通信は REST API（JSON）で、LLM からも利用可能（REQ-Q-009）

---

## 4.4 エラーメッセージ設計

**関連要求:** REQ-Q-009（LLM 親和性）

### エラー出力形式

**text モード:**

```
[ERROR CONN-001] OpenDSS connector failed to initialize
  Cause: DSS engine not found in container
  Resolution: Run 'gridflow status' to check connector health,
              then 'docker compose up' to restart
  Context: connector=OpenDSS, experiment_id=exp-001
```

**json モード:**

```json
{
  "error": {
    "category": "CONN",
    "code": "CONN-001",
    "message": "OpenDSS connector failed to initialize",
    "cause": "DSS engine not found in container",
    "resolution": "Run 'gridflow status' to check connector health, then 'docker compose up' to restart",
    "context": {
      "connector": "OpenDSS",
      "experiment_id": "exp-001"
    }
  }
}
```

### エラーカテゴリ

| カテゴリ | コード接頭辞 | 発生箇所 | 終了コード | 例 |
|---|---|---|---|---|
| ConfigError | `CONF-xxx` | Scenario Pack 検証 | 2 | CONF-001: 必須フィールド欠落 |
| ConnectorError | `CONN-xxx` | Connector 初期化・通信 | 1 | CONN-001: 外部ツール未起動 |
| ExecutionError | `EXEC-xxx` | ステップ実行中 | 1 | EXEC-001: シミュレーション収束失敗 |
| DataError | `DATA-xxx` | CDL 読み書き | 1 | DATA-001: スキーマ不一致 |
| SystemError | `SYS-xxx` | gridflow 内部 | 3 | SYS-001: メモリ不足 |

### 設計原則

1. **resolution フィールドの必須化**: エラーを出す側が対処案を考えることを強制する
2. **raw_error の保持**: 外部ツールのエラーメッセージは握りつぶさず `context` に保持する
3. **エラーコードで検索可能**: `CONN-001` のような一意コードでドキュメント・Issue を検索できる
4. **LLM 解析可能**: `--format json` で構造化出力し、LLM Agent が原因分析に利用可能（REQ-Q-009）
