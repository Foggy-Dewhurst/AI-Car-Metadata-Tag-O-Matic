# Car Identifier (Clean)

AI‑powered desktop app to identify cars from photos using local Ollama vision models, then embed searchable metadata directly into your JPGs (no re‑encoding).

<p align="center">
  <em>Make • Model • Color • Logos • License Plate • AI Summary → saved to EXIF + IPTC</em>
</p>

---

## Features

- Local inference with Ollama (privacy by default)
- Vision model support (default: `qwen2.5vl:32b-q4_K_M`)
- Single image and batch processing (with recursive scanning)
- Overwrite policy for existing metadata: `skip`, `overwrite`, `ask`
- High‑Fidelity input toggle and Enhanced Reasoning mode
- Dark, modern Tkinter UI (optionally styled via `ttkbootstrap`)
- Fast embedding without re‑encoding pixels:
  - EXIF: `UserComment` stores a JSON snapshot
  - IPTC: Keywords, Title, Caption/Abstract for Lightroom/Photoshop search
- Windows‑bundled exiftool in this folder for reliable metadata writing

> Note: Embedding targets JPG/JPEG files. Non‑JPGs are previewed/analyzed but not embedded.

---

## Quick Start

### 1) Requirements

- Python 3.10+
- Ollama running at `http://localhost:11434`
  - Install: https://ollama.com
  - Pull a vision model: `ollama pull qwen2.5vl:32b-q4_K_M`
- Windows: `exiftool.exe` is included in this folder; macOS/Linux users should install exiftool from https://exiftool.org

### 2) Install dependencies

```bash
cd CarIdentifier_GitHub_Clean
pip install -r requirements.txt
# Optional (improves dark themed widgets):
pip install ttkbootstrap
```

### 3) Run

```bash
python car_identifier_gui.py
```

---

## Using the App

1. Click “Select Image” (single) or “Select Folder” (batch).
2. Options:
   - ✅ Auto Approve: auto‑save metadata after each inference
   - 💾 Embed in JPG: write EXIF+IPTC directly into JPG/JPEG
   - 🖼️ High Fidelity Input: send original image bytes for best OCR/logo reading
   - 🤖 Enhanced Reasoning: persona + focused crop strategy for harder cases
   - 📁 Recursive Scan: include subfolders during batch processing
   - Existing Metadata: `skip` / `overwrite` / `ask`
3. Click “Process Image” or “Batch Process”.
4. Review the results, then Approve to embed metadata.
5. Bottom pane keeps the “Last Identified Image & Results”.

Tips:
- Mouse wheel to zoom, click‑drag to pan.
- Batch mode shows live progress and current file.

---

## What Gets Embedded (JPG/JPEG)

- EXIF `UserComment`: JSON snapshot of parsed identification
- IPTC Keywords: make/model tokens + helpful tags (e.g., `Car Make: BMW`, `M3`, `Automotive`)
- IPTC Caption/Abstract: human‑readable description
- IPTC ObjectName: concise title (e.g., `BMW M3`)

Fields extracted include:
- Make, Model, Color
- Logos/emblems/text on the car
- License Plate (if visible)
- AI‑Interpretation Summary (~200‑char description)

> By design, this Clean build does not produce JSON/XMP sidecars and only embeds into JPGs. If you need XMP sidecars or embedded XMP, use the v2 app in `CarIdentifier_v2`.

---

## Troubleshooting

- Ollama connection failed
  - Ensure Ollama is running: `http://localhost:11434`
  - Pull the model: `ollama pull qwen2.5vl:32b-q4_K_M`
- Model not found
  - The app checks models at startup; follow the on‑screen “pull” instructions.
- exiftool not available (non‑Windows)
  - Install exiftool (`brew install exiftool` or `apt-get install exiftool`).
- Tkinter missing (Linux)
  - Install Tk: `sudo apt-get install python3-tk`.
- Pillow/Ollama import errors
  - Reinstall: `pip install -r requirements.txt`

---

## Notes for Power Users

- Default model: `qwen2.5vl:32b-q4_K_M` (solid OCR/logo reading). Any Ollama vision‑capable model should work.
- High‑Fidelity Input sends original bytes; disable if bandwidth is constrained.
- Enhanced Reasoning uses persona hints and optional detail crops for harder brand/model disambiguation.
- Embedding avoids pixel re‑encoding by leveraging exiftool where available.

---

## Acknowledgements

- ExifTool by Phil Harvey (https://exiftool.org)
- Ollama (https://ollama.com)
- Qwen2.5‑VL model family
