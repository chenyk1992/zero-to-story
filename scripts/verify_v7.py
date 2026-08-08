"""Quick verification that schema v7 creates selected_clips correctly."""
from lfo.core.database import Database

db = Database(":memory:")
db.init_schema()

print(f"Schema version: {db.schema_version}")
assert db.schema_version == 7, f"Expected 7, got {db.schema_version}"

rows = db.fetchall(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='selected_clips'"
)
assert len(rows) == 1, "selected_clips table missing"
print("selected_clips table: OK")

idx = db.fetchall(
    "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_selected_clips_current_approved'"
)
assert len(idx) == 1, "idx_selected_clips_current_approved missing"
print("current_approved partial index: OK")

# Verify columns
cols = db.fetchall("PRAGMA table_info(selected_clips)")
col_names = [c[1] for c in cols]
expected = [
    "selected_clip_id", "project_id", "shot_id",
    "normalized_asset_id", "output_asset_id",
    "selected_in_frame", "selected_out_frame_exclusive",
    "fps_num", "fps_den",
    "render_policy_id", "revision", "status",
    "content_hash", "dependency_hash",
    "created_at", "approved_at", "superseded_by",
]
for name in expected:
    assert name in col_names, f"Missing column: {name}"
print(f"All {len(expected)} expected columns present: OK")

# Verify migration path (v6 → v7)
db2 = Database(":memory:")
db2.init_schema()
db2.conn.execute("PRAGMA user_version = 6")
db2.migrate()
assert db2.schema_version == 7, f"Migration failed: {db2.schema_version}"
print("Migration v6 → v7: OK")

print("\nSchema v7 verification PASSED")
