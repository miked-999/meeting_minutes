# Local Diarization Setup Issues & Resolutions

When running the application on Windows in an offline / air-gapped environment, the speaker diarization module failed to load. Below are the details of the bugs encountered and the steps taken to fix them.

---

## 1. File Name / Extension Mismatch (`label_encoder.txt` vs `label_encoder.ckpt`)

### The Problem
SpeechBrain's `Pretrainer` class loads components defined in `hyperparams.yaml`. For the component named `label_encoder`, SpeechBrain generates the expected cached file name by appending the default parameter file extension (`.ckpt`), searching for `label_encoder.ckpt`.
Since the file downloaded from Hugging Face is originally named `label_encoder.txt`, SpeechBrain was unable to locate it in the local cache directory, leading it to assume the file was missing.

### The Resolution
We duplicated or renamed the cached `label_encoder.txt` file in `models_cache/spkrec-ecapa-voxceleb` to:
- `label_encoder.ckpt`

---

## 2. Windows Symbolic Link Permissions (`[WinError 1314]`)

### The Problem
Because SpeechBrain could not find `label_encoder.ckpt` in the local cache, it attempted to fetch `label_encoder.txt` from the Hugging Face Hub. Once downloaded, it tried to create a symbolic link (symlink) to it under the local cache directory.
On Windows, creating symbolic links requires either Administrator privileges or Windows Developer Mode to be enabled. Since the web server process runs without elevated privileges, the OS threw the following error, causing diarization to fail:
```
[WinError 1314] A required privilege is not held by the client
```

### The Resolution
Renaming/duplicating the file to `label_encoder.ckpt` (as done in step 1) resolves the file-missing condition so SpeechBrain never attempts to fetch or create a symlink.

---

## 3. Hugging Face Outbound Check Bypass

### The Problem
Even if files are cached locally, specifying a Hugging Face repository identifier (like `speechbrain/spkrec-ecapa-voxceleb`) in `EncoderClassifier.from_hparams` causes SpeechBrain/HuggingFace Hub to perform outbound network checks to check for updates or verify repository existence.

### The Resolution
In [`backend/diarizer.py`](file:///c:/Programming/meeting_minutes/meeting_minutes/backend/diarizer.py), we updated the `source` argument inside `EncoderClassifier.from_hparams` to point directly to the local model cache directory (`save_dir`) instead of the Hugging Face Hub repo identifier.

```diff
         _SPEAKER_CLASSIFIER = EncoderClassifier.from_hparams(
-            source="speechbrain/spkrec-ecapa-voxceleb",
+            source=save_dir,
             savedir=save_dir,
             run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"}
         )
```
This forces SpeechBrain to operate strictly locally and bypasses any Hugging Face Hub network checks.
