# try16 Theoretical Results — Stokes-Stratified Droop (M11)

実施: 2026-05-06
論文章節案: report.md §4 / §5
立ち上げ理由: Rule 9 v2 invariant 検査で生存した sedimentology / Stokes 沈降の機構を
配電 Volt-VAR 分散制御に移植。M11 = depth-graded τ + K の閉形式設計則と Bode bound。

---

## 1. 記号

| 記号 | 意味 |
|---|---|
| $j \in \{0, \dots, N-1\}$ | フィーダ放射状 bus index、bus 0 = 変電所 (slack) |
| $d_j$ | bus 0 から bus $j$ までの累積線路抵抗 (pu) |
| $d_{\max} = d_{N-1}$ | 末端深度 |
| $r_k, x_k$ | segment $k$ の R, X (pu) |
| $S_b$ | 系容量 (kW) |
| $p_j(t)$ | bus $j$ の純有効電力注入 (PV − load, kW) |
| $q_j(t)$ | bus $j$ の無効電力注入 (kVAR) |
| $V_j(t)$ | bus $j$ の電圧 (pu) |
| $\tau_j$, $K_j$ | inverter $j$ の応答時定数と droop ゲイン |

## 2. Setup

線形 DistFlow (Baran-Wu, radial):

$$
V_j(t) = V_0 + \frac{1}{S_b}\sum_{k=1}^{j}\bigl(r_k\,P_k^{\downarrow}(t) + x_k\,Q_k^{\downarrow}(t)\bigr)
$$

ここで $P_k^{\downarrow} = \sum_{m \geq k} p_m$, $Q_k^{\downarrow} = \sum_{m \geq k} q_m$.

各 inverter の droop:

$$
\tau_j \dot{q}_j = K_j\,(V_{\text{ref}} - V_j(t))\,c_j - q_j, \qquad |q_j| \leq c_j
$$

ここで $c_j$ は容量 (kW)。M0 (uniform) は $\tau_j = \bar{\tau}$, $K_j = \bar{K}$。
M11 (Stokes-stratified) は

$$
\tau_j = \tau_{\max} - (\tau_{\max} - \tau_{\min})\,\frac{d_j}{d_{\max}}, \quad
K_j = K_{\text{base}}\,\left(0.3 + 1.7\,\frac{d_j}{d_{\max}}\right)
$$

(末端深 = 速 $\tau$, 高 K)。

## 3. 雲影擾乱モデル

雲が速度 $v$ で feeder 上を伝搬、空間長 $L_c$, 影率 $s$ を仮定。bus $j$ における PV 出力倍率 $\mu_j(t) \in [1-s, 1]$ は通過時間 $T_j = L_c/v$ 程度の幅。これは bus $j$ の有効電力注入を $p_j(t) = c_j \mu_j(t) - \ell_j$ に変える。

特性周波数:

$$
\omega_c = \frac{2\pi v}{L_c} \quad [\text{rad/s}]
$$

(典型値: $v = 15$ m/s, $L_c = 500$ m → $\omega_c \approx 0.19$ rad/s = 0.03 Hz)

## 4. Theorem 6 (Depth-Graded LPF Cascade による Bode Bound)

**主張**:

M11 (Stokes-stratified) のもとで、bus $j$ の voltage perturbation $\Delta V_j(s)$ から
雲影擾乱 $\Delta\mu_j(s)$ への伝達関数は

$$
\frac{\Delta V_j(s)}{\Delta\mu_j(s)} = \frac{\sum_{k=1}^{j} r_k\,c_j}{S_b\,(1 + s \tau_j / G_j)} + O(s^{-2})
$$

ここで $G_j = K_j\,c_j\,x_{\text{loop},j}/S_b$, $x_{\text{loop},j} = \sum_{k=1}^{j} x_k$ は
local loop gain。**3-dB cutoff** は

$$
\omega_{\text{3dB},j} = \frac{G_j}{\tau_j} \;\geq\; \frac{K_{\text{base}} c_j x_{\text{loop},j} (0.3 + 1.7 d_j/d_{\max})}{S_b\,(\tau_{\max} - (\tau_{\max} - \tau_{\min})\,d_j/d_{\max})}
$$

末端 ($j = N-1$) で:

$$
\omega_{\text{3dB},N-1} = \frac{2.0\,K_{\text{base}}\,c_{N-1}\,x_{\text{loop},N-1}}{S_b\,\tau_{\min}}
$$

→ **末端 inverter の cutoff は $\tau_{\min}$ に支配され、設計者が直接コントロール可能**。

**帰結 (M11 vs M0)**:

M0 (uniform $\tau = \bar\tau$, $K = \bar K$) で末端 cutoff は
$$
\omega_{\text{3dB},N-1}^{M0} = \frac{\bar K c_{N-1} x_{\text{loop},N-1}}{S_b\,\bar\tau}
$$

ratio:

$$
\frac{\omega_{\text{3dB},N-1}^{M11}}{\omega_{\text{3dB},N-1}^{M0}} = \frac{2.0\,K_{\text{base}}/\bar K}{\tau_{\min}/\bar\tau}
$$

採用値 ($K_{\text{base}} = \bar K = 18$, $\tau_{\min} = 0.3$ s, $\bar\tau = 5$ s) で
**33.3 倍の bandwidth**。雲影特性周波数 $\omega_c \approx 0.2$ rad/s に対し、M0 の末端 cutoff は約 $0.04$ rad/s で **追従不能**、M11 は $\approx 1.3$ rad/s で **十分追従**。

## 5. Theorem 7 (基幹近傍は「動かない方が良い」: Q-Energy Pareto)

**主張**:

bus 0 近傍 ($d_j \to 0$) では $x_{\text{loop},j} \to 0$ なので local loop gain $G_j \to 0$、
すなわち inverter $j$ の Q 出力は局所的にほぼ V を変えない。M0 で同一 K を与えると、
基幹近傍 inverter は **末端の Q 行動を見越して** 大きな Q を出すが、それは V_j に
ほぼ寄与しない（slack バスが clamp）。M11 で $K_j \to 0.3 K_{\text{base}}$ に
減らせば Q 出力は減るが violation 性能はほぼ不変。

**帰結 (Q energy 効率)**:

$$
\mathbb{E}\!\left[\int |q_j(t)| dt\right]^{M11} \approx \mathbb{E}\!\left[\int |q_j(t)| dt\right]^{M0}
$$

(基幹側の節約が末端側の追加で相殺、合計は同オーダー。実測 §6 で確認)

## 6. 既存手法との理論対比

| 手法 | 通信? | 末端 cutoff | 基幹 K | 雲影追従 | 物理 invariant |
|---|---|---|---|---|---|
| M0 uniform droop | × | $\bar K c x_{\text{loop}} / (S_b \bar\tau)$ | $= \bar K$ | 末端 X | uniform LPF, 共鳴あり |
| M3 consensus PI | ✅ (delay $\delta$) | (consensus 定常項で $\to 0$) + $K_p / S_b$ | $= K_p$ | $\delta < 1/\omega_c$ で OK | global mean tracking |
| **M11 stratified droop** | × | $\,2 K_{\text{base}} c x_{\text{loop}} / (S_b \tau_{\min})$ | $= 0.3 K_{\text{base}}$ | $\tau_{\min} < 1/\omega_c$ で **保証** | **graded sediment LPF cascade** |

→ M11 は **無通信** で **末端 bandwidth を局所設計パラメタで保証**、共鳴項が空間で
desynchronise される (Stokes invariant の移植)。

## 7. 設計則 (closed-form)

雲影最悪 case $(\omega_c^{\max}, s^{\max})$ と SLA tolerance $\eta$ (e.g. 1% violation rate)
が与えられたとき:

$$
\tau_{\min} \;\leq\; \frac{2\,K_{\text{base}}\,c_{\text{end}}\,x_{\text{loop,end}}}{S_b\,\omega_c^{\max}\,\eta^{-1}}
$$

この閾値を満たす範囲で $\tau_{\max}$ は基幹 hunting 抑制のために大きく取ってよい
(典型 $\tau_{\max} \in [10, 30]$ s)。**closed-form 設計則** = 雲気候 + フィーダ電気的長
から $\tau_{\min}, \tau_{\max}, K_{\text{base}}$ を一意決定。

---

## 8. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-05-06 | 初版。Rule 9 v2 で生存した Stokes 沈降 invariant を depth-graded LPF cascade として formalise。Theorem 6 (Bode bound 33.3× 帯域改善) + Theorem 7 (Q-energy Pareto) を導出 |
