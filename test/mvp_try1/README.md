# MVP try 1: IEEE 13 × DER 浸透率 sweep

隔離スクラッチ領域。gridflow が研究ツールとして「先行研究の未解決課題を
解決できているか」を end-to-end で実証するシナリオ。

- **親ドキュメント**: [../../docs/mvp_scenario.md](../../docs/mvp_scenario.md)
- **背景課題**: [../../docs/research_landscape.md](../../docs/research_landscape.md) §2
- **対応課題 (landscape §3.1)**: C-1 再現性 / C-3 プロビナンス / C-7 電力系 tracker / C-10 指標定義

## 方針

- `src/gridflow/` は一切触らない
- `examples/` / `tools/` / `tests/` も触らない
- 失敗や試行錯誤は本フォルダ内で完結させる
- `test/` (単数) は pytest の `testpaths = ["tests"]` に含まれないので自動収集されない

## ディレクトリ構成

```
test/mvp_try1/
├── README.md                  # 本書
├── packs/                     # Scenario Pack 群
│   ├── ieee13_der_base.dss    # 共通ベース (load + line, Solve なし)
│   ├── der_{00,25,50,75,100}.dss    # base + PV + Solve (5 本)
│   └── der_{00,25,50,75,100}.yaml   # gridflow pack.yaml (5 本)
├── tools/
│   ├── run_der_sweep.sh       # 一発ラッパー
│   ├── verify_reproducibility.py   # 3 回実行一致検証
│   └── plot_hosting_capacity.py    # matplotlib 図化
├── results/                   # 実行時生成物
│   └── .gitkeep
└── report.md                  # 実走結果 (実装完了後に追記)
```

## DER 浸透率の定義

**浸透率 = 系統総負荷に対する PV 総発電容量の比**

IEEE 13 の総負荷 ≈ 3,466 kW (loads の kW を合算):

| 浸透率 | 総 PV 容量 | PV 配置 (671/675/634 均等) |
|---|---:|---|
| 0%   | 0 kW    | (PV なし = baseline) |
| 25%  | 867 kW  | 3 × 289 kW |
| 50%  | 1,733 kW | 3 × 578 kW |
| 75%  | 2,600 kW | 3 × 867 kW |
| 100% | 3,466 kW | 3 × 1,155 kW |

配置バス:
- 671: 総負荷 1,155 kW の最大バス
- 675: 総負荷 843 kW (2 位)
- 634: 総負荷 400 kW (トランス配下の二次側)

均等配置にしたのは配置最適化を Phase 2 以降に送るため (mvp_scenario.md §7)。
PV モデルは簡便のため `Generator` (pf=1.0) を用いる (PVSystem の Loadshape
対応は Phase 2 以降)。

## 再現手順

```bash
cd test/mvp_try1

# 1 コマンドでフル実行
./tools/run_der_sweep.sh

# 個別に実行する場合
for p in der_00 der_25 der_50 der_75 der_100; do
  gridflow scenario register packs/${p}.yaml
done
for p in der_00 der_25 der_50 der_75 der_100; do
  for run in 1 2 3; do
    gridflow run ${p}@1.0.0 --steps 1 --seed 42 --format json \
      > results/${p}_run${run}.json
  done
done
python tools/verify_reproducibility.py results/der_*_run*.json
python tools/plot_hosting_capacity.py results/der_*_run1.json \
  -o results/hosting_capacity.png
```

## 前提

- OpenDSSDirect.py がインストール済み (`pip install OpenDSSDirect.py`)
- gridflow が editable インストール済み (`pip install -e .`)
- numpy (既存 dep)
- matplotlib (可視化時のみ、`pip install matplotlib`)
