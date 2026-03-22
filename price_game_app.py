"""
price_game_app.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
価格競争シミュレーション  〜 Market War 〜
Streamlit版  大学経営戦略授業用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
実行: streamlit run price_game_app.py
"""

import random
import math
from typing import List
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import io

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ゲームパラメータ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL_TURNS       = 10
FIXED_COST        = 20.0
MAX_DEMAND        = 1000.0
PRICE_ELASTICITY  = 0.03
PRICE_MIN         = 21.0
PRICE_MAX         = 120.0
IMITATOR_NOISE    = 0.05
COST_FIRM_BASE    = 28.0
COST_FIRM_NOISE   = 2.0
RANDOM_FIRM_LOW   = 25.0
RANDOM_FIRM_HIGH  = 70.0
SHARE_SENSITIVITY = 2.0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 経済モデル
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def total_demand(prices: List[float]) -> float:
    avg_price = sum(prices) / len(prices)
    return max(MAX_DEMAND * math.exp(-PRICE_ELASTICITY * avg_price), 0.0)

def market_shares(prices: List[float]) -> List[float]:
    weights = [math.exp(-SHARE_SENSITIVITY * p) for p in prices]
    total_w = sum(weights)
    if total_w == 0:
        return [1.0 / len(prices)] * len(prices)
    return [w / total_w for w in weights]

def calc_profit(price: float, share: float, demand: float) -> float:
    return (price - FIXED_COST) * share * demand

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI競合クラス（シリアライズ可能な辞書形式で管理）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_ai_firms():
    return [
        {
            "name": "競合A（模倣型）",
            "type": "imitator",
            "price": 40.0,
            "price_history": [40.0],
            "profit_history": [],
        },
        {
            "name": "競合B（低価格型）",
            "type": "cost",
            "price": COST_FIRM_BASE,
            "price_history": [COST_FIRM_BASE],
            "profit_history": [],
        },
        {
            "name": "競合C（ランダム型）",
            "type": "random",
            "price": random.uniform(RANDOM_FIRM_LOW, RANDOM_FIRM_HIGH),
            "price_history": [random.uniform(RANDOM_FIRM_LOW, RANDOM_FIRM_HIGH)],
            "profit_history": [],
        },
    ]

def ai_decide_price(firm: dict, player_last_price: float) -> float:
    def clamp(p):
        return max(PRICE_MIN, min(PRICE_MAX, p))
    if firm["type"] == "imitator":
        noise = random.uniform(-IMITATOR_NOISE, IMITATOR_NOISE)
        return clamp(player_last_price * (1.0 + noise))
    elif firm["type"] == "cost":
        noise = random.uniform(-COST_FIRM_NOISE, COST_FIRM_NOISE)
        return clamp(COST_FIRM_BASE + noise)
    else:
        return clamp(random.uniform(RANDOM_FIRM_LOW, RANDOM_FIRM_HIGH))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# フィードバック生成
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def generate_feedback(player_prices, player_profits, ai_firms):
    avg_price   = sum(player_prices) / len(player_prices)
    price_std   = math.sqrt(sum((p - avg_price)**2 for p in player_prices) / len(player_prices))
    total_profit = sum(player_profits)

    if avg_price < 35.0:
        porter = "**コストリーダーシップ**に近い価格設定でした。マージンが薄く、大量販売が前提になります。競合B（低価格型）との直接競争になっていた可能性があります。"
    elif avg_price < 55.0:
        porter = "**バランス型**の価格設定でした。コストリーダーでも差別化でもない「中間」に位置します。ポーターはこれを「どっちつかず（Stuck in the Middle）」と警告しています。"
    else:
        porter = "**差別化戦略**的な高価格設定でした。高マージンを狙うが、シェアは犠牲になります。顧客が「高くても買う理由」を持っているかが鍵です。"

    if price_std < 5.0:
        volatility = "価格設定が一貫していました（安定戦略）。"
    elif price_std < 15.0:
        volatility = "価格をある程度調整しながらプレイしました（適応戦略）。"
    else:
        volatility = "価格変動が大きかったです。大幅な価格変更は競合を刺激し、報復を招きやすいです。"

    best_ai = max(sum(f["profit_history"]) for f in ai_firms)
    if total_profit >= best_ai * 1.2:
        game_theory = "競合を大きく上回る利益を獲得しました。競合の戦略パターンを読み、有効な対応ができていた可能性があります。"
    elif total_profit >= best_ai * 0.9:
        game_theory = "競合とほぼ同等の結果でした。市場が均衡に近い状態（ナッシュ均衡的状況）だったかもしれません。"
    else:
        game_theory = "競合に比べ利益が低い結果となりました。競合の価格を観察し、より意図的な価格戦略を試してみましょう。"

    all_results = [("あなた", total_profit)] + [(f["name"], sum(f["profit_history"])) for f in ai_firms]
    all_results.sort(key=lambda x: x[1], reverse=True)
    rank = next(i + 1 for i, (n, _) in enumerate(all_results) if n == "あなた")

    return {
        "avg_price": avg_price,
        "price_std": price_std,
        "total_profit": total_profit,
        "rank": rank,
        "porter": porter,
        "volatility": volatility,
        "game_theory": game_theory,
        "ranking": all_results,
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# グラフ生成
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_charts(player_prices, player_profits, ai_firms):
    turns = list(range(1, TOTAL_TURNS + 1))
    colors = ["tomato", "seagreen", "darkorange"]

    fig, axes = plt.subplots(2, 1, figsize=(10, 7))
    fig.patch.set_facecolor("#0e1117")
    for ax in axes:
        ax.set_facecolor("#262730")
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#555")

    # 価格推移
    ax1 = axes[0]
    ax1.plot(turns, player_prices, marker="o", lw=2.5, label="あなた", color="#4f8ef7", zorder=5)
    for ai, color in zip(ai_firms, colors):
        ax1.plot(turns, ai["price_history"][1:], marker="s", lw=1.5, ls="--",
                 label=ai["name"], color=color, alpha=0.85)
    ax1.axhline(y=FIXED_COST, color="#aaa", ls=":", lw=1.2, label=f"固定コスト ({FIXED_COST:.0f}円)")
    ax1.set_title("各ターンの価格設定推移", fontsize=12)
    ax1.set_ylabel("価格（円）", color="white")
    ax1.set_xticks(turns)
    ax1.legend(fontsize=8, facecolor="#1e1e2e", labelcolor="white")
    ax1.grid(True, alpha=0.2)

    # 累計利益推移
    ax2 = axes[1]
    cumulative_player = []
    running = 0.0
    for p in player_profits:
        running += p
        cumulative_player.append(running)
    ax2.plot(turns, cumulative_player, marker="o", lw=2.5, label="あなた", color="#4f8ef7", zorder=5)
    for ai, color in zip(ai_firms, colors):
        cumul_ai = []
        r = 0.0
        for p in ai["profit_history"]:
            r += p
            cumul_ai.append(r)
        ax2.plot(turns, cumul_ai, marker="s", lw=1.5, ls="--",
                 label=ai["name"], color=color, alpha=0.85)
    ax2.set_title("累計利益推移", fontsize=12)
    ax2.set_ylabel("累計利益（円）", color="white")
    ax2.set_xticks(turns)
    ax2.legend(fontsize=8, facecolor="#1e1e2e", labelcolor="white")
    ax2.grid(True, alpha=0.2)
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    plt.tight_layout(pad=2.0)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# セッション状態の初期化
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def init_state():
    st.session_state.game_started     = False
    st.session_state.turn             = 1
    st.session_state.ai_firms         = make_ai_firms()
    st.session_state.player_prices    = []
    st.session_state.player_profits   = []
    st.session_state.player_last_price = 50.0
    st.session_state.player_cumulative = 0.0
    st.session_state.current_ai_prices = None   # 今ターンのAI価格（入力前に決定）
    st.session_state.awaiting_input   = False    # 入力待ち状態
    st.session_state.turn_result      = None     # 直前ターンの結果
    st.session_state.game_over        = False

if "game_started" not in st.session_state:
    init_state()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ページ設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(
    page_title="Market War | 価格競争シミュレーション",
    page_icon="📈",
    layout="wide",
)

st.markdown("""
<style>
    .big-title { font-size: 2rem; font-weight: bold; text-align: center; margin-bottom: 0; }
    .sub-title { text-align: center; color: #888; margin-top: 0; }
    .result-box { background: #1e1e2e; border-radius: 10px; padding: 1rem 1.5rem; margin: 0.5rem 0; }
    .profit-number { font-size: 1.8rem; font-weight: bold; color: #4f8ef7; }
    .rank-badge { font-size: 1.2rem; font-weight: bold; }
    div[data-testid="stHorizontalBlock"] { align-items: flex-end; }
</style>
""", unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# タイトル画面
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if not st.session_state.game_started:
    st.markdown('<p class="big-title">📈 Market War</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">価格競争シミュレーション ─ 大学経営戦略授業用</p>', unsafe_allow_html=True)
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### あなたの役割")
        st.info("あなたは新興企業のCEOです。\n3社の競合と**10ターン**にわたって価格競争を繰り広げます。\n最終的に**累計利益を最大化**した企業の勝利です。")

        st.markdown("### 競合プロフィール")
        st.markdown("""
| 競合 | 戦略 | 特徴 |
|---|---|---|
| 競合A | 模倣型 | あなたの価格を追いかけてきます |
| 競合B | 低価格型 | 常に低コスト・安定価格で戦います |
| 競合C | ランダム型 | 価格が読めない予測困難なプレイヤー |
""")

    with col2:
        st.markdown("### ゲームの仕組み")
        st.markdown("""
- **固定コスト**: 20円/単位（これ以上の価格を設定してください）
- **設定価格範囲**: 21円 〜 120円
- **需要**: 市場平均価格が高いほど総需要は縮小します
- **シェア**: 相対的に低価格な企業ほど市場シェアが増えます
- **利益** = （価格 − コスト）× シェア × 総需要
""")
        st.markdown("### 教育目標")
        st.markdown("""
1. 価格弾力性と市場需要の関係を体験的に理解する
2. 競合の価格戦略に対する最適応答戦略を探索する
3. マージン vs シェアのトレードオフを学ぶ
""")

    st.divider()
    col_center = st.columns([1, 2, 1])[1]
    with col_center:
        if st.button("🚀  ゲームを開始する", use_container_width=True, type="primary"):
            st.session_state.game_started = True
            # 第1ターンのAI価格を事前決定
            st.session_state.current_ai_prices = [
                ai_decide_price(f, st.session_state.player_last_price)
                for f in st.session_state.ai_firms
            ]
            st.session_state.awaiting_input = True
            st.rerun()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ゲーム終了画面
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif st.session_state.game_over:
    st.markdown('<p class="big-title">🏁  ゲーム終了</p>', unsafe_allow_html=True)
    st.divider()

    fb = generate_feedback(
        st.session_state.player_prices,
        st.session_state.player_profits,
        st.session_state.ai_firms,
    )

    # 結果サマリー
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("あなたの累計利益", f"{fb['total_profit']:,.0f} 円")
    with col2:
        st.metric("最終順位", f"{fb['rank']}位 / 4社")
    with col3:
        st.metric("平均価格", f"{fb['avg_price']:.1f} 円")

    st.divider()

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("### 📊 最終利益ランキング")
        medals = ["🥇", "🥈", "🥉", "4️⃣"]
        for i, (name, profit) in enumerate(fb["ranking"]):
            is_player = name == "あなた"
            bg = "#1a3a5c" if is_player else "#1e1e2e"
            badge = " ← **あなた**" if is_player else ""
            st.markdown(
                f'<div class="result-box" style="background:{bg}">'
                f'{medals[i]} {name}{badge}<br>'
                f'<span class="profit-number">{profit:,.0f}</span> 円'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.markdown("### 🎓 戦略分析フィードバック")
        st.markdown(f"**価格標準偏差**: {fb['price_std']:.1f}円 → {fb['volatility']}")
        st.info(f"**【ポーター競争戦略】** {fb['porter']}")
        st.warning(f"**【ゲーム理論的観点】** {fb['game_theory']}")

    with col_right:
        st.markdown("### 📈 価格・利益推移グラフ")
        chart_buf = make_charts(
            st.session_state.player_prices,
            st.session_state.player_profits,
            st.session_state.ai_firms,
        )
        st.image(chart_buf, use_container_width=True)

    st.divider()
    st.markdown("### 💬 授業での振り返りポイント")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**Q1. 競合Aが「模倣型」だとわかったとき、どう対応しましたか？**
→ 価格リーダーシップ（先導者優位）を活用できましたか？

**Q2. 競合Bの低価格に対抗するとき、何を犠牲にしましたか？**
→ マージン vs シェアのトレードオフを感じましたか？
""")
    with col2:
        st.markdown("""
**Q3. 競合Cの不規則な価格変動はどう影響しましたか？**
→ 不確実性下での意思決定をどう行いましたか？

**Q4. 「全員が値下げした」ターンでは何が起きましたか？**
→ 囚人のジレンマ・価格戦争の構造を確認しましょう。
""")

    st.divider()
    if st.button("🔄  もう一度プレイする", type="primary"):
        init_state()
        st.rerun()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ゲームプレイ画面
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
else:
    turn = st.session_state.turn
    progress = (turn - 1) / TOTAL_TURNS

    # ヘッダー
    st.markdown(f'<p class="big-title">📈 Market War</p>', unsafe_allow_html=True)
    st.progress(progress, text=f"ターン {turn} / {TOTAL_TURNS}")

    # 直前ターンの結果表示
    if st.session_state.turn_result is not None:
        r = st.session_state.turn_result
        st.divider()
        st.markdown(f"#### ターン {r['turn']} の結果")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("あなたの価格", f"{r['player_price']:.1f}円")
        c2.metric("市場シェア", f"{r['player_share']*100:.1f}%")
        c3.metric("今期利益", f"{r['player_profit']:,.0f}円")
        c4.metric("累計利益", f"{r['player_cumulative']:,.0f}円")

        with st.expander("全社の結果を見る"):
            firms_data = {
                "企業": ["あなた"] + [f["name"] for f in st.session_state.ai_firms],
                "価格（円）": [f"{p:.1f}" for p in r["all_prices"]],
                "シェア（%）": [f"{s*100:.1f}" for s in r["all_shares"]],
                "今期利益（円）": [f"{p:,.0f}" for p in r["all_profits"]],
            }
            st.table(firms_data)

    # 価格入力フォーム
    if st.session_state.awaiting_input and turn <= TOTAL_TURNS:
        st.divider()
        st.markdown(f"### ターン {turn} — 価格を設定してください")

        with st.form(key=f"price_form_turn_{turn}"):
            col_input, col_hint = st.columns([2, 1])
            with col_input:
                price_input = st.slider(
                    label=f"価格（前回: {st.session_state.player_last_price:.0f}円）",
                    min_value=int(PRICE_MIN),
                    max_value=int(PRICE_MAX),
                    value=int(st.session_state.player_last_price),
                    step=1,
                    help="コスト20円以上。高いほどマージン大・シェア小。低いほどシェア大・マージン小。",
                )
            with col_hint:
                margin = price_input - FIXED_COST
                st.metric("設定マージン", f"{margin:.0f}円/単位")

            submitted = st.form_submit_button("✅  この価格で確定する", type="primary", use_container_width=True)

        if submitted:
            player_price = float(price_input)
            ai_prices = st.session_state.current_ai_prices

            all_prices = [player_price] + ai_prices
            demand = total_demand(all_prices)
            shares = market_shares(all_prices)
            profits = [calc_profit(p, s, demand) for p, s in zip(all_prices, shares)]

            player_share  = shares[0]
            player_profit = profits[0]
            st.session_state.player_cumulative += player_profit

            for i, firm in enumerate(st.session_state.ai_firms):
                firm["price"] = ai_prices[i]
                firm["price_history"].append(ai_prices[i])
                firm["profit_history"].append(profits[i + 1])

            st.session_state.player_prices.append(player_price)
            st.session_state.player_profits.append(player_profit)
            st.session_state.player_last_price = player_price

            st.session_state.turn_result = {
                "turn": turn,
                "player_price": player_price,
                "player_share": player_share,
                "player_profit": player_profit,
                "player_cumulative": st.session_state.player_cumulative,
                "all_prices": all_prices,
                "all_shares": shares,
                "all_profits": profits,
                "demand": demand,
            }

            st.session_state.awaiting_input = False

            if turn >= TOTAL_TURNS:
                st.session_state.game_over = True
            else:
                st.session_state.turn += 1
                st.session_state.current_ai_prices = [
                    ai_decide_price(f, player_price)
                    for f in st.session_state.ai_firms
                ]
                st.session_state.awaiting_input = True

            st.rerun()

    # ゲーム終了への遷移ボタン（最終ターン結果表示後）
    if not st.session_state.awaiting_input and not st.session_state.game_over:
        if st.button("➡️  次のターンへ", type="primary"):
            st.rerun()
