# MVP 研究シナリオ: IEEE 13 ノード × DER 浸透率 sweep

## 更新履歴

| 版 | 日付 | 変更内容 | 著者 |
|---|---|---|---|
| 0.1 | 2026-04-11 | 初版作成。research_landscape.md §3.1 の C-1 / C-3 / C-7 / C-10 を end-to-end で実証するシナリオとして定義 | Claude |
| 0.2 | 2026-04-11 | 実装成果物を `test/mvp_try1/` 配下に隔離する方針に変更。既存の `examples/` / `tools/` は触らない。§4.1 / §5 の保存先パスを更新 | Claude |
| 0.3 | 2026-04-11 | §5 実装作業完了 + §6 DoD 全項目達成。実走 wall time 20.87 秒 (目標 < 600 秒)。3 runs bit 一致、voltage_deviation 40.5% 減少を確認。実走詳細は `test/mvp_try1/report.md` 参照 | Claude |

---

## 0. 本書の位置付け

gridflow が研究ツールとして**新しい効果を出せているか**を、実装された CLI を
端から端まで走らせて実証するためのシナリオを定義する。

- **背景課題**: [research_landscape.md §2](./research_landscape.md) C-1〜C-10
- **対応する MVP ユーザーストーリー**: [development_plan.md §2.2](./development_plan.md) US-1〜US-6
- **達成判定 KPI**: [development_plan.md §2.6](./development_plan.md) および [basic_design/01_requirements.md](./basic_design/01_requirements.md) REQ-Q-xxx

本書は「何を実験するか」を決めるだけで、実装の詳細は各成果物 (pack.yaml /
スクリプト / 検証レポート) に委ねる。

---

## 1. ゴール

> IEEE 13 ノード配電フィーダー上で **DER (分散電源) の浸透率を 5 段階で振り**、
> 電圧逸脱率の変化を gridflow の標準ワークフローで自動集計し、
> **研究者が半日〜1 日かけていた作業を < 10 分で完了**できることを実証する。
>
> さらに、**同一 seed / 同一 pack / 同一 Docker image で 3 回実行した結果が
> 完全一致する**ことで、電力系研究の再現性危機に対する直接的な解決を示す。

---

## 2. 対応する課題 (research_landscape.md §2)

| 課題 | 本シナリオでの実証方法 |
|---|---|
| **C-1 再現性危機** | 5 パターン × 3 回実行 = 15 実験で、各パターン内 3 回が完全一致することを自動検証 |
| **C-3 データプロビナンス** | 全実験の JSON 出力に `scenario_pack_id` が埋まる。事後に pack を引けば入力条件が完全再現される |
| **C-4 パラメータ sweep 属人性** | `der_penetration_pct` だけが異なる 5 本の pack.yaml で sweep を表現 (自動化手段は Phase 2 だが、手動でも CLI 経路がスクリプト化可能であることを示す) |
| **C-7 電力系 experiment tracker 不在** | `gridflow scenario list` / `gridflow results` / `gridflow benchmark` が電力系固有の型 (Topology / NodeResult / voltage_deviation) を直接扱う |
| **C-10 指標定義ばらつき** | `voltage_deviation` metric の計算式を pack.yaml で固定、全 5 パターンで同一計算式を使用 |

---

## 3. 対応する MVP ユーザーストーリー (development_plan.md §2.2)

| # | US | 本シナリオでの確認方法 |
|---|---|---|
| US-1 | Scenario Pack 作成・登録 | 5 本の pack.yaml を `gridflow scenario register` で登録 |
| US-2 | OpenDSS シミュレーション実行 | 5 パターン × 3 回の 15 実験を `gridflow run` で回す |
| US-3 | CDL 形式で結果参照 | `gridflow results <exp_id> --format json` で全 15 実験を JSON 抽出 |
| US-4 | 2 実験の定量比較 | `gridflow benchmark --baseline der_0 --candidate der_100` などで各ペア比較 |
| US-5 | 3 回実行で結果一致 | パターン内 3 回の voltages が bit レベル一致 (numpy allclose(atol=0)) |
| US-6 | 30 分以内セットアップ | 別環境で README に従って再構築し計測 (別途) |

---

## 4. シナリオ詳細

### 4.1 入力: 5 本の Scenario Pack

**隔離原則**: 本 MVP シナリオの成果物は全て `test/mvp_try1/` 配下に配置する。
既存の `examples/` / `tools/` / `src/` ディレクトリには一切触らない。
`test/` (単数形) は `tests/` (pytest root) とは別ディレクトリで、pytest の
testpaths 設定外なので自動検出されない。失敗や試行錯誤があっても本体プロジェクト
に影響しない scratch 領域として機能する。

```
test/mvp_try1/
├── README.md                       # 目的、使い方、再現手順
├── packs/
│   ├── ieee13_der_base.dss         # IEEE 13 共通ベース (load + line, Solve なし)
│   ├── der_00.dss                  # base + PV 0%, Solve
│   ├── der_25.dss                  # base + PV 25%, Solve
│   ├── der_50.dss
│   ├── der_75.dss
│   ├── der_100.dss
│   ├── der_00.yaml                 # Pack: DER 0% (baseline)
│   ├── der_25.yaml                 # Pack: DER 25%
│   ├── der_50.yaml                 # Pack: DER 50%
│   ├── der_75.yaml                 # Pack: DER 75%
│   └── der_100.yaml                # Pack: DER 100%
├── tools/
│   ├── run_der_sweep.sh            # 5 pack × 3 回実行ラッパー
│   ├── verify_reproducibility.py   # 再現性自動検証
│   └── plot_hosting_capacity.py    # matplotlib 可視化
├── results/                        # 実行時生成物 (生 JSON、図、レポート)
│   └── .gitkeep
└── report.md                       # 実走結果レポート (実装完了後追記)
```

各 pack.yaml の差分は `parameters.der_penetration_pct` と
`network.master_file` のみ。それ以外 (seed / connector / voltage_base_kv 等) は
全て共通。これによって「pack 属性の変更だけで sweep が成立する」ことを示す。

### 4.2 DER 浸透率の定義

**浸透率 = 系統総負荷 [kW] に対する PV 発電容量 [kW] の比率**

- 0% : PV なし (baseline)
- 25%: 総負荷の 25% 相当を PV で供給
- 50%: 同 50%
- 75%: 同 75%
- 100%: 同 100% (昼間ピークで負荷全量を PV でまかなえる水準)

IEEE 13 のおおまかな総負荷 ≈ 3.5 MW を基準に、PV は各 node に均等分散配置する
(手法の複雑化を避けるため均等分散とし、最適配置は Phase 2 以降の課題とする)。

### 4.3 指標: voltage_deviation と voltage_violation_ratio

既存実装の `voltage_deviation` metric (RMSE ベース) に加え、本シナリオで
verify 対象とする追加指標:

- **voltage_violation_ratio**: `0.95 <= V <= 1.05` を外れた bus の比率
  - ANSI C84.1 Range A に準拠 (C-10 で問題提起されていた曖昧性を解消する定義)
  - 計算式は pack.yaml のコメントで明示

voltage_violation_ratio が本 MVP で未実装なら、Phase 1 MVP では既存の
`voltage_deviation` だけを使い、violation_ratio は tools/ 配下の集計スクリプトで
外出しする方針とする (gridflow core の拡張は最小化)。

### 4.4 実行手順

全て `test/mvp_try1/` 配下で完結する:

```bash
cd test/mvp_try1

# 1. 5 本の pack を登録
for p in der_00 der_25 der_50 der_75 der_100; do
  gridflow scenario register packs/${p}.yaml
done

# 2. 各 pack を 3 回実行 (計 15 experiment)
for p in der_00 der_25 der_50 der_75 der_100; do
  for run in 1 2 3; do
    gridflow run ${p}@1.0.0 --steps 1 --seed 42 --format json \
      > results/${p}_run${run}.json
  done
done

# 3. 再現性検証: 各 pack 内の 3 回実行を numpy で比較
python tools/verify_reproducibility.py results/der_*_run*.json

# 4. benchmark でペア比較 (0% vs 100%)
gridflow benchmark --baseline <exp_id_der_00> --candidate <exp_id_der_100> \
  --format json > results/benchmark_00_vs_100.json

# 5. 集計・可視化
python tools/plot_hosting_capacity.py results/der_*_run1.json \
  -o results/hosting_capacity.png

# すべてをまとめた一発ラッパー
./tools/run_der_sweep.sh
```

### 4.5 期待される成果物

| 成果物 | 内容 | 保存先 |
|---|---|---|
| 15 実験の JSON | 各 experiment の ExperimentResult | `test/mvp_try1/results/der_*_run*.json` |
| 再現性レポート | 各 pack 内 3 回比較、全 5 本で完全一致を確認 | stdout (exit code で自動判定) |
| benchmark report | 各 pack ペアの voltage_deviation 差分 | `test/mvp_try1/results/benchmark_*.json` |
| **可視化図**: DER 浸透率 vs voltage_deviation の曲線 | matplotlib 図 | `test/mvp_try1/results/hosting_capacity.png` |
| 所要時間計測 | `time` コマンドで手順 2 の wall time | stderr / report.md |

---

## 5. 実装作業 (MVP scenario 実現に必要な追加物)

本シナリオを実行可能にするために必要な追加実装。**core (`src/gridflow/`) は
触らない方針**、既存の `examples/` / `tools/` / `tests/` も触らない。
すべて `test/mvp_try1/` 配下で完結する:

| # | 作業 | 保存先 | 見積 |
|---|---|---|---|
| 1 | IEEE 13 共通ベース DSS (Solve なし) | `test/mvp_try1/packs/ieee13_der_base.dss` | 既存の examples/ieee13 から派生、30 分 |
| 2 | PV 追加版 × 5 (base を Redirect) | `test/mvp_try1/packs/der_{00,25,50,75,100}.dss` | 1 時間 |
| 3 | pack.yaml × 5 (差分最小化) | `test/mvp_try1/packs/der_*.yaml` | 30 分 |
| 4 | 再現性検証スクリプト (numpy.array_equal) | `test/mvp_try1/tools/verify_reproducibility.py` | 1 時間 |
| 5 | 可視化スクリプト (matplotlib) | `test/mvp_try1/tools/plot_hosting_capacity.py` | 1 時間 |
| 6 | シナリオ実行ラッパー | `test/mvp_try1/tools/run_der_sweep.sh` | 30 分 |
| 7 | 実行レポート | `test/mvp_try1/report.md` (実走後に追記) | 1 時間 |
| 8 | README (目的・再現手順) | `test/mvp_try1/README.md` | 30 分 |
| **合計** | | | **約半日〜1 日** |

matplotlib / numpy は `test/mvp_try1/tools/` 内でのみ使用。**pyproject.toml の
依存は変更しない** (numpy は既に入っている、matplotlib は実走時に pip install)。
core は非依存のまま保つ。

---

## 6. 受入条件 (Definition of Done)

本シナリオが「完了」と判定できる条件:

- [ ] 5 本の pack が `gridflow scenario list` で確認できる
- [ ] 15 実験すべてが exit code 0 で完了する (OpenDSS 収束成功)
- [ ] 各 pack 内の 3 回実行結果 (voltages tuple) が完全一致する
  - 判定: `numpy.array_equal` で bit 一致 (`allclose(atol=0)` ではなく `array_equal`)
  - 一致しない場合は `verify_reproducibility.py` が exit 1 で失敗
- [ ] `gridflow benchmark --baseline der_00 --candidate der_100` が voltage_deviation
      を返す (値の物理的妥当性: `der_100` のほうが `der_00` より小さくなる傾向)
- [ ] `tools/plot_hosting_capacity.py` が `/tmp/hosting_capacity.png` を生成する
  - 横軸 = DER 浸透率 [%], 縦軸 = voltage_deviation [pu]
- [ ] ステップ 1〜5 全体の wall time が **< 10 分** で完了する (手元環境基準)
- [ ] 本 docs が `docs/mvp_scenario_result.md` として実走結果つきで更新される

### 6.1 US カバレッジ

| US | 充足 | 未充足理由 |
|---|---|---|
| US-1 | ✅ 5 pack 登録 | - |
| US-2 | ✅ 15 run 実行 | - |
| US-3 | ✅ JSON 出力 | - |
| US-4 | ✅ benchmark | - |
| US-5 | ✅ 3 回一致 | - |
| US-6 | ⏭ 別途 | README smoke は別セッションで実施 |

---

## 7. 非目標 (Phase 2 以降に送る項目)

本 MVP シナリオでは**やらない**ことを明示する:

- **HCA 手法の本格実装**: streamlined / stochastic / iterative / optimization-based の
  4 流派を gridflow 内部に持つ (C-2 の完全解決)
- **`gridflow sweep` コマンド**: pack 差替えの自動化 (C-4 の完全解決)
- **voltage_violation_ratio metric の core 実装**: ANSI C84.1 準拠の閾値ベース指標
  (本 MVP では `voltage_deviation` で代替、violation_ratio は tools/ 外出し)
- **実データ時系列**: OPF データセット導入 (C-9)
- **PV 配置最適化**: 均等分散で固定
- **24 時間時系列シミュレーション**: 単 step 定常潮流に留める
- **REST container mode での sweep**: inprocess で実行 (container mode smoke は Unit 5 で
  別途検証済み)

これらは本シナリオが「研究価値の**最小実証**」であることを担保するために意図的に
除外する。C-2 / C-4 / C-9 への**完全解決**は Phase 2 の課題として
`development_plan.md` / `gridtwin_lab_plan.md` §3.2 に記録する。

---

## 8. 実施ステータス

| 段階 | 状態 | 実施日 |
|---|---|---|
| シナリオ定義 (本書) | ✅ 完了 | 2026-04-11 |
| 実装作業 (§5) | ✅ 完了 | 2026-04-11 |
| 実走・検証 (§6) | ✅ 完了 | 2026-04-11 |
| 結果レポート ([`test/mvp_try1/report.md`](../test/mvp_try1/report.md)) | ✅ 完了 | 2026-04-11 |

**達成サマリ**:
- 15 実験 (5 DER 浸透率 × 3 runs) 全成功
- 各 pack 内 3 runs が **bit レベル一致** (`numpy.array_equal`)
- voltage_deviation: 0.0545 → 0.0324 (DER 0% → 100%、**-40.5%**)
- DoD wall time 目標 < 600 秒 に対して **実測 20.87 秒** (約 30 倍高速)
