"""
CC0 Royalty-Free Music Asset Generator for CreateFlow AI.
Generates 4 mood-tagged ambient music tracks using NumPy audio synthesis:
  - corporate: warm major chord pad + bell harmonics
  - upbeat: energetic rhythmic pulse + synth chords
  - dramatic: deep minor drone + low cinematic resonance
  - calm: soothing soft ambient pad + gentle harmonics
"""
import os
import wave
import struct
import numpy as np
from typing import Optional

MUSIC_DIR = os.path.join(os.path.dirname(__file__), "assets", "music")
os.makedirs(MUSIC_DIR, exist_ok=True)
SAMPLE_RATE = 44100


def synthesize_track(filename: str, duration_sec: float, synth_fn):
    num_samples = int(SAMPLE_RATE * duration_sec)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False)
    audio = synth_fn(t)
    # Normalize to 0.5 peak amplitude
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = (audio / max_val) * 0.5

    int_samples = (audio * 32767).astype(np.int16)

    path = os.path.join(MUSIC_DIR, filename)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(int_samples.tobytes())

    size_kb = os.path.getsize(path) / 1024.0
    print(f"Generated {filename}: {duration_sec}s, {size_kb:.1f} KB -> {path}")


def corporate_synth(t):
    # C major chord: C4 (261.63Hz), E4 (329.63Hz), G4 (392.00Hz), B4 (493.88Hz)
    freqs = [261.63, 329.63, 392.00, 493.88]
    wave_sum = np.zeros_like(t)
    for i, f in enumerate(freqs):
        lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 0.2 * t + i)
        wave_sum += lfo * np.sin(2 * np.pi * f * t)
    # Add warm sub bass (C2 = 65.41Hz)
    wave_sum += 0.4 * np.sin(2 * np.pi * 65.41 * t)
    return wave_sum


def upbeat_synth(t):
    # F Major / A Minor pulse: 128 BPM (0.46875s per beat)
    beat_dur = 0.46875
    pulse = 0.5 + 0.5 * np.sin(2 * np.pi * (1.0 / beat_dur) * t)
    freqs = [349.23, 440.00, 523.25, 659.25]
    wave_sum = np.zeros_like(t)
    for i, f in enumerate(freqs):
        wave_sum += pulse * np.sin(2 * np.pi * f * t)
    # Bass kick pulse
    kick = np.exp(-10 * (t % beat_dur)) * np.sin(2 * np.pi * 60 * t)
    return wave_sum + 0.5 * kick


def dramatic_synth(t):
    # D Minor cinematic drone: D2 (73.42Hz), A2 (110.00Hz), F3 (174.61Hz)
    freqs = [73.42, 110.00, 174.61, 220.00]
    wave_sum = np.zeros_like(t)
    for i, f in enumerate(freqs):
        lfo = 0.7 + 0.3 * np.sin(2 * np.pi * 0.1 * t + i * 0.5)
        wave_sum += lfo * np.sin(2 * np.pi * f * t)
    # Sub drone (D1 = 36.71Hz)
    wave_sum += 0.6 * np.sin(2 * np.pi * 36.71 * t)
    return wave_sum


def calm_synth(t):
    # A Major ambient pad: A3 (220.00Hz), C#4 (277.18Hz), E4 (329.63Hz), G#4 (415.30Hz)
    freqs = [220.00, 277.18, 329.63, 415.30]
    wave_sum = np.zeros_like(t)
    for i, f in enumerate(freqs):
        lfo = 0.75 + 0.25 * np.sin(2 * np.pi * 0.05 * t + i * 1.2)
        wave_sum += lfo * np.sin(2 * np.pi * f * t)
    return wave_sum


class CC0MusicGenerator:
    """Manager for CC0 background music tracks."""

    @classmethod
    def get_or_generate_music(cls, mood: str = "corporate", output_dir: Optional[str] = None) -> str:
        filename = f"{mood.lower().strip()}.wav"
        if filename not in ["corporate.wav", "upbeat.wav", "dramatic.wav", "calm.wav"]:
            filename = "corporate.wav"

        path = os.path.join(MUSIC_DIR, filename)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            synth_fn = corporate_synth
            if "upbeat" in filename:
                synth_fn = upbeat_synth
            elif "dramatic" in filename:
                synth_fn = dramatic_synth
            elif "calm" in filename:
                synth_fn = calm_synth
            synthesize_track(filename, 60.0, synth_fn)

        return path


def build_music_library():
    print("--> Synthesizing CC0 Music Bed Library for CreateFlow AI...")
    synthesize_track("corporate.wav", 60.0, corporate_synth)
    synthesize_track("upbeat.wav", 60.0, upbeat_synth)
    synthesize_track("dramatic.wav", 60.0, dramatic_synth)
    synthesize_track("calm.wav", 60.0, calm_synth)
    print("--> CC0 Music Bed Library ready!\n")


if __name__ == "__main__":
    build_music_library()
