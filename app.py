import os
import pandas as pd
import altair as alt
import streamlit as st
import model as M
import storage as S

st.set_page_config(page_title="Product & Pricing Decision Lab", page_icon="🥤", layout="wide")

TEAL, NAVY, CORAL, GOLD = "#21867A", "#102B43", "#D9573B", "#EFB23A"

def instructor_password():
    try:
        if "INSTRUCTOR_PASSWORD" in st.secrets:
            return st.secrets["INSTRUCTOR_PASSWORD"]
    except Exception:
        pass
    return os.environ.get("INSTRUCTOR_PASSWORD", "poets")

def esc(s):
    return s.replace('$', '\\$')

def money(x):
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"

def classify(rows):
    """Label a team's pricing path from its submitted prices."""
    p = [r["decisions"]["price"] for r in rows]
    if len(p) < 3:
        return "In progress"
    first, later = p[0], min(p[2:])
    if first >= 4.5 and later <= first * 0.85:
        return "Skimming, then cut"
    if first >= 4.5:
        return "Premium throughout"
    if first <= 3.0 and p[-1] >= first * 1.15:
        return "Penetration, then raise"
    if first <= 3.0:
        return "Low price throughout"
    return "Going-rate pricing"

def flatten(rows):
    out = []
    for r in rows:
        d, res = r["decisions"], r["results"]
        out.append(dict(team=r["team"], round=r["round"], objective=r.get("objective"),
                        quality=d["quality"], pack=d["pack"], brand_spend=d["brand_spend"], price=d["price"],
                        tactic=d["tactic"], refresh=d.get("refresh", False), units=res["units"], share=res["share"],
                        revenue=res["revenue"], profit=res["profit"], brand_strength=res["brand_strength"],
                        price_paid=res["price_paid"], unit_cost=res["unit_cost"]))
    return pd.DataFrame(out)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("### 🥤 Product & Pricing Decision Lab")
    mode = st.radio("I am a…", ["Team", "Instructor"], label_visibility="collapsed")
    st.caption(f"Data: {S.backend_name()}")
    st.caption("All market data and results are invented teaching assumptions.")

# ------------------------------------------------------------------ INSTRUCTOR
def instructor_view():
    if not st.session_state.get("inst_ok"):
        pw = st.text_input("Instructor password", type="password")
        if st.button("Open dashboard"):
            if pw == instructor_password():
                st.session_state["inst_ok"] = True
                st.rerun()
            else:
                st.error("Wrong password.")
        return
    st.title("Instructor dashboard")
    c1, c2 = st.columns([2, 3])
    with c1:
        cur = S.get_max_round()
        new = st.select_slider("Rounds open to teams", options=[1, 2, 3, 4], value=cur,
                               help="Teams cannot start a round above this number. Use it to pause for a mini-debrief.")
        if new != cur:
            S.set_max_round(new)
            st.success(f"Teams can now play up to round {new}.")
    with c2:
        st.write("")
    dashboard()
    with st.expander("Admin: clear all data"):
        ok = st.checkbox("I understand this deletes every team's results")
        if st.button("Clear data", disabled=not ok):
            S.clear_all(); st.success("Cleared."); st.rerun()

@st.fragment(run_every=10)
def dashboard():
    rows = S.load_all()
    if not rows:
        st.info("No submissions yet. This page refreshes every 10 seconds.")
        return
    df = flatten(rows)
    teams = df.groupby("team")
    lb = teams.agg(rounds=("round", "max"), profit=("profit", "sum"), revenue=("revenue", "sum"),
                   avg_share=("share", "mean"), brand=("brand_strength", "last")).reset_index()
    cls = {t: classify([r for r in rows if r["team"] == t]) for t in lb["team"]}
    lb["pricing path"] = lb["team"].map(cls)
    lb = lb.sort_values("profit", ascending=False).reset_index(drop=True)
    lb.index += 1
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Teams", len(lb))
    m2.metric("Finished all 4 rounds", int((lb["rounds"] == 4).sum()))
    m3.metric("Best cumulative profit", money(lb["profit"].max()))
    m4.metric("Average profit", money(lb["profit"].mean()))

    st.subheader("Leaderboard")
    show = lb.copy()
    show["profit"] = show["profit"].map(money); show["revenue"] = show["revenue"].map(money)
    show["avg_share"] = (show["avg_share"] * 100).round(1).astype(str) + "%"; show["brand"] = show["brand"].round(1)
    st.dataframe(show.rename(columns={"avg_share": "avg share", "brand": "brand strength"}), width='stretch')

    a, b = st.columns(2)
    with a:
        st.subheader("Price paths vs rivals")
        avg = df.groupby("round")["price"].mean().reset_index()
        comp = []
        for r in range(1, 5):
            for n, c in M.competitors(r).items():
                comp.append(dict(round=r, price=c["price"], who=n))
        cdf = pd.DataFrame(comp)
        lines = alt.Chart(df).mark_line(opacity=0.35, color=TEAL).encode(x=alt.X("round:O", title="Round"), y=alt.Y("price:Q", title="Price ($)"), detail="team")
        avgl = alt.Chart(avg).mark_line(color=NAVY, strokeWidth=4, point=True).encode(x="round:O", y="price:Q")
        cl = alt.Chart(cdf).mark_line(strokeDash=[4, 3]).encode(x="round:O", y="price:Q", color=alt.Color("who:N", title="Rival"))
        st.altair_chart(lines + avgl + cl, width='stretch')
        st.caption("Teal = each team. Navy = class average. Dashed = rivals.")
    with b:
        st.subheader("Cumulative profit by round")
        df["cum"] = df.sort_values("round").groupby("team")["profit"].cumsum()
        st.altair_chart(alt.Chart(df).mark_line(point=True).encode(x=alt.X("round:O", title="Round"), y=alt.Y("cum:Q", title="Cumulative profit ($)"), color="team:N"), width='stretch')

    c, d = st.columns(2)
    with c:
        st.subheader("Share vs profit, latest round")
        last = df.sort_values("round").groupby("team").tail(1)
        st.altair_chart(alt.Chart(last).mark_circle(size=140).encode(x=alt.X("share:Q", title="Market share", axis=alt.Axis(format="%")), y=alt.Y("profit:Q", title="Round profit ($)"), color=alt.Color("price:Q", title="Price", scale=alt.Scale(scheme="tealblues")), tooltip=["team", "round", "price", "units", "profit"]), width='stretch')
    with d:
        st.subheader("Pricing paths in the room")
        st.altair_chart(alt.Chart(lb).mark_bar(color=TEAL).encode(x=alt.X("count()", title="Teams"), y=alt.Y("pricing path:N", sort="-x", title="")), width='stretch')

    e, f = st.columns(2)
    with e:
        st.subheader("Pricing tactics used")
        st.altair_chart(alt.Chart(df).mark_bar().encode(x=alt.X("round:O", title="Round"), y=alt.Y("count()", title="Teams"), color=alt.Color("tactic:N", title="")), width='stretch')
    with f:
        st.subheader("Product mix by round")
        st.altair_chart(alt.Chart(df).mark_bar().encode(x=alt.X("round:O", title="Round"), y=alt.Y("count()", title="Teams"), color=alt.Color("quality:N", title="Quality", sort=["Basic", "Standard", "Premium"])), width='stretch')

    refl = S.load_reflections()
    if refl:
        with st.expander(f"Team reflections ({len(refl)})"):
            for r in refl:
                st.markdown(f"**{r['team']}**: {r['text']}")
    st.download_button("Download all results (CSV)", df.drop(columns=["cum"], errors="ignore").to_csv(index=False), "pricing_lab_results.csv", "text/csv")

# ------------------------------------------------------------------ TEAM
def team_view():
    st.title("🥤 Poet Pop: Product & Pricing Decision Lab")
    team = st.session_state.get("team")
    if not team:
        st.markdown("""
**Scenario.** Your pair has just launched **Poet Pop**, a new better-for-you sparkling drink, on campus and online. Over four rounds you move through the product life cycle: **Introduction, Growth, Maturity, Decline**.
Each round you choose the **product** (quality, packaging), the **brand** investment, and the **price and pricing tactic**. The market then shows you what happened.

Your goal is to earn the most profit across all four rounds. Your reasoning matters more than the number.""")
        with st.form("join"):
            name = st.text_input("Team name (your pair's name)")
            members = st.text_input("Names of the two team members")
            go = st.form_submit_button("Start or resume")
        if go:
            name = " ".join(name.split())
            if not name:
                st.error("Please enter a team name.")
            else:
                st.session_state["team"] = name
                st.session_state["members"] = members
                st.session_state.pop("just", None)
                st.rerun()
        return

    rows = S.load_team(team)
    done = len(rows)
    members = st.session_state.get("members", "")
    st.caption(f"Team: **{team}**" + (f" ({members})" if members else ""))
    if st.button("Switch team", type="secondary"):
        for k in ("team", "members", "just"):
            st.session_state.pop(k, None)
        st.rerun()

    just = st.session_state.get("just")
    if just and just["round"] == done:
        show_result(just["res"], just["d"], rows)
        if done < M.ROUNDS:
            if st.button(f"Continue to round {done + 1} →", type="primary"):
                st.session_state.pop("just"); st.rerun()
        else:
            if st.button("See your final summary →", type="primary"):
                st.session_state.pop("just"); st.rerun()
        return

    if done >= M.ROUNDS:
        final_view(team, rows)
        return

    rnd = done + 1
    if rnd > S.get_max_round():
        st.info(f"Round {rnd} is not open yet. Your instructor will open it after a short discussion.")
        if st.button("Check again"):
            st.rerun()
        return
    play_round(team, members, rnd, rows)

def prior_state(rows):
    st_ = M.initial_state()
    for r in rows:
        _, st_ = M.simulate_round(r["round"], r["decisions"], st_, r["team"])
    return st_

def play_round(team, members, rnd, rows):
    stage = M.STAGES[rnd - 1]
    st.progress((rnd - 1) / M.ROUNDS, text=f"Round {rnd} of {M.ROUNDS}  |  Stage: {stage}")
    st.subheader(f"Round {rnd}: {stage}")
    st.info(M.NOTES[rnd - 1])
    cdf = pd.DataFrame([dict(Brand=n, Quality=["", "Basic", "Standard", "Premium"][c["q"]], Packaging=c["pk"], Price=f"${c['price']:.2f}") for n, c in M.competitors(rnd).items()])
    st.markdown("**Rivals this round**")
    st.dataframe(cdf, hide_index=True, width='stretch')
    if rows:
        tot = sum(r["results"]["profit"] for r in rows)
        last = rows[-1]["results"]
        st.caption(esc(f"Last round: {last['units']:,} units, {money(last['profit'])} profit, {last['share']*100:.0f}% share. Cumulative profit: {money(tot)}."))

    first = rnd == 1
    with st.form(f"round{rnd}"):
        obj = rows[0]["objective"] if rows else None
        if first:
            obj = st.selectbox("Your main pricing objective (Chapter 12)", ["Maximize profit", "Gain market share", "Build a premium image"],
                               help="Pick the objective your pricing will serve. Be ready to explain it.")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Product**")
            quality = st.radio("Quality tier", list(M.QUALITY), index=1, horizontal=True)
            pack = st.radio("Packaging", list(M.PACK), index=0, horizontal=True, help="Eco appeals to some buyers and signals care. Premium packaging signals status.")
            refresh = False
            if rnd >= 3:
                refresh = st.checkbox(esc(f"Refresh the product (new flavor and look), cost {money(M.REFRESH_COST)}"), help="Extends the life cycle: a perceived quality bump and a brand lift.")
            st.markdown("**Brand**")
            spend = st.select_slider("Brand and advertising spend", options=M.BRAND_SPEND, value=2500, format_func=money,
                                     help="Builds awareness and brand strength. The effect builds over rounds.")
        with c2:
            st.markdown("**Price**")
            price = st.number_input("List price per can ($)", min_value=0.50, max_value=8.00, value=3.50, step=0.25, format="%.2f")
            tactics = M.TACTICS if rnd <= 2 else [t for t in M.TACTICS if not t.startswith("Introductory")]
            tactic = st.radio("Pricing tactic", tactics, index=0)
        uc = M.unit_cost(quality, pack, tactic)
        paid = price * (0.85 if tactic.startswith("Introductory") else 0.92 if tactic.startswith("2-pack") else 1) - (0.01 if tactic.startswith("Charm") else 0)
        st.caption(esc(f"Cost per can with these choices: **${uc:.2f}**. Price buyers pay per can: **${paid:.2f}**. Margin per can: **${paid-uc:.2f}**. Fixed costs this round: **{money(M.OVERHEAD + spend + (M.REFRESH_COST if refresh else 0))}**."))
        go = st.form_submit_button("Lock in decisions", type="primary")
    if go:
        d = dict(quality=quality, pack=pack, brand_spend=int(spend), price=float(price), tactic=tactic, refresh=bool(refresh))
        res, _ = M.simulate_round(rnd, d, prior_state(rows), team)
        S.save_submission(team, rnd, members, obj, d, res)
        st.session_state["just"] = dict(round=rnd, res=res, d=d)
        st.rerun()

def show_result(res, d, rows):
    st.success(f"Round {res['round']} results ({res['stage']})")
    cum = sum(r["results"]["profit"] for r in rows)
    c = st.columns(5)
    c[0].metric("Units sold", f"{res['units']:,}")
    c[1].metric("Revenue", money(res["revenue"]))
    c[2].metric("Profit", money(res["profit"]))
    c[3].metric("Market share", f"{res['share']*100:.0f}%")
    c[4].metric("Cumulative profit", money(cum))
    a, b = st.columns(2)
    with a:
        sd = pd.DataFrame(dict(Segment=list(res["segments"]), Share=[v for v in res["segments"].values()]))
        st.altair_chart(alt.Chart(sd).mark_bar(color=TEAL).encode(x=alt.X("Segment:N", sort=None, title=""), y=alt.Y("Share:Q", axis=alt.Axis(format="%"), title="Your share of segment")), width='stretch')
    with b:
        st.markdown("**What happened**")
        for line in M.explain(res, d):
            st.markdown(f"- {line}")
        st.markdown(f"- Brand strength: **{res['brand_strength']:.1f}** out of 10. Awareness: **{res['awareness']*100:.0f}%**.")
        if res.get("anchor_penalty", 0) > 0.05:
            st.markdown("- Buyers noticed your **price jump** from last round. A higher price than they were used to cost you sales.")
    st.caption(esc(f"Costs: variable {money(res['variable_cost'])}, fixed {money(res['fixed_cost'])}. Cost per can ${res['unit_cost']:.2f}, price paid ${res['price_paid']:.2f}."))

def final_view(team, rows):
    st.subheader("Final summary")
    df = flatten(rows)
    tot = df["profit"].sum()
    path = classify(rows)
    c = st.columns(4)
    c[0].metric("Cumulative profit", money(tot)); c[1].metric("Total units", f"{df['units'].sum():,}")
    c[2].metric("Average share", f"{df['share'].mean()*100:.0f}%"); c[3].metric("Your pricing path", path)
    comp = []
    for r in range(1, 5):
        for n, cc in M.competitors(r).items():
            comp.append(dict(round=r, price=cc["price"], who=n))
    mine = df[["round", "price"]].assign(who="Your team")
    allp = pd.concat([pd.DataFrame(comp), mine])
    ch = alt.Chart(allp).mark_line(point=True).encode(x=alt.X("round:O", title="Round (Introduction → Decline)"), y=alt.Y("price:Q", title="Price ($)"),
                                                     color=alt.Color("who:N", title=""), strokeWidth=alt.condition(alt.datum.who == "Your team", alt.value(5), alt.value(1.5)))
    st.altair_chart(ch, width='stretch')
    st.markdown("""**Connect it to Chapter 12**
- **Product life cycle:** how did the best price and product mix change from Introduction to Decline?
- **Skimming vs penetration:** which did you use, and did it fit the stage?
- **Brand and packaging:** where did brand spend pay off, and when did it stop?
- **Psychological pricing and tactics:** did charm pricing, bundles or discounts really help?
- **Reference price:** what happened when you raised a price?""")
    with st.form("refl"):
        t = st.text_area("Reflection (2–3 sentences): What was your pricing strategy, and what would you change now that you have seen the whole life cycle?")
        if st.form_submit_button("Save reflection"):
            S.save_reflection(team, t); st.success("Saved. Nice work.")

if mode == "Instructor":
    instructor_view()
else:
    team_view()
