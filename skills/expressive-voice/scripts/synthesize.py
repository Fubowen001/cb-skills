"""Generate expressive voice candidates with local MLX Qwen3-TTS models."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path


def load_job(path):
    path = Path(path).resolve()
    job = json.loads(path.read_text(encoding='utf-8'))
    roles = job.get('roles', {})
    lines = job.get('lines', [])
    if not roles or not lines:
        raise ValueError('roles and lines must be nonempty')
    candidates = job.get('candidates', 1)
    if type(candidates) is not int or not 1 <= candidates <= 3:
        raise ValueError('candidates must be an integer from 1 to 3')
    for key, default, lower, upper in [('temperature', .66, .01, 2), ('top_p', .88, .01, 1)]:
        value = job.get(key, default)
        if not isinstance(value, (float, int)) or not lower <= value <= upper:
            raise ValueError(f'Invalid {key}')
    seen = set()
    for line in lines:
        name = line.get('id', '')
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', name) or name in seen:
            raise ValueError('Line IDs must be unique and safe filenames')
        seen.add(name)
        if line.get('role') not in roles:
            raise ValueError(f'Unknown role for {name}')
        if not isinstance(line.get('text'), str) or not line['text'].strip():
            raise ValueError(f'Empty text for {name}')
        if 'spoken_text' in line and (not isinstance(line['spoken_text'], str) or not line['spoken_text'].strip()):
            raise ValueError(f'Empty spoken_text for {name}')
    for name, role in roles.items():
        mode = role.get('mode')
        if mode not in ('custom', 'design', 'clone'):
            raise ValueError(f'Invalid mode for {name}')
        model = role.get('model')
        if not isinstance(model, str) or not model.strip():
            raise ValueError(f'Missing model for {name}')
        local = Path(model).expanduser()
        if not local.is_absolute():
            local = path.parent / local
        if local.exists():
            role['model'] = str(local.resolve())
        elif model.startswith(('.', '/', '~', 'models/')):
            raise ValueError(f'Local model missing for {name}')
        if mode == 'custom' and not role.get('speaker'):
            raise ValueError(f'Missing speaker for {name}')
        if mode == 'design' and not role.get('voice_description'):
            raise ValueError(f'Missing voice_description for {name}')
        if mode == 'clone':
            if not role.get('reference_audio') or not role.get('reference_text', '').strip():
                raise ValueError(f'Missing reference audio/text for {name}')
            ref = Path(role['reference_audio']).expanduser()
            if not ref.is_absolute():
                ref = path.parent / ref
            if not ref.is_file():
                raise ValueError(f'Reference missing for {name}')
            role['reference_audio'] = str(ref.resolve())
            if role.get('direction') or any(l.get('delivery') for l in lines if l['role'] == name):
                raise ValueError('clone uses reference performance; delivery/direction is unsupported')
    return job


def read_reference(path, target_rate):
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import resample_poly
    rate, wave = wavfile.read(path)
    dtype = wave.dtype
    if dtype.kind in 'iu':
        info = np.iinfo(dtype)
        wave = wave.astype(np.float32)
        if dtype.kind == 'u':
            wave -= (info.max + 1) / 2
            wave /= (info.max + 1) / 2
        else:
            wave /= max(abs(info.min), info.max)
    else:
        wave = wave.astype(np.float32)
    if wave.ndim == 2:
        wave = wave.mean(axis=1)
    if wave.ndim != 1 or not len(wave) or not np.isfinite(wave).all() or np.max(np.abs(wave)) < 1e-5:
        raise ValueError('Reference must contain finite audible speech')
    if rate != target_rate:
        divisor = math.gcd(rate, target_rate)
        wave = resample_poly(wave, target_rate // divisor, rate // divisor).astype(np.float32)
    return wave


def finish_audio(wave, rate):
    import numpy as np
    if wave.ndim != 1 or not len(wave) or not np.isfinite(wave).all():
        raise ValueError('Generated audio is empty or nonfinite')
    peak = float(np.max(np.abs(wave)))
    if peak < 1e-5:
        raise ValueError('Generated audio is silent')
    active = np.flatnonzero(np.abs(wave) > min(.001, peak * .004))
    start = max(0, int(active[0]) - round(.08 * rate))
    end = min(len(wave), int(active[-1]) + 1 + round(.14 * rate))
    result = wave[start:end].copy()
    result *= min(10 ** (3 / 20), .94 / peak)
    fade = min(round(.005 * rate), len(result) // 2)
    if fade:
        result[:fade] *= np.linspace(0, 1, fade)
        result[-fade:] *= np.linspace(1, 0, fade)
    return result, start / rate, (len(wave) - end) / rate


def save_wav(path, wave, rate, raw=False):
    import numpy as np
    from scipy.io import wavfile
    temporary = path.with_suffix('.tmp.wav')
    data = wave.astype(np.float32) if raw else (np.clip(wave, -1, 1) * 32767).astype(np.int16)
    wavfile.write(temporary, rate, data)
    temporary.replace(path)


def run(job, output):
    import numpy as np
    import mlx.core as mx
    from mlx_audio.tts.utils import load_model
    from importlib.metadata import version
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'status': 'needs_listening_review', 'mlx_audio_version': version('mlx-audio'), 'job': job, 'takes': []}
    models = {}
    references = {}
    for index, line in enumerate(job['lines']):
        role = job['roles'][line['role']]
        model_path = role['model']
        if model_path not in models:
            models[model_path] = load_model(model_path)
        model = models[model_path]
        mode = role['mode']
        expected = {'custom': 'custom_voice', 'design': 'voice_design', 'clone': 'base'}[mode]
        if model.config.tts_model_type != expected:
            raise ValueError(f'Model type must be {expected}, got {model.config.tts_model_type}')
        if mode == 'custom' and model.config.tts_model_size == '0b6':
            raise ValueError('Use a CustomVoice model that supports performance instructions')
        spoken = line.get('spoken_text', line['text'])
        direction = ' '.join(filter(None, [role.get('direction'), line.get('delivery')]))
        for take in range(job.get('candidates', 1)):
            seed = int(job.get('seed', 227)) + index * 1009 + take * 33
            mx.random.seed(seed)
            options = {'text': spoken, 'temperature': job.get('temperature', .66), 'top_p': job.get('top_p', .88), 'max_tokens': job.get('max_tokens', max(150, len(spoken) * 15 + 32))}
            language = job.get('language', 'chinese')
            reference_hash = None
            if mode == 'clone':
                ref = role['reference_audio']
                if ref not in references:
                    references[ref] = mx.array(read_reference(ref, model.sample_rate))
                options.update(ref_audio=references[ref], ref_text=role['reference_text'], lang_code=language)
                stream = model.generate(**options)
                reference_hash = hashlib.sha256(Path(ref).read_bytes()).hexdigest()
            elif mode == 'custom':
                stream = model.generate_custom_voice(**options, speaker=role['speaker'], instruct=direction, language=language)
            else:
                stream = model.generate_voice_design(**options, instruct=role['voice_description'] + ' ' + direction, language=language)
            chunks = list(stream)
            if not chunks or len({c.sample_rate for c in chunks}) != 1:
                raise ValueError('Missing audio or inconsistent chunk sample rates')
            rate = chunks[0].sample_rate
            raw = np.concatenate([np.asarray(c.audio).reshape(-1) for c in chunks])
            clean, head, tail = finish_audio(raw, rate)
            name = f"{line['id']}-{take + 1}"
            save_wav(output / (name + '-raw.wav'), raw, rate, raw=True)
            save_wav(output / (name + '.wav'), clean, rate)
            manifest['takes'].append({'id': line['id'], 'role': line['role'], 'text': line['text'], 'spoken_text': spoken, 'seed': seed, 'sample_rate': rate, 'seconds': len(clean) / rate, 'head_trim_seconds': head, 'tail_trim_seconds': tail, 'reference_sha256': reference_hash, 'raw': name + '-raw.wav', 'audio': name + '.wav', 'review': 'needs_listening_review'})
            temp = output / 'manifest.tmp.json'
            temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            temp.replace(output / 'manifest.json')
            print(f"Saved {name}.wav ({len(clean) / rate:.2f}s), listening review pending", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    job = load_job(args.job)
    if args.validate_only:
        print(f"Valid job: {len(job['roles'])} roles, {len(job['lines'])} lines")
        return
    if args.out is None:
        parser.error('--out is required for generation')
    run(job, args.out)


if __name__ == '__main__':
    main()
