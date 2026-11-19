"""Regression checks for sample formats, silence handling and configuration."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from synthesize import read_reference, finish_audio, load_job


class AudioTests(unittest.TestCase):
    def test_uint8_stereo_resampling(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'ref.wav'
            wave = np.tile(np.array([128, 192, 128, 64], dtype=np.uint8), 400)
            wavfile.write(path, 16000, np.column_stack([wave, wave]))
            result = read_reference(path, 24000)
            self.assertEqual(len(result), 2400)
            self.assertLess(abs(float(result.mean())), .001)
            self.assertLess(float(np.max(abs(result))), .6)

    def test_internal_pause_and_soft_edges_survive(self):
        wave = np.zeros(24000, dtype=np.float32)
        wave[2400:7200] = .1
        wave[16800:21600] = -.1
        result, head, tail = finish_audio(wave, 24000)
        self.assertEqual(len(result), len(wave) - round((head + tail) * 24000))
        offset = round(head * 24000)
        self.assertTrue(np.all(result[7200-offset:16800-offset] == 0))
        self.assertLess(np.max(abs(result)), .142)

    def test_bad_audio_rejected(self):
        for wave in [np.zeros(10), np.array([np.nan]), np.array([])]:
            with self.assertRaises(ValueError):
                finish_audio(wave, 24000)

    def test_duplicate_ids_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'job.json'
            line = {'id': 'same', 'role': 'one', 'text': 'Hello'}
            path.write_text(json.dumps({'roles': {'one': {'mode': 'custom', 'model': 'owner/model', 'speaker': 'Ryan'}}, 'lines': [line, line]}))
            with self.assertRaises(ValueError):
                load_job(path)


if __name__ == '__main__':
    unittest.main()
