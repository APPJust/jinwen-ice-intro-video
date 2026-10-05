"""timeline.json -> 字幕分段 -> timeline.js（給動畫頁）＋ SRT（中英／中／英）"""
import json, math, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TL = json.load(open(os.path.join(ROOT, 'build', 'timeline.json'), encoding='utf-8'))
WEB = os.path.join(ROOT, 'output', 'interactive')
os.makedirs(WEB, exist_ok=True)

ZH_MAX, EN_MAX = 24, 72
STRIP = '，。；：、 '


def zh_clauses(s):
    parts = re.findall(r'[^，。；：？！]+[，。；：？！]?', s)
    return [p for p in parts if p.strip()]


def zh_chunks(s, mx):
    out, cur = [], ''
    for c in zh_clauses(s):
        while len(c) > mx:  # 單句過長：從中間附近、不拆英數詞與括號處切
            ok = [i for i in range(2, len(c) - 1) if not (c[i - 1].isascii() and c[i - 1].isalnum() and c[i].isascii() and c[i].isalnum())
                  and c[:i].count('《') == c[:i].count('》') and c[:i].count('「') == c[:i].count('」')]
            h = min(ok or [math.ceil(len(c) / 2)], key=lambda i: abs(i - len(c) / 2))
            if cur:
                out.append(cur); cur = ''
            out.append(c[:h]); c = c[h:]
        if len(cur) + len(c) <= mx:
            cur += c
        else:
            out.append(cur); cur = c
    if cur:
        out.append(cur)
    return out


def en_split(s, ratios):
    words = s.split()
    cum, tot = [], 0
    for w in words:
        tot += len(w) + 1; cum.append(tot)
    cuts, last = [], 0
    for r in ratios[:-1]:
        best, bs = None, 1e9
        for i in range(last + 1, len(words)):
            if words[i - 1] in ('Mr.', 'of', 'the', 'a', 'an', 'to', 'and', 'Top-tier', 'Ministry'):
                continue
            sc = abs(cum[i - 1] / tot - r) * 100 - (8 if re.search(r'[,.:;?!]$', words[i - 1]) else 0)
            if sc < bs:
                bs, best = sc, i
        cuts.append(best); last = best
    segs, prev = [], 0
    for c in cuts + [len(words)]:
        segs.append(' '.join(words[prev:c])); prev = c
    return segs


def clean(s):
    return s.strip().rstrip(STRIP).strip()


cues = []
for c in TL['cues']:
    n = max(len(zh_chunks(c['zh'], ZH_MAX)), math.ceil(len(c['en']) / EN_MAX))
    mx = ZH_MAX
    zc = zh_chunks(c['zh'], mx)
    while len(zc) < n and mx > 6:
        mx -= 1; zc = zh_chunks(c['zh'], mx)
    lens = [len(x) for x in zc]
    acc, ratios = 0, []
    for L in lens:
        acc += L; ratios.append(acc / sum(lens))
    ec = en_split(c['en'], ratios) if len(zc) > 1 else [c['en']]
    t0, t1 = c['start'], c['end']
    prev = t0
    for i, (z, e) in enumerate(zip(zc, ec)):
        end = t1 if i == len(zc) - 1 else t0 + (t1 - t0) * ratios[i]
        cues.append({'s': round(prev, 2), 'e': round(end, 2), 'zh': clean(z), 'en': clean(e)})
        prev = end

js = {'duration': TL['duration'], 'scenes': TL['scenes'],
      'cues': [{'start': c['start'], 'end': c['end'], 'scene': c['scene']} for c in TL['cues']],
      'subs': cues}
open(os.path.join(WEB, 'timeline.js'), 'w', encoding='utf-8').write(
    'window.TL = ' + json.dumps(js, ensure_ascii=False, indent=1) + ';\n')


def ts(t):
    ms = int(round(t * 1000))
    return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'


for name, f in [('雙語', lambda c: c['zh'] + '\n' + c['en']), ('中文', lambda c: c['zh']), ('English', lambda c: c['en'])]:
    with open(os.path.join(ROOT, 'output', f'景文資通系介紹_{name}.srt'), 'w', encoding='utf-8-sig') as fp:
        for i, c in enumerate(cues, 1):
            fp.write(f"{i}\n{ts(c['s'])} --> {ts(c['e'])}\n{f(c)}\n\n")

import sys
sys.stdout.reconfigure(encoding='utf-8')
for c in cues:
    print(f"{c['s']:6.2f}-{c['e']:6.2f} [{len(c['zh']):2d}|{len(c['en']):2d}] {c['zh']} | {c['en']}")

