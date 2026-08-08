"""Quick DB check."""
from lfo.core.database import Database

db = Database(r"workspace\db\lfo.db")
db.init_schema()

# Check assets
rows = db.fetchall(
    "SELECT asset_id, asset_type, task_id, file_path FROM assets ORDER BY created_at"
)
print(f"Total assets: {len(rows)}")
for r in rows:
    print(f"  {r[0]} type={r[1]} task_id={r[2]}")

# Check tasks
tasks = db.fetchall("SELECT task_id, project_id, status FROM tasks LIMIT 10")
print(f"\nTasks: {len(tasks)}")
for t in tasks:
    print(f"  {t[0]} proj={t[1]} status={t[2]}")
