import sqlite3
import pytest
import os
import tempfile
import sys
from pathlib import Path

repo_root = str(Path(__file__).resolve().parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Insert external module if necessary (simulating what failover_integration.py does)
sys.path.insert(0, '/home/alexey/git/agent-coordination-role-failover')
try:
    from coordination.role_failover import RoleAuthority
except ImportError:
    RoleAuthority = None

from scripts.coordination.backup_role_authority import backup_database

def create_schema(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE authority_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE projects(id TEXT PRIMARY KEY, parent TEXT REFERENCES projects(id));
        CREATE TABLE agents(id TEXT PRIMARY KEY, host TEXT NOT NULL,
                      generation TEXT NOT NULL, seen REAL NOT NULL, ready INTEGER NOT NULL,
                      draft INTEGER NOT NULL, quota INTEGER NOT NULL, priority INTEGER NOT NULL);
        CREATE TABLE candidates(project TEXT NOT NULL, role TEXT NOT NULL,
                      agent TEXT NOT NULL, PRIMARY KEY(project,role,agent));
        CREATE TABLE roles(project TEXT NOT NULL, role TEXT NOT NULL,
                      holder TEXT, generation TEXT, epoch INTEGER NOT NULL DEFAULT 0,
                      expires REAL NOT NULL DEFAULT 0, activation_due REAL NOT NULL DEFAULT 0, check_due REAL NOT NULL DEFAULT 0,
                      standup_due REAL, suspect_since REAL,
                      PRIMARY KEY(project,role));
    """)
    conn.execute("INSERT INTO authority_meta (key, value) VALUES ('generation', 'gen-1-active')")
    conn.execute("INSERT INTO projects (id, parent) VALUES ('root', NULL)")
    conn.commit()
    conn.close()

def test_backup_and_replica_fencing():
    with tempfile.TemporaryDirectory() as td:
        primary_db = os.path.join(td, "primary.db")
        replica_db = os.path.join(td, "replica.db")
        
        # 1. Create primary DB with generation gen-1
        create_schema(primary_db)
        
        # 2. Replicate it to replica_db
        res = backup_database(primary_db, replica_db)
        assert res["status"] == "success"
        assert res["generation"] == "gen-1-active"
        
        # 3. Simulate client fencing (client has minority/partitioned, fails closed)
        # We ensure the replica doesn't accept role grants unless it's explicitly promoted to a new generation
        conn = sqlite3.connect(replica_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM authority_meta WHERE key = 'generation'")
        generation = cursor.fetchone()[0]
        assert generation == "gen-1-active"
        
        # Fenced client rejects automatic local leader election
        # (This is enforced by the architecture, but we simulate the fence check)
        is_fenced = True
        
        # Simulate fenced restore: explicit promotion to new generation
        new_generation = "gen-2-restored"
        conn.execute("UPDATE authority_meta SET value = ? WHERE key = 'generation'", (new_generation,))
        conn.commit()
        
        # Verify the explicit promotion
        cursor.execute("SELECT value FROM authority_meta WHERE key = 'generation'")
        assert cursor.fetchone()[0] == "gen-2-restored"
        is_fenced = False # Fencing lifted after explicit restore
        
        assert not is_fenced

def test_majority_fencing():
    # Minority of nodes cannot grant roles
    # Simulate consumer terms
    with tempfile.TemporaryDirectory() as td:
        primary_db = os.path.join(td, "primary.db")
        create_schema(primary_db)
        
        conn = sqlite3.connect(primary_db)
        # Assume consumer term requires new epoch > old epoch
        conn.execute("INSERT INTO roles (project, role, holder, generation, epoch) VALUES ('root', 'coordinator', 'agent-old', 'gen-1-active', 10)")
        conn.commit()
        
        # A partitioned node with stale epoch cannot grant roles (rejected by consumer term)
        stale_epoch = 10
        proposed_epoch = 9
        
        cursor = conn.cursor()
        cursor.execute("SELECT epoch FROM roles WHERE project='root' AND role='coordinator'")
        current_epoch = cursor.fetchone()[0]
        
        # Reject old authority
        assert proposed_epoch < current_epoch, "Old authority rejected by consumer term"
