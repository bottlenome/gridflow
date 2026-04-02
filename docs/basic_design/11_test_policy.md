# 第11章 テスト方針

本章では、gridflow の品質を担保するためのテストレベル定義、品質属性ごとのテスト方針、および CI/CD パイプライン設計を定義する。

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-01 | 初版作成 |

---

## 11.1 テストレベル定義

**関連要求:** REQ-C-004 (テストスタック: pytest, pytest-cov, mypy/pyright, ruff)

### テストレベル一覧

| レベル | テスト対象 | 実行速度 | 外部依存 | 実行頻度 | ツール |
|---|---|---|---|---|---|
| Unit | Entities, UseCases | < 1 秒/テスト | なし（モック使用） | PR ごと | pytest, pytest-cov |
| Integration | Connector × 実ツール | < 60 秒/テスト | Docker コンテナ | PR ごと（主要）, Merge 時（全量） | pytest, Docker |
| E2E | フルパイプライン（Scenario Pack → 結果出力） | < 5 分/テスト | Docker Compose 環境 | Merge 時 | pytest, docker compose |
| Reproducibility | 同一 Pack のマルチアーキテクチャ実行 | < 10 分/テスト | 複数アーキテクチャ環境 | Merge 時 | pytest, Docker Buildx |
| Performance | 実行時間・メモリ使用量 | ベースライン比較 | Docker 環境 | Release 時 | pytest-benchmark |

### テスト構成方針

- **Clean Architecture 準拠**: Unit テストは Entities / UseCases 層を対象とし、外部依存はすべてモック化
- **Connector テスト**: Integration テストで実際の OpenDSS / pandapower コンテナとの通信を検証
- **Docker 前提**: Integration 以上のテストは Docker 環境内で実行
- **カバレッジ目標**: Unit + Integration で行カバレッジ 80% 以上

---

## 11.2 品質属性テスト方針

各品質要求（REQ-Q-001 〜 REQ-Q-011）に対する検証方法を定義する。

| 要求 ID | 品質属性 | テストレベル | 検証方法 | 合格基準 |
|---|---|---|---|---|
| REQ-Q-001 | セットアップ容易性 | E2E | クリーン環境で `git clone` → `docker compose up` → sample 実行の所要時間を計測 | < 30 分、成功率 > 90% |
| REQ-Q-002 | TTFS | E2E | セットアップ完了後、独自シナリオ作成・実行までの所要時間を計測 | < 1 時間 |
| REQ-Q-003 | 再現性 | Reproducibility | 同一 Scenario Pack を 2+ マシン（amd64, arm64）で実行し、結果を比較 | 数値結果が許容誤差内で一致 |
| REQ-Q-004 | 拡張容易性 | Unit | サンプル L2 プラグイン（カスタム Connector）の実装 LOC を計測 | < 200 LOC で基本 Connector 実装可能 |
| REQ-Q-005 | 可視化即時性 | E2E | シミュレーション完了からグラフ出力までの所要時間を計測 | < 30 秒 |
| REQ-Q-006 | ドキュメント充実度 | Manual Review | 全公開 API のドキュメントカバレッジを確認 | 公開 API の 100% にドキュメント存在 |
| REQ-Q-007 | 後方互換性 | Integration | 旧バージョンの Scenario Pack / CDL を新バージョンで読み込み・実行 | Migrator 経由で 100% 移行成功 |
| REQ-Q-008 | 依存関係最小化 | Unit | `uv pip install gridflow` の依存パッケージ数を計測 | コア依存 < 15 パッケージ |
| REQ-Q-009 | エラーメッセージ品質 | Unit | 全エラーパスで構造化エラー（エラーコード + 原因 + 対処法）が出力されることを検証 | 全エラーに対処法が含まれる |
| REQ-Q-010 | オーバーヘッド | Performance | gridflow 経由の実行時間 vs ツール直接実行時間を比較 | オーバーヘッド < 10% |
| REQ-Q-011 | オフライン動作 | E2E | ネットワーク遮断状態でキャッシュ済み Pack の実行を検証 | オフラインで正常実行完了 |

---

## 11.3 CI/CD パイプライン設計

**関連要求:** REQ-C-004 (テストスタック), REQ-Q-001 (セットアップ容易性)

### パイプライン構成

GitHub Actions を使用し、3 段階のパイプラインを構成する。

#### PR パイプライン（Pull Request 作成・更新時）

```
PR Created/Updated
  ├─ Lint: ruff check + ruff format --check
  ├─ Type Check: mypy + pyright
  └─ Unit Test: pytest tests/unit/ --cov --cov-fail-under=80
```

- **実行時間目標:** < 3 分
- **必須パス:** マージの前提条件

#### Merge パイプライン（main ブランチへのマージ時）

```
Merge to main
  ├─ Unit Test: pytest tests/unit/
  ├─ Integration Test: pytest tests/integration/ (Docker 環境)
  ├─ E2E Test: pytest tests/e2e/ (docker compose 環境)
  ├─ Reproducibility Test: マルチアーキテクチャ実行比較
  └─ Docker Buildx: linux/amd64, linux/arm64 イメージビルド
```

- **実行時間目標:** < 20 分
- **失敗時:** main ブランチへのマージをブロック（branch protection）

#### Release パイプライン（タグ作成時）

```
Tag v*.*.* Created
  ├─ 全テストスイート実行
  ├─ Performance Test: pytest-benchmark によるベースライン比較
  ├─ Package Build: uv build (wheel + sdist)
  ├─ PyPI Publish: uv publish
  └─ Docker Image Publish: ghcr.io/gridflow/gridflow:<tag>
```

- **実行時間目標:** < 30 分
- **成果物:** PyPI パッケージ（uv publish）+ Docker イメージ（マルチアーキテクチャ）

### テスト環境マトリクス

| 環境 | Python | OS | Docker | 用途 |
|---|---|---|---|---|
| CI Primary | 3.11 | Ubuntu 22.04 | Docker-in-Docker | 全テスト |
| CI Secondary | 3.12 | Ubuntu 22.04 | Docker-in-Docker | 互換性確認 |
| CI Multi-arch | 3.11 | Ubuntu 22.04 | Buildx (QEMU) | arm64 再現性テスト |
