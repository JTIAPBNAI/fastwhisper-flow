# FastWhisper Flow

Free, local, hold-to-talk Thai/English dictation for macOS — a minimal
Wispr Flow clone. Everything runs on-device (mlx-whisper on Apple Silicon
Metal); no audio ever leaves your Mac.

## Use

1. Start the app:
   ```
   .venv/bin/python flow.py
   ```
2. A 🎙 icon appears in the menu bar (⏳ while the model loads, first run
   downloads ~1.6 GB once).
3. Click into any app, **hold Right ⌘**, speak Thai or English, release.
4. 🔴 while recording, ⏳ while transcribing, then the cleaned text is
   pasted at your cursor.

## Permissions (one-time)

macOS will prompt for both on first use — approve them for your terminal
app (or whatever launches flow.py):

- **Microphone** — System Settings → Privacy & Security → Microphone
- **Accessibility** — needed to detect the hotkey and simulate ⌘V

## Configuration

Edit the top of `flow.py`:

- `MODEL` — swap for a smaller (`mlx-community/whisper-medium-mlx`) or a
  Thai fine-tuned model.
- `LANGUAGE` — `None` auto-detects; set `"th"` to force Thai.
- `HOTKEY` — default `Key.cmd_r` (Right Command).

Filler-word removal lives in `cleanup.py` — add your own Thai fillers.

## Start at login

```
cp com.fastwhisper.flow.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fastwhisper.flow.plist
```
