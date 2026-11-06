from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--device", default="auto", choices=("auto", "cuda", "cpu"))
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor
    from moss_transcribe_diarize import parse_transcript
    from moss_transcribe_diarize.inference_utils import (
        build_transcription_messages,
        generate_transcription,
        resolve_device,
    )

    device = resolve_device(args.device)
    dtype = torch.bfloat16 if device.type == "cuda" else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        trust_remote_code=True,
        local_files_only=True,
        dtype="auto",
    ).to(dtype=dtype).to(device).eval()
    processor = AutoProcessor.from_pretrained(
        args.model,
        trust_remote_code=True,
        local_files_only=True,
    )
    messages = build_transcription_messages(args.audio)
    result = generate_transcription(
        model,
        processor,
        messages,
        max_new_tokens=8192,
        do_sample=False,
        device=device,
        dtype=dtype,
    )
    segments = [
        {
            "speaker_id": segment.speaker,
            "start_time": segment.start,
            "end_time": segment.end,
            "text": segment.text,
            "confidence": None,
        }
        for segment in parse_transcript(result["text"])
    ]
    print(json.dumps({"device": device.type, "raw_text": result["text"], "segments": segments}, ensure_ascii=True))


if __name__ == "__main__":
    main()
