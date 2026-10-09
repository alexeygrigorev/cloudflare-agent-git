"""Durable project role election authority, called by existing supervisor ticks.

This authority is single-host SQLite. Partitioned clients fail closed; no local
fallback election is permitted. Epochs must be enforced by every launch consumer.
"""
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class Fenced(RuntimeError):
    pass


class RoleAuthority:
    def __init__(self, path, clock=time.time, boot_id=None):
        self.path = str(path)
        self.clock = clock
        self.boot_id = boot_id or Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._tx() as db:
            for stmt in '''
            CREATE TABLE IF NOT EXISTS authority_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, parent TEXT REFERENCES projects(id));
            CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY, host TEXT NOT NULL,
              generation TEXT NOT NULL, seen REAL NOT NULL, ready INTEGER NOT NULL,
              draft INTEGER NOT NULL, quota INTEGER NOT NULL, priority INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS candidates(project TEXT NOT NULL, role TEXT NOT NULL,
              agent TEXT NOT NULL, PRIMARY KEY(project,role,agent));
            CREATE TABLE IF NOT EXISTS roles(project TEXT NOT NULL, role TEXT NOT NULL,
              holder TEXT, generation TEXT, epoch INTEGER NOT NULL DEFAULT 0,
              expires REAL NOT NULL DEFAULT 0, activation_due REAL NOT NULL DEFAULT 0, check_due REAL NOT NULL DEFAULT 0,
              standup_due REAL, suspect_since REAL,
              PRIMARY KEY(project,role));
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,
              project TEXT NOT NULL, role TEXT NOT NULL, kind TEXT NOT NULL,
              epoch INTEGER NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS activation_receipts(project TEXT NOT NULL, role TEXT NOT NULL,
              epoch INTEGER NOT NULL, role_ack TEXT NOT NULL, first_action TEXT NOT NULL,
              PRIMARY KEY(project,role,epoch));
            CREATE TABLE IF NOT EXISTS startup_plans(project TEXT NOT NULL, role TEXT NOT NULL, task TEXT NOT NULL, PRIMARY KEY(project,role));
            CREATE TABLE IF NOT EXISTS actions(key TEXT PRIMARY KEY, project TEXT NOT NULL,
              role TEXT NOT NULL, epoch INTEGER NOT NULL, payload TEXT NOT NULL);

            CREATE TABLE IF NOT EXISTS reply_obligations(key TEXT PRIMARY KEY, nonce TEXT UNIQUE NOT NULL,
              project TEXT NOT NULL, role TEXT NOT NULL, actor TEXT NOT NULL, generation TEXT NOT NULL,
              epoch INTEGER NOT NULL, body TEXT NOT NULL, created REAL NOT NULL, state TEXT NOT NULL,
              delivered REAL, deadline REAL, envelope TEXT UNIQUE, delivery_ref TEXT UNIQUE,
              reply_ref TEXT UNIQUE, reply_event REAL, reply_native_event TEXT UNIQUE, next_action TEXT, checkpoint TEXT);
            CREATE TABLE IF NOT EXISTS reply_tombstones(actor TEXT NOT NULL, generation TEXT NOT NULL,
              created REAL NOT NULL, PRIMARY KEY(actor,generation));
            CREATE TABLE IF NOT EXISTS reply_logical_roles(project TEXT NOT NULL, role TEXT NOT NULL,
              logical TEXT NOT NULL, PRIMARY KEY(project,role));
            '''.strip().split(';'):
                if stmt.strip():
                    db.execute(stmt)
            if 'activation_due' not in [r[1] for r in db.execute('PRAGMA table_info(roles)')]:
                db.execute('ALTER TABLE roles ADD COLUMN activation_due REAL NOT NULL DEFAULT 0')
            if 'reply_native_event' not in [row[1] for row in db.execute('PRAGMA table_info(reply_obligations)')]:
                db.execute('ALTER TABLE reply_obligations ADD COLUMN reply_native_event TEXT')
                db.execute('CREATE UNIQUE INDEX reply_native_event_unique ON reply_obligations(reply_native_event)')
            old = db.execute("SELECT value FROM authority_meta WHERE key='boot'").fetchone()
            if old and old[0] != self.boot_id:
                db.execute('UPDATE roles SET expires=0,suspect_since=NULL')
                # Retain wall-clock highwater: reboot cannot revive a due reply obligation.
            db.execute("INSERT OR REPLACE INTO authority_meta VALUES('boot',?)", (self.boot_id,))
        Path(self.path).chmod(0o600)

    def _reply_sweep(self, db):
        """Commit-independent safety prelude; caller action writes are never present here."""
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='authority_meta'").fetchone():
            return False
        now = float(self.clock())
        import math
        if not math.isfinite(now):
            raise Fenced('nonfinite authority clock')
        last = db.execute("SELECT value FROM authority_meta WHERE key='last_clock'").fetchone()
        highwater = max(now, float(last[0]) if last else now)
        db.execute("INSERT OR REPLACE INTO authority_meta VALUES('last_clock',?)", (str(highwater),))
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='reply_obligations'").fetchone():
            due = db.execute("SELECT * FROM reply_obligations WHERE state IN ('pending','delivered') AND deadline<=?", (highwater,)).fetchall()
            for ob in due:
                changed = db.execute("""UPDATE roles SET holder=NULL,generation=NULL,epoch=epoch+1,
                  expires=0,activation_due=0,suspect_since=NULL WHERE project=? AND role=?
                  AND holder=? AND generation=? AND epoch=?""",
                  (ob['project'],ob['role'],ob['actor'],ob['generation'],ob['epoch'])).rowcount
                db.execute("UPDATE reply_obligations SET state='revoked' WHERE nonce=? AND state IN ('pending','delivered')", (ob['nonce'],))
                db.execute('INSERT OR IGNORE INTO reply_tombstones VALUES(?,?,?)', (ob['actor'],ob['generation'],highwater))
                if changed:
                    self._event(db,ob['project'],ob['role'],'reply_deadline_revoked',ob['epoch']+1,
                      {'nonce':ob['nonce'],'preserve_conversation':True,'reason':'delivery_unconfirmed' if ob['state']=='pending' else 'model_reply_missing'})
        return last is not None and now < float(last[0])

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            db.execute('BEGIN IMMEDIATE')
            rollback_clock = self._reply_sweep(db)
            db.commit()  # No caller mutations exist: publish highwater/revocations first.
            if rollback_clock:
                raise Fenced('authority clock rollback; leases unavailable until clock catches up')
            db.execute('BEGIN IMMEDIATE')
            # Lock gap may permit another writer; sweep again before exposing transaction.
            rollback_clock = self._reply_sweep(db)
            db.commit()
            if rollback_clock:
                raise Fenced('authority clock rollback; leases unavailable until clock catches up')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()  # Discard caller writes before a separate safety-only transaction.
            db.execute('BEGIN IMMEDIATE')
            self._reply_sweep(db)
            db.commit()
            raise
        finally:
            db.close()

    def _reply_guard(self, db, project, role, actor, generation, epoch):
        highwater=db.execute("SELECT value FROM authority_meta WHERE key='last_clock'").fetchone()
        if highwater and self.clock()<float(highwater[0]):
            raise Fenced('authority clock rollback at final guard')
        if db.execute('SELECT 1 FROM reply_tombstones WHERE actor=? AND generation=?', (actor,generation)).fetchone():
            raise Fenced('revoked root incarnation')
        if db.execute("""SELECT 1 FROM reply_obligations WHERE project=? AND role=? AND actor=?
          AND generation=? AND epoch=? AND state IN ('pending','delivered') AND deadline<=?""",
          (project,role,actor,generation,epoch,self.clock())).fetchone():
            raise Fenced('genuine reply deadline missed')

        logical = self._logical_role(db,project,role)
        if logical:
            for other in db.execute('SELECT * FROM roles WHERE holder IS NOT NULL').fetchall():
                if (other['project'],other['role'])==(project,role) or not self._live_role(db,other):
                    continue
                other_logical=self._logical_role(db,other['project'],other['role'])
                if other_logical==logical or other['holder']==actor and other_logical and (logical=='root' or other_logical=='root' or logical.startswith('principal:') and other_logical.startswith('principal:')):
                    raise Fenced('conflicting global root or logical principal custody')

    def _live_role(self, db, row):
        """Election occupancy probe, never an effect authorization."""
        now=self.clock()
        if not row['holder'] or row['expires']<=now or row['suspect_since'] is not None or row['check_due']+120<=now:
            return False
        if row['standup_due'] is not None and row['standup_due']+120<=now:
            return False
        observed=db.execute('SELECT generation FROM agents WHERE id=?',(row['holder'],)).fetchone()
        if not observed or observed['generation']!=row['generation']:
            return False
        if row['activation_due']>0 and row['activation_due']<=now and not db.execute('SELECT 1 FROM activation_receipts WHERE project=? AND role=? AND epoch=?',(row['project'],row['role'],row['epoch'])).fetchone():
            return False
        if db.execute('SELECT 1 FROM reply_tombstones WHERE actor=? AND generation=?',(row['holder'],row['generation'])).fetchone():
            return False
        return not db.execute("SELECT 1 FROM reply_obligations WHERE project=? AND role=? AND epoch=? AND state IN ('pending','delivered') AND deadline<=?",(row['project'],row['role'],row['epoch'],now)).fetchone()

    def _logical_role(self, db, project, role):
        if role == 'root':
            return 'root'
        row = db.execute('SELECT logical FROM reply_logical_roles WHERE project=? AND role=?', (project,role)).fetchone()
        if row:
            return row['logical']
        return 'principal:legacy' if role == 'principal' else None

    def register_logical_role(self, project, role, logical):
        """Server configuration API; never expose through actor RPC."""
        if not isinstance(logical,str) or not logical or (role=='root' and logical!='root'):
            raise ValueError('invalid logical role')
        with self._tx() as db:
            old = db.execute('SELECT logical FROM reply_logical_roles WHERE project=? AND role=?',(project,role)).fetchone()
            if old and old['logical'] != logical:
                raise Fenced('logical role registration is immutable')
            held = db.execute('SELECT holder FROM roles WHERE project=? AND role=?',(project,role)).fetchone()
            if held and held['holder'] and self._logical_role(db,project,role)!=logical:
                raise Fenced('cannot reclassify held role')
            db.execute('INSERT OR IGNORE INTO reply_logical_roles VALUES(?,?,?)',(project,role,logical))

    def _event(self, db, project, role, kind, epoch, payload):
        db.execute('INSERT INTO events(project,role,kind,epoch,payload,created) VALUES(?,?,?,?,?,?)',
                   (project, role, kind, epoch, json.dumps(payload), self.clock()))

    def configure(self, project, role, candidates, parent=None, standup_due=None):
        """Explicit project membership is required; no implicit cross-project takeover."""
        with self._tx() as db:
            if parent and not db.execute('SELECT 1 FROM projects WHERE id=?', (parent,)).fetchone():
                raise ValueError('unknown parent project')
            db.execute('INSERT OR IGNORE INTO projects VALUES(?,?)', (project, parent))
            db.execute('INSERT OR IGNORE INTO roles(project,role,standup_due) VALUES(?,?,?)',
                       (project, role, standup_due))
            db.execute('DELETE FROM candidates WHERE project=? AND role=?', (project, role))
            db.executemany('INSERT INTO candidates VALUES(?,?,?)',
                           [(project, role, actor) for actor in candidates])

    def observe(self, actor, host, generation, *, ready, draft, quota_ok, priority=100):
        """Runtime adapter supplies genuine identity/readiness/quota observations.

        Observation alone never renews role liveness or proves useful progress.
        """
        if not actor or not host or not generation:
            raise ValueError('identity, host and execution generation required')
        with self._tx() as db:
            db.execute('INSERT OR REPLACE INTO agents VALUES(?,?,?,?,?,?,?,?)',
                       (actor, host, generation, self.clock(), bool(ready), bool(draft),
                        bool(quota_ok), priority))

    def _get(self, db, project, role):
        row = db.execute('SELECT * FROM roles WHERE project=? AND role=?', (project, role)).fetchone()
        if row is None:
            raise ValueError('unconfigured project role')
        return row

    def _valid(self, db, project, role, actor, generation, epoch):
        row = self._get(db, project, role)
        self._reply_guard(db, project, role, actor, generation, epoch)
        if (row['holder'], row['generation'], row['epoch']) != (actor, generation, epoch):
            raise Fenced('stale role identity or epoch')
        if row['activation_due']>0 and row['activation_due']<=self.clock():
            activated=db.execute('SELECT 1 FROM activation_receipts WHERE project=? AND role=? AND epoch=?',
                                 (project,role,epoch)).fetchone()
            if not activated:
                raise Fenced('role first-action deadline missed')
        observed=db.execute('SELECT generation FROM agents WHERE id=?',(actor,)).fetchone()
        if not observed or observed['generation']!=generation:
            raise Fenced('runtime generation has changed')
        if (row['expires'] <= self.clock() or row['check_due']+120 <= self.clock()
                or (row['standup_due'] is not None and row['standup_due']+120 <= self.clock())
                or row['suspect_since'] is not None):
            raise Fenced('expired or suspected lease; diagnose before restoring authority')
        return row

    def renew(self, project, role, actor, generation, epoch, *, ttl=180):
        with self._tx() as db:
            self._valid(db, project, role, actor, generation, epoch)
            db.execute('UPDATE roles SET expires=? WHERE project=? AND role=? AND holder=? AND generation=? AND epoch=?',
                       (self.clock()+ttl, project, role, actor, generation, epoch))

    def complete_check(self, project, role, actor, generation, epoch, *, evidence,
                       interval=1800, next_standup=None):
        """Only an actual completed periodic/standup check extends check deadline."""
        if not evidence:
            raise ValueError('completed-check evidence required')
        with self._tx() as db:
            self._valid(db, project, role, actor, generation, epoch)
            db.execute('UPDATE roles SET check_due=?,standup_due=? WHERE project=? AND role=? AND holder=? AND generation=? AND epoch=?',
                       (self.clock()+interval, next_standup, project, role, actor, generation, epoch))
            self._event(db, project, role, 'check_completed', epoch, {'evidence': evidence})

    def tick(self, project, role, *, ttl=180, check_interval=1800,
             observation_ttl=60, diagnosis_grace=120):
        """Deterministic election after missed lease/check, with durable sync probe.

        Every standby calls this against the SAME authority. No clock-only
        role transfer of file/task ownership: request separate fenced recovery.
        """
        now = self.clock()
        with self._tx() as db:
            old = self._get(db, project, role)
            incumbent=db.execute('SELECT generation FROM agents WHERE id=?',(old['holder'],)).fetchone()
            generation_changed=incumbent and incumbent['generation']!=old['generation']
            activated=db.execute('SELECT 1 FROM activation_receipts WHERE project=? AND role=? AND epoch=?',
                                 (project,role,old['epoch'])).fetchone()
            first_action_missed=old['activation_due']>0 and old['activation_due']<=now and not activated
            missed = old['holder'] and (generation_changed or first_action_missed or (old['expires'] <= now or old['check_due']+120 <= now
                       or (old['standup_due'] is not None and old['standup_due']+120 <= now)))
            if old['holder'] and not missed:
                return {'state': 'healthy', 'holder': old['holder'], 'generation': old['generation'], 'epoch': old['epoch']}
            if missed and old['suspect_since'] is None:
                db.execute('UPDATE roles SET suspect_since=? WHERE project=? AND role=? AND epoch=?', (now, project, role, old['epoch']))
                self._event(db, project, role, 'sync_probe', old['epoch'],
                            {'recipient': old['holder'], 'generation': old['generation'],
                             'request': 'Diagnose runtime, busy/draft, quota, service and cursor; preserve tasks'})
                return {'state': 'diagnosing', 'epoch': old['epoch']}
            if missed and now < old['suspect_since']+diagnosis_grace:
                return {'state': 'diagnosing', 'epoch': old['epoch']}
            choices = db.execute('''SELECT a.* FROM agents a JOIN candidates c ON c.agent=a.id
                WHERE c.project=? AND c.role=? AND a.seen>? AND a.ready=1 AND a.draft=0 AND a.quota=1
                AND NOT EXISTS(SELECT 1 FROM roles r WHERE r.holder=a.id AND r.expires>?
                  AND (r.role='principal' OR r.role='coordinator') AND NOT(r.project=? AND r.role=?))
                ORDER BY a.priority,a.id''', (project,role,now-observation_ttl,now,project,role)).fetchall()
            # A suspected generation cannot elect itself through a status heartbeat.
            choices = [a for a in choices if (a['id'],a['generation']) != (old['holder'],old['generation'])]
            if not choices:
                self._event(db, project, role, 'replacement_required', old['epoch'],
                            {'owner_role': 'standby', 'retain_busy_or_draft': True})
                return {'state': 'replacement_required', 'epoch': old['epoch']}
            logical = self._logical_role(db,project,role)
            active = []
            for held in db.execute('SELECT * FROM roles WHERE holder IS NOT NULL').fetchall():
                if (held['project'],held['role'])==(project,role):
                    continue
                if not self._live_role(db,held):
                    continue
                active.append((held,self._logical_role(db,held['project'],held['role'])))
            if logical and any(other==logical for _,other in active):
                return {'state':'conflict_active_logical_role','epoch':old['epoch']}
            def eligible(candidate):
                if db.execute('SELECT 1 FROM reply_tombstones WHERE actor=? AND generation=?',(candidate['id'],candidate['generation'])).fetchone():
                    return False
                for held,other in active:
                    if held['holder']==candidate['id'] and logical and other:
                        if logical=='root' or other=='root' or logical.startswith('principal:') and other.startswith('principal:'):
                            return False
                return True
            choices = [candidate for candidate in choices if eligible(candidate)]
            if not choices:
                return {'state':'replacement_required','epoch':old['epoch']}
            new = choices[0]
            epoch = old['epoch']+1
            db.execute('''UPDATE roles SET holder=?,generation=?,epoch=?,expires=?,check_due=?,
                suspect_since=NULL,standup_due=?,activation_due=? WHERE project=? AND role=? AND epoch=?''',
                (new['id'],new['generation'],epoch,now+ttl,now+check_interval,
                 now+diagnosis_grace if old['standup_due'] is not None and old['standup_due']<=now else old['standup_due'],
                 now+300,project,role,old['epoch']))
            # A promoted head relinquishes role authority, not in-flight file custody.
            if role == 'principal':
                heads = db.execute("SELECT * FROM roles WHERE holder=? AND role LIKE 'head:%'", (new['id'],)).fetchall()
                for head in heads:
                    db.execute('UPDATE roles SET holder=NULL,generation=NULL,epoch=epoch+1,expires=0 WHERE project=? AND role=?',
                               (head['project'],head['role']))
                    self._event(db,head['project'],head['role'],'head_backfill_required',head['epoch']+1,
                                {'promoted':new['id'],'preserve_task_custody':True})
            self._event(db, project, role, 'elected', epoch,
                        {'holder':new['id'],'host':new['host'],'generation':new['generation'],
                         'previous':old['holder'],'reconcile_before_writes':True})
            return {'state':'elected','holder':new['id'],'generation':new['generation'],'epoch':epoch}

    def activation(self, project, role, actor, generation, epoch, *, role_ack=None, first_action=None):
        """Trusted adapter records authenticated semantic ACK + actual first tool.

        These cannot be inferred from PID, queue acceptance, or source tests.
        """
        with self._tx() as db:
            self._valid(db,project,role,actor,generation,epoch)
            if role_ack is not None or first_action is not None:
                if not role_ack or not first_action:
                    raise ValueError('both exact semantic role ACK and first-tool receipt required')
                old=db.execute('SELECT * FROM activation_receipts WHERE project=? AND role=? AND epoch=?',
                               (project,role,epoch)).fetchone()
                if old and (old['role_ack'],old['first_action'])!=(role_ack,first_action):
                    raise Fenced('conflicting activation receipts')
                db.execute('INSERT OR IGNORE INTO activation_receipts VALUES(?,?,?,?,?)',
                           (project,role,epoch,role_ack,first_action))
            row=db.execute('SELECT * FROM activation_receipts WHERE project=? AND role=? AND epoch=?',
                           (project,role,epoch)).fetchone()
            return dict(row) if row else {'state':'pending_role_ack_and_first_action'}

    def startup_plan(self, project, role, task=None):
        """Persist owner-approved recovery task before election for crash retries."""
        with self._tx() as db:
            self._get(db,project,role)
            if task is not None:
                body=json.dumps(task,sort_keys=True)
                old=db.execute('SELECT task FROM startup_plans WHERE project=? AND role=?',(project,role)).fetchone()
                if old and old[0]!=body:
                    raise Fenced('existing startup plan requires explicit ownership reconciliation')
                db.execute('INSERT OR IGNORE INTO startup_plans VALUES(?,?,?)',(project,role,body))
            row=db.execute('SELECT task FROM startup_plans WHERE project=? AND role=?',(project,role)).fetchone()
            return json.loads(row[0]) if row else None

    def sync_response(self, project, role, actor, generation, epoch, *, envelope_id, evidence):
        """Exact semantic sync response can clear suspicion only within live deadlines.

        It cannot renew an expired epoch or stand in for a completed periodic check.
        """
        if not envelope_id or not evidence:
            raise ValueError('exact envelope and semantic runtime evidence required')
        with self._tx() as db:
            row = self._get(db, project, role)
            self._reply_guard(db,project,role,actor,generation,epoch)
            if (row['holder'],row['generation'],row['epoch']) != (actor,generation,epoch):
                raise Fenced('stale sync response')
            if (row['expires'] <= self.clock() or row['check_due']+120 <= self.clock()
                    or (row['standup_due'] is not None and row['standup_due']+120 <= self.clock())):
                raise Fenced('semantic response cannot waive missed deadlines')
            db.execute('UPDATE roles SET suspect_since=NULL WHERE project=? AND role=? AND holder=? AND generation=? AND epoch=?',(project,role,actor,generation,epoch))
            self._event(db,project,role,'sync_response',epoch,{'envelope_id':envelope_id,'evidence':evidence})

    def guarded_effect(self, project, role, actor, generation, epoch, key, payload, effect, *, reconcile=False):
        """Serialize control-plane enqueue with election; callback MUST dedup key.

        A crash after callback before commit may retry it. External effects require
        their own durable idempotency key; this is not exactly-once execution.
        """
        with self._tx() as db:
            self._valid(db,project,role,actor,generation,epoch)
            observed = db.execute('SELECT * FROM agents WHERE id=?',(actor,)).fetchone()
            if not observed or observed['seen']<=self.clock()-60 or not observed['quota'] or observed['draft']:
                raise Fenced('fresh quota and safe runtime required')
            body=json.dumps(payload,sort_keys=True)
            old=db.execute('SELECT * FROM actions WHERE key=?',(key,)).fetchone()
            if old:
                same_effect=(old['project'],old['role'],old['payload'])==(project,role,body)
                if not same_effect or (not reconcile and old['epoch']!=epoch):
                    raise Fenced('conflicting intent')
                return {'state':'already_enqueued'}
            self._valid(db,project,role,actor,generation,epoch)
            # Callback is the final synchronous sink; asynchronous native effects
            # must independently validate epoch at /v1/sink-proof before mutation.
            # Record an already performed effect even if completion crosses expiry:
            # erasing that receipt would permit duplicate external work on retry.
            result=effect(key,payload)
            db.execute('INSERT INTO actions VALUES(?,?,?,?,?)',(key,project,role,epoch,body))
            return result

    def submit_action(self, project, role, actor, generation, epoch, key, payload):
        """Durable fenced intent. Consumer must claim with authorize before execution."""
        with self._tx() as db:
            self._valid(db,project,role,actor,generation,epoch)
            observed = db.execute('SELECT * FROM agents WHERE id=?', (actor,)).fetchone()
            if observed is None or observed['seen'] <= self.clock()-60 or not observed['quota'] or observed['draft']:
                raise Fenced('fresh quota and draft-safe runtime required for new dispatch')
            old = db.execute('SELECT * FROM actions WHERE key=?',(key,)).fetchone()
            body = json.dumps(payload,sort_keys=True)
            if old:
                if (old['project'],old['role'],old['epoch'],old['payload']) != (project,role,epoch,body):
                    raise Fenced('idempotency key conflicts with previous intent')
                return False
            db.execute('INSERT INTO actions VALUES(?,?,?,?,?)',(key,project,role,epoch,body))
            return True

    def authorize(self, project, role, actor, generation, epoch):
        """Must be checked at mutation/launcher commit, never cached across outages."""
        with self._tx() as db:
            self._valid(db,project,role,actor,generation,epoch)
            return True

    def in_scope(self, principal_project, child_project):
        with self._tx() as db:
            visited=set()
            while child_project and child_project not in visited:
                if child_project==principal_project:
                    return True
                visited.add(child_project)
                row=db.execute('SELECT parent FROM projects WHERE id=?',(child_project,)).fetchone()
                child_project=row['parent'] if row else None
            return False

    def role_state(self, project, role):
        with self._tx() as db:
            return dict(self._get(db,project,role))

    def events(self):
        with self._tx() as db:
            return [dict(row) for row in db.execute('SELECT * FROM events ORDER BY id')]
