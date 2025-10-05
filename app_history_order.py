import random
import pandas as pd
import streamlit as st
import time
from datetime import datetime, timedelta, timezone
import io

# ==== 日本時間 ====
try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except Exception:
    JST = timezone(timedelta(hours=9))

now = datetime.now(JST)

# ==== 利用制限 ====
if 0 <= now.hour < 6:
    st.error("本アプリは深夜0時～朝6時まで利用できません。")
    st.stop()

if now.date() >= datetime(2025, 11, 1, tzinfo=JST).date():
    st.error("本アプリの利用期限は2025年10月31日までです。")
    st.stop()

# ==== スタイル ====
st.markdown(
    """
    <style>
    h1, h2, h3, h4, h5, h6 {margin-top: 0.2em; margin-bottom: 0.2em;}
    p, div, label {margin-top: 0.05em; margin-bottom: 0.05em; line-height: 1.1;}
    button, .stButton>button {
        padding: 0.4em;
        margin: 0.05em 0;
        font-size:20px;
        width:100%;
    }
    .stTextInput>div>div>input {padding: 0.2em; font-size: 16px;}
    .progress {font-weight:bold; margin: 0.5rem 0;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ==== タイトル ====
st.markdown("<h1 style='font-size:22px;'>年表並べ替えクイズ（CSV版・スマホ対応）</h1>", unsafe_allow_html=True)

# ==== ファイルアップロード ====
uploaded_file = st.file_uploader(
    "年表データ（CSV, UTF-8推奨, 列名：出来事・年号）をアップロードしてください （利用期限25-10-31）",
    type=["csv"],
    key="file_uploader",
)

# ==== 初期化 ====
def reset_all(keep_history=False):
    keep_keys = {"file_uploader"}
    if keep_history:
        keep_keys.update({"history", "total_elapsed"})
    for key in list(st.session_state.keys()):
        if key not in keep_keys:
            del st.session_state[key]

if uploaded_file is None:
    reset_all(keep_history=True)
    st.info("まずは CSV ファイルをアップロードしてください。")
    st.stop()

# ==== CSV読み込み ====
try:
    df = pd.read_csv(uploaded_file, encoding="utf-8")
except UnicodeDecodeError:
    df = pd.read_csv(uploaded_file, encoding="shift-jis")

required_cols = {"出来事", "年号"}
if not required_cols.issubset(df.columns):
    st.error("CSVには『出来事』『年号』列が必要です。")
    st.stop()

# ==== 分類番号付与 ====
df["歴史並替"] = "分類" + (df.index // 10 + 1).astype(str)

# ==== セッション初期化 ====
ss = st.session_state
ss.setdefault("phase", "menu")
ss.setdefault("history", [])
ss.setdefault("total_elapsed", 0)
ss.setdefault("run_total_questions", 0)
ss.setdefault("run_answered", 0)
ss.setdefault("current_group", None)
ss.setdefault("current_questions", [])
ss.setdefault("selected_events", [])
ss.setdefault("remaining_events", [])
ss.setdefault("q_start_time", time.time())
ss.setdefault("segment_start", time.time())
ss.setdefault("total_elapsed_before_run", 0)
ss.setdefault("user_name", "")
ss.setdefault("last_result", None)

# ==== ユーティリティ ====
def human_time(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{m}分{s}秒"

def start_run(num_questions: int):
    ss.total_elapsed_before_run = int(ss.total_elapsed)
    ss.segment_start = time.time()
    ss.q_start_time = time.time()
    ss.run_total_questions = num_questions
    ss.run_answered = 0
    next_question()

def next_question():
    groups = df["歴史並替"].unique().tolist()
    ss.current_group = random.choice(groups)
    subset = df[df["歴史並替"] == ss.current_group]
    if len(subset) < 4:
        next_question()
        return
    ss.current_questions = subset.sample(4).sort_values("年号")
    shuffled = list(ss.current_questions["出来事"].sample(frac=1))
    ss.selected_events = []
    ss.remaining_events = shuffled[:]
    ss.q_start_time = time.time()
    ss.phase = "quiz"

def prepare_csv():
    history_df = pd.DataFrame(ss.history)
    total_seconds = int(ss.total_elapsed)
    history_df["累計時間"] = human_time(total_seconds)
    desired_cols = ["歴史並替", "出来事", "年号", "正誤", "所要時間", "累計時間"]
    for c in desired_cols:
        if c not in history_df.columns:
            history_df[c] = pd.NA
    history_df = history_df[desired_cols]
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    filename = f"{ss.user_name}_{timestamp}.csv" if ss.user_name else f"history_{timestamp}.csv"
    csv_buffer = io.StringIO()
    history_df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    csv_data = csv_buffer.getvalue().encode("utf-8-sig")
    return filename, csv_data

# ==== メニュー ====
if ss.phase == "menu":
    st.subheader("問題数を選んでください")

    choice = st.radio(
        "出題数を選択",
        ["5題", "10題", "好きな数"],
        index=0,
        horizontal=True,
    )

    if choice == "好きな数":
        num = st.number_input(
            "好きな数を入力",
            min_value=1,
            max_value=len(df),
            value=min(5, len(df)),
            step=1,
        )
        selected_n = int(num)
    else:
        selected_n = 5 if choice == "5題" else 10
        selected_n = min(selected_n, len(df))

    if st.button("開始", use_container_width=True):
        start_run(selected_n)
        st.rerun()
    st.stop()

# ==== クイズ ====
if ss.phase == "quiz" and ss.current_questions is not None:
    st.markdown(f"<div class='progress'>進捗: {ss.run_answered+1}/{ss.run_total_questions} 問</div>", unsafe_allow_html=True)
    st.subheader(f"分類番号: {ss.current_group}")
    st.write("出来事を古い順に並べてください（クリック順に ➞ が表示されます）")

    cols = st.columns(max(1, min(4, len(ss.remaining_events))))
    for i, ev in enumerate(ss.remaining_events[:]):
        with cols[i % len(cols)]:
            if st.button(ev, key=f"pick_{ss.run_answered}_{i}"):
                ss.selected_events.append(ev)
                ss.remaining_events.remove(ev)
                st.rerun()

    st.write("あなたの並べ替え:", " ➞ ".join(ss.selected_events))

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("やり直し"):
            shuffled = list(ss.current_questions["出来事"].sample(frac=1))
            ss.selected_events = []
            ss.remaining_events = shuffled[:]
            st.rerun()
    with c2:
        if st.button("1つ戻す"):
            if ss.selected_events:
                last = ss.selected_events.pop()
                ss.remaining_events.append(last)
                st.rerun()

    # ==== 採点 ====
    if st.button("採点"):
        elapsed_q = int(time.time() - ss.q_start_time)
        correct_df = ss.current_questions.sort_values("年号")
        correct_order = list(correct_df["出来事"])
        correct_with_year = [f"{r['出来事']}（{r['年号']}）" for _, r in correct_df.iterrows()]
        answer_status = "正解" if ss.selected_events == correct_order else "不正解"

        ss.last_result = {
            "status": answer_status,
            "correct_with_year": correct_with_year,
            "elapsed": elapsed_q,
        }
        ss.phase = "result"
        st.rerun()

# ==== 結果フェーズ ====
if ss.phase == "result" and ss.last_result:
    res = ss.last_result
    elapsed_q = res["elapsed"]

    if res["status"] == "正解":
        st.success("✅ 正解！")
        ss.history.append({
            "歴史並替": ss.current_group,
            "出来事": " ➞ ".join(ss.selected_events),
            "年号": " / ".join(map(str, ss.current_questions["年号"])),
            "正誤": "正解",
            "所要時間": human_time(elapsed_q),
        })
        ss.total_elapsed += elapsed_q
        ss.run_answered += 1
        if ss.run_answered >= ss.run_total_questions:
            ss.phase = "done"
        else:
            next_question()
        st.rerun()

    else:
        st.error("❌ 不正解…")
        st.info("正しい順序: " + " ➞ ".join(res["correct_with_year"]))
        ss.history.append({
            "歴史並替": ss.current_group,
            "出来事": " ➞ ".join(ss.selected_events),
            "年号": " / ".join(map(str, ss.current_questions["年号"])),
            "正誤": "不正解",
            "所要時間": human_time(elapsed_q),
        })
        ss.total_elapsed += elapsed_q

        if st.button("次の問題"):
            ss.run_answered += 1
            if ss.run_answered >= ss.run_total_questions:
                ss.phase = "done"
            else:
                next_question()
            st.rerun()

# ==== 終了 ====
if ss.phase == "done":
    st.success("全問終了！お疲れさまでした🎉")
    this_run_seconds = int(ss.total_elapsed - ss.total_elapsed_before_run)
    st.info(f"今回の所要時間: {human_time(this_run_seconds)}")
    st.info(f"累計総時間: {human_time(int(ss.total_elapsed))}")

    st.subheader("学習履歴の保存")
    ss.user_name = st.text_input("氏名を入力してください", value=ss.user_name)

    if ss.user_name:
        filename, csv_data = prepare_csv()
        st.download_button("📥 保存（ダウンロード）", data=csv_data, file_name=filename, mime="text/csv")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("もう一回"):
            ss.phase = "menu"
            st.rerun()
    with c2:
        if st.button("終了"):
            reset_all(keep_history=False)
            ss.phase = "menu"
            st.rerun()
