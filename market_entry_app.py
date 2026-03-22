# market_entry_app.py
# STP x 製品ライフサイクル 経営戦略シミュレーション
# 1人プレイ（プレイヤー1チーム vs AI 4チーム）
# 教育目標: STP分析・ポジショニング戦略・PLC管理・競合行動の実践的理解
#
# 起動: streamlit run market_entry_app.py

import io
import streamlit as st
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

# --- 日本語フォント設定（環境依存、フォールバックあり）---
rcParams["font.family"] = ["MS Gothic", "Meiryo", "IPAexGothic", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False

# ============================================================
# 定数定義
# ============================================================

TOTAL_TURNS = 15

# 価格帯・品質帯のラベル（グリッドインデックス 0/1/2 に対応）
PRICE_LABELS  = ["低価格", "中価格", "高価格"]
QUALITY_LABELS = ["低品質", "中品質", "高品質"]

# セグメント定義: {名前: {coord(price_idx, quality_idx), 初期規模, 説明}}
SEGMENTS = {
    "マス市場":   {"coord": (0, 1), "base_size": 400, "plc_start": "成熟期"},
    "プレミアム": {"coord": (2, 2), "base_size": 150, "plc_start": "導入期"},
    "バリュー":   {"coord": (0, 2), "base_size": 250, "plc_start": "成長期"},
    "ニッチ":     {"coord": (2, 0), "base_size":  80, "plc_start": "衰退期"},
}

# PLCフェーズ定義（市場全体・ターンレンジ）
PLC_PHASES_BY_TURN = {
    1: "導入期", 2: "導入期", 3: "導入期",
    4: "成長期", 5: "成長期", 6: "成長期", 7: "成長期",
    8: "成熟期", 9: "成熟期", 10: "成熟期", 11: "成熟期",
    12: "衰退期", 13: "衰退期", 14: "衰退期", 15: "衰退期",
}

# PLCフェーズ別補正係数
PLC_MULTIPLIERS = {
    "導入期": {"demand": 0.7,  "marketing": 2.0, "rd": 1.5, "prod": 1.0},
    "成長期": {"demand": 1.0,  "marketing": 1.5, "rd": 1.0, "prod": 1.0},
    "成熟期": {"demand": 1.0,  "marketing": 1.0, "rd": 2.0, "prod": 2.0},
    "衰退期": {"demand": 1.0,  "marketing": 1.0, "rd": 3.0, "prod": 2.0},
}

# セグメント別 PLCフェーズ初期オフセット（全体フェーズを基準に加算）
# "成熟期スタート" = 全体が導入期のとき、このセグメントは成熟期相当の補正を使う
SEG_PHASE_OFFSET = {
    "マス市場":   2,  # 2フェーズ先行（導入期時に成熟期補正）
    "プレミアム": 0,  # オフセットなし（全体と同期）
    "バリュー":   1,  # 1フェーズ先行（導入期時に成長期補正）
    "ニッチ":     3,  # 3フェーズ先行（導入期時に衰退期補正）
}

PHASE_ORDER = ["導入期", "成長期", "成熟期", "衰退期"]

# 単価テーブル（価格帯インデックス → 単価）
UNIT_PRICE = {0: 50, 1: 100, 2: 180}

# チームカラー
TEAM_COLORS = {
    "player": "#E74C3C",
    "Alpha":  "#3498DB",
    "Beta":   "#2ECC71",
    "Gamma":  "#F39C12",
    "Delta":  "#9B59B6",
}

# AIチーム表示名
AI_PROFILES = {
    "Alpha": {
        "full_name": "AI-Alpha（コストリーダー）",
        "strategy": "低価格・低品質に固定。成熟期・衰退期に生産効率投資を増大。",
        "icon": "A",
    },
    "Beta": {
        "full_name": "AI-Beta（差別化型）",
        "strategy": "高価格・高品質に固定。成長期にR&D重視、導入期から積極参入。",
        "icon": "B",
    },
    "Gamma": {
        "full_name": "AI-Gamma（フォロワー）",
        "strategy": "プレイヤーを2ターン遅れで模倣。PLCに関係なく追随。",
        "icon": "G",
    },
    "Delta": {
        "full_name": "AI-Delta（適応型）",
        "strategy": "PLCフェーズに応じて戦略変更。成長期:高品質、成熟期:低価格、衰退期:ニッチ。",
        "icon": "D",
    },
}

# PLCフェーズ別推奨戦略ヒント
PLC_HINTS = {
    "導入期": [
        "市場はまだ小さい。マーケティング投資で認知度を高めよう。",
        "R&D投資が後の差別化につながる。品質ポジションを意識せよ。",
        "価格設定は将来のブランドイメージを決める重要な判断だ。",
    ],
    "成長期": [
        "需要が急拡大中。シェア獲得のチャンス。",
        "競合との差別化を明確にするポジショニングが有効。",
        "R&D投資を続けてプレミアム市場を狙うか、低価格で量を取るか。",
    ],
    "成熟期": [
        "需要が安定。生産効率投資でコスト削減が有効（効果2倍）。",
        "R&D効果も2倍。技術革新でポジションを変える好機。",
        "セグメントを絞り込んだターゲット戦略が利益率を高める。",
    ],
    "衰退期": [
        "需要が減少中。ニッチセグメントへの集中が有効。",
        "R&D効果3倍。イノベーションで市場を作り直せるか。",
        "不採算ポジションからの撤退も戦略的選択肢だ。",
    ],
}

# ============================================================
# ゲーム状態の初期化
# ============================================================

def init_game_state(player_name: str) -> None:
    """session_state にゲーム初期状態を書き込む。"""
    # 各チームの状態テンプレート
    def make_team(name: str, is_ai: bool) -> dict:
        return {
            "name": name,
            "is_ai": is_ai,
            "price_pos": 1,        # 0:低 / 1:中 / 2:高
            "quality_pos": 1,
            "mkt": 34,             # 初期投資配分
            "rd": 33,
            "prod": 33,
            "rd_cumulative": 0,    # R&D累積効果
            "prod_cumulative": 0,  # 生産効率累積
            "profit_history": [],  # ターンごとの利益リスト
            "share_history": [],   # ターンごとのシェアリスト
            "pos_history": [],     # ターンごとの(price_pos, quality_pos)
        }

    st.session_state.teams = {
        "player": make_team(player_name, False),
        "Alpha":  make_team("AI-Alpha", True),
        "Beta":   make_team("AI-Beta",  True),
        "Gamma":  make_team("AI-Gamma", True),
        "Delta":  make_team("AI-Delta", True),
    }

    # セグメント現在規模（初期値）
    st.session_state.segment_sizes = {
        seg: data["base_size"] for seg, data in SEGMENTS.items()
    }

    st.session_state.turn = 1
    st.session_state.phase = "playing"   # title / playing / result
    st.session_state.turn_results = []   # 各ターンの全チーム結果リスト

    # プレイヤーの仮決定入力（確定前バッファ）
    st.session_state.input_price    = 1
    st.session_state.input_quality  = 1
    st.session_state.input_mkt      = 34
    st.session_state.input_rd       = 33

# ============================================================
# AI戦略ロジック
# ============================================================

def ai_decide(ai_key: str, turn: int, plc_phase: str) -> dict:
    """AIチームの意思決定を返す。price_pos, quality_pos, mkt, rd, prod を含む dict。"""
    teams = st.session_state.teams

    if ai_key == "Alpha":
        # コストリーダー: 低価格・低品質に固定
        price_pos   = 0
        quality_pos = 0
        if plc_phase in ("成熟期", "衰退期"):
            mkt, rd, prod = 20, 10, 70
        else:
            mkt, rd, prod = 30, 20, 50

    elif ai_key == "Beta":
        # 差別化型: 高価格・高品質に固定
        price_pos   = 2
        quality_pos = 2
        if plc_phase == "成長期":
            mkt, rd, prod = 20, 60, 20
        elif plc_phase == "導入期":
            mkt, rd, prod = 50, 30, 20
        else:
            mkt, rd, prod = 30, 40, 30

    elif ai_key == "Gamma":
        # フォロワー: プレイヤーを2ターン遅れで模倣
        player = teams["player"]
        if turn <= 2:
            # 最初の2ターンはデフォルト
            price_pos   = 1
            quality_pos = 1
            mkt, rd, prod = 34, 33, 33
        else:
            # 2ターン前のプレイヤー履歴を参照
            idx = turn - 3  # 0始まりの履歴インデックス
            if idx < len(player["pos_history"]):
                price_pos, quality_pos = player["pos_history"][idx]
            else:
                price_pos, quality_pos = player["price_pos"], player["quality_pos"]
            if idx < len(player["profit_history"]):
                # 投資配分も2ターン前の値を使う（履歴に保存していないためデフォルト流用）
                mkt, rd, prod = 34, 33, 33
            else:
                mkt, rd, prod = 34, 33, 33

    elif ai_key == "Delta":
        # 適応型: PLCフェーズに応じて戦略変更
        if plc_phase == "導入期":
            price_pos, quality_pos = 1, 1
            mkt, rd, prod = 40, 40, 20
        elif plc_phase == "成長期":
            price_pos, quality_pos = 2, 2  # 高品質へ
            mkt, rd, prod = 30, 50, 20
        elif plc_phase == "成熟期":
            price_pos, quality_pos = 0, 1  # 低価格へ
            mkt, rd, prod = 20, 20, 60
        else:  # 衰退期
            price_pos, quality_pos = 2, 0  # ニッチへ
            mkt, rd, prod = 20, 50, 30
    else:
        price_pos, quality_pos = 1, 1
        mkt, rd, prod = 34, 33, 33

    return {
        "price_pos":   price_pos,
        "quality_pos": quality_pos,
        "mkt":  mkt,
        "rd":   rd,
        "prod": prod,
    }

# ============================================================
# ターン処理（シェア・利益計算）
# ============================================================

def get_segment_plc_phase(seg_name: str, global_phase: str) -> str:
    """セグメントごとのPLCフェーズを返す（オフセット適用）。"""
    global_idx = PHASE_ORDER.index(global_phase)
    offset = SEG_PHASE_OFFSET[seg_name]
    seg_idx = min(global_idx + offset, len(PHASE_ORDER) - 1)
    return PHASE_ORDER[seg_idx]

def calc_distance(team_price: int, team_quality: int,
                  seg_price: int, seg_quality: int) -> float:
    """ポジションとセグメント中心の距離を返す。"""
    return np.sqrt((team_price - seg_price) ** 2 + (team_quality - seg_quality) ** 2)

def calc_marketing_power(mkt: int, seg_plc: str) -> float:
    """マーケティングパワー = 投資額 × PLCフェーズ補正。"""
    mult = PLC_MULTIPLIERS[seg_plc]["marketing"]
    return mkt * mult

def process_turn(turn: int) -> dict:
    """
    1ターン分の処理を実行し、全チームの結果を返す。
    戻り値: {team_key: {profit, share, price_pos, quality_pos, mkt, rd, prod, ...}}
    """
    plc_phase = PLC_PHASES_BY_TURN[turn]
    teams     = st.session_state.teams
    seg_sizes = st.session_state.segment_sizes

    # --- AIの意思決定を適用 ---
    for ai_key in ("Alpha", "Beta", "Gamma", "Delta"):
        decision = ai_decide(ai_key, turn, plc_phase)
        for k, v in decision.items():
            teams[ai_key][k] = v

    # --- 全チームのシェア・利益計算 ---
    team_keys     = list(teams.keys())
    turn_result   = {}
    total_profit  = {}

    # R&D・生産効率の累積更新（プレイヤー + AI）
    for key, team in teams.items():
        team["rd_cumulative"]   += team["rd"]
        team["prod_cumulative"] += team["prod"]

    # セグメントごとにシェアを計算し、利益を集計
    seg_shares_all = {key: 0.0 for key in team_keys}
    seg_volumes    = {key: 0.0 for key in team_keys}

    for seg_name, seg_data in SEGMENTS.items():
        seg_phase = get_segment_plc_phase(seg_name, plc_phase)
        seg_mult  = PLC_MULTIPLIERS[seg_phase]

        # セグメント規模更新
        current_size = seg_sizes[seg_name]
        if seg_phase == "成長期":
            current_size *= 1.15
        elif seg_phase == "衰退期":
            current_size *= 0.92
        seg_sizes[seg_name] = current_size

        # 各チームの引力パワー計算
        seg_coord = seg_data["coord"]  # (price_idx, quality_idx)
        powers    = {}
        for key, team in teams.items():
            dist  = calc_distance(team["price_pos"], team["quality_pos"],
                                  seg_coord[0], seg_coord[1])
            power = calc_marketing_power(team["mkt"], seg_phase) / (1 + dist ** 2)
            powers[key] = max(power, 0.001)  # ゼロ除算防止

        total_power = sum(powers.values())

        for key in team_keys:
            share  = powers[key] / total_power
            volume = current_size * seg_mult["demand"] * share
            seg_shares_all[key] += share
            seg_volumes[key]    += volume

    # シェアを全セグメント平均に正規化
    for key in team_keys:
        seg_shares_all[key] /= len(SEGMENTS)

    # 利益計算
    for key, team in teams.items():
        rd_eff   = team["rd_cumulative"]
        prod_eff = team["prod_cumulative"]

        unit_price = UNIT_PRICE[team["price_pos"]] * (1 + rd_eff * 0.005)
        margin     = min(0.20 + team["rd"] * 0.003, 0.60)
        fixed_cost = max(500 - prod_eff * 3, 100)
        volume     = seg_volumes[key]
        profit     = volume * unit_price * margin - fixed_cost

        team["profit_history"].append(profit)
        team["share_history"].append(seg_shares_all[key])
        team["pos_history"].append((team["price_pos"], team["quality_pos"]))

        turn_result[key] = {
            "name":        team["name"],
            "price_pos":   team["price_pos"],
            "quality_pos": team["quality_pos"],
            "mkt":         team["mkt"],
            "rd":          team["rd"],
            "prod":        team["prod"],
            "share":       seg_shares_all[key],
            "profit":      profit,
            "cum_profit":  sum(team["profit_history"]),
        }

    st.session_state.turn_results.append(turn_result)
    return turn_result

# ============================================================
# グラフ描画ユーティリティ
# ============================================================

def fig_to_bytes(fig) -> bytes:
    """matplotlib figure を PNG バイト列に変換。"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    buf.seek(0)
    data = buf.read()
    plt.close(fig)
    return data

def draw_profit_bar(turn_result: dict) -> bytes:
    """今ターンの利益比較棒グラフ。"""
    keys   = list(turn_result.keys())
    names  = [turn_result[k]["name"] for k in keys]
    profits = [turn_result[k]["profit"] for k in keys]
    colors  = [TEAM_COLORS.get(k, "#AAAAAA") for k in keys]

    fig, ax = plt.subplots(figsize=(6, 3))
    bars = ax.bar(names, profits, color=colors, edgecolor="white", linewidth=0.5)
    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax.set_title("今ターンの利益比較", fontsize=11)
    ax.set_ylabel("利益 (pt)")
    ax.set_xlabel("")
    for bar, val in zip(bars, profits):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + (max(profits) * 0.02 if max(profits) > 0 else 50),
                f"{val:,.0f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    return fig_to_bytes(fig)

def draw_cumprofit_line() -> bytes:
    """累計利益の推移折れ線グラフ。"""
    teams = st.session_state.teams
    turns = list(range(1, len(next(iter(teams.values()))["profit_history"]) + 1))

    fig, ax = plt.subplots(figsize=(6, 3.5))
    for key, team in teams.items():
        cum = np.cumsum(team["profit_history"])
        ax.plot(turns, cum, marker="o", markersize=4,
                color=TEAM_COLORS.get(key, "#AAAAAA"),
                label=team["name"], linewidth=1.8)
    ax.set_title("累計利益推移", fontsize=11)
    ax.set_xlabel("ターン")
    ax.set_ylabel("累計利益 (pt)")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    return fig_to_bytes(fig)

def draw_positioning_map() -> bytes:
    """全チームの 15 ターン分ポジショニング軌跡散布図。"""
    teams  = st.session_state.teams
    fig, ax = plt.subplots(figsize=(5, 5))

    # セグメント中心をプロット
    for seg_name, seg_data in SEGMENTS.items():
        px, qy = seg_data["coord"]
        ax.scatter(px, qy, s=200, marker="*", color="gold", zorder=2,
                   edgecolors="gray", linewidths=0.5)
        ax.text(px + 0.08, qy + 0.08, seg_name, fontsize=7, color="dimgray")

    # チームの軌跡
    for key, team in teams.items():
        xs = [p[0] for p in team["pos_history"]]
        ys = [p[1] for p in team["pos_history"]]
        color = TEAM_COLORS.get(key, "#AAAAAA")
        ax.plot(xs, ys, color=color, alpha=0.5, linewidth=1.2)
        ax.scatter(xs, ys, c=color, s=30, zorder=3, alpha=0.7)
        # 最終ポジションにラベル
        if xs:
            ax.text(xs[-1] + 0.07, ys[-1] + 0.07, team["name"],
                    fontsize=7, color=color)

    ax.set_xlim(-0.3, 2.3)
    ax.set_ylim(-0.3, 2.3)
    ax.set_xticks([0, 1, 2])
    ax.set_yticks([0, 1, 2])
    ax.set_xticklabels(PRICE_LABELS, fontsize=9)
    ax.set_yticklabels(QUALITY_LABELS, fontsize=9)
    ax.set_xlabel("価格ポジション", fontsize=10)
    ax.set_ylabel("品質ポジション", fontsize=10)
    ax.set_title("ポジショニング軌跡マップ（全ターン）", fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()
    return fig_to_bytes(fig)

def draw_plc_profit() -> bytes:
    """PLCフェーズ別利益推移（4フェーズ帯を背景色で表現）。"""
    teams  = st.session_state.teams
    n_hist = len(next(iter(teams.values()))["profit_history"])
    turns  = list(range(1, n_hist + 1))

    fig, ax = plt.subplots(figsize=(7, 3.5))

    # フェーズ背景色
    phase_colors = {
        "導入期": "#FFF9C4", "成長期": "#C8E6C9",
        "成熟期": "#BBDEFB", "衰退期": "#FFCCBC",
    }
    prev_phase = None
    phase_start = 1
    for t in turns + [n_hist + 1]:
        cur_phase = PLC_PHASES_BY_TURN.get(t, prev_phase)
        if cur_phase != prev_phase and prev_phase is not None:
            ax.axvspan(phase_start - 0.5, t - 0.5,
                       facecolor=phase_colors[prev_phase], alpha=0.4)
            ax.text((phase_start + t - 1) / 2, ax.get_ylim()[1] * 0.9,
                    prev_phase, ha="center", fontsize=8, color="gray")
            phase_start = t
        prev_phase = cur_phase

    for key, team in teams.items():
        ax.plot(turns, team["profit_history"], marker="o", markersize=3,
                color=TEAM_COLORS.get(key, "#AAAAAA"),
                label=team["name"], linewidth=1.5)

    ax.axhline(0, color="black", linewidth=0.7, linestyle="--")
    ax.set_title("PLCフェーズ別利益推移", fontsize=11)
    ax.set_xlabel("ターン")
    ax.set_ylabel("利益 (pt)")
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()
    return fig_to_bytes(fig)

# ============================================================
# フィードバックテキスト生成
# ============================================================

def generate_feedback() -> str:
    """プレイヤーの戦略履歴に基づく教育フィードバックを生成。"""
    player     = st.session_state.teams["player"]
    cum_profit = sum(player["profit_history"])
    pos_hist   = player["pos_history"]

    # ポジション変化回数（STP意識度の指標）
    pos_changes = sum(
        1 for i in range(1, len(pos_hist))
        if pos_hist[i] != pos_hist[i - 1]
    )

    # フェーズごとの平均利益
    phase_profits = {}
    for turn, phase in PLC_PHASES_BY_TURN.items():
        idx = turn - 1
        if idx < len(player["profit_history"]):
            phase_profits.setdefault(phase, []).append(player["profit_history"][idx])

    lines = []
    lines.append("## あなたの戦略フィードバック\n")

    # 総合評価
    if cum_profit > 150000:
        lines.append("**総合評価: 優秀** - 競合を上回る利益を達成しました。戦略的意思決定が機能しています。")
    elif cum_profit > 80000:
        lines.append("**総合評価: 良好** - 安定した利益を確保できています。一部フェーズで改善の余地があります。")
    else:
        lines.append("**総合評価: 要改善** - 利益が伸び悩みました。ポジショニングと投資配分を見直しましょう。")

    lines.append("")

    # ポジショニング柔軟性
    lines.append(f"**ポジション変更回数: {pos_changes} 回**")
    if pos_changes == 0:
        lines.append("ポジションを全く変えませんでした。市場変化への適応（リポジショニング）が競争優位につながる場合があります。")
    elif pos_changes <= 3:
        lines.append("ポジションをある程度維持しつつ、要所で変更しました。一貫性と柔軟性のバランスが取れています。")
    else:
        lines.append("積極的にポジションを変更しました。頻繁な変更はブランド混乱を招くリスクもあります。")

    lines.append("")

    # フェーズ別パフォーマンス
    lines.append("**PLCフェーズ別パフォーマンス:**")
    for phase in PHASE_ORDER:
        if phase in phase_profits:
            avg = np.mean(phase_profits[phase])
            lines.append(f"- {phase}: 平均利益 {avg:,.0f} pt")

    lines.append("")
    lines.append("**STP・PLC理論との対応:**")
    lines.append("- セグメンテーション: 4つの市場セグメントのうち、どこを主戦場にしましたか？")
    lines.append("- ターゲティング: 選んだポジションは特定セグメントに響いていましたか？")
    lines.append("- ポジショニング: 競合との差別化は明確でしたか？")
    lines.append("- PLC対応: 各フェーズの特性（マーケティング効果・R&D効果）を活用できましたか？")

    return "\n".join(lines)

# ============================================================
# UI: タイトル画面
# ============================================================

def render_title() -> None:
    st.title("市場参入シミュレーション")
    st.subheader("STP x 製品ライフサイクル 経営戦略ゲーム")

    st.markdown("""
    あなたは新興企業のCEOとして4つのAI競合企業と市場シェアを争います。
    **15ターン** を通じて **ポジショニング** と **投資配分** を意思決定し、
    累計利益で競合を上回ることを目指してください。

    **学習目標**
    - STP分析（セグメンテーション / ターゲティング / ポジショニング）の実践
    - 製品ライフサイクル（PLC）に応じた戦略適応
    - 競合分析と差別化戦略の理解
    """)

    st.divider()

    # 競合プロフィール表示
    st.subheader("競合AIプロフィール")
    cols = st.columns(4)
    for i, (key, profile) in enumerate(AI_PROFILES.items()):
        with cols[i]:
            color = TEAM_COLORS[key]
            st.markdown(
                f"<div style='background:{color}22; border-left:4px solid {color};"
                f"padding:10px; border-radius:4px;'>"
                f"<b style='color:{color}'>{profile['full_name']}</b><br>"
                f"<small>{profile['strategy']}</small>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # 市場セグメント一覧
    st.subheader("市場セグメント")
    seg_data = []
    for name, d in SEGMENTS.items():
        coord = d["coord"]
        seg_data.append({
            "セグメント":     name,
            "価格ポジション": PRICE_LABELS[coord[0]],
            "品質ポジション": QUALITY_LABELS[coord[1]],
            "初期規模":       d["base_size"],
            "PLCスタート":   d["plc_start"],
        })
    st.table(seg_data)

    st.divider()

    # 会社名入力とゲーム開始
    st.subheader("ゲーム開始")
    player_name = st.text_input("あなたの会社名", value="あなたの会社", max_chars=20)
    if st.button("ゲーム開始", type="primary", use_container_width=True):
        init_game_state(player_name.strip() or "あなたの会社")
        st.rerun()

# ============================================================
# UI: ポジショングリッド
# ============================================================

def render_position_grid() -> None:
    """3x3 ポジショニンググリッドをボタンで表示。選択中セルは強調。"""
    st.markdown("**ポジショニングマップ（価格 x 品質）**")
    st.caption("縦: 品質（下=低 / 上=高）、横: 価格（左=低 / 右=高）")

    # 品質を高→低の順で表示（上が高品質）
    for quality_idx in reversed(range(3)):
        cols = st.columns(3)
        for price_idx in range(3):
            label = f"{PRICE_LABELS[price_idx]}\n{QUALITY_LABELS[quality_idx]}"
            is_selected = (
                st.session_state.input_price   == price_idx and
                st.session_state.input_quality == quality_idx
            )
            btn_label = f"✅ {label}" if is_selected else label
            with cols[price_idx]:
                if st.button(
                    btn_label,
                    key=f"pos_{price_idx}_{quality_idx}",
                    use_container_width=True,
                ):
                    st.session_state.input_price   = price_idx
                    st.session_state.input_quality = quality_idx
                    st.rerun()

# ============================================================
# UI: 投資配分スライダー
# ============================================================

def render_investment_sliders() -> tuple[int, int, int]:
    """マーケティング・R&Dスライダーを表示し、(mkt, rd, prod) を返す。"""
    st.markdown("**投資配分（合計100pt）**")

    mkt = st.slider(
        "マーケティング投資",
        min_value=0, max_value=100,
        value=st.session_state.input_mkt,
        key="slider_mkt",
    )
    st.session_state.input_mkt = mkt

    rd_max = 100 - mkt
    rd = st.slider(
        "R&D 投資",
        min_value=0, max_value=rd_max,
        value=min(st.session_state.input_rd, rd_max),
        key="slider_rd",
    )
    st.session_state.input_rd = rd

    prod = 100 - mkt - rd
    st.metric("生産効率（自動）", f"{prod} pt")

    return mkt, rd, prod

# ============================================================
# UI: ゲームプレイ画面
# ============================================================

def render_playing() -> None:
    turn      = st.session_state.turn
    plc_phase = PLC_PHASES_BY_TURN[turn]
    teams     = st.session_state.teams
    player    = teams["player"]

    # --- ヘッダー ---
    # PLCフェーズバッジ
    phase_badge = {
        "導入期": ("🌱", "#FFF9C4", "#856404"),
        "成長期": ("🚀", "#C8E6C9", "#155724"),
        "成熟期": ("🏆", "#BBDEFB", "#004085"),
        "衰退期": ("📉", "#FFCCBC", "#7B3100"),
    }
    icon, bg, fg = phase_badge[plc_phase]
    st.markdown(
        f"<span style='background:{bg};color:{fg};padding:4px 10px;"
        f"border-radius:12px;font-weight:bold;'>{icon} {plc_phase}</span>",
        unsafe_allow_html=True,
    )

    # プログレスバー
    st.progress(turn / TOTAL_TURNS, text=f"ターン {turn} / {TOTAL_TURNS}")

    # 暫定順位
    if st.session_state.turn_results:
        last = st.session_state.turn_results[-1]
        cum_profits = {k: v["cum_profit"] for k, v in last.items()}
        sorted_keys = sorted(cum_profits, key=cum_profits.get, reverse=True)
        rank = sorted_keys.index("player") + 1
        st.caption(f"現在の暫定順位: **{rank} 位** / 5社")

    st.divider()

    # --- メイン 2 カラム ---
    col_left, col_right = st.columns([1.1, 0.9])

    with col_left:
        st.subheader("戦略を選択")

        render_position_grid()

        st.markdown("---")

        mkt, rd, prod = render_investment_sliders()

        st.markdown("---")

        # 実行ボタン
        if st.button("この戦略で実行", type="primary", use_container_width=True):
            # プレイヤーの決定を確定
            player["price_pos"]   = st.session_state.input_price
            player["quality_pos"] = st.session_state.input_quality
            player["mkt"]         = mkt
            player["rd"]          = rd
            player["prod"]        = prod

            # ターン処理実行
            result = process_turn(turn)

            if turn >= TOTAL_TURNS:
                st.session_state.phase = "result"
            else:
                st.session_state.turn += 1

            st.rerun()

    with col_right:
        # 前ターンの結果サマリー
        if st.session_state.turn_results:
            st.subheader("前ターンの結果")
            last_result = st.session_state.turn_results[-1]

            # テーブル
            rows = []
            for key, res in last_result.items():
                rows.append({
                    "チーム":   res["name"],
                    "ポジション": f"{PRICE_LABELS[res['price_pos']]} / {QUALITY_LABELS[res['quality_pos']]}",
                    "シェア":   f"{res['share']*100:.1f}%",
                    "利益":     f"{res['profit']:,.0f}",
                    "累計利益": f"{res['cum_profit']:,.0f}",
                })
            st.table(rows)

            # 利益棒グラフ
            img = draw_profit_bar(last_result)
            st.image(img, use_container_width=True)

        else:
            st.info("ターン 1 です。初めての意思決定を行ってください。")

        st.divider()

        # セグメント情報
        st.subheader("セグメント状況")
        seg_rows = []
        for seg_name, seg_data in SEGMENTS.items():
            seg_phase = get_segment_plc_phase(seg_name, plc_phase)
            current   = st.session_state.segment_sizes[seg_name]
            seg_rows.append({
                "セグメント": seg_name,
                "現在規模":   f"{current:.0f}",
                "フェーズ":   seg_phase,
            })
        st.table(seg_rows)

        st.divider()

        # PLCヒント
        st.subheader(f"{plc_phase} の推奨戦略ヒント")
        for hint in PLC_HINTS[plc_phase]:
            st.markdown(f"- {hint}")

# ============================================================
# UI: 最終結果画面
# ============================================================

REFLECTION_QUESTIONS = [
    "どのPLCフェーズであなたの利益が最も高かったですか？その理由を考えてみましょう。",
    "AI-Gammaはあなたのポジションを模倣しました。これに対してどう対応すべきでしたか？",
    "AI-Deltaは市場フェーズに応じて戦略を変えました。あなたの戦略変更はどう違いましたか？",
    "セグメント「マス市場」と「プレミアム」では最適なポジションが異なります。なぜですか？",
    "もう一度プレイするなら、どのフェーズで何を変えますか？",
]

def render_result() -> None:
    teams  = st.session_state.teams
    player = teams["player"]

    st.title("ゲーム終了 - 最終結果")

    # --- 最終ランキング ---
    st.subheader("最終利益ランキング")
    final_data = []
    for key, team in teams.items():
        final_data.append({
            "key":        key,
            "name":       team["name"],
            "cum_profit": sum(team["profit_history"]),
        })
    final_data.sort(key=lambda x: x["cum_profit"], reverse=True)

    for rank, row in enumerate(final_data, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"{rank}位")
        is_player = row["key"] == "player"
        style = "font-weight:bold;" if is_player else ""
        st.markdown(
            f"<span style='{style}'>{medal} {row['name']} — "
            f"累計利益 **{row['cum_profit']:,.0f} pt**"
            f"{'  ← あなた' if is_player else ''}</span>",
            unsafe_allow_html=True,
        )

    player_rank = next(i + 1 for i, r in enumerate(final_data) if r["key"] == "player")
    st.info(f"あなたの最終順位: **{player_rank} 位** / 5社")

    st.divider()

    # --- グラフ ---
    st.subheader("分析グラフ")
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        st.markdown("**ポジショニング軌跡マップ**")
        st.image(draw_positioning_map(), use_container_width=True)

    with g_col2:
        st.markdown("**PLCフェーズ別利益推移**")
        st.image(draw_plc_profit(), use_container_width=True)

    st.markdown("**累計利益推移**")
    st.image(draw_cumprofit_line(), use_container_width=True)

    st.divider()

    # --- 戦略フィードバック ---
    st.markdown(generate_feedback())

    st.divider()

    # --- 振り返り設問 ---
    st.subheader("振り返り設問")
    st.caption("以下の設問について、グループまたは個人で考えてみましょう。")
    for i, q in enumerate(REFLECTION_QUESTIONS, 1):
        st.markdown(f"**Q{i}.** {q}")
        st.text_area(f"あなたの回答 (Q{i})", key=f"reflection_{i}", height=80)

    st.divider()

    # もう一度プレイ
    if st.button("もう一度プレイ", type="primary", use_container_width=True):
        # session_state をリセット
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.phase = "title"
        st.rerun()

# ============================================================
# メインエントリーポイント
# ============================================================

def main() -> None:
    st.set_page_config(
        page_title="市場参入シミュレーション",
        page_icon="📊",
        layout="wide",
    )

    # 初回アクセス時に phase を設定
    if "phase" not in st.session_state:
        st.session_state.phase = "title"

    phase = st.session_state.phase

    if phase == "title":
        render_title()
    elif phase == "playing":
        render_playing()
    elif phase == "result":
        render_result()
    else:
        st.error(f"不明なフェーズ: {phase}")
        if st.button("タイトルに戻る"):
            st.session_state.phase = "title"
            st.rerun()


if __name__ == "__main__":
    main()
