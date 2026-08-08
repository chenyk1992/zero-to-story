"""Quick verification that schema v8 creates edit_decision_lists correctly."""
from lfo.core.database import Database

db = Database(":memory:")
db.init_schema()

assert db.schema_version == 8, f"Expected 8, got {db.schema_version}"

rows = db.fetchall(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='edit_decision_lists'"
)
assert len(rows) == 1, "edit_decision_lists table missing"

cols = db.fetchall("PRAGMA table_info(edit_decision_lists)")
col_names = {c[1] for c in cols}
expected = {
    "edl_id", "project_id", "revision",
    "content_json", "content_hash", "dependency_hash",
    "status", "created_at", "approved_at",
}
for name in expected:
    assert name in col_names, f"Missing column: {name}"

# Verify migration v7 → v8
db2 = Database(":memory:")
db2.init_schema()
db2.conn.execute("PRAGMA user_version = 7")
db2.migrate()
assert db2.schema_version == 8, f"Migration failed: {db2.schema_version}"

print("Schema v8 verification PASSED")
