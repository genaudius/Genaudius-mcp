# DAW Bridge Protocol: Sync Specification v1.0

## 1. Webhook / WebSocket Events
The DAW plugin communicates with n8n/Maestro via these events:

### `TRACK_SYNC` (Outbound from DAW)
Sent when a track is created or updated.
```json
{
  "event": "track_sync",
  "track_id": "uuid",
  "name": "Conga Real",
  "type": "audio",
  "status": "user_import",
  "file_url": "https://..."
}
```

### `MAESTRO_ADVICE` (Inbound to DAW)
Maestro responds with processing parameters.
```json
{
  "event": "maestro_advice",
  "track_id": "uuid",
  "processing": {
    "eq": { "low_cut": 100, "gain": 3, "freq": 3000 },
    "compression": { "threshold": -15, "ratio": 4 },
    "reverb": { "mix": 0.15, "size": "hall" }
  },
  "message": "He ajustado el ataque para que tu conga real empaste con el bongo virtual."
}
```

## 2. Emergency Correction Protocol
If Maestro detects issues in the imported audio:
- **Pitch**: Auto-tunes to the session `key`.
- **Tempo**: Time-stretches to match session `bpm`.
- **Phase**: Flips phase if cancellation is detected between layers.

## 3. Export Package Structure
When the production is finished, Maestro prepares a ZIP:
- `/master/`: Stereo Master (WAV -9 LUFS).
- `/instrumental/`: No vocals master.
- `/stems/`: Individual tracks (Percussion, Harmony, Vocals).
- `/midi/`: Original MIDI tracks.
- `report.txt`: Maestro's production notes.
