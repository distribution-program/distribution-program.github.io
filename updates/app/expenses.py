"""Driver and vehicle expense ledger (SOURCE-ONLY CANDIDATE, local tables only, no cloud schema, no sync yet).
One shared total-cash ledger: receipts add to it, expenses and cash returns are recorded as separate kinds.
Driver and vehicle are attribution on a line, never separate balances. Entries are append-only revisions:
an edit or void adds a new revision with the user and time; nothing is overwritten, so the balance can always be rebuilt.
Nothing here assumes a currency, an opening balance or a fuel price: they stay UNKNOWN until the user enters them."""
import os, sqlite3, threading, time, uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

KINDS = ("receipt", "expense", "return")   # cash received / spent / handed back (return is NOT an expense)
DEFAULT_CATEGORIES = ["Fuel", "Toll cards", "Maintenance", "Spare parts", "Washing and parking"]
D0 = Decimal(0)

class Store:
    """Own SQLite file (expenses.db next to the data folder). The invoice database is never opened, altered or migrated here."""
    def __init__(self, path):
        self.cx = sqlite3.connect(path, check_same_thread=False); self.lock = threading.Lock()
    def q(self, sql, args=()):
        with self.lock:
            rows = self.cx.execute(sql, args).fetchall(); self.cx.commit(); return rows

_STORES = {}
def store(data_dir):
    path = os.path.join(data_dir, "expenses.db")
    if path not in _STORES:
        st = Store(path); init(st); _STORES[path] = st
    return _STORES[path]

def init(core):
    core.q("""CREATE TABLE IF NOT EXISTS exp_rev(
        entry_id TEXT, rev INTEGER, kind TEXT, entry_date TEXT, amount TEXT, category TEXT, driver TEXT, vehicle TEXT,
        note TEXT, receipt_ref TEXT, odometer TEXT, fuel_price TEXT, fuel_price_source TEXT, liters_receipt TEXT,
        voided INTEGER, by_user TEXT, at REAL, reason TEXT, PRIMARY KEY(entry_id, rev))""")
    core.q("""CREATE TABLE IF NOT EXISTS exp_cfg(key TEXT, value TEXT, effective_from TEXT, by_user TEXT, at REAL)""")

def _dec(v, name, positive=True):
    try:
        d = Decimal(str(v).strip().replace(",", ""))
    except (InvalidOperation, AttributeError):
        raise ValueError(f"{name}: enter a number.")
    if d.is_finite() and d.as_tuple().exponent < -2:
        raise ValueError(f"{name}: at most 2 decimals.")
    if not d.is_finite() or (positive and d <= 0) or d < 0:
        raise ValueError(f"{name}: must be greater than zero." if positive else f"{name}: cannot be negative.")
    return d

def _date(v):
    s = str(v or "").strip()
    try:
        import datetime
        datetime.date.fromisoformat(s)
        return s
    except ValueError:
        raise ValueError("Date: use YYYY-MM-DD.")

# ---------- settings (append-only history; the newest effective_from wins for a given date) ----------
def set_cfg(core, key, value, effective_from, user):
    if key not in ("currency", "opening_balance", "fuel_price"):
        raise ValueError("Unknown setting.")
    v = str(value).strip()
    if key == "currency":
        if not v: raise ValueError("Currency: enter a name or code.")
    elif key == "opening_balance":
        v = str(_dec(v, "Opening balance", positive=False))
    else:
        v = str(_dec(v, "Fuel price per liter"))
    ef = _date(effective_from) if key != "currency" else ""
    core.q("INSERT INTO exp_cfg VALUES(?,?,?,?,?)", (key, v, ef, user, time.time()))
    return {"ok": True}

def cfg_at(core, key, date=None):
    rows = core.q("SELECT value,effective_from,by_user,at FROM exp_cfg WHERE key=? ORDER BY effective_from, at", (key,))
    if key == "currency": return rows[-1][0] if rows else "EGP"
    best = None
    for v, ef, u, at in rows:
        if date is None or ef <= date: best = (v, ef, u)
    if best is None and key == "fuel_price": best = ("20.50", "built-in default", "")
    return best

# ---------- entries ----------
def _current():
    pass

def _latest(core):
    out = {}
    for r in core.q("SELECT * FROM exp_rev ORDER BY entry_id, rev"):
        out[r[0]] = r
    return out

COLS = ["entry_id","rev","kind","entry_date","amount","category","driver","vehicle","note","receipt_ref","odometer",
        "fuel_price","fuel_price_source","liters_receipt","voided","by_user","at","reason"]

def _row(r): return dict(zip(COLS, r))

def _check(core, f, entry_id=None):
    kind = f.get("kind", "expense")
    if kind not in KINDS: raise ValueError("Kind must be receipt, expense or return.")
    out = {"kind": kind, "entry_date": _date(f.get("entry_date")), "amount": str(_dec(f.get("amount"), "Amount")),
           "category": str(f.get("category", "")).strip(), "driver": str(f.get("driver", "")).strip(),
           "vehicle": str(f.get("vehicle", "")).strip(), "note": str(f.get("note", "")).strip(),
           "receipt_ref": str(f.get("receipt_ref", "")).strip(), "odometer": "", "fuel_price": "", "fuel_price_source": "",
           "liters_receipt": ""}
    if kind == "expense" and not out["category"]: raise ValueError("Category is needed for an expense.")
    if kind != "expense": out["category"] = out["category"] or ("Cash received" if kind == "receipt" else "Cash returned")
    if out["category"].casefold() == "fuel" and kind == "expense":
        if not out["vehicle"]: raise ValueError("Fuel: choose the vehicle (fuel is tracked per vehicle).")
        if str(f.get("odometer", "")).strip() == "": raise ValueError("Fuel: enter the odometer reading.")
        odo = _dec(f.get("odometer"), "Odometer", positive=False)
        out["odometer"] = str(odo)
        price = str(f.get("fuel_price", "")).strip()
        if price:
            out["fuel_price"] = str(_dec(price, "Fuel price per liter")); out["fuel_price_source"] = "typed on this entry"
        else:
            cfg = cfg_at(core, "fuel_price", out["entry_date"])
            if not cfg:
                raise ValueError("Fuel: no price per liter is set for this date. Type the price on this entry (or set it in Settings).")
            if f.get("accept_default") is not True:
                raise ValueError(f"Fuel: the Settings price {cfg[0]} (effective {cfg[1]}) would be applied to this entry. Confirm it, or type the price.")
            out["fuel_price"] = cfg[0]; out["fuel_price_source"] = f"Settings price effective {cfg[1]}"
        if str(f.get("liters_receipt", "")).strip(): out["liters_receipt"] = str(_dec(f.get("liters_receipt"), "Liters on receipt"))
    return out

def _write(core, entry_id, rev, v, voided, user, reason):
    core.q("INSERT INTO exp_rev VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
           (entry_id, rev, v["kind"], v["entry_date"], v["amount"], v["category"], v["driver"], v["vehicle"], v["note"],
            v["receipt_ref"], v["odometer"], v["fuel_price"], v["fuel_price_source"], v["liters_receipt"], 1 if voided else 0,
            user, time.time(), reason))

def _opening_guard(core, v):
    ob = cfg_at(core, "opening_balance")
    if ob and ob[1] and v["entry_date"] < ob[1]:
        raise ValueError(f"This date is before the opening balance date {ob[1]}. It would not be counted in the cash balance. "
                         "Change the date, or enter a new opening balance dated earlier.")

def add(core, f, user):
    v = _check(core, f); _opening_guard(core, v)
    eid = "x_" + uuid.uuid4().hex[:12]
    _write(core, eid, 1, v, False, user, "created")
    return {"ok": True, "entry_id": eid}

def edit(core, entry_id, f, user, reason):
    cur = _latest(core).get(entry_id)
    if not cur: raise ValueError("Entry not found.")
    if not str(reason or "").strip(): raise ValueError("Say why this entry is changed.")
    if cur[14]: raise ValueError("This entry was voided. Add a new entry instead.")
    v = _check(core, f); _opening_guard(core, v)
    _write(core, entry_id, cur[1] + 1, v, False, user, reason.strip())
    return {"ok": True}

def void(core, entry_id, user, reason):
    cur = _latest(core).get(entry_id)
    if not cur: raise ValueError("Entry not found.")
    if cur[14]: raise ValueError("Already voided.")
    if not str(reason or "").strip(): raise ValueError("Say why this entry is voided.")
    v = {k: cur[COLS.index(k)] for k in ("kind","entry_date","amount","category","driver","vehicle","note","receipt_ref","odometer","fuel_price","fuel_price_source","liters_receipt")}
    _write(core, entry_id, cur[1] + 1, v, True, user, reason.strip())
    return {"ok": True}

def history(core, entry_id):
    return [_row(r) for r in core.q("SELECT * FROM exp_rev WHERE entry_id=? ORDER BY rev", (entry_id,))]

def ledger(core):
    """Entries oldest first with the balance after each one. Balance is None (unknown) until an opening balance is entered."""
    live = [_row(r) for r in _latest(core).values() if not r[14]]
    live.sort(key=lambda e: (e["entry_date"], e["at"]))
    ob = cfg_at(core, "opening_balance")
    bal = Decimal(ob[0]) if ob else None
    opening_date = ob[1] if ob else None
    last_odo = {}
    rows = []
    for e in live:
        a = Decimal(e["amount"])
        counted = bal is not None and (opening_date is None or e["entry_date"] >= opening_date)
        if counted:
            bal = bal + a if e["kind"] == "receipt" else bal - a
        e = dict(e); e["balance_after"] = str(bal) if counted else None
        e["negative_balance"] = bool(counted and bal < 0)
        if e["kind"] == "expense" and e["category"].casefold() == "fuel" and e["vehicle"] and e["odometer"]:
            odo = Decimal(e["odometer"]); prev = last_odo.get(e["vehicle"])
            e["liters_calc"] = str((Decimal(e["amount"]) / Decimal(e["fuel_price"])).quantize(Decimal("0.01"), ROUND_HALF_UP))
            if e["liters_receipt"]:
                e["liters_diff"] = str((Decimal(e["liters_receipt"]) - Decimal(e["liters_calc"])).quantize(Decimal("0.01")))
            if prev is None: e["distance_since_previous"] = None; e["distance_note"] = "First fuel entry for this vehicle."
            elif odo <= prev[0]: e["distance_since_previous"] = None; e["distance_note"] = "Odometer is not higher than the previous reading; check it."
            else:
                e["distance_since_previous"] = str(odo - prev[0])
                # Money bought at the PREVIOUS fill over the distance driven since it. Not a burn rate: fills are by amount,
                # not full-to-full, so liters bought are not liters burned.
                e["previous_fill_amount_per_distance"] = str((Decimal(prev[1]) / (odo - prev[0])).quantize(Decimal("0.0001")))
                e["distance_note"] = "Estimate of money bought, not fuel actually burned."
            last_odo[e["vehicle"]] = (odo, e["amount"])
        rows.append(e)
    return {"currency": cfg_at(core, "currency"), "opening_balance": ob[0] if ob else None, "opening_effective": opening_date,
            "balance": str(bal) if bal is not None else None, "entries": rows,
            "needs_setup": [k for k, v in (("currency", cfg_at(core, "currency")), ("opening_balance", ob)) if not v],
            "negative_from": next((x["entry_date"] for x in rows if x.get("negative_balance")), None),
            "pending_upload": None, "note": "Local only. Not shared with other PCs yet."}
