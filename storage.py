"""Storage: Supabase when secrets are present, otherwise a local SQLite file (for testing)."""
import json, os, sqlite3, time
import streamlit as st

TABLE = "pp_submissions"

def _has_supabase():
    try:
        return "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets
    except Exception:
        return False

@st.cache_resource
def _sb():
    from supabase import create_client
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

DB_PATH = os.environ.get("PP_DB", "local_results.db")

def _lite():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS pp_submissions (
        team TEXT, round INTEGER, members TEXT, objective TEXT, decisions TEXT, results TEXT, created REAL,
        PRIMARY KEY (team, round))""")
    con.execute("CREATE TABLE IF NOT EXISTS pp_settings (k TEXT PRIMARY KEY, v TEXT)")
    con.execute("""CREATE TABLE IF NOT EXISTS pp_reflections (team TEXT PRIMARY KEY, text TEXT, created REAL)""")
    return con

def backend_name():
    return "Supabase" if _has_supabase() else "Local test database (not shared)"

def save_submission(team, rnd, members, objective, decisions, results):
    row = dict(team=team, round=rnd, members=members, objective=objective,
               decisions=json.dumps(decisions), results=json.dumps(results))
    if _has_supabase():
        _sb().table(TABLE).upsert(row, on_conflict="team,round").execute()
    else:
        con = _lite()
        con.execute("INSERT OR REPLACE INTO pp_submissions VALUES (?,?,?,?,?,?,?)",
                    (team, rnd, members, objective, row["decisions"], row["results"], time.time()))
        con.commit(); con.close()

def load_team(team):
    """Return list of rows (dict) for this team ordered by round."""
    if _has_supabase():
        r = _sb().table(TABLE).select("*").eq("team", team).order("round").execute().data
    else:
        con = _lite(); cur = con.execute("SELECT team,round,members,objective,decisions,results FROM pp_submissions WHERE team=? ORDER BY round", (team,))
        r = [dict(zip(["team", "round", "members", "objective", "decisions", "results"], x)) for x in cur.fetchall()]; con.close()
    for x in r:
        x["decisions"] = json.loads(x["decisions"]) if isinstance(x["decisions"], str) else x["decisions"]
        x["results"] = json.loads(x["results"]) if isinstance(x["results"], str) else x["results"]
    return r

def load_all():
    if _has_supabase():
        r = _sb().table(TABLE).select("*").order("round").execute().data
    else:
        con = _lite(); cur = con.execute("SELECT team,round,members,objective,decisions,results FROM pp_submissions ORDER BY round")
        r = [dict(zip(["team", "round", "members", "objective", "decisions", "results"], x)) for x in cur.fetchall()]; con.close()
    for x in r:
        x["decisions"] = json.loads(x["decisions"]) if isinstance(x["decisions"], str) else x["decisions"]
        x["results"] = json.loads(x["results"]) if isinstance(x["results"], str) else x["results"]
    return r

def get_max_round(default=4):
    if _has_supabase():
        r = _sb().table("pp_settings").select("v").eq("k", "max_round").execute().data
        return int(r[0]["v"]) if r else default
    con = _lite(); r = con.execute("SELECT v FROM pp_settings WHERE k='max_round'").fetchone(); con.close()
    return int(r[0]) if r else default

def set_max_round(n):
    if _has_supabase():
        _sb().table("pp_settings").upsert({"k": "max_round", "v": str(n)}, on_conflict="k").execute()
    else:
        con = _lite(); con.execute("INSERT OR REPLACE INTO pp_settings VALUES ('max_round',?)", (str(n),)); con.commit(); con.close()

def save_reflection(team, text):
    if _has_supabase():
        _sb().table("pp_reflections").upsert({"team": team, "text": text}, on_conflict="team").execute()
    else:
        con = _lite(); con.execute("INSERT OR REPLACE INTO pp_reflections VALUES (?,?,?)", (team, text, time.time())); con.commit(); con.close()

def load_reflections():
    if _has_supabase():
        return _sb().table("pp_reflections").select("*").execute().data
    con = _lite(); cur = con.execute("SELECT team,text FROM pp_reflections"); r = [dict(team=a, text=b) for a, b in cur.fetchall()]; con.close(); return r

def clear_all():
    if _has_supabase():
        for t, col in (("pp_submissions", "team"), ("pp_reflections", "team")):
            _sb().table(t).delete().neq(col, "").execute()
    else:
        con = _lite(); con.execute("DELETE FROM pp_submissions"); con.execute("DELETE FROM pp_reflections"); con.commit(); con.close()
