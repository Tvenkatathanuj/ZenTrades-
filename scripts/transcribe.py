"""
Transcription module using OpenAI Whisper (open-source, local, zero-cost).
Converts audio/video recordings to text transcripts.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def transcribe_with_whisper(audio_path: str, model_size: str = "base") -> dict:
    """
    Transcribe audio using local Whisper model.
    
    Args:
        audio_path: Path to audio/video file
        model_size: Whisper model size (tiny, base, small, medium, large)
    
    Returns:
        dict with 'text' (full transcript) and 'segments' (timestamped segments)
    """
    try:
        import whisper
    except ImportError:
        logger.error(
            "Whisper not installed. Install with: pip install openai-whisper\n"
            "Also requires ffmpeg. Install ffmpeg from https://ffmpeg.org/download.html"
        )
        raise

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info(f"Loading Whisper model: {model_size}")
    model = whisper.load_model(model_size)

    logger.info(f"Transcribing: {audio_path}")
    result = model.transcribe(audio_path, language="en", verbose=False)

    transcript = {
        "source_file": os.path.basename(audio_path),
        "text": result["text"].strip(),
        "segments": [
            {
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip()
            }
            for seg in result.get("segments", [])
        ],
        "language": result.get("language", "en")
    }

    logger.info(f"Transcription complete. Length: {len(transcript['text'])} chars")
    return transcript


def transcribe_file(input_path: str, output_path: str = None, model_size: str = "base") -> str:
    """
    Transcribe a single file and optionally save the result.
    
    Args:
        input_path: Path to audio/video file
        output_path: Path to save transcript JSON (optional)
        model_size: Whisper model size
    
    Returns:
        Transcript text
    """
    transcript = transcribe_with_whisper(input_path, model_size)

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(transcript, f, indent=2, ensure_ascii=False)
        logger.info(f"Transcript saved to: {output_path}")

    return transcript["text"]


def load_transcript(path: str) -> str:
    """
    Load a transcript from file. Supports .txt and .json formats.
    If .json, extracts the 'text' field.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Transcript file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if path.endswith(".json"):
        data = json.loads(content)
        if isinstance(data, dict) and "text" in data:
            return data["text"]
        return content

    return content


def batch_transcribe(input_dir: str, output_dir: str, model_size: str = "base") -> list:
    """
    Transcribe all audio/video files in a directory.
    
    Args:
        input_dir: Directory containing audio/video files
        output_dir: Directory to save transcript JSONs
        model_size: Whisper model size
    
    Returns:
        List of (input_file, output_file) tuples
    """
    audio_extensions = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac"}
    results = []

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for file in sorted(input_path.iterdir()):
        if file.suffix.lower() in audio_extensions:
            out_file = output_path / f"{file.stem}_transcript.json"
            try:
                transcribe_file(str(file), str(out_file), model_size)
                results.append((str(file), str(out_file)))
                logger.info(f"[OK] Transcribed: {file.name}")
            except Exception as e:
                logger.error(f"[FAIL] Failed to transcribe {file.name}: {e}")

    logger.info(f"Batch transcription complete. {len(results)}/{len(list(input_path.iterdir()))} files processed.")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe audio/video files using Whisper")
    parser.add_argument("input", help="Path to audio/video file or directory")
    parser.add_argument("-o", "--output", help="Output path for transcript")
    parser.add_argument("-m", "--model", default="base", choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model size (default: base)")
    parser.add_argument("--batch", action="store_true", help="Process all files in input directory")

    args = parser.parse_args()

    if args.batch:
        output_dir = args.output or os.path.join(args.input, "transcripts")
        batch_transcribe(args.input, output_dir, args.model)
    else:
        output = args.output or args.input.rsplit(".", 1)[0] + "_transcript.json"
        text = transcribe_file(args.input, output, args.model)
        print(f"\n--- Transcript ---\n{text[:500]}...")
