# burger_game.py
# バーガーウォーズ：差別化戦略×マーケティング戦略 シミュレーションゲーム
# 教育目標：ポーターの差別化戦略・コストリーダーシップ、4P意思決定、
#           どっちつかず（Stuck in the Middle）リスクの体験

import streamlit as st
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------
# フォント設定
# -----------------------------------------------------------------------
matplotlib.rcParams["font.family"] = ["Noto Serif CJK JP", "Noto Sans CJK JP",
                                       "Meiryo", "MS Gothic", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False

# -----------------------------------------------------------------------
# 定数定義
# -----------------------------------------------------------------------
MAX_TURNS = 10
FIXED_COST = 500
PRICE_UNIT = 200  # 価格段階1あたりの単価（円）
TOTAL_INVEST_BUDGET = 200  # 4Pのうちスライダー3つの合計上限

COMPETITORS = {
    "ビッグスマイル":     {"strategy": "コストリーダー",    "price": 1, "quality_invest": 20,
                           "place_invest": 60, "promo_invest": 40, "target": "ファミリー"},
    "モリバーガー":       {"strategy": "差別化（素材）",    "price": 3, "quality_invest": 75,
                           "place_invest": 40, "promo_invest": 45, "target": "こだわり層"},
    "シェイクプレミアム": {"strategy": "プレミアム",        "price": 5, "quality_invest": 90,
                           "place_invest": 30, "promo_invest": 60, "target": "グルメ"},
    "フレッシュダイナー": {"strategy": "ナチュラル差別化",  "price": 3, "quality_invest": 65,
                           "place_invest": 50, "promo_invest": 45, "target": "健康志向"},
}

SEGMENTS = {
    "ファミリー":  {"size": 400, "price_sens": 0.8, "quality_sens": 0.3, "brand_sens": 0.5},
    "若者":       {"size": 300, "price_sens": 0.7, "quality_sens": 0.4, "brand_sens": 0.7},
    "ビジネス":   {"size": 200, "price_sens": 0.3, "quality_sens": 0.6, "brand_sens": 0.6},
    "こだわり層": {"size": 150, "price_sens": 0.2, "quality_sens": 0.9, "brand_sens": 0.5},
    "健康志向":   {"size": 180, "price_sens": 0.4, "quality_sens": 0.7, "brand_sens": 0.6},
}

# 競合のターゲットセグメント（シェア計算で参照）
COMP_TARGET_BONUS = {
    "ビッグスマイル":     "ファミリー",
    "モリバーガー":       "こだわり層",
    "シェイクプレミアム": "ビジネス",
    "フレッシュダイナー": "健康志向",
}

# ポジショニングマップ用の固定座標（価格×品質）
COMP_POSITION = {
    "ビッグスマイル":     (1, 20),
    "モリバーガー":       (3, 75),
    "シェイクプレミアム": (5, 90),
    "フレッシュダイナー": (3, 65),
}

COMP_COLORS = {
    "ビッグスマイル":     "#e74c3c",
    "モリバーガー":       "#2ecc71",
    "シェイクプレミアム": "#9b59b6",
    "フレッシュダイナー": "#1abc9c",
}
PLAYER_COLOR = "#f39c12"

# -----------------------------------------------------------------------
# セッション状態の初期化
# -----------------------------------------------------------------------
def init_state():
    """ゲーム状態をセッションに初期化する"""
    st.session_state.game_phase = "title"   # title / playing / result
    st.session_state.company_name = ""
    st.session_state.turn = 1
    st.session_state.cumulative_profit = 0
    st.session_state.brand_score = 0        # 累積ブランド資産
    st.session_state.history = []           # ターン履歴リスト
    st.session_state.last_result = None     # 直前ターンの結果dict
    # 競合の累積ブランドスコア
    st.session_state.comp_brand = {k: 0 for k in COMPETITORS}

if "game_phase" not in st.session_state:
    init_state()

# -----------------------------------------------------------------------
# ゲームロジック関数
# -----------------------------------------------------------------------

def calc_quality_score(product_invest: int) -> float:
    """Product投資から品質スコア（0〜100）を計算する"""
    return float(product_invest)


def calc_brand_score(current_brand: float, promo_invest: int) -> float:
    """Promotion投資で累積ブランドスコアを更新する（減衰あり）"""
    decay = 0.85
    return current_brand * decay + promo_invest * 0.5


def calc_attractiveness(price: int, quality: float, place: int,
                         brand: float, segment: dict,
                         is_target: bool) -> float:
    """
    顧客セグメントに対する魅力度スコアを計算する。
    価格は低いほど価格感度の高いセグメントに刺さる設計。
    """
    # 価格魅力度：価格1=最高、価格5=最低（感度に応じてスケール）
    price_score = (6 - price) / 5.0 * 100  # 0〜100
    quality_score = quality                  # 0〜100
    place_score = float(place)               # 0〜100
    brand_score_norm = min(brand, 200) / 2.0  # 0〜100 に正規化

    ps = segment["price_sens"]
    qs = segment["quality_sens"]
    bs = segment["brand_sens"]
    # アクセス感度は固定0.4
    ls = 0.4

    attractiveness = (ps * price_score
                      + qs * quality_score
                      + ls * place_score
                      + bs * brand_score_norm)

    # ターゲット一致ボーナス（20%増）
    if is_target:
        attractiveness *= 1.2

    return attractiveness


def calc_shares(player_decision: dict, player_brand: float,
                comp_brands: dict, target_segment: str) -> dict:
    """
    全社の市場シェアをセグメント別に計算し、
    プレイヤーのターゲットセグメントでの販売数を返す。
    returns: {"player_share": float, "player_sales": int,
              "all_shares": {company: share}, "segment_size": int}
    """
    seg = SEGMENTS[target_segment]
    seg_size = seg["size"]

    scores = {}

    # プレイヤースコア
    is_player_target = True  # プレイヤーは選択セグメントで計算
    scores["player"] = calc_attractiveness(
        price=player_decision["price"],
        quality=calc_quality_score(player_decision["product"]),
        place=player_decision["place"],
        brand=player_brand,
        segment=seg,
        is_target=is_player_target
    )

    # 競合スコア
    for name, comp in COMPETITORS.items():
        comp_target_matches = (COMP_TARGET_BONUS.get(name, "") == target_segment)
        scores[name] = calc_attractiveness(
            price=comp["price"],
            quality=calc_quality_score(comp["quality_invest"]),
            place=comp["place_invest"],
            brand=comp_brands[name],
            segment=seg,
            is_target=comp_target_matches
        )

    total = sum(scores.values())
    if total == 0:
        shares = {k: 1 / len(scores) for k in scores}
    else:
        shares = {k: v / total for k, v in scores.items()}

    player_sales = int(shares["player"] * seg_size)

    return {
        "player_share": shares["player"],
        "player_sales": player_sales,
        "all_shares": shares,
        "segment_size": seg_size,
    }


def calc_profit(player_decision: dict, player_sales: int) -> dict:
    """
    利益計算を行う。
    returns: {"revenue": int, "cost": int, "profit": int, "unit_price": int}
    """
    unit_price = player_decision["price"] * PRICE_UNIT
    revenue = unit_price * player_sales

    product = player_decision["product"]
    place = player_decision["place"]
    promo = player_decision["promo"]

    cost = int(product * 2 + place * 1.5 + promo * 1.0 + FIXED_COST)
    profit = revenue - cost

    return {
        "revenue": revenue,
        "cost": cost,
        "profit": profit,
        "unit_price": unit_price,
    }


def check_stuck_in_middle(product: int, price: int) -> dict:
    """
    どっちつかず判定。
    高品質投資なのに低価格、または低品質なのに高価格はペナルティ。
    returns: {"stuck": bool, "severity": float, "message": str}
    """
    # 品質スコアと価格の矛盾度を計算
    # 品質0〜100を1〜5にスケール換算
    quality_equiv_price = 1 + product / 100 * 4  # 品質に見合う期待価格

    mismatch = abs(quality_equiv_price - price)

    if mismatch >= 2.5:
        severity = min(mismatch / 4.0, 1.0)
        msg = ("【どっちつかず警告】高品質投資と低価格設定が矛盾しています。"
               if quality_equiv_price > price
               else "【どっちつかず警告】低品質にもかかわらず高価格設定です。")
        return {"stuck": True, "severity": severity, "message": msg}
    elif mismatch >= 1.5:
        severity = mismatch / 4.0
        msg = ("品質と価格のバランスに注意してください（どっちつかずリスクあり）。")
        return {"stuck": True, "severity": severity, "message": msg}
    else:
        return {"stuck": False, "severity": 0.0, "message": ""}


def apply_stuck_penalty(profit: int, severity: float) -> int:
    """どっちつかずペナルティを利益に適用する（最大30%減）"""
    if severity <= 0:
        return profit
    penalty_rate = severity * 0.30
    return int(profit * (1 - penalty_rate))


def execute_turn(player_decision: dict, target_segment: str) -> dict:
    """
    1ターン分の処理を実行し、結果dictを返す。
    """
    # ブランドスコア更新
    new_brand = calc_brand_score(st.session_state.brand_score,
                                  player_decision["promo"])
    st.session_state.brand_score = new_brand

    # 競合ブランドスコア更新
    for name, comp in COMPETITORS.items():
        st.session_state.comp_brand[name] = calc_brand_score(
            st.session_state.comp_brand[name], comp["promo_invest"]
        )

    # シェア計算
    share_result = calc_shares(player_decision, new_brand,
                                st.session_state.comp_brand, target_segment)

    # 利益計算
    profit_result = calc_profit(player_decision, share_result["player_sales"])

    # どっちつかず判定
    stuck_result = check_stuck_in_middle(player_decision["product"],
                                          player_decision["price"])

    # ペナルティ適用
    final_profit = apply_stuck_penalty(profit_result["profit"],
                                        stuck_result["severity"])

    st.session_state.cumulative_profit += final_profit

    result = {
        "turn": st.session_state.turn,
        "target_segment": target_segment,
        "decision": dict(player_decision),
        "share": share_result["player_share"],
        "sales": share_result["player_sales"],
        "segment_size": share_result["segment_size"],
        "revenue": profit_result["revenue"],
        "cost": profit_result["cost"],
        "profit": final_profit,
        "unit_price": profit_result["unit_price"],
        "all_shares": share_result["all_shares"],
        "stuck": stuck_result,
        "brand_score": new_brand,
        "cumulative_profit": st.session_state.cumulative_profit,
    }

    st.session_state.history.append(result)
    st.session_state.last_result = result
    st.session_state.turn += 1

    return result


# -----------------------------------------------------------------------
# matplotlib チャート関数
# -----------------------------------------------------------------------

def draw_positioning_map(player_price: int = None,
                          player_quality: int = None,
                          history: list = None):
    """
    価格×品質のポジショニングマップを描画する。
    player_price / player_quality が指定された場合は現在地点を表示。
    history がある場合は軌跡を描画する。
    """
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.set_xlim(0, 6)
    ax.set_ylim(-5, 110)
    ax.set_xlabel("価格設定（1=低 → 5=高）", fontsize=9)
    ax.set_ylabel("品質スコア（Product投資）", fontsize=9)
    ax.set_title("ポジショニングマップ", fontsize=10, fontweight="bold")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.grid(True, alpha=0.3)

    # 競合プロット
    for name, (px, py) in COMP_POSITION.items():
        ax.scatter(px, py, color=COMP_COLORS[name], s=120, zorder=5)
        ax.annotate(name, (px, py), textcoords="offset points",
                    xytext=(6, 3), fontsize=7, color=COMP_COLORS[name])

    # プレイヤー軌跡
    if history:
        hx = [r["decision"]["price"] for r in history]
        hy = [r["decision"]["product"] for r in history]
        ax.plot(hx, hy, color=PLAYER_COLOR, linewidth=1.5,
                linestyle="--", alpha=0.6, zorder=4)
        # 過去地点（小さめ）
        for i, (x, y) in enumerate(zip(hx[:-1], hy[:-1])):
            ax.scatter(x, y, color=PLAYER_COLOR, s=40, alpha=0.5, zorder=5)

    # 現在地点
    if player_price is not None and player_quality is not None:
        ax.scatter(player_price, player_quality,
                   color=PLAYER_COLOR, s=200, marker="*",
                   zorder=10, label=st.session_state.company_name or "自社")
        ax.annotate(st.session_state.company_name or "自社",
                    (player_price, player_quality),
                    textcoords="offset points", xytext=(6, 3),
                    fontsize=8, color=PLAYER_COLOR, fontweight="bold")

    # 凡例
    patches = [mpatches.Patch(color=c, label=n)
               for n, c in COMP_COLORS.items()]
    patches.append(mpatches.Patch(color=PLAYER_COLOR,
                                   label=st.session_state.company_name or "自社"))
    ax.legend(handles=patches, fontsize=6, loc="upper left",
              framealpha=0.7)

    plt.tight_layout()
    return fig


def draw_radar_chart(product: int, price_score: int,
                      place: int, promo: int, title: str = "4P バランス"):
    """
    4Pのレーダーチャートを描画する。
    price_score は 価格設定(1〜5)を 0〜100 に変換して渡す。
    """
    labels = ["Product\n（品質）", "Price\n（価格）",
              "Place\n（立地）", "Promotion\n（広告）"]
    values = [product, price_score, place, promo]
    values_closed = values + [values[0]]

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw={"polar": True})
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles), labels, fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25", "50", "75", "100"], fontsize=7)

    ax.plot(angles_closed, values_closed, color=PLAYER_COLOR, linewidth=2)
    ax.fill(angles_closed, values_closed, color=PLAYER_COLOR, alpha=0.25)
    ax.set_title(title, fontsize=10, fontweight="bold", pad=15)

    plt.tight_layout()
    return fig


def draw_profit_history(history: list):
    """累計利益の推移折れ線グラフを描画する"""
    turns = [r["turn"] for r in history]
    cumulative = [r["cumulative_profit"] for r in history]
    profits = [r["profit"] for r in history]

    fig, ax1 = plt.subplots(figsize=(6, 3))
    ax2 = ax1.twinx()

    ax1.bar(turns, profits, color=PLAYER_COLOR, alpha=0.5, label="各ターン利益")
    ax2.plot(turns, cumulative, color="#e74c3c", linewidth=2,
             marker="o", markersize=5, label="累計利益")

    ax1.set_xlabel("ターン", fontsize=9)
    ax1.set_ylabel("各ターン利益（円）", fontsize=9, color=PLAYER_COLOR)
    ax2.set_ylabel("累計利益（円）", fontsize=9, color="#e74c3c")
    ax1.set_title("利益推移", fontsize=10, fontweight="bold")
    ax1.set_xticks(turns)
    ax1.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax1.grid(axis="y", alpha=0.3)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper left")

    plt.tight_layout()
    return fig


def draw_final_trajectory(history: list):
    """最終結果用：10ターンの戦略軌跡ポジショニングマップ"""
    return draw_positioning_map(history=history)


def draw_cumulative_radar(history: list):
    """10ターン分の4P投資平均でレーダーチャートを描画する"""
    if not history:
        return None
    avg_product = int(np.mean([r["decision"]["product"] for r in history]))
    avg_price   = int(np.mean([(r["decision"]["price"] - 1) / 4 * 100
                                for r in history]))
    avg_place   = int(np.mean([r["decision"]["place"] for r in history]))
    avg_promo   = int(np.mean([r["decision"]["promo"] for r in history]))
    return draw_radar_chart(avg_product, avg_price, avg_place, avg_promo,
                             title="10ターン平均 4P バランス")


# -----------------------------------------------------------------------
# 戦略評価フィードバック生成
# -----------------------------------------------------------------------

def generate_strategy_feedback(history: list) -> dict:
    """
    10ターンの意思決定履歴から差別化戦略の評価コメントを生成する。
    returns: {"type": str, "title": str, "description": str, "advice": str}
    """
    if not history:
        return {}

    avg_product = np.mean([r["decision"]["product"] for r in history])
    avg_price   = np.mean([r["decision"]["price"] for r in history])
    avg_promo   = np.mean([r["decision"]["promo"] for r in history])
    avg_place   = np.mean([r["decision"]["place"] for r in history])
    stuck_count = sum(1 for r in history if r["stuck"]["stuck"])
    # 主なターゲット
    target_counts = {}
    for r in history:
        t = r["target_segment"]
        target_counts[t] = target_counts.get(t, 0) + 1
    main_target = max(target_counts, key=target_counts.get)

    # 戦略タイプ判定
    if avg_product >= 65 and avg_price >= 3.5:
        stype = "差別化戦略"
        title = "差別化戦略型"
        desc  = ("高品質投資と高価格設定を一貫して維持しました。"
                 "ポーターの競争優位論でいう「差別化戦略」を実践できています。"
                 "顧客は品質に対してプレミアムを支払うことを認めており、"
                 "持続的競争優位につながりやすいポジションです。")
        advice = ("ブランド投資をさらに強化することで、価格競争に巻き込まれにくい"
                  "強固なポジションを確立できます。")
    elif avg_product <= 35 and avg_price <= 2.5:
        stype = "コストリーダーシップ"
        title = "コストリーダーシップ型"
        desc  = ("低価格・標準品質のポジションで大量販売を目指しました。"
                 "コストリーダーシップ戦略は、規模の経済が働く大市場で有効です。"
                 "ファミリー層など価格感度の高いセグメントには刺さりやすい反面、"
                 "コスト管理が収益の鍵となります。")
        advice = ("Place（立地・アクセス）投資を増やして販売数を拡大することが"
                  "コストリーダーシップ戦略の効果を最大化します。")
    elif stuck_count >= 5:
        stype = "どっちつかず"
        title = "どっちつかず（Stuck in the Middle）"
        desc  = ("品質と価格の方向性が一致していないターンが多く見られました。"
                 "ポーターは「どっちつかず」の企業は差別化コストを負担しながら"
                 "低コストの利点も得られず、最も不利な競争状態に陥ると警告しています。"
                 "その結果、利益が圧迫されたターンが発生しています。")
        advice = ("戦略の一貫性が重要です。高品質なら高価格、低価格なら品質投資を"
                  "絞るという「選択と集中」を次回は意識してください。")
    else:
        stype = "集中戦略"
        title = "集中戦略型"
        desc  = (f"特定セグメント（主に「{main_target}」）に注力した戦略でした。"
                 "ポーターの集中戦略は、ニッチ市場で差別化またはコスト優位を築く方法です。"
                 "セグメントの特性に合った4P設計ができていれば高いシェアが獲得できます。")
        advice = ("選んだセグメントの感度（価格・品質・ブランド）に合わせて"
                  "投資配分を最適化すると、さらに効果的な集中戦略になります。")

    return {
        "type": stype,
        "title": title,
        "description": desc,
        "advice": advice,
        "main_target": main_target,
        "stuck_count": stuck_count,
    }


# -----------------------------------------------------------------------
# 画面：タイトル
# -----------------------------------------------------------------------

def page_title():
    st.title("バーガーウォーズ")
    st.subheader("差別化戦略 × マーケティング4P シミュレーション")
    st.markdown("ハンバーガー業界で競合4社と戦い、10ターンで最大利益を目指せ！")

    # ルール説明エクスパンダー
    with st.expander("差別化戦略・4Pとは？（クリックで展開）", expanded=False):
        st.markdown("""
### ポーターの3つの競争戦略
| 戦略 | 概要 | 向いている市場 |
|------|------|--------------|
| **コストリーダーシップ** | 最低コストで大量販売 | 規模が大きく価格競争が激しい市場 |
| **差別化戦略** | 独自価値で高価格を正当化 | 品質・ブランドへの支払意欲が高い市場 |
| **集中戦略** | 特定セグメントに特化 | ニッチ市場・特定顧客層 |

### マーケティング4P
- **Product（製品）**：食材・品質への投資。高いほど差別化顧客に刺さる
- **Price（価格）**：1（200円）〜5（1000円）の5段階
- **Place（流通・立地）**：出店・アクセス投資。高いほど集客力UP
- **Promotion（プロモーション）**：広告・ブランド投資。累積でブランド資産が積み上がる
        """)

    with st.expander("どっちつかず（Stuck in the Middle）とは？", expanded=False):
        st.markdown("""
### どっちつかいのワナ
ポーターは、**差別化戦略**と**コストリーダーシップ**を中途半端に追うと、
どちらの優位性も得られない「**どっちつかず**」の状態に陥ると警告しています。

**例：危険なパターン**
- 高品質投資（Product=80）なのに低価格設定（Price=1）
  → 差別化コストを負担しながら価格競争もしようとしている
- 低品質投資（Product=20）なのに高価格設定（Price=5）
  → 顧客は低品質に高値を払わない

**このゲームでのペナルティ**：品質スコアと価格が大きく矛盾している場合、
利益に最大30%のペナルティが発生します。

**一貫した戦略**こそが持続的競争優位の源泉です。
        """)

    st.divider()
    st.subheader("競合4社プロファイル")

    comp_table = []
    for name, data in COMPETITORS.items():
        comp_table.append({
            "企業名": name,
            "戦略": data["strategy"],
            "価格設定": f"{data['price']}段階（{data['price'] * PRICE_UNIT}円）",
            "品質投資": data["quality_invest"],
            "ターゲット": data["target"],
        })
    st.dataframe(pd.DataFrame(comp_table).set_index("企業名"), use_container_width=True)

    st.divider()
    company_name = st.text_input("あなたの会社名を入力してください",
                                  value="マイバーガー",
                                  max_chars=20)

    if st.button("ゲームスタート！", type="primary", use_container_width=True):
        if not company_name.strip():
            st.error("会社名を入力してください。")
        else:
            st.session_state.company_name = company_name.strip()
            st.session_state.game_phase = "playing"
            st.rerun()


# -----------------------------------------------------------------------
# 画面：ゲームプレイ（2カラム構成）
# -----------------------------------------------------------------------

def page_playing():
    company = st.session_state.company_name
    turn = st.session_state.turn

    st.title(f"バーガーウォーズ — {company}")
    st.progress((turn - 1) / MAX_TURNS,
                text=f"ターン {turn} / {MAX_TURNS}")

    left_col, right_col = st.columns([1, 1], gap="large")

    # -------- 左カラム：意思決定 --------
    with left_col:
        st.subheader("経営判断")

        # 累計利益
        profit_color = "green" if st.session_state.cumulative_profit >= 0 else "red"
        st.metric("累計利益",
                  f"{st.session_state.cumulative_profit:,} 円",
                  delta=None)

        st.divider()

        # ターゲット顧客選択
        target_segment = st.radio(
            "ターゲット顧客セグメント",
            options=list(SEGMENTS.keys()),
            horizontal=False,
            key=f"target_{turn}",
        )
        seg_info = SEGMENTS[target_segment]
        st.caption(
            f"市場規模: {seg_info['size']}人  |  "
            f"価格感度: {seg_info['price_sens']}  |  "
            f"品質感度: {seg_info['quality_sens']}  |  "
            f"ブランド感度: {seg_info['brand_sens']}"
        )

        st.divider()

        # 価格設定
        price_setting = st.radio(
            "価格設定",
            options=[1, 2, 3, 4, 5],
            format_func=lambda x: f"{x}段階 ({x * PRICE_UNIT}円)",
            horizontal=True,
            key=f"price_{turn}",
        )

        st.divider()

        # 4Pスライダー（Product / Place / Promo の3つで合計200pt）
        st.markdown("**4P 投資配分（合計 200pt）**")
        st.caption("Product + Place + Promotion の合計が 200pt になるよう配分してください。")

        product_invest = st.slider("Product（食材・品質投資）", 0, 200, 60,
                                    key=f"product_{turn}")
        remaining_after_product = max(0, TOTAL_INVEST_BUDGET - product_invest)

        place_invest = st.slider("Place（出店・アクセス投資）", 0, remaining_after_product,
                                  min(60, remaining_after_product),
                                  key=f"place_{turn}")
        promo_invest = remaining_after_product - place_invest

        st.info(f"Promotion（広告・ブランド投資）: **{promo_invest} pt**（自動算出）")

        total_check = product_invest + place_invest + promo_invest
        if total_check != TOTAL_INVEST_BUDGET:
            st.warning(f"合計: {total_check}pt（{TOTAL_INVEST_BUDGET}ptに自動調整されます）")

        st.divider()

        # どっちつかいリアルタイム警告
        stuck = check_stuck_in_middle(product_invest, price_setting)
        if stuck["stuck"]:
            severity_pct = int(stuck["severity"] * 100)
            if stuck["severity"] >= 0.5:
                st.error(f"危険度 {severity_pct}%\n{stuck['message']}")
            else:
                st.warning(f"注意 {severity_pct}%\n{stuck['message']}")
        else:
            st.success("戦略の一貫性: 問題なし")

        st.divider()

        # ターン実行ボタン
        if st.button(f"ターン {turn} を実行する", type="primary",
                      use_container_width=True):
            decision = {
                "product": product_invest,
                "price": price_setting,
                "place": place_invest,
                "promo": promo_invest,
            }
            result = execute_turn(decision, target_segment)

            if st.session_state.turn > MAX_TURNS:
                st.session_state.game_phase = "result"

            st.rerun()

    # -------- 右カラム：情報表示 --------
    with right_col:
        st.subheader("市場ポジション")

        # ポジショニングマップ
        fig_map = draw_positioning_map(
            player_price=price_setting,
            player_quality=product_invest,
            history=st.session_state.history,
        )
        st.pyplot(fig_map)
        plt.close(fig_map)

        # 前ターン結果
        if st.session_state.last_result:
            r = st.session_state.last_result
            st.subheader(f"前ターン（第{r['turn']}ターン）の結果")

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("市場シェア", f"{r['share']*100:.1f}%")
            col_b.metric("販売数", f"{r['sales']}人")
            col_c.metric("利益", f"{r['profit']:,}円")

            # 全社シェアテーブル
            share_data = []
            for company_name_key, share_val in r["all_shares"].items():
                display_name = (st.session_state.company_name
                                if company_name_key == "player"
                                else company_name_key)
                share_data.append({
                    "企業": display_name,
                    "シェア": f"{share_val*100:.1f}%",
                })
            st.dataframe(pd.DataFrame(share_data).set_index("企業"),
                         use_container_width=True)

            # 累計利益ランキング（概算）
            st.caption(f"累計利益: {r['cumulative_profit']:,} 円 | "
                       f"ブランドスコア: {r['brand_score']:.1f}")


# -----------------------------------------------------------------------
# 画面：最終結果
# -----------------------------------------------------------------------

def page_result():
    company = st.session_state.company_name
    history = st.session_state.history
    total_profit = st.session_state.cumulative_profit

    st.title(f"ゲーム終了！ — {company}")
    st.balloons()

    # -------- 最終スコア --------
    st.header("最終結果")
    col1, col2, col3 = st.columns(3)
    col1.metric("10ターン累計利益", f"{total_profit:,} 円")
    col2.metric("平均シェア",
                f"{np.mean([r['share'] for r in history])*100:.1f}%")
    col3.metric("総販売数", f"{sum(r['sales'] for r in history):,} 人")

    st.divider()

    # -------- 利益推移 --------
    st.subheader("利益推移")
    fig_profit = draw_profit_history(history)
    st.pyplot(fig_profit)
    plt.close(fig_profit)

    st.divider()

    # -------- 戦略軌跡 --------
    st.subheader("10ターンの戦略軌跡（ポジショニングマップ）")
    fig_traj = draw_final_trajectory(history)
    st.pyplot(fig_traj)
    plt.close(fig_traj)

    st.divider()

    # -------- 4P 累計バランス --------
    st.subheader("4P 投資の累計バランス")
    fig_radar = draw_cumulative_radar(history)
    if fig_radar:
        st.pyplot(fig_radar)
        plt.close(fig_radar)

    st.divider()

    # -------- 戦略評価フィードバック --------
    st.subheader("あなたの差別化戦略 評価")
    feedback = generate_strategy_feedback(history)
    if feedback:
        st.markdown(f"### 判定：{feedback['title']}")
        st.info(feedback["description"])
        st.success(f"アドバイス: {feedback['advice']}")

        if feedback["stuck_count"] > 0:
            st.warning(
                f"「どっちつかず」警告が発生したターン数: {feedback['stuck_count']} / {MAX_TURNS}ターン"
            )

    st.divider()

    # -------- 全ターン詳細テーブル --------
    st.subheader("全ターン詳細")
    detail_rows = []
    for r in history:
        detail_rows.append({
            "ターン": r["turn"],
            "ターゲット": r["target_segment"],
            "価格": r["decision"]["price"],
            "Product": r["decision"]["product"],
            "Place": r["decision"]["place"],
            "Promo": r["decision"]["promo"],
            "シェア(%)": f"{r['share']*100:.1f}",
            "販売数": r["sales"],
            "売上(円)": r["revenue"],
            "コスト(円)": r["cost"],
            "利益(円)": r["profit"],
            "どっちつかず": "警告" if r["stuck"]["stuck"] else "—",
        })
    st.dataframe(pd.DataFrame(detail_rows).set_index("ターン"),
                 use_container_width=True)

    st.divider()

    # -------- 振り返り設問 --------
    st.subheader("振り返り設問")
    st.markdown("""
以下の設問について、ゲーム体験をもとに考えてみてください。

**Q1. あなたが選んだ戦略は「差別化戦略」「コストリーダーシップ」「集中戦略」のどれに近かったですか？
その根拠となる意思決定（価格・品質投資）を説明してください。**

**Q2. 「どっちつかず」警告が発生したターンでは利益にどのような影響がありましたか？
現実のビジネスで「どっちつかず」が問題になる事例を一つ挙げてください。**

**Q3. ターゲットセグメントを変更したターンがある場合、シェアや利益にどのような変化がありましたか？
なぜその変化が起きたと思いますか？（顧客感度の観点から考察してください）**

**Q4. ブランドスコアが高まるにつれて市場シェアはどう変化しましたか？
マーケティングにおけるプロモーション投資の長期的意義を4P理論の観点から述べてください。**
    """)

    st.divider()

    # -------- リスタートボタン --------
    if st.button("もう一度プレイする", type="secondary", use_container_width=True):
        init_state()
        st.rerun()


# -----------------------------------------------------------------------
# メインルーティング
# -----------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="バーガーウォーズ",
        page_icon="🍔",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    phase = st.session_state.get("game_phase", "title")

    if phase == "title":
        page_title()
    elif phase == "playing":
        page_playing()
    elif phase == "result":
        page_result()
    else:
        init_state()
        st.rerun()


if __name__ == "__main__":
    main()
