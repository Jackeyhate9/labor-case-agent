from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    import torch
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        trust_remote_code=True,
        local_files_only=True,
    )
    model = AutoModel.from_pretrained(
        args.model,
        trust_remote_code=True,
        local_files_only=True,
        use_safetensors=True,
        torch_dtype=torch.bfloat16,
    ).eval().cuda()
    output_dir = Path(args.image).parent / ".unlimited-ocr-output"
    output_dir.mkdir(exist_ok=True)
    value = model.infer(
        tokenizer,
        prompt="<image>document parsing.",
        image_file=args.image,
        output_path=str(output_dir),
        base_size=1024,
        image_size=640,
        crop_mode=True,
        max_length=32768,
        no_repeat_ngram_size=35,
        ngram_window=128,
        save_results=False,
        eval_mode=True,
    )
    print(
        json.dumps(
            {
                "text": value if isinstance(value, str) else str(value or ""),
                "device": "cuda",
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
