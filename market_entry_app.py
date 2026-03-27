# market_entry_app.py
# STP x 製品ライフサイクル 競争戦略シミュレーション
# 1人プレイ vs 競合他社4社版
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

# --- 日本語フォント設定 ---
import matplotlib.font_manager as _fm
_JP_FONTS = ["Meiryo", "MS Gothic", "Yu Gothic", "IPAexGothic", "Noto Sans CJK JP"]
_available = {f.name for f in _fm.fontManager.ttflist}
_found = next((f for f in _JP_FONTS if f in _available), None)
if _found:
    rcParams["font.family"] = _found
else:
    rcParams["font.family"] = "sans-serif"
rcParams["axes.unicode_minus"] = False

# ============================================================
# 定数定義
# ============================================================

TOTAL_TURNS = 15

PRICE_LABELS   = ["低価格", "中価格", "高価格"]
QUALITY_LABELS = ["低品質", "中品質", "高品質"]

# セグメント定義
SEGMENTS = {
    "マス市場":   {"coord": (0, 1), "base_size": 400, "plc_start": "成熟期"},
    "プレミアム": {"coord": (2, 2), "base_size": 150, "plc_start": "導入期"},
    "バリュー":   {"coord": (0, 2), "base_size": 250, "plc_start": "成長期"},
    "ニッチ":     {"coord": (2, 0), "base_size":  80, "plc_start": "衰退期"},
}

# PLCフェーズ定義（15ターン）
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

# セグメント別 PLCフェーズオフセット
SEG_PHASE_OFFSET = {
    "マス市場":   2,
    "プレミアム": 0,
    "バリュー":   1,
    "ニッチ":     3,
}

PHASE_ORDER = ["導入期", "成長期", "成熟期", "衰退期"]

# 単価テーブル（価格帯インデックス → 単価）
UNIT_PRICE = {0: 50, 1: 100, 2: 180}

# PLCフェーズバッジ色
PHASE_BADGE = {
    "導入期": ("#FFF9C4", "#856404"),
    "成長期": ("#C8E6C9", "#155724"),
    "成熟期": ("#BBDEFB", "#004085"),
    "衰退期": ("#FFCCBC", "#7B3100"),
}

# プレイヤーおよびAIのカラー（key: "player" / AI名）
ENTITY_COLORS = {
    "player":  "#E74C3C",
    "コストキング":   "#3498DB",
    "プレステージ":   "#2ECC71",
    "ミラー商事":     "#F39C12",
    "カメレオン産業": "#9B59B6",
}

# 競合戦略プロファイル
AI_PROFILES = {
    "コストキング": {
        "full_name": "コストキング",
        "strategy":  "低価格・低品質に固定。コストで勝負するライバル。",
        "price": 0,
        "quality": 0,
    },
    "プレステージ": {
        "full_name": "プレステージ",
        "strategy":  "高価格・高品質に固定。差別化で勝負するライバル。",
        "price": 2,
        "quality": 2,
    },
    "ミラー商事": {
        "full_name": "ミラー商事",
        "strategy":  "あなたの前ターンのポジションをそのまま真似してくるライバル。",
        "price": None,
        "quality": None,
    },
    "カメレオン産業": {
        "full_name": "カメレオン産業",
        "strategy":  "市場の状況（PLCフェーズ）に合わせてポジションを変えるライバル。",
        "price": None,
        "quality": None,
    },
}

# 風見産業のフェーズ別ポジション
DELTA_PHASE_POS = {
    "導入期": (2, 2),
    "成長期": (1, 2),
    "成熟期": (0, 1),
    "衰退期": (0, 0),
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

# 振り返り設問
REFLECTION_QUESTIONS = [
    "どのPLCフェーズであなたの利益が最も高かったですか？その理由を考えてみましょう。",
    "コストキング・プレステージ・ミラー商事・カメレオン産業のどのライバルが最も手強かったですか？その戦略の強みはなぜですか？",
    "PLCフェーズが変わるたびに投資配分をどう変えましたか？その判断は適切でしたか？",
    "セグメント「マス市場」と「プレミアム」では最適なポジションが異なります。なぜですか？",
]

# ============================================================
# ゲームメカニクス（計算ロジック）
# ============================================================

def get_segment_plc_phase(seg_name: str, global_phase: str) -> str:
    """セグメントごとのPLCフェーズを返す（オフセット適用）。"""
    global_idx = PHASE_ORDER.index(global_phase)
    offset     = SEG_PHASE_OFFSET[seg_name]
    seg_idx    = min(global_idx + offset, len(PHASE_ORDER) - 1)
    return PHASE_ORDER[seg_idx]


def calc_distance(p1: int, q1: int, p2: int, q2: int) -> float:
    """ポジション間のユークリッド距離を返す。"""
    return np.sqrt((p1 - p2) ** 2 + (q1 - q2) ** 2)


def calc_ai_position(ai_name: str, turn: int, plc_phase: str,
                     player_prev_price: int, player_prev_quality: int) -> tuple:
    """
    AIのポジションを返す。
    ミラー商事: プレイヤーの前ターン値を模倣（ターン1はデフォルト(1,1)）
    カメレオン産業: PLCフェーズに応じたポジション
    """
    if ai_name == "コストキング":
        return (0, 0)
    elif ai_name == "プレステージ":
        return (2, 2)
    elif ai_name == "ミラー商事":
        if turn == 1:
            return (1, 1)
        return (player_prev_price, player_prev_quality)
    elif ai_name == "カメレオン産業":
        return DELTA_PHASE_POS[plc_phase]
    return (1, 1)


def build_all_entities(turn: int, plc_phase: str, ss: dict) -> dict:
    """
    プレイヤーと競合他社4社のエンティティ辞書を組み立てて返す。
    {entity_key: {price_pos, quality_pos, mkt, rd, prod}}
    """
    entities = {}

    # プレイヤー
    p = ss["player"]
    entities["player"] = {
        "price_pos":   p["price_pos"],
        "quality_pos": p["quality_pos"],
        "mkt":         p["mkt"],
        "rd":          p["rd"],
        "prod":        p["prod"],
    }

    # AI各社
    p_prev_price   = p["pos_history"][-1][0] if p["pos_history"] else 1
    p_prev_quality = p["pos_history"][-1][1] if p["pos_history"] else 1

    for ai_name in AI_PROFILES:
        ai_state = ss["ai_teams"][ai_name]
        pos = calc_ai_position(ai_name, turn, plc_phase, p_prev_price, p_prev_quality)
        entities[ai_name] = {
            "price_pos":   pos[0],
            "quality_pos": pos[1],
            "mkt":         ai_state["mkt"],
            "rd":          ai_state["rd"],
            "prod":        ai_state["prod"],
        }

    return entities


def process_turn(ss: dict) -> dict:
    """
    1ターン分の処理を実行し、全エンティティの結果を返す。
    ss: st.session_state（直接参照・更新）
    戻り値: {entity_key: {profit, seg_results, ...}}
    """
    turn      = ss["turn"]
    plc_phase = PLC_PHASES_BY_TURN[turn]
    seg_sizes = ss["segment_sizes"]

    entities = build_all_entities(turn, plc_phase, ss)
    entity_keys = list(entities.keys())

    # R&D・生産効率の累積更新（プレイヤーのみ。AIは固定）
    ss["player"]["rd_cumulative"]   += ss["player"]["rd"]
    ss["player"]["prod_cumulative"] += ss["player"]["prod"]

    # ---- セグメント別シェア・販売量計算 ----
    seg_vol_all   = {k: 0.0 for k in entity_keys}
    seg_share_all = {k: {seg: 0.0 for seg in SEGMENTS} for k in entity_keys}

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

        # 引力パワー計算
        seg_coord = seg_data["coord"]
        powers = {}
        for k, ent in entities.items():
            dist      = calc_distance(ent["price_pos"], ent["quality_pos"],
                                      seg_coord[0], seg_coord[1])
            mkt_power = ent["mkt"] * PLC_MULTIPLIERS[seg_phase]["marketing"]
            powers[k] = max(mkt_power / (1 + dist ** 2), 0.001)

        total_power = sum(powers.values())
        for k in entity_keys:
            share  = powers[k] / total_power
            volume = current_size * seg_mult["demand"] * share
            seg_share_all[k][seg_name] = share
            seg_vol_all[k] += volume

    # ---- 利益計算 ----
    turn_result = {}

    # プレイヤー
    p          = ss["player"]
    rd         = p["rd"]
    prod       = p["prod"]
    unit_price = UNIT_PRICE[p["price_pos"]]
    margin     = 0.2 + (rd / 100) * 0.5
    fixed_cost = 200 * (1 - prod / 200)
    plc_mult   = PLC_MULTIPLIERS[plc_phase]["demand"]
    volume     = seg_vol_all["player"]
    profit     = volume * unit_price * margin * plc_mult - fixed_cost

    p["profit_history"].append(profit)
    p["pos_history"].append((p["price_pos"], p["quality_pos"]))

    turn_result["player"] = {
        "full_name":   player_name(),
        "price_pos":   p["price_pos"],
        "quality_pos": p["quality_pos"],
        "mkt":         p["mkt"],
        "rd":          p["rd"],
        "prod":        p["prod"],
        "seg_shares":  seg_share_all["player"],
        "total_vol":   volume,
        "profit":      profit,
        "cum_profit":  sum(p["profit_history"]),
    }

    # AI各社
    for ai_name, ai_state in ss["ai_teams"].items():
        ent        = entities[ai_name]
        unit_price = UNIT_PRICE[ent["price_pos"]]
        margin     = 0.2 + (ai_state["rd"] / 100) * 0.5
        fixed_cost = 200 * (1 - ai_state["prod"] / 200)
        volume     = seg_vol_all[ai_name]
        profit     = volume * unit_price * margin * plc_mult - fixed_cost

        ai_state["profit_history"].append(profit)
        ai_state["pos_history"].append((ent["price_pos"], ent["quality_pos"]))

        turn_result[ai_name] = {
            "full_name":   AI_PROFILES[ai_name]["full_name"],
            "price_pos":   ent["price_pos"],
            "quality_pos": ent["quality_pos"],
            "mkt":         ai_state["mkt"],
            "rd":          ai_state["rd"],
            "prod":        ai_state["prod"],
            "seg_shares":  seg_share_all[ai_name],
            "total_vol":   volume,
            "profit":      profit,
            "cum_profit":  sum(ai_state["profit_history"]),
        }

    ss["turn_results"].append(turn_result)
    return turn_result


def player_name() -> str:
    """入力された自社名を返す。未入力時は「あなた」。"""
    return st.session_state.get("company_name", "あなた") or "あなた"


def init_session_state() -> None:
    """ゲーム状態をst.session_stateに初期化する。"""
    st.session_state["phase"] = "title"
    st.session_state["turn"]  = 1
    st.session_state["player"] = {
        "price_pos":      1,
        "quality_pos":    1,
        "mkt":            34,
        "rd":             33,
        "prod":           33,
        "rd_cumulative":  0,
        "prod_cumulative": 0,
        "profit_history": [],
        "pos_history":    [],
    }
    # 競合他社4社の初期状態（固定投資配分）
    st.session_state["ai_teams"] = {
        "コストキング":   {"mkt": 50, "rd": 10, "prod": 40, "profit_history": [], "pos_history": []},
        "プレステージ":   {"mkt": 30, "rd": 40, "prod": 30, "profit_history": [], "pos_history": []},
        "ミラー商事":     {"mkt": 40, "rd": 30, "prod": 30, "profit_history": [], "pos_history": []},
        "カメレオン産業": {"mkt": 35, "rd": 35, "prod": 30, "profit_history": [], "pos_history": []},
    }
    st.session_state["segment_sizes"] = {
        seg: data["base_size"] for seg, data in SEGMENTS.items()
    }
    st.session_state["turn_results"] = []
    # 入力バッファ
    st.session_state["inp_price"]   = 1
    st.session_state["inp_quality"] = 1
    st.session_state["inp_mkt"]     = 34
    st.session_state["inp_rd"]      = 33


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


def draw_grid_preview(sel_price: int, sel_quality: int, submitted: bool) -> bytes:
    """ポジショニングマップ（選択位置を強調したシンプル版）。"""
    SEG_COLORS = {
        "マス市場":   "#E74C3C",
        "プレミアム": "#8E44AD",
        "バリュー":   "#1A9E5F",
        "ニッチ":     "#D35400",
    }

    fig, ax = plt.subplots(figsize=(3.8, 3.8), dpi=110)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#FAFAFA")

    # グリッド線のみ
    for i in [-0.5, 0.5, 1.5, 2.5]:
        ax.axhline(i, color="#DDDDDD", linewidth=0.8, zorder=1)
        ax.axvline(i, color="#DDDDDD", linewidth=0.8, zorder=1)

    # 選択セル強調
    hl = "#2980B9" if not submitted else "#27AE60"
    ax.add_patch(plt.Rectangle(
        (sel_price - 0.5, sel_quality - 0.5), 1.0, 1.0,
        facecolor=hl, alpha=0.15, zorder=2
    ))
    ax.add_patch(plt.Rectangle(
        (sel_price - 0.5, sel_quality - 0.5), 1.0, 1.0,
        facecolor="none", edgecolor=hl, linewidth=2.2, zorder=3
    ))
    ax.plot(sel_price, sel_quality, marker="o", markersize=14,
            color=hl, zorder=4, alpha=0.85)

    # セグメントマーカー（★ + 名前）
    for seg_name, seg_data in SEGMENTS.items():
        px, qy = seg_data["coord"]
        c = SEG_COLORS[seg_name]
        ax.scatter(px, qy, s=120, marker="*", color=c,
                   edgecolors="white", linewidths=0.5, zorder=5)
        ax.text(px, qy - 0.32, seg_name,
                ha="center", va="top",
                fontsize=7, color=c, fontweight="bold", zorder=5)

    # 軸
    ax.set_xlim(-0.5, 2.5)
    ax.set_ylim(-0.5, 2.5)
    ax.set_xticks([0, 1, 2])
    ax.set_yticks([0, 1, 2])
    ax.set_xticklabels(PRICE_LABELS, fontsize=9)
    ax.set_yticklabels(QUALITY_LABELS, fontsize=9)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_edgecolor("#CCCCCC")
    ax.set_title("ポジショニングマップ", fontsize=10, pad=6, fontweight="bold")

    fig.tight_layout(pad=0.5)
    return fig_to_bytes(fig)


def draw_positioning_map(ss: dict) -> bytes:
    """全エンティティの全ターン分ポジショニング軌跡散布図。"""
    fig, ax = plt.subplots(figsize=(5, 5))

    for seg_name, seg_data in SEGMENTS.items():
        px, qy = seg_data["coord"]
        ax.scatter(px, qy, s=200, marker="*", color="gold", zorder=2,
                   edgecolors="gray", linewidths=0.5)
        ax.text(px + 0.08, qy + 0.08, seg_name, fontsize=7, color="dimgray")

    # プレイヤー
    p     = ss["player"]
    xs    = [pos[0] for pos in p["pos_history"]]
    ys    = [pos[1] for pos in p["pos_history"]]
    color = ENTITY_COLORS["player"]
    if xs:
        ax.plot(xs, ys, color=color, alpha=0.6, linewidth=2.0)
        ax.scatter(xs, ys, c=color, s=50, zorder=3, alpha=0.8)
        ax.text(xs[-1] + 0.07, ys[-1] + 0.07, player_name(),
                fontsize=8, color=color, fontweight="bold")

    # AI各社
    for ai_name, ai_state in ss["ai_teams"].items():
        xs    = [pos[0] for pos in ai_state["pos_history"]]
        ys    = [pos[1] for pos in ai_state["pos_history"]]
        color = ENTITY_COLORS[ai_name]
        if xs:
            ax.plot(xs, ys, color=color, alpha=0.5, linewidth=1.2)
            ax.scatter(xs, ys, c=color, s=30, zorder=3, alpha=0.7)
            ax.text(xs[-1] + 0.07, ys[-1] + 0.07, ai_name, fontsize=7, color=color)

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


def draw_plc_profit(ss: dict) -> bytes:
    """PLCフェーズ別利益推移（フェーズ帯を背景色で表現）。"""
    n_hist = len(ss["player"]["profit_history"])
    if n_hist == 0:
        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.text(0.5, 0.5, "データなし", ha="center", va="center")
        return fig_to_bytes(fig)

    turns = list(range(1, n_hist + 1))
    fig, ax = plt.subplots(figsize=(7, 3.5))

    phase_colors = {
        "導入期": "#FFF9C4", "成長期": "#C8E6C9",
        "成熟期": "#BBDEFB", "衰退期": "#FFCCBC",
    }
    prev_phase  = None
    phase_start = 1
    for t in turns + [n_hist + 1]:
        cur_phase = PLC_PHASES_BY_TURN.get(t, prev_phase)
        if cur_phase != prev_phase and prev_phase is not None:
            ax.axvspan(phase_start - 0.5, t - 0.5,
                       facecolor=phase_colors[prev_phase], alpha=0.4)
            phase_start = t
        prev_phase = cur_phase

    # プレイヤー
    ax.plot(turns, ss["player"]["profit_history"],
            marker="o", markersize=3,
            color=ENTITY_COLORS["player"],
            label=player_name(), linewidth=2.0)

    # AI各社
    for ai_name, ai_state in ss["ai_teams"].items():
        hist = ai_state["profit_history"][:n_hist]
        if hist:
            ax.plot(turns[:len(hist)], hist,
                    marker="o", markersize=3,
                    color=ENTITY_COLORS[ai_name],
                    label=ai_name, linewidth=1.5)

    ax.axhline(0, color="black", linewidth=0.7, linestyle="--")
    ax.set_title("PLCフェーズ別利益推移", fontsize=11)
    ax.set_xlabel("ターン")
    ax.set_ylabel("利益 (pt)")
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()
    return fig_to_bytes(fig)


def draw_cum_profit_bar(ss: dict) -> bytes:
    """全5社の累計利益比較棒グラフ。"""
    labels  = [player_name()] + list(AI_PROFILES.keys())
    keys    = ["player"] + list(AI_PROFILES.keys())
    profits = []
    for k in keys:
        if k == "player":
            profits.append(sum(ss["player"]["profit_history"]))
        else:
            profits.append(sum(ss["ai_teams"][k]["profit_history"]))
    colors = [ENTITY_COLORS[k] for k in keys]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    bars = ax.bar(labels, profits, color=colors, edgecolor="white", linewidth=0.5)
    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax.set_title("累計利益比較", fontsize=11)
    ax.set_ylabel("累計利益 (pt)")
    max_p = max(profits) if profits else 1
    for bar, val in zip(bars, profits):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(abs(max_p) * 0.02, 50),
                f"{val:,.0f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    return fig_to_bytes(fig)


# ============================================================
# PLCフェーズバッジ
# ============================================================

def render_plc_badge(phase: str) -> None:
    bg, fg = PHASE_BADGE[phase]
    st.markdown(
        f"<span style='background:{bg};color:{fg};padding:4px 12px;"
        f"border-radius:12px;font-weight:bold;font-size:1rem;'>{phase}</span>",
        unsafe_allow_html=True,
    )


# ============================================================
# 画面1: タイトル画面
# ============================================================

def render_title() -> None:
    st.title("市場参入シミュレーション")
    st.caption("STP × 製品ライフサイクル 競争戦略ゲーム")

    # 自社名入力
    st.divider()
    st.subheader("あなたの会社名を入力してください")
    company_name = st.text_input(
        "会社名",
        value=st.session_state.get("company_name", ""),
        placeholder="例：山田商事、チームA、など",
        max_chars=20,
    )
    st.session_state["company_name"] = company_name or "あなた"

    st.divider()

    # STP説明
    with st.expander("STP分析とは？"):
        st.markdown("""
**STP分析**は、効果的なマーケティング戦略を立てるためのフレームワークです。

| ステップ | 内容 | このゲームでは |
|---|---|---|
| **S**egmentation（市場細分化） | 市場を特性の似たグループに分ける | マス市場・プレミアム・バリュー・ニッチの4セグメント |
| **T**argeting（ターゲット選定） | どのグループを狙うかを決める | ポジショニングマップで自社の位置を選択 |
| **P**ositioning（ポジショニング） | 競合との差別化を図る | 価格帯×品質帯の3×3マスで定義 |

> **ポーターの競争戦略との関係**
> - コストリーダーシップ → 低価格ゾーン
> - 差別化戦略 → 高品質ゾーン
> - 集中戦略 → 特定セグメントへの特化
        """)

    # PLC説明
    with st.expander("製品ライフサイクル（PLC）とは？"):
        st.markdown("""
**製品ライフサイクル（Product Life Cycle）**は、製品・市場が時間とともにたどる4つのフェーズです。

| フェーズ | ターン | 特徴 | 有効な戦略 |
|---|---|---|---|
| 🌱 **導入期** | 1〜3 | 市場が小さく認知度が低い | 広告・宣伝費を多く投じて認知拡大 |
| 🚀 **成長期** | 4〜7 | 需要が急拡大 | シェア獲得を優先・ポジション確立 |
| ⚖️ **成熟期** | 8〜11 | 需要が安定・競争激化 | コスト削減・R&D投資で差別化 |
| 📉 **衰退期** | 12〜15 | 需要が縮小 | ニッチ特化 or 撤退も選択肢 |

> **注意**：このゲームでは、セグメントごとにPLCのタイミングが異なります。
> マス市場はすでに成熟期からスタートし、プレミアムは導入期から始まります。
        """)

    # ゲームルール
    with st.expander("ゲームルール"):
        st.markdown("""
**ゲームの流れ**
- 全15ターン。毎ターン、ポジションと投資配分を決定します。
- 競合他社4社と市場シェアを奪い合い、累計利益の最大化を目指します。

**投資配分（合計100pt）**
- **広告・宣伝費**：多いほどセグメントに自社を認知させ、シェアが上がる
- **R&D（研究開発費）**：多いほど粗利率が上がる（品質向上）
- **生産効率**：多いほど固定費が下がる（コスト削減）

**セグメント一覧**
        """)
        seg_rows = []
        for name, d in SEGMENTS.items():
            coord = d["coord"]
            seg_rows.append({
                "セグメント":   name,
                "価格":        PRICE_LABELS[coord[0]],
                "品質":        QUALITY_LABELS[coord[1]],
                "初期市場規模": d["base_size"],
                "PLCスタート": d["plc_start"],
            })
        st.table(seg_rows)

    st.divider()

    # 競合他社プロファイル
    st.subheader("競合他社4社のプロファイル")
    ai_rows = []
    for profile in AI_PROFILES.values():
        ai_rows.append({
            "社名": profile["full_name"],
            "戦略": profile["strategy"],
        })
    st.table(ai_rows)

    st.divider()

    if not st.session_state.get("company_name", ""):
        st.warning("会社名を入力してからゲームを開始してください。")
    if st.button("ゲーム開始", type="primary", use_container_width=True,
                 disabled=not st.session_state.get("company_name", "")):
        init_session_state()
        st.session_state["phase"] = "playing"
        st.rerun()


# ============================================================
# 画面2: ゲームプレイ画面
# ============================================================

def render_playing() -> None:
    ss        = st.session_state
    turn      = ss["turn"]
    plc_phase = PLC_PHASES_BY_TURN[turn]

    # プログレスバー
    st.progress(turn / TOTAL_TURNS, text=f"ターン {turn} / {TOTAL_TURNS}")
    render_plc_badge(plc_phase)
    st.markdown("")

    col_left, col_right = st.columns([1.1, 0.9])

    # ============ 左カラム: 意思決定 ============
    with col_left:
        st.subheader("戦略を選択")

        # セグメント別PLCフェーズ状況
        with st.expander("セグメント別PLCフェーズ状況"):
            seg_rows = []
            for seg_name, seg_data in SEGMENTS.items():
                seg_phase = get_segment_plc_phase(seg_name, plc_phase)
                current   = ss["segment_sizes"].get(seg_name, seg_data["base_size"])
                hints_map = {
                    "導入期": "認知拡大期。広告・宣伝費が重要。",
                    "成長期": "需要拡大中。シェア争奪。",
                    "成熟期": "安定期。効率化が鍵。",
                    "衰退期": "縮小中。集中か撤退。",
                }
                seg_rows.append({
                    "セグメント":     seg_name,
                    "現在規模":       f"{current:.0f}",
                    "フェーズ":       seg_phase,
                    "位置":           f"{PRICE_LABELS[seg_data['coord'][0]]} / {QUALITY_LABELS[seg_data['coord'][1]]}",
                    "ヒント":         hints_map[seg_phase],
                })
            st.table(seg_rows)


        # 3×3セル選択ボタン
        st.caption("クリックしてポジションを選択")
        CELL_ICONS_DISPLAY = [
            ["[安]", "[均]", "[高]"],
            ["[量]", "[的]", "[宝]"],
            ["[効]", "[速]", "[革]"],
        ]
        for quality_idx in reversed(range(3)):
            gcols = st.columns(3)
            for price_idx in range(3):
                is_selected = (
                    ss.get("inp_price", 1) == price_idx and
                    ss.get("inp_quality", 1) == quality_idx
                )
                icon  = CELL_ICONS_DISPLAY[quality_idx][price_idx]
                label = (
                    f"[選択済] {icon} {PRICE_LABELS[price_idx]}x{QUALITY_LABELS[quality_idx]}"
                    if is_selected else
                    f"{icon} {PRICE_LABELS[price_idx]}x{QUALITY_LABELS[quality_idx]}"
                )
                with gcols[price_idx]:
                    if st.button(
                        label,
                        key=f"pos_{price_idx}_{quality_idx}_t{turn}",
                        use_container_width=True,
                        type="primary" if is_selected else "secondary",
                    ):
                        ss["inp_price"]   = price_idx
                        ss["inp_quality"] = quality_idx
                        st.rerun()

        st.markdown("---")

        # 投資配分スライダー
        st.markdown("**投資配分（合計100pt）**")

        mkt = st.slider(
            "広告・宣伝費（シェア獲得に影響）",
            min_value=0, max_value=100,
            value=ss.get("inp_mkt", 34),
            key=f"slider_mkt_t{turn}",
        )
        ss["inp_mkt"] = mkt

        rd_max = 100 - mkt
        rd = st.slider(
            "R&D投資 (rd)",
            min_value=0, max_value=rd_max,
            value=min(ss.get("inp_rd", 33), rd_max),
            key=f"slider_rd_t{turn}",
        )
        ss["inp_rd"] = rd

        prod = 100 - mkt - rd
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("広告・宣伝費", f"{mkt} pt")
        col_b.metric("R&D", f"{rd} pt")
        col_c.metric("生産効率（自動）", f"{prod} pt")

        st.markdown("---")

        # ターン実行ボタン
        if st.button("ターン実行", type="primary", use_container_width=True):
            # プレイヤーの入力を確定
            ss["player"]["price_pos"]   = ss["inp_price"]
            ss["player"]["quality_pos"] = ss["inp_quality"]
            ss["player"]["mkt"]         = mkt
            ss["player"]["rd"]          = rd
            ss["player"]["prod"]        = prod

            # ターン計算
            process_turn(ss)

            # フェーズ遷移
            if turn >= TOTAL_TURNS:
                ss["phase"] = "result"
            else:
                ss["phase"] = "turn_result"

            st.rerun()

    # ============ 右カラム: 状況 ============
    with col_right:
        p         = ss["player"]
        cum_profit = sum(p["profit_history"])
        st.metric("現在の累計利益", f"{cum_profit:,.0f} pt")

        st.divider()

        # 前ターンの結果
        if ss["turn_results"]:
            last_result = ss["turn_results"][-1]
            pr = last_result["player"]
            st.subheader("前ターンの結果")

            c1, c2 = st.columns(2)
            c1.metric("今期利益", f"{pr['profit']:,.0f} pt")
            c2.metric("累計利益", f"{pr['cum_profit']:,.0f} pt")
            st.caption(
                f"ポジション: {PRICE_LABELS[pr['price_pos']]} / {QUALITY_LABELS[pr['quality_pos']]}  |  "
                f"販売量: {pr['total_vol']:.1f}"
            )

            st.divider()

            # AIとの利益比較棒グラフ
            st.subheader("累計利益ランキング")
            all_cum = {player_name(): pr["cum_profit"]}
            for ai_name in AI_PROFILES:
                all_cum[ai_name] = last_result[ai_name]["cum_profit"]

            ranking = sorted(all_cum.items(), key=lambda x: x[1], reverse=True)
            for rank, (name, cum) in enumerate(ranking, 1):
                key   = "player" if name == "あなた" else name
                color = ENTITY_COLORS[key]
                me    = "  (あなた)" if name == "あなた" else ""
                st.markdown(
                    f"<div style='padding:3px 8px;margin-bottom:2px;"
                    f"border-left:3px solid {color};'>"
                    f"<b>{rank}位</b> <span style='color:{color}'>{name}</span>"
                    f" {cum:,.0f} pt{me}</div>",
                    unsafe_allow_html=True,
                )

            st.divider()

            # セグメント別シェア表示
            with st.expander("前ターンのセグメント別シェア"):
                share_rows = []
                for seg_name in SEGMENTS:
                    row = {"セグメント": seg_name}
                    row[player_name()] = f"{pr['seg_shares'].get(seg_name, 0)*100:.1f}%"
                    for ai_name in AI_PROFILES:
                        row[ai_name] = f"{last_result[ai_name]['seg_shares'].get(seg_name, 0)*100:.1f}%"
                    share_rows.append(row)
                st.table(share_rows)

        else:
            st.info("ターン1です。初めての意思決定を行ってください。")

        st.divider()

        # PLCヒント
        st.subheader(f"{plc_phase} の戦略ヒント")
        for hint in PLC_HINTS[plc_phase]:
            st.markdown(f"- {hint}")


# ============================================================
# 画面3: ターン結果（インライン表示）
# ============================================================

def render_turn_result() -> None:
    ss          = st.session_state
    turn        = ss["turn"]
    plc_phase   = PLC_PHASES_BY_TURN[turn]
    last_result = ss["turn_results"][-1]

    st.title(f"ターン {turn} 結果")
    render_plc_badge(plc_phase)
    st.markdown("")

    # 全5社の結果テーブル
    st.subheader("全社結果")
    rows = []
    entity_order = ["player"] + list(AI_PROFILES.keys())
    for k in entity_order:
        r    = last_result[k]
        name = r["full_name"]
        rows.append({
            "社名":         name,
            "ポジション":   f"{PRICE_LABELS[r['price_pos']]} / {QUALITY_LABELS[r['quality_pos']]}",
            "広告/R&D/生産": f"{r['mkt']}/{r['rd']}/{r['prod']}",
            "販売量":       f"{r['total_vol']:.1f}",
            "今期利益":     f"{r['profit']:,.0f}",
            "累計利益":     f"{r['cum_profit']:,.0f}",
        })
    st.table(rows)

    # 累計利益棒グラフ
    st.image(draw_cum_profit_bar(ss), use_container_width=True)

    st.divider()

    # セグメント需要変化
    st.subheader("セグメント需要の変化")
    seg_cols = st.columns(len(SEGMENTS))
    for i, (seg_name, seg_data) in enumerate(SEGMENTS.items()):
        seg_phase = get_segment_plc_phase(seg_name, plc_phase)
        current   = ss["segment_sizes"][seg_name]
        bg, fg    = PHASE_BADGE.get(seg_phase, ("#eee", "#333"))
        with seg_cols[i]:
            st.markdown(
                f"<div style='border:1px solid {fg};border-radius:6px;"
                f"padding:8px;background:{bg};text-align:center;'>"
                f"<b>{seg_name}</b><br>"
                f"規模: {current:.0f}<br>"
                f"<small style='color:{fg}'>{seg_phase}</small>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # 次ターン予告
    next_turn = turn + 1
    if next_turn <= TOTAL_TURNS:
        next_phase = PLC_PHASES_BY_TURN[next_turn]
        st.subheader(f"次のターン ({next_turn}) のPLCフェーズ予告")
        render_plc_badge(next_phase)
        st.markdown("")
        for hint in PLC_HINTS[next_phase]:
            st.markdown(f"- {hint}")

    st.divider()

    # 「次のターンへ」ボタン
    if st.button("次のターンへ", type="primary", use_container_width=True):
        ss["turn"] += 1
        ss["phase"] = "playing"
        # 入力バッファを前ターンのポジションで初期化
        ss["inp_price"]   = ss["player"]["price_pos"]
        ss["inp_quality"] = ss["player"]["quality_pos"]
        ss["inp_mkt"]     = ss["player"]["mkt"]
        ss["inp_rd"]      = ss["player"]["rd"]
        st.rerun()


# ============================================================
# 画面4: 最終結果画面
# ============================================================

def render_result() -> None:
    ss = st.session_state

    st.title("ゲーム終了 - 最終結果")

    # 最終ランキング
    st.subheader("最終利益ランキング")

    final_data = []
    final_data.append({
        "key": "player", "name": player_name(),
        "cum_profit": sum(ss["player"]["profit_history"]),
    })
    for ai_name in AI_PROFILES:
        final_data.append({
            "key": ai_name,
            "name": AI_PROFILES[ai_name]["full_name"],
            "cum_profit": sum(ss["ai_teams"][ai_name]["profit_history"]),
        })
    final_data.sort(key=lambda x: x["cum_profit"], reverse=True)

    player_rank = next(i + 1 for i, d in enumerate(final_data) if d["key"] == "player")
    rank_msgs = {1: "優勝！すばらしい戦略でした。", 2: "2位！惜しくも2位でした。",
                 3: "3位でした。", 4: "4位でした。", 5: "5位でした。次は戦略を変えてみましょう。"}
    st.info(f"あなたの順位: {player_rank}位 — {rank_msgs.get(player_rank, '')}")

    for rank, row in enumerate(final_data, 1):
        color  = ENTITY_COLORS[row["key"]]
        me_tag = "  ← あなた" if row["key"] == "player" else ""
        st.markdown(
            f"<div style='border-left:5px solid {color};padding:8px 14px;"
            f"margin-bottom:6px;background:{color}11;font-size:1rem;'>"
            f"<b>{rank}位</b>  "
            f"<span style='color:{color}'>{row['name']}</span>"
            f" &nbsp; 累計利益 <b>{row['cum_profit']:,.0f} pt</b>{me_tag}"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # 分析グラフ
    st.subheader("分析グラフ")

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**ポジショニング軌跡マップ**")
        st.image(draw_positioning_map(ss), use_container_width=True)
    with g2:
        st.markdown("**PLCフェーズ別利益推移**")
        st.image(draw_plc_profit(ss), use_container_width=True)

    st.markdown("**累計利益比較（最終）**")
    st.image(draw_cum_profit_bar(ss), use_container_width=True)

    st.divider()

    # PLCフェーズ別戦略サマリー（全5社）
    st.subheader("PLCフェーズ別 戦略サマリー")

    phase_turn_map = {
        "導入期": list(range(1, 4)),
        "成長期": list(range(4, 8)),
        "成熟期": list(range(8, 12)),
        "衰退期": list(range(12, 16)),
    }

    for phase_name, phase_turns in phase_turn_map.items():
        with st.expander(f"{phase_name}（ターン {phase_turns[0]}〜{phase_turns[-1]}）"):
            summary_rows = []

            # プレイヤー
            p_profits = [
                ss["player"]["profit_history"][t - 1]
                for t in phase_turns if t - 1 < len(ss["player"]["profit_history"])
            ]
            p_positions = [
                ss["player"]["pos_history"][t - 1]
                for t in phase_turns if t - 1 < len(ss["player"]["pos_history"])
            ]
            avg_p = np.mean(p_profits) if p_profits else 0
            pos_str = ", ".join(
                f"{PRICE_LABELS[pos[0]]}/{QUALITY_LABELS[pos[1]]}" for pos in p_positions
            ) if p_positions else "-"
            summary_rows.append({
                "社名":         player_name(),
                "平均利益":     f"{avg_p:,.0f}",
                "ポジション履歴": pos_str,
            })

            # AI各社
            for ai_name in AI_PROFILES:
                ai_state = ss["ai_teams"][ai_name]
                ai_profits = [
                    ai_state["profit_history"][t - 1]
                    for t in phase_turns if t - 1 < len(ai_state["profit_history"])
                ]
                ai_positions = [
                    ai_state["pos_history"][t - 1]
                    for t in phase_turns if t - 1 < len(ai_state["pos_history"])
                ]
                avg_a = np.mean(ai_profits) if ai_profits else 0
                pos_str = ", ".join(
                    f"{PRICE_LABELS[pos[0]]}/{QUALITY_LABELS[pos[1]]}" for pos in ai_positions
                ) if ai_positions else "-"
                summary_rows.append({
                    "社名":         AI_PROFILES[ai_name]["full_name"],
                    "平均利益":     f"{avg_a:,.0f}",
                    "ポジション履歴": pos_str,
                })

            st.table(summary_rows)

    st.divider()

    # 振り返り設問
    st.subheader("振り返り設問")
    st.caption("以下の設問について考えてみましょう。")
    for i, q in enumerate(REFLECTION_QUESTIONS, 1):
        st.markdown(f"**Q{i}.** {q}")
        st.text_area(f"回答 (Q{i})", key=f"reflection_{i}", height=80)

    st.divider()

    # もう一度プレイ
    if st.button("もう一度プレイ", type="primary", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ============================================================
# メインエントリーポイント
# ============================================================

def main() -> None:
    st.set_page_config(
        page_title="市場参入シミュレーション",
        page_icon="S",
        layout="wide",
    )

    # 初回アクセス時は title フェーズ
    if "phase" not in st.session_state:
        st.session_state["phase"] = "title"

    phase = st.session_state["phase"]

    if phase == "title":
        render_title()
    elif phase == "playing":
        render_playing()
    elif phase == "turn_result":
        render_turn_result()
    elif phase == "result":
        render_result()
    else:
        st.error(f"不明なフェーズ: {phase}")
        if st.button("最初に戻る"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


if __name__ == "__main__":
    main()
