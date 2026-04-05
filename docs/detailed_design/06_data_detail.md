# 第6章 データ詳細設計

本章では、基本設計 第5章（データ設計）で定義した Canonical Data Layer (CDL) のエンティティ関係・属性定義、YAML/JSON スキーマ、およびファイル I/O 仕様を詳細化する。

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-03 | 初版作成（6.1〜6.4） |
| 0.2 | 2026-04-03 | 6.5〜6.8追記 |

---

## 6.1 CDL エンティティ関係図（ER図）

**関連要件**: `REQ-F-003`

CDL を構成する全エンティティ間の関係を以下の ER 図に示す。ScenarioPack を起点として、ExperimentMetadata が実験単位の集約ルートとなり、Topology・TimeSeries・Event・Metric を束ねる。Topology は Node・Edge・Asset を所有する。

```mermaid
erDiagram
    ScenarioPack ||--o{ ExperimentMetadata : "generates"
    ScenarioPack {
        string schema_version
        string name
        string description
        boolean baseline
    }

    ExperimentMetadata ||--|| Topology : "references"
    ExperimentMetadata ||--o{ TimeSeries : "contains"
    ExperimentMetadata ||--o{ Event : "records"
    ExperimentMetadata ||--o{ Metric : "evaluates"
    ExperimentMetadata {
        string experiment_id PK
        datetime created_at
        string scenario_pack_id FK
        string connector
        int seed
    }

    Topology ||--|{ Node : "has"
    Topology ||--|{ Edge : "has"
    Topology ||--o{ Asset : "has"
    Topology {
        string id PK
        dict metadata
    }

    Node {
        string id PK
        string name
        float voltage_kv
        tuple coordinates
    }

    Edge {
        string id PK
        string from_node FK
        string to_node FK
        string edge_type
        dict properties
    }

    Asset {
        string id PK
        AssetType asset_type
        string node_id FK
        dict parameters
    }

    TimeSeries {
        string id PK
        string name
        list_datetime timestamps
        list_float values
        string unit
        dict metadata
    }

    Event {
        string id PK
        string event_type
        datetime timestamp
        string target_id FK
        dict params
    }

    Metric {
        string name PK
        float value
        string unit
        float threshold
        dict metadata
    }

    Node ||--o{ Asset : "hosts"
    Node ||--o{ Edge : "connects(from)"
    Node ||--o{ Edge : "connects(to)"
```

### カーディナリティ一覧

| 親エンティティ | 子エンティティ | 関係 | カーディナリティ | 説明 |
|---|---|---|---|---|
| ScenarioPack | ExperimentMetadata | generates | 1 : 0..* | 1 つの Pack から複数実験を生成可能 |
| ExperimentMetadata | Topology | references | 1 : 1 | 実験は 1 つの Topology を参照 |
| ExperimentMetadata | TimeSeries | contains | 1 : 0..* | 実験は 0 個以上の時系列を保持 |
| ExperimentMetadata | Event | records | 1 : 0..* | 実験は 0 個以上のイベントを記録 |
| ExperimentMetadata | Metric | evaluates | 1 : 0..* | 実験は 0 個以上のメトリクスを算出 |
| Topology | Node | has | 1 : 1..* | トポロジーは 1 個以上のノードを持つ |
| Topology | Edge | has | 1 : 1..* | トポロジーは 1 個以上のエッジを持つ |
| Topology | Asset | has | 1 : 0..* | トポロジーは 0 個以上のアセットを持つ |
| Node | Asset | hosts | 1 : 0..* | ノードは 0 個以上のアセットを接続 |
| Node | Edge | connects | 1 : 0..* | ノードは 0 個以上のエッジの端点となる |

---

## 6.2 CDL エンティティ属性定義

各エンティティの属性を以下の表で定義する。Python 型は `dataclasses.dataclass(frozen=True)` による不変オブジェクトとして実装する。

### 6.2.1 Topology

| 属性名 | Python 型 | 必須/オプション | 制約 | 説明 |
|---|---|---|---|---|
| `id` | `str` | 必須 | 空文字不可、一意 | トポロジー識別子 |
| `nodes` | `tuple[Node, ...]` | 必須 | 1 個以上 | 所属するノードの不変タプル |
| `edges` | `tuple[Edge, ...]` | 必須 | 1 個以上 | 所属するエッジの不変タプル |
| `metadata` | `dict[str, object]` | オプション | デフォルト `{}` | 座標系、基準電圧等の補助情報 |

### 6.2.2 Node

| 属性名 | Python 型 | 必須/オプション | 制約 | 説明 |
|---|---|---|---|---|
| `id` | `str` | 必須 | 空文字不可、Topology 内で一意 | ノード識別子 |
| `name` | `str` | 必須 | 空文字不可 | ノード表示名 |
| `voltage_kv` | `float` | 必須 | 正の値 | 定格電圧 (kV) |
| `coordinates` | `tuple[float, float] \| None` | オプション | デフォルト `None`、(緯度, 経度) | 地理座標 |

### 6.2.3 Edge

| 属性名 | Python 型 | 必須/オプション | 制約 | 説明 |
|---|---|---|---|---|
| `id` | `str` | 必須 | 空文字不可、Topology 内で一意 | エッジ識別子 |
| `from_node` | `str` | 必須 | 有効な Node.id を参照 | 始点ノード ID |
| `to_node` | `str` | 必須 | 有効な Node.id を参照 | 終点ノード ID |
| `edge_type` | `str` | 必須 | `"line"` \| `"transformer"` \| `"switch"` | エッジ種別 |
| `properties` | `dict[str, object]` | オプション | デフォルト `{}` | インピーダンス、定格容量等の物理パラメータ |

### 6.2.4 Asset

| 属性名 | Python 型 | 必須/オプション | 制約 | 説明 |
|---|---|---|---|---|
| `id` | `str` | 必須 | 空文字不可、一意 | アセット識別子 |
| `asset_type` | `AssetType` | 必須 | Enum: `GENERATOR`, `LOAD`, `STORAGE`, `LINE`, `TRANSFORMER` | アセット種別 |
| `node_id` | `str` | 必須 | 有効な Node.id を参照 | 接続先ノード ID |
| `parameters` | `dict[str, object]` | オプション | デフォルト `{}` | 定格出力、容量等のアセット固有パラメータ |

### 6.2.5 TimeSeries

| 属性名 | Python 型 | 必須/オプション | 制約 | 説明 |
|---|---|---|---|---|
| `id` | `str` | 必須 | 空文字不可、一意 | 時系列識別子 |
| `name` | `str` | 必須 | 空文字不可 | 時系列の表示名（例: `"load_profile"` ） |
| `timestamps` | `tuple[datetime, ...]` | 必須 | 昇順、1 個以上、`values` と同数 | タイムスタンプ列 |
| `values` | `tuple[float, ...]` | 必須 | `timestamps` と同数 | 値列 |
| `unit` | `str` | 必須 | 空文字不可（例: `"kW"`, `"kVar"`, `"V"` ） | 物理単位 |
| `metadata` | `dict[str, object]` | オプション | デフォルト `{}` | 解像度、補間方式等の補助情報 |

### 6.2.6 Event

| 属性名 | Python 型 | 必須/オプション | 制約 | 説明 |
|---|---|---|---|---|
| `id` | `str` | 必須 | 空文字不可、一意 | イベント識別子 |
| `event_type` | `str` | 必須 | `"fault"` \| `"switch"` \| `"load_change"` \| `"generation_change"` | イベント種別 |
| `timestamp` | `datetime` | 必須 | シミュレーション時間範囲内 | 発生時刻 |
| `target_id` | `str` | 必須 | 有効な Node.id または Edge.id を参照 | 対象要素 ID |
| `params` | `dict[str, object]` | オプション | デフォルト `{}` | イベント固有パラメータ（障害種別、変化量等） |

### 6.2.7 Metric

| 属性名 | Python 型 | 必須/オプション | 制約 | 説明 |
|---|---|---|---|---|
| `name` | `str` | 必須 | 空文字不可、実験内で一意 | メトリクス名（例: `"voltage_deviation_rate"` ） |
| `value` | `float` | 必須 | 有限値 | 計算結果値 |
| `unit` | `str` | 必須 | 空文字不可（例: `"%"`, `"hours"`, `"kWh"` ） | 物理単位 |
| `threshold` | `float \| None` | オプション | デフォルト `None`、指定時は有限値 | 閾値（超過で警告） |
| `metadata` | `dict[str, object]` | オプション | デフォルト `{}` | 算出条件等の補助情報 |

### 6.2.8 ExperimentMetadata

| 属性名 | Python 型 | 必須/オプション | 制約 | 説明 |
|---|---|---|---|---|
| `experiment_id` | `str` | 必須 | 空文字不可、グローバル一意（UUID 推奨） | 実験識別子 |
| `created_at` | `datetime` | 必須 | ISO 8601 形式 | 実験作成日時 |
| `scenario_pack_id` | `str` | 必須 | 有効な ScenarioPack 名を参照 | 元となる Scenario Pack の識別子 |
| `connector` | `str` | 必須 | 登録済み Connector 名（例: `"opendss"`, `"pandapower"` ） | 使用した Connector |
| `parameters` | `dict[str, object]` | オプション | デフォルト `{}` | 実験固有パラメータ（シミュレーション設定等） |
| `seed` | `int` | オプション | デフォルト `0`、非負整数 | 乱数シード（再現性担保） |

---

## 6.3 YAML/JSON スキーマ定義

### 6.3.1 pack.yaml (config.yaml) JSON Schema

Scenario Pack のメイン設定ファイル `config.yaml` に対する JSON Schema を以下に定義する（`REQ-Q-011`）。バリデーションは `jsonschema` ライブラリにより実行時に検証される。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://gridflow.dev/schemas/pack-config-v1.json",
  "title": "Scenario Pack config.yaml",
  "description": "gridflow Scenario Pack のメイン設定ファイルスキーマ",
  "type": "object",
  "required": ["schema_version", "name", "network", "simulation"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+$",
      "description": "スキーマバージョン（例: '1.0'）"
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[a-z0-9][a-z0-9_-]*$",
      "description": "Scenario Pack 名（小文字英数字・ハイフン・アンダースコア）"
    },
    "description": {
      "type": "string",
      "maxLength": 1024,
      "description": "Scenario Pack の説明"
    },
    "baseline": {
      "type": "boolean",
      "default": false,
      "description": "ベースラインフラグ（比較基準として使用する場合 true）"
    },
    "citation": {
      "type": "string",
      "description": "引用情報"
    },
    "network": {
      "type": "object",
      "required": ["topology", "assets"],
      "additionalProperties": false,
      "properties": {
        "topology": {
          "type": "string",
          "pattern": "\\.json$",
          "description": "トポロジー定義ファイルの相対パス"
        },
        "assets": {
          "type": "string",
          "pattern": "\\.json$",
          "description": "アセット定義ファイルの相対パス"
        }
      }
    },
    "timeseries": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "type", "resolution_sec"],
        "additionalProperties": false,
        "properties": {
          "path": {
            "type": "string",
            "description": "時系列データファイルの相対パス"
          },
          "type": {
            "type": "string",
            "enum": ["load", "generation", "price", "temperature"],
            "description": "時系列データ種別"
          },
          "resolution_sec": {
            "type": "integer",
            "minimum": 1,
            "description": "時間解像度（秒）"
          }
        }
      }
    },
    "simulation": {
      "type": "object",
      "required": ["connector", "duration_hours", "step_size_sec"],
      "additionalProperties": false,
      "properties": {
        "connector": {
          "type": "string",
          "enum": ["opendss", "pandapower", "helics", "grid2op"],
          "description": "使用する Connector 名"
        },
        "duration_hours": {
          "type": "number",
          "exclusiveMinimum": 0,
          "description": "シミュレーション時間（時間）"
        },
        "step_size_sec": {
          "type": "integer",
          "minimum": 1,
          "description": "シミュレーションステップサイズ（秒）"
        }
      }
    },
    "evaluation": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "metrics": {
          "type": "string",
          "description": "メトリクス定義ファイルの相対パス"
        },
        "expected": {
          "type": "string",
          "description": "期待結果ファイルの相対パス"
        },
        "tolerance": {
          "type": "number",
          "minimum": 0,
          "default": 0.01,
          "description": "回帰テスト用許容誤差"
        }
      }
    },
    "visualization": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "templates": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "可視化テンプレートファイルの相対パスリスト"
        }
      }
    }
  }
}
```

### 6.3.2 スキーマバリデーション適用方針

| 項目 | 方針 |
|---|---|
| バリデーションタイミング | `ImportScenario` ユースケース実行時、および CLI の `validate` サブコマンド実行時 |
| バリデーションライブラリ | `jsonschema` (Python) |
| スキーマ格納先 | `src/gridflow/infra/schema/` ディレクトリ配下に JSON ファイルとして配置 |
| バージョン管理 | `schema_version` フィールドにより後方互換性を管理。旧バージョンのスキーマも保持する |
| エラー報告 | バリデーションエラーは全件収集し、エラーメッセージのリストとして返却する |

---

## 6.4 ファイル I/O 仕様

### 6.4.1 対応フォーマット一覧

CDL データの永続化およびエクスポートに使用するファイル形式を以下に定義する（`REQ-F-003`）。

| 形式 | 拡張子 | エンコーディング | ヘッダー | 圧縮 | 主な用途 |
|---|---|---|---|---|---|
| CSV | `.csv` | UTF-8 (BOM なし) | 1 行目をカラム名ヘッダーとする | なし（オプションで gzip `.csv.gz`） | TimeSeries の入出力、Metric 一覧エクスポート |
| JSON | `.json` | UTF-8 (BOM なし) | なし（自己記述的構造） | なし | Topology、Asset、ExperimentMetadata、config.yaml のシリアライズ |
| Parquet | `.parquet` | バイナリ | スキーマ埋め込み | Snappy（デフォルト）、gzip、zstd から選択可 | 大規模 TimeSeries の高速列指向アクセス、長期保存 |

### 6.4.2 CSV I/O 仕様

| 項目 | 仕様 |
|---|---|
| 区切り文字 | カンマ (`,`) |
| 改行コード | LF (`\n`) |
| クォート | ダブルクォート (`"`)、フィールド内にカンマ・改行を含む場合のみ適用 |
| エンコーディング | UTF-8（BOM なし） |
| ヘッダー行 | 必須（1 行目にカラム名） |
| 日時フォーマット | ISO 8601（`YYYY-MM-DDTHH:MM:SS+00:00`） |
| 欠損値表現 | 空文字列 (`""`) |
| 浮動小数点精度 | 小数点以下 6 桁（出力時）、入力時は任意精度を受け入れ |
| 読み込みライブラリ | `pandas.read_csv()` または標準 `csv` モジュール |
| 書き出しライブラリ | `pandas.DataFrame.to_csv(index=False)` |

### 6.4.3 JSON I/O 仕様

| 項目 | 仕様 |
|---|---|
| エンコーディング | UTF-8（BOM なし） |
| フォーマット | インデント 2 スペースの整形済み JSON（出力時） |
| 日時フォーマット | ISO 8601 文字列 |
| 数値 | IEEE 754 浮動小数点。`NaN`・`Infinity` は使用不可（JSON 標準準拠） |
| `null` の扱い | オプション属性が未設定の場合、キーごと省略を推奨。明示的に `null` としても可 |
| 読み込みライブラリ | `json.load()` (標準ライブラリ) |
| 書き出しライブラリ | `json.dump(ensure_ascii=False, indent=2)` |
| 最大ファイルサイズ | 100 MB（超過する場合は Parquet を使用） |

### 6.4.4 Parquet I/O 仕様

| 項目 | 仕様 |
|---|---|
| エンジン | `pyarrow`（必須依存） |
| 圧縮形式 | Snappy（デフォルト）。設定により gzip、zstd に切り替え可 |
| スキーマ | PyArrow Schema をファイルメタデータに埋め込み |
| 日時フォーマット | `timestamp[us, tz=UTC]`（マイクロ秒精度、UTC） |
| パーティション | 単一ファイル出力（デフォルト）。大規模データはディレクトリパーティションを許容 |
| 読み込みライブラリ | `pandas.read_parquet(engine="pyarrow")` |
| 書き出しライブラリ | `pandas.DataFrame.to_parquet(engine="pyarrow", compression="snappy")` |
| 推奨用途 | 行数 10,000 以上の TimeSeries データ、ベンチマーク結果の長期保存 |

### 6.4.5 形式選択ガイドライン

| ユースケース | 推奨形式 | 理由 |
|---|---|---|
| TimeSeries 入力（ユーザー作成） | CSV | テキストエディタ・Excel で編集可能 |
| TimeSeries 保存（大規模） | Parquet | 圧縮効率とクエリ性能に優れる |
| Topology / Asset 定義 | JSON | ネスト構造を自然に表現可能 |
| ExperimentMetadata | JSON | 構造化データの可読性を確保 |
| Metric エクスポート | CSV | 他ツール（Excel、R 等）との連携が容易 |
| Metric 期待値（回帰テスト） | JSON | 構造化された比較が容易 |
| Scenario Pack 設定 | YAML | 人間可読性とコメント記述を重視 |

---

## 6.5 入出力設計

**関連要件**: `REQ-F-001`〜`REQ-F-007`

各機能の入力・出力およびそのデータ形式を以下の表に定義する。

| 機能 ID | 機能名 | 入力 | 入力形式 | 出力 | 出力形式 |
|---|---|---|---|---|---|
| FN-001 | Scenario Pack 管理 | パック名・テンプレート名・フィルタ条件 | CLI 引数 / YAML (`pack.yaml`) | Scenario Pack ディレクトリ・パック一覧・検証結果 | ディレクトリツリー / JSON |
| FN-002 | 実験実行オーケストレーション | Scenario Pack ID・実行オプション（シード、並列数等） | CLI 引数 / YAML (`pack.yaml`) | ExperimentResult（メタデータ＋CDL データセット） | JSON / Parquet / CSV |
| FN-003 | Connector 統合 | Connector 種別・シミュレーション設定・ネットワーク定義 | JSON / YAML / OpenDSS `.dss` ファイル | シミュレーション結果（電圧・電流・電力時系列） | CDL TimeSeries (Parquet / CSV) |
| FN-004 | Canonical Data Layer | CDL エンティティオブジェクト（Topology, TimeSeries 等） | Python オブジェクト (`dataclass`) | 永続化されたデータファイル | JSON / CSV / Parquet |
| FN-005 | ベンチマーク評価 | ExperimentResult・期待値ファイル・メトリクス定義 | JSON / CSV / YAML (`metrics.yaml`) | 評価レポート（メトリクス比較結果・合否判定） | JSON / CSV |
| FN-006 | CLI インターフェース | サブコマンド・オプション・引数 | CLI 引数 (argv) | コマンド実行結果（テーブル・JSON・プログレスバー） | stdout (テーブル / JSON) |
| FN-007 | Notebook Bridge | Python API 呼び出し（Pack ID、クエリ条件等） | Python 関数引数 | CDL オブジェクト・pandas DataFrame・可視化ウィジェット | Python オブジェクト / DataFrame / HTML |
| FN-008 | ロギング・トレーシング | ログレベル・コンテキスト情報（実験 ID、ステップ名等） | Python API / 環境変数 | 構造化ログレコード | JSON Lines (`.jsonl`) / stderr |
| FN-009 | 段階的カスタムレイヤー | プラグインモジュールパス・フック定義 | Python エントリポイント / YAML | カスタム処理結果（CDL 拡張データ） | プラグイン依存（CDL 準拠） |

---

## 6.6 データ変換ロジック

**関連要件**: `REQ-F-003`, `REQ-F-007`

### 6.6.1 OpenDSS → CDL フィールドマッピング

OpenDSS Connector がシミュレーション結果およびネットワーク定義を CDL エンティティに変換する際のフィールドマッピングを以下に定義する。

| OpenDSS ソース | OpenDSS フィールド | CDL エンティティ | CDL 属性 | 変換ロジック |
|---|---|---|---|---|
| `Bus` | `Name` | Node | `id` | 小文字正規化。プレフィックス `bus_` を付与 |
| `Bus` | `kVBase` | Node | `voltage_kv` | そのまま `float` にマッピング |
| `Bus` | `x`, `y` | Node | `coordinates` | `(y, x)` → `(latitude, longitude)` タプルに変換。未設定時は `None` |
| `Line` / `Transformer` | `Name` | Edge | `id` | 小文字正規化。元の要素種別をプレフィックスとして付与 |
| `Line` / `Transformer` | `Bus1`, `Bus2` | Edge | `from_node`, `to_node` | バス名を Node.id 形式に正規化。位相指定子（`.1.2.3`）を除去 |
| `Line` / `Transformer` | (種別) | Edge | `edge_type` | `Line` → `"line"`, `Transformer` → `"transformer"`, `SwtControl` → `"switch"` |
| `Generator` / `Load` / `Storage` | `Name`, 各パラメータ | Asset | `id`, `asset_type`, `parameters` | `asset_type` を Enum にマッピング。`kW`, `kVar`, `kWRated` 等をパラメータ dict に格納 |
| `Monitor` / `EnergyMeter` | 時系列出力 | TimeSeries | `timestamps`, `values`, `unit` | OpenDSS の `dblHour` を `datetime` に変換（基準日時 + hours）。値は `float` リストとして格納 |

### 6.6.2 変換時の共通ルール

| ルール | 説明 |
|---|---|
| ID 正規化 | すべての ID は小文字英数字・アンダースコア・ハイフンのみ許可。不正文字はアンダースコアに置換 |
| 単位変換 | OpenDSS の内部単位系（per-unit 含む）から SI 単位系に変換。電圧は kV、電力は kW、電流は A |
| 欠損値処理 | OpenDSS で未定義のオプション属性は CDL のデフォルト値（空 dict `{}`、`None`）を適用 |
| エラーハンドリング | マッピング不可能なフィールドは警告ログを出力し、`metadata` dict に `_unmapped` キーで元データを保存 |

---

## 6.7 ファイルストレージ物理設計

**関連要件**: `REQ-F-001`, `REQ-F-003`

### 6.7.1 ディレクトリレイアウト

gridflow はユーザーホーム配下の `~/.gridflow/` をルートディレクトリとして使用する。以下にディレクトリツリーを示す。

```
~/.gridflow/
├── config.toml                          # グローバル設定（ログレベル、デフォルト Connector 等）
├── registry/                            # Scenario Pack レジストリ
│   ├── index.json                       # 登録済みパックのインデックス（ID・名前・パス・バージョン）
│   └── packs/                           # 登録済み Scenario Pack の実体
│       ├── ieee13-baseline/             # パック名ディレクトリ
│       │   ├── 1.0.0/                   # バージョン別ディレクトリ
│       │   │   ├── config.yaml          # pack.yaml（メイン設定）
│       │   │   ├── network/
│       │   │   │   ├── topology.json    # トポロジー定義
│       │   │   │   └── assets.json      # アセット定義
│       │   │   ├── timeseries/          # 時系列データ
│       │   │   │   ├── load_profile.csv
│       │   │   │   └── pv_output.csv
│       │   │   ├── config/              # シミュレータ固有設定
│       │   │   ├── metrics.yaml         # 評価指標定義
│       │   │   └── expected/            # 期待出力（回帰テスト用）
│       │   └── 1.1.0/
│       └── ieee123-pv30/
├── experiments/                          # 実験結果格納領域
│   └── <experiment_id>/                  # UUID ベースのディレクトリ名
│       ├── metadata.json                 # ExperimentMetadata
│       ├── topology.json                 # スナップショット（実行時 Topology）
│       ├── timeseries/                   # シミュレーション結果時系列
│       │   ├── voltage.parquet
│       │   ├── power_flow.parquet
│       │   └── load_actual.csv
│       ├── events.json                   # イベントログ
│       ├── metrics.json                  # 算出メトリクス
│       └── logs/                         # 実験固有ログ
│           └── experiment.jsonl
├── cache/                                # 一時キャッシュ領域
│   ├── connectors/                       # Connector ランタイムキャッシュ
│   └── schemas/                          # ダウンロード済みスキーマキャッシュ
├── plugins/                              # カスタムプラグイン格納領域
│   └── <plugin_name>/
└── logs/                                 # グローバルログ
    ├── gridflow.jsonl                    # アプリケーションログ
    └── audit.jsonl                       # 操作監査ログ
```

### 6.7.2 ストレージ管理ポリシー

| 項目 | ポリシー |
|---|---|
| ディレクトリ自動作成 | 初回起動時に `~/.gridflow/` 配下の必須ディレクトリを自動作成する |
| パーミッション | `~/.gridflow/` は `0700`（ユーザーのみ読み書き実行可） |
| 実験結果の保持期間 | デフォルト無期限。`config.toml` の `storage.retention_days` で設定可 |
| キャッシュ自動削除 | `cache/` 配下は `gridflow cache clean` コマンドで手動削除。`storage.cache_max_mb` 超過時に LRU で自動削除 |
| ディスク容量チェック | 実験実行前に `experiments/` の空き容量を確認。100 MB 未満で警告、10 MB 未満でエラー |
| バックアップ | `registry/` および `experiments/` を対象とした `gridflow export` コマンドで tar.gz アーカイブを生成可能 |

---

## 6.8 バリデーションルール一覧

**関連要件**: `REQ-F-001`〜`REQ-F-003`, `REQ-Q-011`

CDL エンティティおよび入力データに対して適用するバリデーションルールを以下に定義する。バリデーションは `src/gridflow/domain/validators.py` に集約し、ユースケース層から呼び出す。

| ルール ID | 対象 | ルール | エラー時動作 |
|---|---|---|---|
| VR-001 | ScenarioPack `name` | 小文字英数字・ハイフン・アンダースコアのみ。1〜128 文字。先頭は英数字 | `ValidationError` を送出。メッセージにパック名と違反箇所を含める |
| VR-002 | ScenarioPack `schema_version` | `^\d+\.\d+$` パターンに一致すること | `ValidationError` を送出。サポート対象バージョン一覧を提示 |
| VR-003 | ScenarioPack `config.yaml` | JSON Schema (`pack-config-v1.json`) に準拠すること | 全バリデーションエラーを収集し、エラーリストとして返却 |
| VR-004 | Topology `nodes` | 1 個以上の Node を含むこと | `ValidationError`（空トポロジーは不正） |
| VR-005 | Topology `edges` | 1 個以上の Edge を含むこと。各 Edge の `from_node`・`to_node` が Topology 内の有効な Node.id を参照すること | `ValidationError`。参照先不明の Node.id を報告 |
| VR-006 | Node `id` | Topology 内で一意であること。空文字不可 | `ValidationError`。重複 ID を列挙 |
| VR-007 | Node `voltage_kv` | 正の有限浮動小数点値であること | `ValidationError`。不正値を報告 |
| VR-008 | Edge `edge_type` | `"line"` / `"transformer"` / `"switch"` のいずれかであること | `ValidationError`。許可値の一覧を提示 |
| VR-009 | Asset `asset_type` | `AssetType` Enum の有効値であること（`GENERATOR` / `LOAD` / `STORAGE` / `LINE` / `TRANSFORMER`） | `ValidationError`。有効な Enum 値を提示 |
| VR-010 | Asset `node_id` | 所属 Topology 内の有効な Node.id を参照すること | `ValidationError`。参照先不明の Node.id を報告 |
| VR-011 | TimeSeries `timestamps` | 昇順であること。1 個以上。`values` と同数であること | `ValidationError`。違反箇所のインデックスを報告 |
| VR-012 | TimeSeries `values` | すべて有限浮動小数点値であること（`NaN`・`Infinity` 不可） | `ValidationError`。不正値のインデックスと値を報告 |
| VR-013 | Event `timestamp` | シミュレーション時間範囲内であること | `ValidationError`。許容範囲と実値を報告 |
| VR-014 | Metric `value` | 有限浮動小数点値であること | `ValidationError`。メトリクス名と不正値を報告 |
| VR-015 | CSV 入力ファイル | UTF-8 エンコーディング（BOM なし）であること。ヘッダー行が存在すること。必須カラムがすべて存在すること | `FileFormatError`。欠損カラム名・エンコーディング不一致を報告 |

---

## 6.9 トレースデータ設計（Perfetto Chrome Trace Format）

**関連要件**: REQ-Q-008

実験実行時にOrchestratorがTraceRecorderを通じて記録したトレースデータのストレージ形式を定義する。

### 6.9.1 保存先

```
{experiments_path}/{experiment_id}/
├── result.json          # 実験結果（ExperimentResult）
├── error.log            # エラーログ（ERROR以上）
└── trace.json           # ← トレースデータ（Perfetto形式）
```

### 6.9.2 Chrome Trace Format スキーマ

Perfetto / Chrome DevTools が解釈する JSON 形式。gridflow は **JSON Object Format**（`traceEvents` キー）を採用する。

```json
{
  "traceEvents": [ ... ],
  "displayTimeUnit": "ms",
  "metadata": { ... }
}
```

#### traceEvents 配列要素

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `name` | string | Yes | イベント名（スパン名） |
| `ph` | string | Yes | フェーズ。gridflow では `"X"`（Complete Event）を使用 |
| `ts` | number | Yes | 開始時刻（マイクロ秒、Unix epoch） |
| `dur` | number | Yes | 所要時間（マイクロ秒） |
| `pid` | number | Yes | プロセスID。gridflow では実験ごとに固定値 `1` |
| `tid` | number | Yes | スレッドID。スパンのネスト深度に対応（ルート=1, 子=2, ...） |
| `args` | object | No | メタデータ。`span_id`, `parent_span_id`, `status` + 任意属性 |

#### metadata オブジェクト

| フィールド | 型 | 説明 |
|---|---|---|
| `gridflow_version` | string | gridflow バージョン |
| `trace_id` | string | トレースID（32桁hex） |
| `experiment_id` | string | 実験ID |
| `format` | string | `"perfetto"` 固定 |
| `otel_compatible` | boolean | `true` — TraceSpan が OTel Span と 1:1 対応することを示す |

### 6.9.3 OTel 互換性の保証

将来の OTLP JSON エクスポートのために、以下の対応関係を維持する。

| gridflow TraceSpan | Perfetto 出力 | OTel Span（将来） |
|---|---|---|
| `trace_id` | `metadata.trace_id` | `traceId` |
| `span_id` | `args.span_id` | `spanId` |
| `parent_span_id` | `args.parent_span_id` | `parentSpanId` |
| `name` | `name` | `name` |
| `start_time_ns` | `ts` (μs変換) | `startTimeUnixNano` |
| `end_time_ns` | `ts + dur` (μs変換) | `endTimeUnixNano` |
| `status` | `args.status` | `status.code` |
| `attributes` | `args` (マージ) | `attributes` |

この対応表により、PerfettoExporter → OTelExporter の追加は TraceSpan の変換先を変えるだけで実現できる。
