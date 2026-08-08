"""Run lfo comfy doctor against the local environment."""
import sys

sys.path.insert(0, r"C:\Users\Administrator\Documents\lfo")

from lfo.comfy.client import ComfyApiClient
from lfo.comfy.doctor import ComfyDoctor

client = ComfyApiClient()
doctor = ComfyDoctor(client)
report = doctor.run_all_checks()
doctor.print_report(report)

# Exit code: 0 healthy, 1 warning, 2 critical
if report.status == "critical":
    sys.exit(2)
elif report.status == "warning":
    sys.exit(0)  # warnings don't block
else:
    sys.exit(0)
