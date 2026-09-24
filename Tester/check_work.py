"""SonicSentinel audio preparation and listening bot.

Examples:
    python "Tester/check_work.py" organize
    python "Tester/check_work.py" report
    python "Tester/check_work.py" listen --category gunshot
    python "Tester/check_work.py" record --seconds 5

The organizer uses UrbanSound8K.csv when a file is present there. Files that
cannot be labelled from metadata are kept in unknown instead of being given a
misleading category.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Dataset" / "audio"
OUTPUT = ROOT / "Dataset" / "categorized_audio"
CSV_FILE = ROOT / "UrbanSound8K.csv"
SUPPORTED = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}

CATEGORIES = (
    "gunshot",
    "glassbreak",
    "alarm_siren_vehicle_horn",
    "animal_sound",
    "panic_scream",
    "aggressive_shouting",
    "person_asking_for_help",
    "mechanical_fault",
    "background_noise",
    "unknown",
)

SOURCE_TO_CATEGORY = {
    "gun_shot": "gunshot",
    "car_horn": "alarm_siren_vehicle_horn",
    "siren": "alarm_siren_vehicle_horn",
    "dog_bark": "animal_sound",
    "drilling": "mechanical_fault",
    "jackhammer": "mechanical_fault",
    "engine_idling": "mechanical_fault",
    "air_conditioner": "background_noise",
    "street_music": "background_noise",
    "children_playing": "unknown",
}


def read_labels() -> dict[str, str]:
    """Return filename-to-source-label metadata from the project CSV."""
    if not CSV_FILE.exists():
        return {}
    with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as stream:
        return {
            row["slice_file_name"].lower(): row["class"]
            for row in csv.DictReader(stream)
            if row.get("slice_file_name") and row.get("class")
        }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def convert_to_wav(source: Path, destination: Path) -> None:
    """Convert a non-WAV file with ffmpeg, preserving the original sample rate."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg is required to convert non-WAV files. Install it and add it to PATH."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(source), "-vn", "-acodec", "pcm_s16le", str(destination)],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-1000:])


def category_for(path: Path, labels: dict[str, str]) -> str:
    source_label = labels.get(path.name.lower())
    return SOURCE_TO_CATEGORY.get(source_label or "", "unknown")


def organize() -> None:
    labels = read_labels()
    for category in CATEGORIES:
        (OUTPUT / category).mkdir(parents=True, exist_ok=True)
    files = [path for path in SOURCE.rglob("*") if path.is_file()]
    seen: set[str] = set()
    counts = {category: 0 for category in CATEGORIES}
    duplicates = 0
    converted = 0
    skipped = 0

    for source in files:
        if source.suffix.lower() not in SUPPORTED:
            skipped += 1
            continue
        try:
            file_hash = sha256(source)
            if file_hash in seen:
                duplicates += 1
                continue
            seen.add(file_hash)
            category = category_for(source, labels)
            target = OUTPUT / category / f"{file_hash[:12]}_{source.stem}{source.suffix.lower()}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            counts[category] += 1
        except (OSError, RuntimeError) as error:
            print(f"Skipped {source}: {error}", file=sys.stderr)

    print(f"Organized {sum(counts.values())} unique audio files into {OUTPUT}")
    print(f"Converted to WAV: {converted}; duplicates removed: {duplicates}; unsupported: {skipped}")
    for category, count in counts.items():
        print(f"  {category}: {count}")


def report() -> None:
    if not OUTPUT.exists():
        print("No categorized dataset yet. Run: python Tester/check_work.py organize")
        return
    for category in CATEGORIES:
        count = (
            sum(1 for path in (OUTPUT / category).iterdir() if path.is_file())
            if (OUTPUT / category).exists()
            else 0
        )
        print(f"{category}: {count}")


def play(path: Path) -> None:
    """Play one file using the operating system's default audio player."""
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def listen(category: str) -> None:
    folder = OUTPUT / category
    choices = (
        sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED)
        if folder.exists()
        else []
    )
    if not choices:
        raise RuntimeError(f"No audio found in category: {category}")
    print(f"Playing {choices[0].name} from {category}")
    play(choices[0])


def record(seconds: int) -> None:
    """Record a WAV clip when sounddevice is installed, then play it."""
    try:
        import sounddevice as sd
        from scipy.io.wavfile import write
    except ImportError as error:
        raise RuntimeError("Recording needs: pip install sounddevice scipy") from error
    rate = 44100
    print(f"Recording for {seconds} seconds...")
    audio = sd.rec(seconds * rate, samplerate=rate, channels=1, dtype="int16")
    sd.wait()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
        filename = Path(file.name)
    write(filename, rate, audio)
    print(f"Recorded: {filename}")
    play(filename)


def main() -> None:
    parser = argparse.ArgumentParser(description="SonicSentinel audio organizer and listener")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("organize", help="convert, deduplicate, and categorize audio")
    subparsers.add_parser("report", help="show categorized file counts")
    listen_parser = subparsers.add_parser("listen", help="play the first clip in a category")
    listen_parser.add_argument("--category", choices=CATEGORIES, required=True)
    record_parser = subparsers.add_parser("record", help="record a short microphone clip")
    record_parser.add_argument("--seconds", type=int, default=5)
    args = parser.parse_args()
    if args.command == "organize":
        organize()
    elif args.command == "report":
        report()
    elif args.command == "listen":
        listen(args.category)
    else:
        record(max(1, args.seconds))


if __name__ == "__main__":
    main()