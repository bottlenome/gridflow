# 第9章 設定管理設計

本章では、gridflow の全設定項目、設定の優先順位ルール、デフォルト値とバリデーション、および Docker Compose 設定テンプレートを定義する。基本設計書 第9章（セキュリティ設計）のクレデンシャル管理方針、および第2章（システム方式設計）の Docker Compose 構成を詳細化する。

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-03 | 初版作成 |

## 関連要件

| 要件 ID | 関連セクション | 内容 |
|---|---|---|
| REQ-C-002 | 9.1, 9.4 | Docker 環境（ローカル Docker Compose） |
| REQ-C-005 | 9.1 | OSS 公開（イメージダイジェストピン留め） |
| REQ-Q-001 | 9.3 | 導入容易性（デフォルト値で即時動作） |
| REQ-Q-008 | 9.1 | 可観測性（ログ設定） |
| REQ-Q-011 | 9.1 | 論文生産性（出力フォーマット設定） |
| DD-CFG-001 | 9.1 | 設定項目一覧 |
| DD-CFG-002 | 9.2 | 優先順位ルール |
| DD-CFG-003 | 9.3 | バリデーション定義 |
| DD-CFG-004 | 9.4 | Docker Compose 設定テンプレート |

---

## 9.1 設定項目一覧

gridflow の全設定項目を以下に定義する。各項目は環境変数、設定ファイル（YAML）キー、CLI 引数の 3 つの経路で指定可能である。

### DD-CFG-001: 設定項目マスター表

| # | 項目名 | 環境変数 | 設定ファイルキー | CLI 引数 | 型 | デフォルト値 | 説明 |
|---|---|---|---|---|---|---|---|
| 1 | ログレベル | `GRIDFLOW_LOG_LEVEL` | `log.level` | `--log-level` | `enum(DEBUG,INFO,WARNING,ERROR)` | `INFO` | structlog 出力レベル |
| 2 | ログフォーマット | `GRIDFLOW_LOG_FORMAT` | `log.format` | `--log-format` | `enum(json,console)` | `console` | ログ出力形式 |
| 3 | ログ出力先 | `GRIDFLOW_LOG_FILE` | `log.file` | `--log-file` | `Optional[str]` | `None`（stderr） | ログファイルパス |
| 4 | データディレクトリ | `GRIDFLOW_DATA_DIR` | `paths.data_dir` | `--data-dir` | `Path` | `./data` | CDL データ保存ディレクトリ |
| 5 | Scenario Pack ディレクトリ | `GRIDFLOW_PACK_DIR` | `paths.pack_dir` | `--pack-dir` | `Path` | `./scenario-packs` | Scenario Pack 格納ディレクトリ |
| 6 | 出力ディレクトリ | `GRIDFLOW_OUTPUT_DIR` | `paths.output_dir` | `--output-dir` | `Path` | `./output` | シミュレーション結果出力先 |
| 7 | Docker ネットワーク名 | `GRIDFLOW_DOCKER_NETWORK` | `docker.network` | `--docker-network` | `str` | `gridflow-net` | Docker ブリッジネットワーク名 |
| 8 | Docker Compose プロジェクト名 | `GRIDFLOW_COMPOSE_PROJECT` | `docker.compose_project` | `--compose-project` | `str` | `gridflow` | Docker Compose プロジェクト名 |
| 9 | コンテナタイムアウト | `GRIDFLOW_CONTAINER_TIMEOUT` | `docker.container_timeout` | `--container-timeout` | `int`（秒） | `300` | Connector コンテナの起動・停止タイムアウト |
| 10 | 並列コンテナ数上限 | `GRIDFLOW_MAX_PARALLEL` | `docker.max_parallel` | `--max-parallel` | `int` | `4` | 同時実行コンテナ数の上限 |
| 11 | 共有ボリューム名 | `GRIDFLOW_SHARED_VOLUME` | `docker.shared_volume` | `--shared-volume` | `str` | `shared-data` | Docker 共有ボリューム名 |
| 12 | デフォルト出力フォーマット | `GRIDFLOW_OUTPUT_FORMAT` | `output.format` | `--format` | `enum(table,json,csv,yaml)` | `table` | CLI 出力のデフォルトフォーマット |
| 13 | カラー出力有効 | `GRIDFLOW_COLOR` | `output.color` | `--color / --no-color` | `bool` | `true` | ターミナルカラー出力の有効/無効 |
| 14 | Benchmark 許容誤差 | `GRIDFLOW_BENCHMARK_TOLERANCE` | `benchmark.tolerance` | `--tolerance` | `float` | `0.01` | Benchmark メトリクスの許容誤差（再現性検証用） |
| 15 | Benchmark レポート形式 | `GRIDFLOW_BENCHMARK_REPORT` | `benchmark.report_format` | `--report-format` | `enum(html,json,csv)` | `html` | Benchmark レポートの出力形式 |
| 16 | OpenDSS Connector イメージ | `GRIDFLOW_OPENDSS_IMAGE` | `connectors.opendss.image` | — | `str` | `gridflow/opendss-connector:latest` | OpenDSS Connector Docker イメージ |
| 17 | pandapower Connector イメージ | `GRIDFLOW_PANDAPOWER_IMAGE` | `connectors.pandapower.image` | — | `str` | `gridflow/pandapower-connector:latest` | pandapower Connector Docker イメージ |
| 18 | HELICS Connector イメージ | `GRIDFLOW_HELICS_IMAGE` | `connectors.helics.image` | — | `str` | `gridflow/helics-connector:latest` | HELICS Connector Docker イメージ |
| 19 | Grid2Op Connector イメージ | `GRIDFLOW_GRID2OP_IMAGE` | `connectors.grid2op.image` | — | `str` | `gridflow/grid2op-connector:latest` | Grid2Op Connector Docker イメージ |
| 20 | Connector ヘルスチェック間隔 | `GRIDFLOW_HEALTH_INTERVAL` | `connectors.health_check_interval` | `--health-interval` | `int`（秒） | `10` | Connector ヘルスチェックのポーリング間隔 |
| 21 | Connector リトライ回数 | `GRIDFLOW_RETRY_COUNT` | `connectors.retry_count` | `--retry-count` | `int` | `3` | Connector 通信失敗時のリトライ回数 |
| 22 | Connector リトライ間隔 | `GRIDFLOW_RETRY_DELAY` | `connectors.retry_delay` | `--retry-delay` | `float`（秒） | `1.0` | リトライ間のベース待機時間（指数バックオフ） |
| 23 | CDL スキーマバージョン | `GRIDFLOW_CDL_VERSION` | `cdl.schema_version` | — | `str` | `1.0` | 使用する CDL スキーマバージョン |
| 24 | CDL エクスポート形式 | `GRIDFLOW_CDL_EXPORT` | `cdl.export_format` | `--cdl-export` | `enum(csv,json,parquet)` | `csv` | CDL データのエクスポート形式 |
| 25 | Plugin ディレクトリ | `GRIDFLOW_PLUGIN_DIR` | `paths.plugin_dir` | `--plugin-dir` | `Path` | `~/.gridflow/plugins` | Plugin 検索ディレクトリ |

### 設定ファイルの配置場所

| スコープ | パス | 用途 |
|---|---|---|
| プロジェクト設定 | `<project_root>/gridflow.yaml` | プロジェクト固有設定 |
| ユーザー設定 | `~/.gridflow/config.yaml` | ユーザーグローバル設定 |
| デフォルト設定 | パッケージ内蔵 `defaults.yaml` | 出荷時デフォルト値 |

### 設定ファイル構造例

```yaml
# gridflow.yaml（プロジェクト設定の例）
log:
  level: DEBUG
  format: json
  file: ./logs/gridflow.log

paths:
  data_dir: ./data
  pack_dir: ./scenario-packs
  output_dir: ./output
  plugin_dir: ~/.gridflow/plugins

docker:
  network: gridflow-net
  compose_project: gridflow
  container_timeout: 300
  max_parallel: 4
  shared_volume: shared-data

output:
  format: table
  color: true

benchmark:
  tolerance: 0.01
  report_format: html

connectors:
  opendss:
    image: gridflow/opendss-connector:latest
  pandapower:
    image: gridflow/pandapower-connector:latest
  helics:
    image: gridflow/helics-connector:latest
  grid2op:
    image: gridflow/grid2op-connector:latest
  health_check_interval: 10
  retry_count: 3
  retry_delay: 1.0

cdl:
  schema_version: "1.0"
  export_format: csv
```

---

## 9.2 設定の優先順位ルール

### DD-CFG-002: 優先順位（高い順）

gridflow は以下の優先順位で設定値を解決する。番号が小さいほど優先度が高い。

```
1. CLI 引数           （最優先：明示的なユーザー指示）
   ↓
2. 環境変数           （デプロイ・CI 環境での上書き）
   ↓
3. プロジェクト設定   （<project_root>/gridflow.yaml）
   ↓
4. ユーザー設定       （~/.gridflow/config.yaml）
   ↓
5. デフォルト値       （パッケージ内蔵 defaults.yaml）
```

### 解決アルゴリズム

```python
def resolve_config(key: str, cli_args: dict, env: dict, project_cfg: dict, user_cfg: dict, defaults: dict) -> Any:
    """設定値を優先順位に従い解決する。

    Args:
        key: ドット区切りの設定キー（例: "log.level"）
        cli_args: CLI 引数から解析された設定値
        env: 環境変数から変換された設定値
        project_cfg: プロジェクト設定ファイルの値
        user_cfg: ユーザー設定ファイルの値
        defaults: デフォルト設定の値

    Returns:
        解決された設定値
    """
    sources = [cli_args, env, project_cfg, user_cfg, defaults]
    for source in sources:
        value = _get_nested(source, key)
        if value is not _UNSET:
            return value
    raise ConfigKeyError(key)
```

### 環境変数の命名規則

| 設定ファイルキー | 環境変数 | 変換ルール |
|---|---|---|
| `log.level` | `GRIDFLOW_LOG_LEVEL` | 接頭辞 `GRIDFLOW_` + ドット `.` をアンダースコア `_` に置換 + 大文字化 |
| `docker.max_parallel` | `GRIDFLOW_DOCKER_MAX_PARALLEL` | 同上 |
| `connectors.opendss.image` | `GRIDFLOW_OPENDSS_IMAGE` | ネスト 2 階層目からは短縮名を使用 |

### 設定値のマージ動作

| ケース | 動作 | 例 |
|---|---|---|
| スカラー値 | 上位ソースの値で完全上書き | `log.level: DEBUG` が `INFO` を上書き |
| リスト値 | 上位ソースの値で完全置換（マージしない） | `connectors` リスト全体を置換 |
| マップ値 | キー単位で再帰マージ | `docker.max_parallel` のみ上書き、他の `docker.*` は下位ソースを維持 |

---

## 9.3 デフォルト値・バリデーション

### DD-CFG-003: バリデーションルール

全設定項目に対し、型チェック・範囲チェック・依存チェックの 3 段階バリデーションを適用する。

#### バリデーション定義表

| # | 設定キー | 型制約 | 範囲・値制約 | 依存制約 | エラーコード |
|---|---|---|---|---|---|
| 1 | `log.level` | `str` | `{DEBUG, INFO, WARNING, ERROR}` | — | `E-CFG-001` |
| 2 | `log.format` | `str` | `{json, console}` | — | `E-CFG-002` |
| 3 | `log.file` | `Optional[str]` | 有効なファイルパス（親ディレクトリが存在） | — | `E-CFG-003` |
| 4 | `paths.data_dir` | `str` | 有効なディレクトリパス | 書き込み権限あり | `E-CFG-004` |
| 5 | `paths.pack_dir` | `str` | 有効なディレクトリパス | 読み取り権限あり | `E-CFG-005` |
| 6 | `paths.output_dir` | `str` | 有効なディレクトリパス | 書き込み権限あり | `E-CFG-006` |
| 7 | `docker.network` | `str` | 正規表現 `^[a-zA-Z0-9][a-zA-Z0-9_.-]+$` | — | `E-CFG-007` |
| 8 | `docker.compose_project` | `str` | 正規表現 `^[a-z][a-z0-9_-]+$` | — | `E-CFG-008` |
| 9 | `docker.container_timeout` | `int` | `10 <= x <= 3600` | — | `E-CFG-009` |
| 10 | `docker.max_parallel` | `int` | `1 <= x <= 16` | — | `E-CFG-010` |
| 11 | `docker.shared_volume` | `str` | 正規表現 `^[a-zA-Z0-9][a-zA-Z0-9_.-]+$` | — | `E-CFG-011` |
| 12 | `output.format` | `str` | `{table, json, csv, yaml}` | — | `E-CFG-012` |
| 13 | `output.color` | `bool` | `{true, false}` | — | `E-CFG-013` |
| 14 | `benchmark.tolerance` | `float` | `0.0 < x <= 1.0` | — | `E-CFG-014` |
| 15 | `benchmark.report_format` | `str` | `{html, json, csv}` | — | `E-CFG-015` |
| 16 | `connectors.*.image` | `str` | 有効な Docker イメージ参照 | Docker デーモンがアクセス可能 | `E-CFG-016` |
| 17 | `connectors.health_check_interval` | `int` | `1 <= x <= 300` | — | `E-CFG-017` |
| 18 | `connectors.retry_count` | `int` | `0 <= x <= 10` | — | `E-CFG-018` |
| 19 | `connectors.retry_delay` | `float` | `0.1 <= x <= 60.0` | — | `E-CFG-019` |
| 20 | `cdl.schema_version` | `str` | Semantic Versioning 形式 | サポート範囲内 | `E-CFG-020` |
| 21 | `cdl.export_format` | `str` | `{csv, json, parquet}` | — | `E-CFG-021` |
| 22 | `paths.plugin_dir` | `str` | 有効なディレクトリパス | 読み取り権限あり | `E-CFG-022` |

### バリデーション実行タイミング

```
1. 設定ロード時（起動直後）
   └─ 全項目の型チェック + 範囲チェック
      ├─ 成功 → 次ステップへ
      └─ 失敗 → E-CFG-xxx エラー出力、起動中止

2. 依存チェック（Docker 接続確認後）
   └─ Docker 関連設定の実行時バリデーション
      ├─ ネットワーク存在確認
      ├─ イメージ取得可能性確認
      └─ ボリュームアクセス権確認

3. gridflow doctor コマンド
   └─ 全バリデーションを明示的に実行し、結果をレポート
```

### エラーメッセージ形式

バリデーション失敗時は構造化エラーメッセージを出力する（`REQ-Q-009`）。

```
Error [E-CFG-010]: Invalid configuration value
  Key:      docker.max_parallel
  Value:    32
  Expected: integer in range [1, 16]
  Source:   gridflow.yaml (project config)
  Fix:      Set docker.max_parallel to a value between 1 and 16.
```

---

## 9.4 Docker Compose 設定テンプレート

### DD-CFG-004: Docker Compose テンプレート

以下は gridflow のデフォルト Docker Compose 設定テンプレートである（`REQ-C-002`）。

```yaml
# docker-compose.yml
# gridflow Docker Compose 設定テンプレート
# 生成元: DD-CFG-004

services:
  # ===== gridflow コアコンテナ =====
  gridflow-core:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime              # マルチステージビルドの runtime ステージ
    image: gridflow/gridflow-core:latest
    container_name: gridflow-core
    ports:
      - "${GRIDFLOW_NOTEBOOK_PORT:-8888}:8888"    # Jupyter Notebook Bridge
      - "${GRIDFLOW_WEBUI_PORT:-8080}:8080"       # Web UI（将来拡張）
    volumes:
      - shared-data:/data                          # CDL 共有データ
      - ./scenario-packs:/scenario-packs:ro        # Scenario Pack（読み取り専用）
      - ./output:/output                           # シミュレーション結果出力
      - ./logs:/logs                               # ログ出力
    environment:
      - GRIDFLOW_LOG_LEVEL=${GRIDFLOW_LOG_LEVEL:-INFO}
      - GRIDFLOW_LOG_FORMAT=${GRIDFLOW_LOG_FORMAT:-json}
      - GRIDFLOW_OUTPUT_FORMAT=${GRIDFLOW_OUTPUT_FORMAT:-table}
      - GRIDFLOW_MAX_PARALLEL=${GRIDFLOW_MAX_PARALLEL:-4}
    networks:
      - gridflow-net
    user: "1000:1000"                              # non-root 実行（REQ セキュリティ）
    read_only: true                                # ルートファイルシステム読み取り専用
    tmpfs:
      - /tmp:size=512M                             # 一時ファイル用 tmpfs
    healthcheck:
      test: ["CMD", "python", "-m", "gridflow", "health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    restart: unless-stopped

  # ===== OpenDSS Connector =====
  opendss-connector:
    build:
      context: ./connectors/opendss
      dockerfile: Dockerfile
    image: gridflow/opendss-connector:latest
    container_name: gridflow-opendss
    volumes:
      - shared-data:/data                          # CDL 共有データ
    environment:
      - GRIDFLOW_LOG_LEVEL=${GRIDFLOW_LOG_LEVEL:-INFO}
      - CONNECTOR_PORT=5001
    networks:
      - gridflow-net
    user: "1000:1000"
    read_only: true
    tmpfs:
      - /tmp:size=256M
    depends_on:
      gridflow-core:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:5001/health')"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s
    restart: unless-stopped

  # ===== HELICS Connector（P1 フェーズ） =====
  helics-connector:
    build:
      context: ./connectors/helics
      dockerfile: Dockerfile
    image: gridflow/helics-connector:latest
    container_name: gridflow-helics
    volumes:
      - shared-data:/data
    environment:
      - GRIDFLOW_LOG_LEVEL=${GRIDFLOW_LOG_LEVEL:-INFO}
      - CONNECTOR_PORT=5002
      - HELICS_BROKER_PORT=23404
    networks:
      - gridflow-net
    user: "1000:1000"
    read_only: true
    tmpfs:
      - /tmp:size=256M
    depends_on:
      gridflow-core:
        condition: service_healthy
    profiles:
      - helics                                     # 明示的に有効化が必要
    restart: unless-stopped

  # ===== pandapower Connector（P2 フェーズ） =====
  pandapower-connector:
    build:
      context: ./connectors/pandapower
      dockerfile: Dockerfile
    image: gridflow/pandapower-connector:latest
    container_name: gridflow-pandapower
    volumes:
      - shared-data:/data
    environment:
      - GRIDFLOW_LOG_LEVEL=${GRIDFLOW_LOG_LEVEL:-INFO}
      - CONNECTOR_PORT=5003
    networks:
      - gridflow-net
    user: "1000:1000"
    read_only: true
    tmpfs:
      - /tmp:size=256M
    depends_on:
      gridflow-core:
        condition: service_healthy
    profiles:
      - pandapower                                 # 明示的に有効化が必要
    restart: unless-stopped

  # ===== Grid2Op Connector（P2 フェーズ） =====
  grid2op-connector:
    build:
      context: ./connectors/grid2op
      dockerfile: Dockerfile
    image: gridflow/grid2op-connector:latest
    container_name: gridflow-grid2op
    volumes:
      - shared-data:/data
    environment:
      - GRIDFLOW_LOG_LEVEL=${GRIDFLOW_LOG_LEVEL:-INFO}
      - CONNECTOR_PORT=5004
    networks:
      - gridflow-net
    user: "1000:1000"
    read_only: true
    tmpfs:
      - /tmp:size=256M
    depends_on:
      gridflow-core:
        condition: service_healthy
    profiles:
      - grid2op                                    # 明示的に有効化が必要
    restart: unless-stopped

# ===== ボリューム定義 =====
volumes:
  shared-data:
    driver: local
    name: gridflow-shared-data

# ===== ネットワーク定義 =====
networks:
  gridflow-net:
    driver: bridge
    name: gridflow-net
    ipam:
      config:
        - subnet: 172.20.0.0/24
```

### 環境別オーバーライドファイル

#### 開発環境用（docker-compose.override.yml）

```yaml
# docker-compose.override.yml（開発環境）
services:
  gridflow-core:
    build:
      target: development                          # 開発用ステージ（ホットリロード対応）
    volumes:
      - .:/app:ro                                  # ソースコードのバインドマウント
    environment:
      - GRIDFLOW_LOG_LEVEL=DEBUG
      - GRIDFLOW_LOG_FORMAT=console
    read_only: false                               # 開発時はファイルシステム書き込み許可

  opendss-connector:
    environment:
      - GRIDFLOW_LOG_LEVEL=DEBUG
```

#### CI 環境用（docker-compose.ci.yml）

```yaml
# docker-compose.ci.yml（CI 環境）
services:
  gridflow-core:
    environment:
      - GRIDFLOW_LOG_LEVEL=WARNING
      - GRIDFLOW_LOG_FORMAT=json
      - GRIDFLOW_MAX_PARALLEL=2                    # CI ランナーのリソース制約
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4G

  opendss-connector:
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 2G
```

### Docker Secrets によるクレデンシャル管理

基本設計書 9.3 に従い、外部サービスへの認証情報は Docker Secrets で管理する。

```yaml
# docker-compose.secrets.yml（クレデンシャル拡張）
services:
  gridflow-core:
    secrets:
      - connector_credentials

secrets:
  connector_credentials:
    file: ./secrets/connector_credentials.json     # ローカル環境
    # external: true                               # Docker Swarm 環境（将来）
```

### 起動コマンド例

```bash
# 基本起動（gridflow-core + opendss-connector のみ）
docker compose up -d

# HELICS Connector も含めて起動
docker compose --profile helics up -d

# 全 Connector を起動
docker compose --profile helics --profile pandapower --profile grid2op up -d

# CI 環境での起動
docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d

# 開発環境での起動
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

---

## トレーサビリティ

| 詳細設計 ID | 内容 | 基本設計参照 |
|---|---|---|
| DD-CFG-001 | 設定項目マスター表 | 基本設計 2.4, 9.3 |
| DD-CFG-002 | 優先順位ルール | 基本設計 2.4 |
| DD-CFG-003 | バリデーション定義 | 基本設計 9.1, 9.3 |
| DD-CFG-004 | Docker Compose テンプレート | 基本設計 2.1, 2.3, 9.2, 10.1 |
