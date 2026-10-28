#!/usr/bin/env python3
"""测量已生成音频的真实时长，产出 audio-manifest.json 并回写元数据。

用法：python3 scripts/measure_audio.py

产出：
  知识点元数据/mappings/audio-manifest.json   —— 音频台账（voice / model / 每段实测）
  知识点元数据/subjects/<sid>/<sid>.json      —— tts.clips[] 追加 file/bytes/dur_sec
"""
import json
import pathlib
import statistics
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'
AUDIO = META / 'audio'
OUT = META / 'mappings' / 'audio-manifest.json'

VOICE_META = {
    'reference_id': '36ef842120654ee6b38ef43c8f08535a',
    'name': '宣传片浑厚男声',
    'model': 's2.1-pro-free',
    'format': 'mp3',
    'sample_rate': 44100,
    'bitrate': 128,
    'lang': 'zh',
}


def duration(path):
    """ffprobe 读 mp3 时长（秒）。失败返回 None。"""
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', str(path)],
            capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        return round(float(r.stdout.strip()), 2)
    except Exception:  # noqa: BLE001
        return None


def main():
    clips = {}
    missing = []
    for sid in ('812', '315', '101', '204'):
        d = json.loads((META / 'subjects' / sid / f'{sid}.json').read_text(encoding='utf-8'))
        for p in d['points']:
            for c in (p.get('tts') or {}).get('clips', []):
                cid = c['clip_id']
                f = AUDIO / sid / f'{cid}.mp3'
                if not f.exists():
                    missing.append(f'{sid}/{cid}')
                    continue
                dur = duration(f)
                if dur is None:
                    missing.append(f'{sid}/{cid}(时长读取失败)')
                    continue
                clips[cid] = {
                    'subject': sid,
                    'file': f'{cid}.mp3',
                    'path': f'audio/{sid}/{cid}.mp3',
                    'bytes': f.stat().st_size,
                    'dur_sec': dur,
                    'chars': len(c.get('text', '')),
                }

    if missing:
        print(f'缺失 {len(missing)} 段：{missing[:10]}{"…" if len(missing) > 10 else ""}')

    durs = [v['dur_sec'] for v in clips.values()]
    cps = [v['chars'] / v['dur_sec'] for v in clips.values() if v['dur_sec'] > 0]
    est_err = []
    for sid in ('812', '315', '101', '204'):
        d = json.loads((META / 'subjects' / sid / f'{sid}.json').read_text(encoding='utf-8'))
        for p in d['points']:
            for c in (p.get('tts') or {}).get('clips', []):
                m = clips.get(c['clip_id'])
                if m and c.get('est_sec'):
                    est_err.append(m['dur_sec'] - c['est_sec'])

    manifest = {
        'schema': 'ky-audio/1.0',
        'voice': VOICE_META,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'stats': {
            'clips': len(clips),
            'total_bytes': sum(v['bytes'] for v in clips.values()),
            'total_dur_sec': round(sum(durs), 1),
            'total_dur_min': round(sum(durs) / 60, 1),
            'dur_min': min(durs) if durs else 0,
            'dur_max': max(durs) if durs else 0,
            'dur_median': round(statistics.median(durs), 2) if durs else 0,
            'chars_per_sec_median': round(statistics.median(cps), 3) if cps else 0,
            'chars_per_sec_mean': round(statistics.mean(cps), 3) if cps else 0,
            'est_bias_sec_mean': round(statistics.mean(est_err), 2) if est_err else 0,
            'est_bias_sec_median': round(statistics.median(est_err), 2) if est_err else 0,
        },
        'clips': clips,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'台账 → {OUT.relative_to(ROOT)}')
    s = manifest['stats']
    print(f"  段数 {s['clips']} · 体积 {s['total_bytes'] / 1048576:.1f}MB · "
          f"总时长 {s['total_dur_min']} 分钟")
    print(f"  单段 {s['dur_min']}–{s['dur_max']}s（中位 {s['dur_median']}s）")
    print(f"  实测语速中位 {s['chars_per_sec_median']} 字/秒（预估口径偏差 中位 {s['est_bias_sec_median']}s）")
    return 0 if not missing else 1


if __name__ == '__main__':
    sys.exit(main())
