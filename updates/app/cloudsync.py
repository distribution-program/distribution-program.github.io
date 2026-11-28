"""Distribution Program cloud protocol v2. Durable soft deletes, timestamp-checked writes, live lists.
No credentials or cloud connection is created here. The caller supplies its existing client.
"""
import json
import threading
import time


class CloudSync:
    def __init__(self, core):
        self.c = core
        self.conflicts = []
        self.changed = False
        self.acks = {}          # uid -> 'written' | 'server_newer' | 'deleted' (last push result per invoice)
        self.live = False       # True only after the first full state arrived; only live listener changes are counted
        # last = the latest SUCCESSFUL receive batch (listener delivery or finished F5 pull) that changed something.
        self.recv = {"last": None, "session": {"new": 0, "updated": 0, "deleted": 0}, "initial_at": 0.0}
        self.recv["history"] = json.loads(core.meta("receive_history_v36", "[]"))
        self.recv["events"]=[]
        self.event_seq=0
        try: self.wm=float(core.meta("notify_wm","0") or 0)
        except ValueError: self.wm=0.0
        self.kept_local = 0     # pull: remote copies NOT applied because local is unsent/newer
        core.q("CREATE TABLE IF NOT EXISTS sync_conflicts(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, key TEXT, data TEXT, recorded REAL)")

    def journal(self):
        try: return json.loads(self.c.meta("notify_journal_v55", "[]"))
        except ValueError: return []

    def event(self, operation, uid, data, count, actor="", old=None):
        if count is None or data.get("_kind"):return
        self.event_seq+=1
        self.recv["events"].append({"seq":self.event_seq,"operation":operation,"invoice":str(data.get("Invoice Number",uid)),"customer":str(data.get("Customer Name",""))})
        self.recv["events"]=self.recv["events"][-1000:]
        # Persistent notification journal (v55). Delete rows keep only number, customer and deleting user: no snapshot.
        now=time.time();eid=int(now*1000)
        j=self.journal()
        if j and eid<=j[-1]["id"]: eid=j[-1]["id"]+1
        row={"id":eid,"at":now,"operation":operation,"invoice":str(data.get("Invoice Number",uid)),"customer":str(data.get("Customer Name",""))}
        if operation=="Delete": row["by"]=actor or ""
        else:
            row["by"]=data.get("Last Updated By","") if operation=="Edit" else data.get("Entered By","")
            row["entered_by"]=data.get("Entered By","")
            row["details"]={k:v for k,v in data.items() if not k.startswith("_") and k not in ("updated","seq","sync_protocol")}
            if operation=="Edit" and isinstance(old,dict):
                skip=("updated","seq","sync_protocol","Last Updated By")
                ch=[]
                for k in sorted(set(old)|set(data)):
                    if k.startswith("_") or k in skip: continue
                    ov,nv=str(old.get(k,"") or ""),str(data.get(k,"") or "")
                    if ov!=nv: ch.append({"field":k,"old":ov,"new":nv})
                row["changes"]=ch
        j.append(row)
        self.c.setmeta("notify_journal_v55", json.dumps(j[-300:],ensure_ascii=False))

    def preserve(self, kind, key, data):
        self.c.q("INSERT INTO sync_conflicts(kind,key,data,recorded) VALUES(?,?,?,?)",
                 (kind, key, json.dumps(data, ensure_ascii=False), time.time()))

    @staticmethod
    def newbatch(source):
        return {"source": source, "new": 0, "updated": 0, "deleted": 0, "kept_local": 0, "conflicts": 0, "at": 0.0}

    def publish(self, b):
        """Only called after a delivery/pull completed successfully. No-op batches are not published."""
        if not (b["new"] or b["updated"] or b["deleted"] or b["conflicts"]): return   # kept-only is reported by the F5 line, not as a receive
        b["at"] = time.time(); self.recv["last"] = b
        self.recv["history"] = ([dict(b)] + self.recv.get("history", []))[:50]
        self.c.setmeta("receive_history_v36",json.dumps(self.recv["history"]))
        for k in ("new", "updated", "deleted"): self.recv["session"][k] += b[k]

    def tombstone(self, uid, data, count=None):
        c = self.c
        ts = float(data.get("updated", 0) or 0)
        old = c.q("SELECT ts FROM dellan WHERE uid=?", (uid,))
        present = c.q("SELECT data,dirty FROM inv WHERE uid=?", (uid,))
        if present and present[0][1]:
            self.preserve("deleted_invoice", uid, json.loads(present[0][0]))
            if count is not None: count["conflicts"] += 1
        with c.LOCK:
            c.cx.execute("DELETE FROM inv WHERE uid=?", (uid,))
            if not old or float(old[0][0]) < ts:
                c.cx.execute("INSERT OR REPLACE INTO dellan VALUES(?,?,1)", (uid, ts))
            c.cx.commit()
        self.changed |= bool(present) or not old
        if count is not None and present:
            count["deleted"] += 1
            self.event("Delete",uid,json.loads(present[0][0]),count,data.get("deleted_by",""))

    def apply_record(self, uid, data, count=None):
        c = self.c
        if data.get("_deleted") is True:
            self.tombstone(uid, data, count)
            return
        if c.q("SELECT 1 FROM dellan WHERE uid=?", (uid,)):
            return
        up = float(data.get("updated", 0) or 0)
        if count is None and not self.live and self.wm and up > self.wm - 5:
            count = self.newbatch("startup catch-up")   # changes made while this PC was closed still get notices
        with c.LOCK:
            r = c.cx.execute("SELECT updated,dirty,data FROM inv WHERE uid=?", (uid,)).fetchone()
            if r and (r[1] or float(r[0] or 0) > up):
                if json.loads(r[2]) != data:
                    self.kept_local += 1
                    if count is not None: count["kept_local"] += 1
                return
            if r and float(r[0] or 0) == up:
                if json.loads(r[2]) == data:
                    return
                self.preserve("invoice_equal_timestamp", uid, json.loads(r[2]))
                if count is not None: count["conflicts"] += 1
            old_rec = json.loads(r[2]) if r else None
            c.cx.execute("INSERT OR REPLACE INTO inv(uid,data,updated,dirty,lan) VALUES(?,?,?,0,1)",
                         (uid, json.dumps(data, ensure_ascii=False), up))
            c.cx.commit()
            if count is not None:
                count["new" if r is None else "updated"] += 1
                self.event("Add" if r is None else "Edit",uid,data,count,"",old_rec)
                try: edited_before_seen = r is None and int(data.get("_rev", 1) or 1) >= 2
                except (TypeError, ValueError): edited_before_seen = False
                if edited_before_seen: self.event("Edit",uid,data,count,"",None)   # arrived already edited: keep the Edit notice
        self.changed = True

    def checked_write(self, ref, payload, permanently_deleted=False):
        """All clients must perform this check in a Firestore transaction.
        A tombstone always wins, regardless of the stale writer's clock.
        """
        c = self.c
        @c.firestore.transactional
        def run(tx):
            snap = ref.get(transaction=tx)
            remote = snap.to_dict() if snap.exists else None
            self._prev = remote
            if remote and remote.get("_deleted") is True:
                return "deleted", remote
            if permanently_deleted:
                tx.set(ref, payload)
                return "written", payload
            if remote and float(remote.get("updated", 0) or 0) >= float(payload.get("updated", 0) or 0):
                return "remote", remote
            tx.set(ref, payload)
            return "written", payload
        return run(c.db.transaction())

    # ---- driver_state marker: the phone watches one tiny doc per driver instead of querying invoices ----
    def _note_driver_change(self, old, new):
        """Remember which drivers' lists changed (old and new driver)."""
        names = getattr(self, "_dn", None)
        if names is None: names = self._dn = set()
        old = old or {}; new = new or {}
        keys = ("Driver name", "Invoice Status", "Delivered By", "Delivered At")
        if old and all(old.get(k) == new.get(k) for k in keys): return
        for d in (old, new):
            n = str(d.get("Driver name", "") or "").strip()
            if n: names.add(n)

    def _bump_drivers(self):
        names = getattr(self, "_dn", None); self._dn = set()
        if not names: return
        try:
            c = self.c
            for n in names:
                key = n.replace("/", "_")    # document id: the Driver name as printed on invoices, "/" replaced by "_"
                c.db.collection("driver_state").document(key).set({"rev": c.firestore.Increment(1), "updated": time.time()}, merge=True)
        except Exception:
            pass   # the marker is best effort: a failure never blocks invoice sync

    def push(self):
        c = self.c
        self.conflicts = []
        # Tombstones go first. Existing queued physical invoice deletes are migrated here.
        for kind, key in c.q("SELECT kind,key FROM del"):
            if kind != "invoices":
                c.db.collection(kind).document(key).delete()
                c.q("DELETE FROM del WHERE kind=? AND key=?", (kind, key))
                continue
            rows = c.q("SELECT ts FROM dellan WHERE uid=?", (key,))
            ts = float(rows[0][0]) if rows else time.time()
            payload = {"_deleted": True, "updated": ts, "sync_protocol": 2}
            by = c.meta("delby_" + key, "")
            if by: payload["deleted_by"] = by
            _, remote = self.checked_write(c.db.collection("invoices").document(key), payload, True)
            self.tombstone(key, remote)
            c.q("DELETE FROM del WHERE kind=? AND key=?", (kind, key))
        for uid, raw, updated in c.q("SELECT uid,data,updated FROM inv WHERE dirty=1"):
            if c.q("SELECT 1 FROM dellan WHERE uid=?", (uid,)):
                self.tombstone(uid, {"updated": float(c.q("SELECT ts FROM dellan WHERE uid=?", (uid,))[0][0])})
                continue
            _mine = json.loads(raw)
            self._prev = None
            result, remote = self.checked_write(c.db.collection("invoices").document(uid), _mine)
            if result == "written":
                self._note_driver_change(self._prev, _mine)
            if result == "deleted":
                self.acks[uid] = ("deleted", updated)
                self.tombstone(uid, remote)
                self.conflicts.append("A locally edited invoice was deleted on another device: " + uid)
            else:
                self.acks[uid] = ("server_newer", float(remote.get("updated", 0) or 0)) if result == "remote" else ("written", updated)
                c.q("UPDATE inv SET dirty=0 WHERE uid=? AND updated=?", (uid, updated))
                if result == "remote":
                    if remote != json.loads(raw):
                        self.preserve("invoice", uid, json.loads(raw))
                    self.apply_record(uid, remote)
                    self.conflicts.append("A newer remote invoice was kept: " + uid)
        self._bump_drivers()
        for name, raw in c.q("SELECT name,items FROM lst WHERE dirty=1"):
            key = "list_updated:" + name
            ts = float(c.meta(key, 0) or 0)
            if not ts:  # legacy unsynced list, timestamp assigned once and persisted
                ts = time.time()
                c.setmeta(key, ts)
            result, remote = self.checked_write(c.db.collection("lists").document(name),
                                                {"items": json.loads(raw), "updated": ts})
            with c.LOCK:
                # Do not erase an edit made while the network call was running.
                if float(c.meta(key, 0) or 0) != ts:
                    continue
                if result == "remote":
                    c.cx.execute("UPDATE lst SET items=?,dirty=0 WHERE name=?", (json.dumps(remote.get("items", [])), name))
                    c.setmeta(key, float(remote.get("updated", 0) or 0))
                    if remote.get("items", []) != json.loads(raw):
                        self.preserve("list", name, {"items": json.loads(raw), "updated": ts})
                        self.conflicts.append("A newer remote list was kept: " + name)
                    self.changed = True
                else:
                    c.cx.execute("UPDATE lst SET dirty=0 WHERE name=?", (name,))
                c.cx.commit()
        for name, pw, up in c.q("SELECT name,pw,updated FROM usr WHERE dirty=1"):
            c.db.collection("users").document(name).set({"pw": pw, "updated": up})
            c.q("UPDATE usr SET dirty=0 WHERE name=? AND updated=?", (name, up))

    def apply_list(self, name, data):
        c = self.c
        key = "list_updated:" + name
        ts = float(data.get("updated", 0) or 0)
        with c.LOCK:
            r = c.cx.execute("SELECT dirty,items FROM lst WHERE name=?", (name,)).fetchone()
            local = float(c.meta(key, -1))
            if r and (r[0] or local > ts):
                return
            if r and local == ts:
                if json.loads(r[1]) == data.get("items", []):
                    return
                self.preserve("list_equal_timestamp", name, {"items": json.loads(r[1]), "updated": local})
            c.cx.execute("INSERT OR REPLACE INTO lst VALUES(?,?,0)", (name, json.dumps(data.get("items", []))))
            c.setmeta(key, ts)
            c.cx.commit()
        self.changed = True

    def pull(self, first=False):
        c = self.c
        self.kept_local = 0
        b = self.newbatch("manual F5 read") if self.live else None
        for doc in c.db.collection("invoices").stream():
            self.apply_record(doc.id, doc.to_dict(), b)
        for doc in c.db.collection("lists").stream():
            self.apply_list(doc.id, doc.to_dict())
        if b is not None: self.publish(b)   # reached only when both streams finished without an error
        if first:
            for doc in c.db.collection("users").stream():
                data = doc.to_dict()
                rows = c.q("SELECT dirty,updated FROM usr WHERE name=?", (doc.id,))
                if not (rows and (rows[0][0] or rows[0][1] >= data.get("updated", 0))):
                    c.q("INSERT OR REPLACE INTO usr VALUES(?,?,?,0)", (doc.id, data["pw"], data.get("updated", 0)))
                    self.changed = True

    def watch(self, changed, ready=None):
        # Firestore manages reconnect/resume tokens. No timestamp cursor is used.
        # Both listeners are kept alive by the caller for the process lifetime.
        def invoices(snapshots, changes, read_time):
            b = self.newbatch("live update") if self.live else None
            for change in changes:
                doc = change.document
                if change.type.name == "REMOVED":
                    # Legacy physical deletion: retain a local tombstone and queue repair
                    # so this protocol's other clients also learn the deletion.
                    self.tombstone(doc.id, {"updated": time.time()}, b)
                    self.c.q("INSERT INTO del VALUES('invoices',?)", (doc.id,))
                else:
                    self.apply_record(doc.id, doc.to_dict(), b)
            if b is not None: self.publish(b)
            if self.live: self.c.setmeta("notify_wm", time.time())
            changed()
            if ready: ready[0].set()
        def lists(snapshots, changes, read_time):
            for change in changes:
                if change.type.name != "REMOVED":
                    self.apply_list(change.document.id, change.document.to_dict())
            changed()
            if ready: ready[1].set()
        return [self.c.db.collection("invoices").on_snapshot(invoices),
                self.c.db.collection("lists").on_snapshot(lists)]

    def first_sync(self, changed, timeout=180):
        """Startup candidate: the listeners' initial snapshots ARE the first pull (one full read instead of two).
        Returns the live listeners only after BOTH initial snapshots were applied. On timeout the listeners are
        removed and TimeoutError is raised, so the caller never reports 'received' for a partial read."""
        c = self.c
        self.kept_local = 0
        ready = (threading.Event(), threading.Event())
        watches = self.watch(changed, ready)
        end = time.monotonic() + timeout
        for ev in ready:
            if not ev.wait(max(0, end - time.monotonic())):
                for w in watches:
                    try: w.unsubscribe()
                    except Exception: pass
                raise TimeoutError("initial cloud snapshot did not finish")
        for doc in c.db.collection("users").stream():
            data = doc.to_dict()
            rows = c.q("SELECT dirty,updated FROM usr WHERE name=?", (doc.id,))
            if not (rows and (rows[0][0] or rows[0][1] >= data.get("updated", 0))):
                c.q("INSERT OR REPLACE INTO usr VALUES(?,?,?,0)", (doc.id, data["pw"], data.get("updated", 0)))
                self.changed = True
        self.recv["initial_at"] = time.time(); self.live = True; self.wm = time.time(); self.c.setmeta("notify_wm", self.wm)   # from now on listener changes are operational receipts
        return watches
