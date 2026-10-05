"""產生中英配音並計算時間軸 -> build/timeline.json"""
import asyncio, json, os, subprocess, wave, sys
import edge_tts, imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = imageio_ffmpeg.get_ffmpeg_exe()
OUT = os.path.join(ROOT, 'build', 'tts')
S = json.load(open(os.path.join(ROOT, 'src', 'script.json'), encoding='utf-8'))
RATE = {'zh': '+4%', 'en': '+6%'}

# 每幕前後留白（秒）：給畫面動作與音效呼吸
LEAD = {'hook': 1.6, 'data': 0.8, 'answer': 1.0, 'heroes': 0.9, 'lab': 0.9,
        'fourplus': 0.9, 'commute': 1.2, 'tuition': 0.8, 'montage': 0.6, 'outro': 0.9}
TAIL = {'hook': 0.5, 'data': 1.4, 'answer': 1.2, 'heroes': 1.2, 'lab': 1.0,
        'fourplus': 1.6, 'commute': 2.6, 'tuition': 1.8, 'montage': 1.0, 'outro': 7.9}
GAP = 0.45


async def synth(text, voice, rate, path):
    if os.path.exists(path):
        return
    await edge_tts.Communicate(text, voice, rate=rate).save(path)


def to_wav(mp3):
    wav = mp3[:-4] + '.wav'
    if not os.path.exists(wav):
        subprocess.run([FF, '-y', '-loglevel', 'error', '-i', mp3, '-ar', '48000', '-ac', '1', wav], check=True)
    with wave.open(wav) as w:
        return wav, w.getnframes() / w.getframerate()


async def main():
    jobs = []
    for si, sc in enumerate(S['scenes']):
        for ci, c in enumerate(sc['cues']):
            for lang in ('zh', 'en'):
                c[f'{lang}_mp3'] = os.path.join(OUT, f'{si:02d}_{ci:02d}_{lang}.mp3')
                jobs.append(synth(c[lang], S['voices'][lang], RATE[lang], c[f'{lang}_mp3']))
    await asyncio.gather(*jobs)

    t = 0.0
    tl = {'scenes': [], 'cues': []}
    for sc in S['scenes']:
        st = t
        t += LEAD[sc['id']]
        for c in sc['cues']:
            durs = {}
            for lang in ('zh', 'en'):
                wav, d = to_wav(c[f'{lang}_mp3'])
                durs[lang] = d
                c[f'{lang}_wav'] = wav
            slot = max(durs.values())
            tl['cues'].append({'scene': sc['id'], 'start': round(t, 3), 'end': round(t + slot, 3),
                               'zh': c['zh'], 'en': c['en'], 'zh_wav': c['zh_wav'], 'en_wav': c['en_wav'],
                               'zh_dur': round(durs['zh'], 3), 'en_dur': round(durs['en'], 3)})
            t += slot + GAP
        t += TAIL[sc['id']] - GAP
        tl['scenes'].append({'id': sc['id'], 'start': round(st, 3), 'end': round(t, 3)})
    tl['duration'] = round(t, 3)
    json.dump(tl, open(os.path.join(ROOT, 'build', 'timeline.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    sys.stdout.reconfigure(encoding='utf-8')
    for s in tl['scenes']:
        print(f"{s['id']:9s} {s['start']:7.2f} -> {s['end']:7.2f}  ({s['end']-s['start']:.1f}s)")
    for c in tl['cues']:
        print(f"  {c['start']:6.2f} zh{c['zh_dur']:5.2f} en{c['en_dur']:5.2f}  {c['zh'][:18]}")
    print('TOTAL', tl['duration'])

asyncio.run(main())
