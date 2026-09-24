# SonicSentinel

Audio preparation and listening utility for SonicSentinel.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Put source audio files in `Dataset/audio`. Supported formats are WAV, MP3,
FLAC, OGG, and M4A. Run the organizer:

```powershell
python "Tester/check_work.py" organize
python "Tester/check_work.py" report
```

The organizer uses `UrbanSound8K.csv` labels where available, removes exact
duplicates using SHA-256, and writes files under
`Dataset/categorized_audio`. It never changes the original audio folder.

Play a category or record a microphone sample:

```powershell
python "Tester/check_work.py" listen --category gunshot
python "Tester/check_work.py" record --seconds 5
```

The ten output categories are `gunshot`, `glassbreak`,
`alarm_siren_vehicle_horn`, `animal_sound`, `panic_scream`,
`aggressive_shouting`, `person_asking_for_help`, `mechanical_fault`,
`background_noise`, and `unknown`.

Large audio folders are intentionally excluded from Git. Keep the dataset
locally or store it in Git LFS/object storage when publishing it.