"""Patch the local-windows profile to add ComfyUI root + input/output dirs."""
import json
import pathlib

p = pathlib.Path(r"C:\Users\Administrator\AppData\Roaming\LFO\machines\local-windows.json")
data = json.loads(p.read_text(encoding="utf-8"))

# Fill in ComfyUI root, input/output paths
data["comfyui"]["root"] = r"D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI"
data["storage"]["comfy_input"] = r"D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI\input"
data["storage"]["comfy_output"] = r"D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI\output"
data["storage"]["lfo_cache"] = r"E:\ideaProjects\zero-to-story\workspace\db"
data["storage"]["lfo_projects"] = r"E:\ideaProjects\zero-to-story\workspace\projects"

p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"updated: {p}")
print(f"  comfyui.root = {data['comfyui']['root']}")
print(f"  comfy_input  = {data['storage']['comfy_input']}")
print(f"  comfy_output = {data['storage']['comfy_output']}")
