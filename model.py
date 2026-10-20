"""Market model for the Product & Pricing Decision Lab (BSAD 130, Chapter 12).
All numbers are invented teaching assumptions. Pure Python, no dependencies."""
import math, random, hashlib

ROUNDS = 4
STAGES = ["Introduction", "Growth", "Maturity", "Decline"]
MARKET_UNITS = [66000, 114000, 136000, 97000]          # whole-category units per round
PRICE_SENS_MULT = [0.70, 0.90, 1.20, 1.40]            # early adopters care less about price
BRAND_MULT = [0.80, 1.00, 1.10, 0.90]

QUALITY = {"Basic": 1, "Standard": 2, "Premium": 3}
QUALITY_COST = {"Basic": 0.00, "Standard": 0.60, "Premium": 1.70}
PACK = {"Basic": (0.0, 0.0), "Eco": (0.3, 0.8), "Premium": (0.0, 1.3)}   # (functional, image)
PACK_COST = {"Basic": 0.00, "Eco": 0.30, "Premium": 0.50}
BASE_COST = 1.10
OVERHEAD = 2000
BRAND_SPEND = [0, 1000, 2500, 4000, 6000]
TACTICS = ["Everyday price", "Introductory discount (15% off)", "Charm price (ends in .99)", "2-pack bundle (8% off per unit)"]
REFRESH_COST = 3000

# segments: (name, share of buyers, price sens, quality wt, brand wt, packaging image wt, packaging functional wt)
SEGMENTS = [
    ("Budget seekers",  0.40, 1.70, 0.30, 0.25, 0.05, 0.10),
    ("Quality seekers", 0.30, 0.80, 0.85, 0.35, 0.10, 0.20),
    ("Trend followers", 0.30, 0.70, 0.30, 0.90, 0.50, 0.10),
]

NONE_W = {"Budget seekers": 0.9, "Quality seekers": 0.5, "Trend followers": 0.7}

# competitors per round: name -> (quality, pack, price, brand, awareness)
def competitors(rnd):
    c = {
        "ValueCo":   dict(q=1, pk="Basic",   price=2.49, brand=3.0, aw=0.90),
        "MainBrand": dict(q=2, pk="Basic",   price=3.49, brand=6.0, aw=0.95),
        "PremiumCo": dict(q=3, pk="Eco",     price=4.99, brand=5.0, aw=0.80),
    }
    if rnd >= 3:
        c["MainBrand"]["price"] = 3.29                      # price war starts
        c["Trendster"] = dict(q=2, pk="Premium", price=3.99, brand=4.0, aw=0.65)   # new entrant
    if rnd == 4:
        c["ValueCo"]["price"] = 1.99
        c["MainBrand"]["price"] = 2.99
    return c

NOTES = [
    "Introduction: few buyers, mostly early adopters who care about novelty. Few people know your brand yet.",
    "Growth: the market is booming and more rivals are noticing. Word of mouth starts to work.",
    "Maturity: the market is at its biggest, but buyers compare prices harder. A newcomer, Trendster, enters and MainBrand cuts its price.",
    "Decline: the category is shrinking and shoppers look for bargains. ValueCo and MainBrand cut prices again.",
]

def unit_cost(quality, pack, tactic):
    c = BASE_COST + QUALITY_COST[quality] + PACK_COST[pack]
    if tactic.startswith("2-pack"):
        c += 0.05
    return round(c, 2)

def initial_state():
    return dict(brand=1.0, prev_share=0.0, ref_price=None)

def _noise(team, rnd):
    h = hashlib.md5(f"{team}|{rnd}".encode()).hexdigest()
    return 1 + (random.Random(h).random() - 0.5) * 0.06   # +/-3%, stable per team and round

def simulate_round(rnd, d, state, team="x"):
    """d: dict(quality, pack, brand_spend, price, tactic, refresh). Returns (result, new_state)."""
    q = QUALITY[d["quality"]] + (0.5 if d.get("refresh") else 0.0)
    price = float(d["price"])
    tactic = d["tactic"]
    if tactic.startswith("Introductory") and rnd > 2:
        tactic = TACTICS[0]
    # brand strength this round
    b = state["brand"]
    b = 0.70 * b + 1.1 * math.log(1 + d["brand_spend"] / 1000.0) + 0.5 * (QUALITY[d["quality"]] - 2)
    if state["prev_share"] > 0.20:
        b += 0.4
    if d.get("refresh"):
        b += 1.0
    if tactic.startswith("Introductory") and b < 4:
        b += 0.3                                           # trial effect for a little-known brand
    b = max(0.0, min(10.0, b))
    awareness = max(0.10, 1 - math.exp(-b / 3.0))

    # prices buyers perceive
    pay = price
    unit_mult = 1.0
    perc_adj = {"Budget seekers": 0.0, "Quality seekers": 0.0, "Trend followers": 0.0}
    if tactic.startswith("Introductory"):
        pay = price * 0.85
    elif tactic.startswith("Charm"):
        pay = price - 0.01
        perc_adj = {"Budget seekers": 0.12, "Quality seekers": 0.05, "Trend followers": 0.08}
    elif tactic.startswith("2-pack"):
        pay = price * 0.92
        unit_mult = 1.10                                    # bundle buyers take more units
    ref = state.get("ref_price")
    anchor = 0.0
    if ref:
        anchor = 1.6 * max(0.0, pay / ref - 1.05)          # buyers resent price jumps
    comp = competitors(rnd)
    pf, pi = PACK[d["pack"]]
    sm, bm = PRICE_SENS_MULT[rnd - 1], BRAND_MULT[rnd - 1]

    units_share = 0.0
    seg_detail = {}
    for name, w, ps, wq, wb, wpi, wpf in SEGMENTS:
        def util(qv, packname, p, br, adj=0.0):
            f, i = PACK[packname]
            return (-ps * sm * (p - adj) + wq * qv + wb * bm * (br / 2.0) + wpi * i + wpf * f)
        weights = {}
        weights["YOU"] = awareness * math.exp(util(q, d["pack"], pay, b, perc_adj[name]) - anchor)
        for cn, c in comp.items():
            weights[cn] = c["aw"] * math.exp(util(c["q"], c["pk"], c["price"], c["brand"]))
        weights["NONE"] = NONE_W[name]
        tot = sum(weights.values())
        s = weights["YOU"] / tot
        seg_detail[name] = s
        units_share += w * s
    noise = _noise(team, rnd)
    market = MARKET_UNITS[rnd - 1]
    units = int(round(market * units_share * unit_mult * noise))
    share = units_share * noise
    uc = unit_cost(d["quality"], d["pack"], tactic)
    # for a bundle, price per unit is `pay`
    revenue = units * pay
    var_cost = units * uc
    fixed = OVERHEAD + d["brand_spend"] + (REFRESH_COST if d.get("refresh") else 0)
    profit = revenue - var_cost - fixed
    res = dict(round=rnd, stage=STAGES[rnd - 1], units=units, share=round(share, 4), price_paid=round(pay, 2),
               unit_cost=uc, revenue=round(revenue), variable_cost=round(var_cost), fixed_cost=fixed,
               profit=round(profit), brand_strength=round(b, 2), anchor_penalty=round(anchor, 2), awareness=round(awareness, 2),
               market_units=market, segments={k: round(v, 3) for k, v in seg_detail.items()},
               margin_per_unit=round(pay - uc, 2))
    return res, dict(brand=b, prev_share=share, ref_price=pay)

def explain(res, d):
    """Plain-language reading of the results tied to chapter concepts."""
    out = []
    segs = res["segments"]
    best = max(segs, key=segs.get)
    out.append(f"Your strongest segment was **{best}** (you won {segs[best]*100:.0f}% of them).")
    if res["margin_per_unit"] < 0.8:
        out.append("Your margin per unit is thin. Volume has to do all the work.")
    elif res["margin_per_unit"] > 2.2:
        out.append("A fat margin per unit. Check whether the volume you lost was worth it.")
    if res["awareness"] < 0.35:
        out.append("Few buyers know your brand yet. Branding spend works with a lag and builds on itself.")
    if res["profit"] < 0:
        out.append("A loss this round. Look at fixed costs against units sold.")
    return out
