# 電力系研究ワークフロー領域: 先行研究と未解決課題

## 更新履歴

| 版 | 日付 | 変更内容 | 著者 |
|---|---|---|---|
| 0.1 | 2026-04-11 | 初版作成。先行ツール棚卸 (§1)、未解決課題 C-1〜C-10 (§2)、gridflow のスコープマッピング (§3) を整理 | Claude |

---

## 0. 本書の位置付け

gridflow が「研究ツールとして **従来手法に対して新しく提供する効果**」を論じるための
土台資料。`gridtwin_lab_plan.md` §1.2 が提示する pain point を、**2024〜2025 の公開
文献と関連 OSS の現状調査**で裏付け、MVP で実証すべき差分を絞り込むための外部
エビデンスをまとめる。

MVP 検証シナリオ本体は [mvp_scenario.md](./mvp_scenario.md) に別立てで定義する。
本書は「どの課題が存在するか」と「gridflow がどれに触れるか」を網羅し、シナリオは
そこから 1 本を選び出して具体的な実証手順を定義する責務分離とする。

---

## 1. 関連ツール棚卸 (2026-04 時点)

### 1.1 電力系シミュレータ (solver)

| ツール | 役割 | 特徴 | 出典 |
|---|---|---|---|
| OpenDSS | 配電系潮流 | 業界デファクト。CLI/COM/Python API あり。周辺運用基盤は別途必要 | [OpenDSSDirect.py](https://dss-extensions.org/OpenDSSDirect.py/) |
| pandapower | 潮流 / OPF | Python ベース、pandas 互換、テスト容易 | [arxiv:1709.06743](https://arxiv.org/pdf/1709.06743) |
| PyPSA | 最適化中心、系統スケール | CO2 制約・sector coupling に強い | [arxiv:1707.09913](https://arxiv.org/pdf/1707.09913) |
| GridLAB-D | 配電 agent ベース | CLI 中心、導入障壁が明示されている | [gridlabd.org](https://www.gridlabd.org/) |
| PSS/E, PSCAD, DIgSILENT PowerFactory | 商用 | GUI 中心、自動化困難 | [HCA review 2020](https://www.mdpi.com/1996-1073/13/11/2758) |

**共通特徴**: すべて「計算エンジン」に閉じており、**実験の管理・比較・再現保証**は
各ユーザ任せ。gridflow は solver を自作せず、これらを connector として包む。

### 1.2 Co-simulation framework

| ツール | 役割 | 特徴 | 出典 |
|---|---|---|---|
| HELICS | 多ドメイン co-simulation | NREL/PNNL 主導、broker/federation ベース、マルチスケール対応 | [HELICS IEEE Access 2024](https://faculty.sites.iastate.edu/tesfatsi/archive/tesfatsi/HELICSCoSimFramework.HardyEtAl.IEEEAccess2024.pdf) |
| Mosaik | co-simulation scheduler | OffIS 主導、ドメイン統合と scheduling | [Mosaik docs](https://mosaik.offis.de/) |

**限界**: HELICS は「message topology と broker topology の設計が属人的」と 2024 の
pitfalls 論文で明示されている ([Springer 2024](https://link.springer.com/chapter/10.1007/978-3-031-78806-2_11))。
導入は高度 user に限られる。

### 1.3 RL 環境・ベンチマーク

| ツール | 役割 | 特徴 | 出典 |
|---|---|---|---|
| Grid2Op | RL 用系統運用環境 | RTE France、L2RPN 競技の基盤 | [LF Energy Grid2Op](https://lfenergy.org/projects/grid2op/) |
| RL2Grid | RL 標準ベンチマーク | 2025 新規、Grid2Op の標準化不足を受けて登場 | [arxiv:2503.23101](https://arxiv.org/abs/2503.23101) |

### 1.4 汎用 experiment tracker (ML 分野)

| ツール | 分野 | 電力系への応用 | 出典 |
|---|---|---|---|
| MLflow | ML 実験管理 | ML 特化、電力系メタデータ非対応 | [MLflow docs](https://mlflow.org/) |
| Kedro / kedro-mlflow | pipeline + tracking | ML 特化、Kedro 本体が ML DAG 指向 | [kedro-mlflow](https://kedro-mlflow.readthedocs.io/) |
| DVC | data/model versioning | 電力系メタデータ非対応 | [dvc.org](https://dvc.org/) |

**重要な欠落**: 上記はいずれも **ML 特化**。電力系固有の Topology / TimeSeries /
Event / Metric を 1 級データ型として扱う experiment tracker は、公開 OSS では
現状存在しない (2026-04 調査時点)。

### 1.5 HCA (Hosting Capacity Analysis) ツール

| ツール | 手法 | 特徴 | 出典 |
|---|---|---|---|
| EPRI DRIVE | streamlined + stochastic + iterative のハイブリッド | 商用寄り、方法論自体が調整対象 | [ScienceDirect HCA challenges 2025](https://www.sciencedirect.com/science/article/pii/S0306261925020537) |
| IREC 調査 | 手法比較 | 「どの HCA 手法も十分ではない」と明言 | [IREC](https://irecusa.org/our-work/hosting-capacity-analysis/) |

### 1.6 Open data / FAIR

| 取り組み | 役割 | 電力系研究への影響 | 出典 |
|---|---|---|---|
| Open Power System Data | 時系列・地理データ公開 | データ側は進んだが、**それを使った実験が再現可能である保証は別問題** | [open-power-system-data.org](https://open-power-system-data.org/) |
| FAIR principles | データ基本原則 | Findable/Accessible/Interoperable/Reusable | [Open science in energy research, PMC 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11907185/) |

---

## 2. 先行研究で認定されている未解決課題

各課題に通し番号 **C-番号** を付与する。§3 の gridflow スコープマッピングと
[mvp_scenario.md](./mvp_scenario.md) §2 から参照する。

### C-1 再現性危機: エネルギー系モデリングの black-box 化

**症状**: エネルギー系モデリング論文は「black-box モデル + private data」で
再実行不能との批判が継続している。オープン化の努力はあるが、**実験単位 (pack)
での再現性は個々の研究者任せ**のまま。

**出典**:
- [Energy system modeling: Public transparency, scientific reproducibility, and open development (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2211467X17300949)
- [Open science in energy research (PMC 2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11907185/)
- [Improving energy research practices: transparency, reproducibility and quality (Buildings & Cities)](https://journal-buildingscities.org/articles/10.5334/bc.67)

### C-2 HCA 手法の標準化欠如

**症状**: Hosting Capacity Analysis (HCA) は streamlined / iterative / stochastic /
optimization-based の 4 流派があり、IREC は「**どの HCA 手法も十分ではない**」と
明言。論文間の定量比較が困難で、手法の優劣比較研究ですら成立しにくい。

**出典**:
- [Challenges and applications of hosting capacity analysis in DER-rich power systems (ScienceDirect 2025)](https://www.sciencedirect.com/science/article/pii/S0306261925020537)
- [A Review of the Tools and Methods for HCA (MDPI Energies 2020)](https://www.mdpi.com/1996-1073/13/11/2758)
- [DER Hosting capacity: definitions, attributes, use-cases and challenges (arxiv 2501.15339, 2025)](https://arxiv.org/html/2501.15339v1)

### C-3 データ品質・プロビナンスの欠落

**症状**: 「outdated / incomplete network models と inaccurate load profiles が
HCA 信頼性を根本的に崩す」(ScienceDirect 2025)。実験が**どのネットワーク・どの
負荷・どの seed で走ったか**を事後追跡できる仕組みがない。

**出典**:
- [ScienceDirect HCA challenges 2025](https://www.sciencedirect.com/science/article/pii/S0306261925020537)
- [arxiv 2501.15339 2025](https://arxiv.org/html/2501.15339v1)

### C-4 パラメータ sweep の属人性

**症状**: 浸透率 / 負荷 / 気象等のパラメータを振って結果を集めるのは研究の
日常業務だが、研究者はツールを手で N 回叩き、結果 CSV を Excel に貼って
グラフ化するパターンが多数。自動化は各自のスクリプトに閉じる。

**出典**:
- ScienceDirect HCA challenges 2025 (同上、"iterative method" の記述)
- `gridtwin_lab_plan.md` §1.2 (gridflow プロジェクト自身の認識)

### C-5 RL 競技の比較不能性 (L2RPN)

**症状**: 「each method uses custom input features and action spaces ... different
time series, making effective comparisons far from trivial」— RL2Grid 2025 が
この課題のために新規に標準化を試みている。

**出典**:
- [RL2Grid (arxiv 2503.23101, 2025)](https://arxiv.org/abs/2503.23101)
- [Optimizing Power Grid Topologies with RL: Survey (arxiv 2504.08210, 2025)](https://arxiv.org/html/2504.08210)

### C-6 HELICS co-simulation 設計の複雑性

**症状**: message topology と broker topology の設計が属人的。異なる時空間
スケールを扱うためのスケーラビリティ問題が実運用で現れる。

**出典**:
- [HELICS development pitfalls (Springer 2024)](https://link.springer.com/chapter/10.1007/978-3-031-78806-2_11)
- [Comparison of co-simulation frameworks (Springer 2022)](https://link.springer.com/article/10.1186/s42162-022-00231-6)

### C-7 電力系に特化した experiment tracker の不在

**症状**: MLflow / Kedro は ML 特化。電力系固有の Topology / TimeSeries / Event /
Metric を 1 級データ型として扱う experiment tracker は公開 OSS に存在しない。
研究者は「自作 shell スクリプト + ディレクトリ命名規則」で管理している。

**出典**: ML/OSS 調査の消去法的結論 (§1.4 参照、該当する正の論文なし)。

### C-8 co-simulation vs 単一 solver の使い分け指針不足

**症状**: 研究者が co-simulation を使うべきか単一 solver で十分かを決める
体系的ガイドがない。論文ごとに独自判断。

**出典**:
- [Comparison of co-simulation frameworks for multi-energy systems (Springer 2022)](https://link.springer.com/article/10.1186/s42162-022-00231-6)

### C-9 時系列負荷プロファイルの標準化不足

**症状**: Grid2Op は合成データに依存、実データ公開が課題。論文間で異なる
時系列が使われ、結果比較が困難。

**出典**:
- [RL2Grid arxiv 2503.23101 2025](https://arxiv.org/abs/2503.23101)
- Open Power System Data (データ側の進展)

### C-10 電圧/熱違反の定義のばらつき

**症状**: voltage violation ratio の計算式が論文ごとに異なる (0.95/1.05 pu か、
0.94/1.06 pu か、時間重み付けはどうするか 等)。指標の共有オントロジーが無い。

**出典**:
- [Hosting Capacity Assessment Strategies and RL for Coordinated Voltage Control (MDPI Energies 2023)](https://www.mdpi.com/1996-1073/16/5/2371)

---

## 3. gridflow のスコープマッピング

各課題を gridflow が **直接解決できる (✅)**、**部分的に対応 (⚠️)**、
**スコープ外 (❌)** で分類する。

| 課題 | gridflow 対応 | 根拠 (実装 / 設計) |
|---|---|---|
| **C-1 再現性危機** | ✅ 直接 | Scenario Pack + seed + Dockerized 実行。`test_reproducibility_three_runs` E2E で 3 回実行一致を担保 |
| **C-2 HCA 手法標準化** | ⚠️ 部分 | voltage_deviation / runtime metric の共通化まで。4 手法の本格実装は Phase 2+ |
| **C-3 データプロビナンス** | ✅ 直接 | `pack_id = name@version` で一意。`FileScenarioRegistry` がネットワーク・パラメータを包む。shared volume 経由で解決 (03b §3.5.6) |
| **C-4 パラメータ sweep** | ⚠️ 部分 | 手動 pack 差替えは可 (gridflow run × N)。自動 sweep 機能は Phase 2 (P1 §3.2) |
| **C-5 RL 比較不能性** | ❌ スコープ外 | RL 環境ではない。Grid2Op/RL2Grid と隣接領域 |
| **C-6 HELICS 設計複雑性** | ⚠️ 将来 | `FederationDriven` (Infra 03d §3.8.5) を Phase 2+ で取り込む設計あり |
| **C-7 電力系 experiment tracker 不在** | ✅ 直接 | gridflow の中核価値そのもの。CDL 8 型 (Topology/Asset/TimeSeries/Event/Metric etc.) が 1 級データ型 |
| **C-8 co-simulation 判断支援** | ❌ スコープ外 | 判断支援は対象外 |
| **C-9 時系列負荷標準化** | ⚠️ 部分 | Pack 単位で TimeSeries を内包できる (`TimeSeriesSet`)。データそのものの標準提供は別 |
| **C-10 指標定義ばらつき** | ✅ 直接 | `voltage_deviation` metric を計算式付きで提供、pack で違反閾値を明示可能 |

### 3.1 gridflow が「✅ 直接対応」する 4 課題のまとめ

MVP 時点で gridflow が先行研究に対して**新しく提供できる効果**は以下 4 点に絞られる:

1. **C-1 実験単位での再現性**: 同一 seed + 同一 pack + 同一 Docker image で結果完全一致
2. **C-3 実験プロビナンス**: 結果 JSON に pack_id が紐づく、事後追跡可能
3. **C-7 電力系ネイティブな experiment tracker**: Scenario Pack / Experiment Result /
   Benchmark Report という電力系 1 級データ型でのトラッキング
4. **C-10 指標の再現可能な定義**: voltage_deviation などの metric 計算が Python
   コードとしてコミット・バージョン管理される

### 3.2 gridflow が「⚠️ 部分対応」する 3 課題 (将来拡張余地)

5. **C-2 HCA 手法**: voltage_deviation + runtime の 2 指標から、Phase 2 で HCA
   手法群 (streamlined/stochastic/iterative) のプラグ差替えへ拡張可能な土台あり
6. **C-4 パラメータ sweep**: 現状は手動差替えだが、Pack のパラメータ化が既に
   frozen 構造で可能。Phase 2 で `gridflow sweep` コマンド追加
7. **C-9 時系列標準化**: Pack が TimeSeriesSet を内包可能で、データセット提供は
   Phase 2+ の共同研究 loop で獲得

### 3.3 スコープ外 (明確に対象外)

8. **C-5 RL 比較**: Grid2Op / RL2Grid の領域
9. **C-8 co-simulation 判断支援**: 人間 / ドキュメンテーションの役割

---

## 4. 本書と他ドキュメントの関係

| ドキュメント | 関係 |
|---|---|
| [gridtwin_lab_plan.md §1.2](./gridtwin_lab_plan.md) | 本書の根拠 (プロジェクト自身が認識する pain) |
| [development_plan.md §2.2](./development_plan.md) | MVP ユーザーストーリー US-1〜US-6 を定義 |
| [mvp_scenario.md](./mvp_scenario.md) | 本書 §3.1 の「✅ 直接対応」課題を end-to-end で実証するシナリオ |
| [basic_design/01_requirements.md](./basic_design/01_requirements.md) | REQ-B / REQ-F / REQ-Q の番号空間 |
| [architecture/02_architecture_significance.md](./architecture/02_architecture_significance.md) | QA-1〜QA-11 品質属性 |

---

## 5. 参考文献 (まとめ)

### 電力系研究ワークフロー
- [PyPSA: Python for Power System Analysis (arxiv 1707.09913)](https://arxiv.org/pdf/1707.09913)
- [pandapower (arxiv 1709.06743)](https://arxiv.org/pdf/1709.06743)
- [HELICS: A Co-Simulation Framework (IEEE Access 2024)](https://faculty.sites.iastate.edu/tesfatsi/archive/tesfatsi/HELICSCoSimFramework.HardyEtAl.IEEEAccess2024.pdf)
- [HELICS development pitfalls (Springer 2024)](https://link.springer.com/chapter/10.1007/978-3-031-78806-2_11)
- [Comparison of co-simulation frameworks (Springer 2022)](https://link.springer.com/article/10.1186/s42162-022-00231-6)

### RL / 逐次運用
- [Grid2Op (LF Energy)](https://lfenergy.org/projects/grid2op/)
- [RL2Grid (arxiv 2503.23101, 2025)](https://arxiv.org/abs/2503.23101)
- [Optimizing Power Grid Topologies with RL: Survey (arxiv 2504.08210, 2025)](https://arxiv.org/html/2504.08210)

### HCA (Hosting Capacity Analysis)
- [Challenges and applications of HCA in DER-rich power systems (ScienceDirect 2025)](https://www.sciencedirect.com/science/article/pii/S0306261925020537)
- [DER Hosting capacity: definitions, attributes, use-cases and challenges (arxiv 2501.15339, 2025)](https://arxiv.org/html/2501.15339v1)
- [A Review of the Tools and Methods for HCA (MDPI Energies 2020)](https://www.mdpi.com/1996-1073/13/11/2758)
- [HCA Strategies and RL for Voltage Control (MDPI Energies 2023)](https://www.mdpi.com/1996-1073/16/5/2371)

### 再現性・オープンサイエンス
- [Energy system modeling reproducibility (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2211467X17300949)
- [Open science in energy research (PMC 2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11907185/)
- [Improving energy research practices (Buildings & Cities)](https://journal-buildingscities.org/articles/10.5334/bc.67)

### Experiment tracker (ML 参考)
- [MLflow](https://mlflow.org/)
- [kedro-mlflow](https://kedro-mlflow.readthedocs.io/)
- [DVC](https://dvc.org/)
