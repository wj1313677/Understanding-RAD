#!/usr/bin/env python3
"""
Convert a PDF into a "rich" Markdown file using the marker-pdf library.
"""

import argparse
import os
import marker
from marker.models import create_model_dict

def main():
    p = argparse.ArgumentParser(description="Convert a PDF to a high-quality markdown file.")
    p.add_argument("--input", "-i", required=True, help="Input PDF path")
    p.add_argument("--output", "-o", required=True, help="Output markdown file path")
    args = p.parse_args()

    # Get output directory from output file path
    output_dir = os.path.dirname(args.output)
    os.makedirs(output_dir, exist_ok=True)

    # Load models and run conversion
    model_lst = list(create_model_dict().values())
    full_text, out_meta = marker.convert_pdf(args.input, model_lst)
    
    if full_text:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"Successfully converted PDF to Markdown at {args.output}")
    else:
        print("PDF conversion failed.")

if __name__ == "__main__":
    main()