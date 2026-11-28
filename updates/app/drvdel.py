"""Driver Deliveries: invoices the phone marked delivered wait here until a user confirms them by typing the invoice number."""
import re, time

def _s(x): return str(x or "").strip()
def _inproc(d): return d.get("Invoice Status") == "inprocess"
def _marked(d): return bool(_s(d.get("Delivered By")))

def _tail(n):
    m = re.search(r"(\d+)$", n)
    return (m.group(1).lstrip("0") or "0") if m else None

def match(query, number):
    q, n = _s(query).casefold(), _s(number).casefold()
    if not q: return False
    if q == n: return True
    if re.fullmatch(r"\d+", q): return _tail(n) == (q.lstrip("0") or "0")
    return False

def install(s):
    def rows():
        return [(u, d) for u, d in s.docs.items() if not d.get("_kind")]
    def drivers():
        out = {}
        for u, d in rows():
            if not _inproc(d): continue
            n = _s(d.get("Driver name"))
            if not n: continue
            r = out.setdefault(n, {"driver": n, "car": _s(d.get("Car No")), "line": _s(d.get("Line")), "inprocess": 0, "marked": 0})
            r["inprocess"] += 1
            if _marked(d): r["marked"] += 1
        lst = sorted(out.values(), key=lambda r: (-r["marked"], r["driver"].casefold()))
        return {"ok": True, "drivers": lst, "to_check": sum(r["marked"] for r in lst)}
    def driver(name):
        name = _s(name)
        items = []
        for u, d in rows():
            if _s(d.get("Driver name")) == name and _inproc(d) and _marked(d):
                items.append({"invoice": _s(d.get("Invoice Number")), "customer": _s(d.get("Customer Name")), "district": _s(d.get("District")),
                              "by": _s(d.get("Delivered By")), "at": _s(d.get("Delivered At")), "status": "In Process"})
        items.sort(key=lambda r: r["at"])
        return {"ok": True, "driver": name, "items": items}
    def check(name, number, user):
        name, number = _s(name), _s(number)
        if not number: return {"ok": False, "msg": "Type an invoice number."}
        hits = [(u, d) for u, d in rows() if match(number, d.get("Invoice Number"))]
        mine = [(u, d) for u, d in hits if _s(d.get("Driver name")) == name]
        if not mine:
            return {"ok": False, "kind": "outside", "msg": "Outside this driver's line/list."}
        exact = [(u, d) for u, d in mine if _s(d.get("Invoice Number")).casefold() == number.casefold()]
        mine = exact or mine
        if len(mine) > 1: return {"ok": False, "kind": "many", "msg": "More than one invoice matches. Type the full invoice number."}
        uid, d = mine[0]
        if d.get("Invoice Status") == "Delivered": return {"ok": False, "kind": "duplicate", "msg": "Duplicate: " + _s(d.get("Invoice Number")) + " is already Delivered."}
        if not _inproc(d): return {"ok": False, "kind": "outside", "msg": "Outside this driver's list: status is " + _s(d.get("Invoice Status")) + "."}
        with s.core.LOCK, s.STATE_LOCK:
            cur = s.docs.get(uid)
            if not cur or not _inproc(cur): return {"ok": False, "msg": "The invoice changed. Try again."}
            rec = dict(cur)
            rec["Invoice Status"] = "Delivered"
            if not _s(rec.get("Delivered By")):
                rec["Delivered By"] = name; rec["Delivered At"] = time.strftime("%d/%m/%Y %H:%M:%S")
            s.ACTOR.user = user
            s.save_doc(uid, rec)
        return {"ok": True, "msg": "Checked: " + _s(rec.get("Invoice Number")) + " is now Delivered.", "invoice": _s(rec.get("Invoice Number"))}
    return drivers, driver, check
