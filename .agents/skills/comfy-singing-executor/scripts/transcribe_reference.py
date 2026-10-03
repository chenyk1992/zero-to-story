"""Read-only local ASR to locate candidate singing phrases; never an acceptance verdict."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--duration", type=float)
    args = parser.parse_args()
    import librosa
    import torch
    from transformers import pipeline

    torch.set_num_threads(8)
    audio, _ = librosa.load(args.audio, sr=16000, offset=args.start, duration=args.duration)
    asr = pipeline("automatic-speech-recognition", model=str(args.model_dir),
                   device=-1, torch_dtype=torch.float32)
    chunking = {"chunk_length_s": 30, "stride_length_s": (4, 2)} if len(audio) > 30 * 16000 else {}
    result = asr({"raw": audio, "sampling_rate": 16000}, **chunking,
                 batch_size=1, return_timestamps=True,
                 generate_kwargs={"language": "chinese", "task": "transcribe"})
    result["status"] = "approximate ASR; phrase timings require listening"
    result["source_offset_seconds"] = args.start
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
