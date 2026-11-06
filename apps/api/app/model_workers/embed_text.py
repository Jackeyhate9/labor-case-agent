from __future__ import annotations

import argparse
import json
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--role", choices=("query", "passage"), required=True)
    args = parser.parse_args()
    payload = json.load(sys.stdin)
    texts = payload["texts"]
    if args.provider == "nemotron-3-embed-1b":
        prefix = "query: " if args.role == "query" else "passage: "
        texts = [prefix + text for text in texts]

    import torch
    import torch.nn.functional as functional
    from transformers import AutoModel, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    model = AutoModel.from_pretrained(args.model, local_files_only=True).to(device).eval()
    encoded = tokenizer(texts, padding=True, truncation=True, max_length=8192, return_tensors="pt")
    encoded = {key: value.to(device) for key, value in encoded.items()}
    with torch.inference_mode():
        output = model(**encoded).last_hidden_state
        mask = encoded["attention_mask"].unsqueeze(-1)
        pooled = (output * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
        vectors = functional.normalize(pooled.float(), p=2, dim=1).cpu().tolist()
    print(json.dumps({"device": device, "vectors": vectors}))


if __name__ == "__main__":
    main()
