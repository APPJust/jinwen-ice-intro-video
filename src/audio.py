"""合成配樂＋物理音效，放入中/英配音，旁白時自動壓低音樂（ducking），整體正規化至 -15 LUFS。
輸出：build/mix_zh.wav、build/mix_en.wav（以及互動頁用 m4a）"""
import json, os, re, subprocess, sys, wave
import numpy as np
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, 'build')
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 48000
TL = json.load(open(os.path.join(B, 'timeline.json'), encoding='utf-8'))
SFX = json.load(open(os.path.join(B, 'sfx.json')))
DUR = TL['duration'] + 0.5
N = int(DUR * SR)
rng = np.random.default_rng(7)
sys.stdout.reconfigure(encoding='utf-8')


# ---------------- 基本工具 ----------------
def t_(d):
    return np.arange(int(d * SR)) / SR


def noise(d):
    return rng.standard_normal(int(d * SR))


def onepole_lp(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x); s = 0.0
    # 向量化近似：用 lfilter 等效
    from scipy.signal import lfilter
    return lfilter([1 - a], [1, -a], x)


def bp(x, lo, hi, order=2):
    from scipy.signal import butter, sosfilt
    sos = butter(order, [lo, hi], btype='band', fs=SR, output='sos')
    return sosfilt(sos, x)


def hp(x, f, order=2):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(order, f, btype='high', fs=SR, output='sos'), x)


def lp(x, f, order=2):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(order, f, btype='low', fs=SR, output='sos'), x)


def env_ad(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / d)


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


def sweep_bp(x, f0, f1):
    """分段掃頻帶通"""
    out = np.zeros_like(x); seg = 1024
    nseg = len(x) // seg + 1
    for i in range(nseg):
        a, b = i * seg, min(len(x), (i + 1) * seg + 512)
        if a >= len(x): break
        f = f0 * (f1 / f0) ** (i / max(1, nseg - 1))
        y = bp(x[max(0, a - 512):b], f * 0.6, min(f * 1.6, SR / 2 - 100))
        y = y[(a - max(0, a - 512)):]
        out[a:a + seg] += y[:min(seg, len(x) - a)]
    return out


# ---------------- 音效 ----------------
def s_paper():
    d = 0.28; x = bp(noise(d), 1500, 7000) * env_ad(int(d * SR), 0.01, 0.07)
    x *= (1 + 0.8 * np.sin(2 * np.pi * 37 * t_(d)) * rng.random())
    return norm(x, .7)


def s_slap():
    d = 0.22; t = t_(d)
    body = np.sin(2 * np.pi * (140 * np.exp(-t * 18) + 60) * t) * np.exp(-t * 28)
    crack = hp(noise(d), 1200) * np.exp(-t * 70)
    rust = bp(noise(d), 2000, 8000) * env_ad(len(t), 0.005, 0.05) * .5
    return norm(body * .9 + crack * .7 + rust, .9)


def s_tear():
    d = 0.62; n = int(d * SR); x = bp(noise(d), 900, 7000)
    imp = (rng.random(n) < 0.02).astype(float); imp = lp(imp, 900) * 40
    e = np.minimum(1, t_(d) / 0.05) * np.exp(-np.maximum(0, t_(d) - 0.45) / 0.06)
    return norm(x * (0.35 + np.abs(imp)) * e, .85)


def s_snip():
    d = 0.12; t = t_(d)
    click = hp(noise(d), 3000) * np.exp(-t * 300)
    ring = (np.sin(2 * np.pi * 3400 * t) + .6 * np.sin(2 * np.pi * 5200 * t)) * np.exp(-t * 60)
    return norm(click + ring * .35, .8)


def s_whoosh(d=0.48, f0=300, f1=3000):
    x = sweep_bp(noise(d), f0, f1)
    t = t_(d); e = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2
    return norm(x * e, .7)


def s_flip():
    return s_whoosh(0.18, 800, 4000) * .8 + np.pad(s_paper()[:int(.1 * SR)], (0, int(.08 * SR)))[:int(.18 * SR)] * .4


def s_marker():
    d = 0.42; t = t_(d); x = bp(noise(d), 2500, 6000) * (0.6 + 0.4 * np.sin(2 * np.pi * 22 * t))
    return norm(x * np.sin(np.pi * t / d) ** .6, .5)


def s_scribble():
    d = 0.7; t = t_(d); x = bp(noise(d), 2200, 7000) * np.abs(np.sin(2 * np.pi * 9 * t)) ** 2
    return norm(x * np.sin(np.pi * t / d) ** .5, .55)


def s_stamp():
    d = 0.45; t = t_(d)
    thud = np.sin(2 * np.pi * (90 * np.exp(-t * 12) + 45) * t) * np.exp(-t * 14)
    crack = bp(noise(d), 600, 5000) * np.exp(-t * 55)
    return norm(thud + crack * .6, 1.0)


def s_boom():
    d = 1.4; t = t_(d)
    sub = np.sin(2 * np.pi * (70 * np.exp(-t * 4) + 38) * t) * np.exp(-t * 3.2)
    hit = lp(noise(d), 2500) * np.exp(-t * 18)
    tail = bp(noise(d), 200, 1800) * np.exp(-t * 4) * .15
    return norm(sub + hit * .5 + tail, 1.0)


def s_pop():
    d = 0.09; t = t_(d); f = 380 + 900 * t / d
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 40), .6)


def s_shutter():
    d = 0.2; out = np.zeros(int(d * SR))
    for off, g in ((0, 1), (0.065, .7)):
        a = int(off * SR); c = hp(noise(0.03), 1500) * np.exp(-t_(0.03) * 140) * g
        out[a:a + len(c)] += c
    out += bp(noise(d), 300, 1500) * np.exp(-t_(d) * 30) * .3
    return norm(out, .75)


def s_ding():
    d = 1.6; t = t_(d)
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * k) for f, a, k in ((1318.5, 1, 2.5), (2637, .4, 4), (3951, .2, 6), (1975.5, .3, 3)))
    return norm(x * np.minimum(1, t / 0.003), .55)


def s_tick1():
    d = 0.03; t = t_(d)
    return norm(np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 220), .35)


def s_typeclick():
    d = 0.05; t = t_(d)
    x = hp(noise(d), 1800) * np.exp(-t * 160) + np.sin(2 * np.pi * 900 * t) * np.exp(-t * 120) * .5
    return norm(x, .55 + .2 * rng.random())


def s_tape():
    d = 0.8; n = int(d * SR); t = t_(d)
    x = bp(noise(d), 1200, 9000)
    crackle = lp((rng.random(n) < 0.06).astype(float), 3000) * 25
    e = np.minimum(1, t / 0.03) * np.exp(-np.maximum(0, t - 0.6) / 0.08)
    return norm(x * (0.25 + np.abs(crackle)) * e, .8)


def s_riser():
    d = 1.3; t = t_(d)
    f = 200 * (6 ** (t / d))
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * .3
    x = sweep_bp(noise(d), 400, 6000) * .7
    return norm((tone + x) * (t / d) ** 2, .6)


def s_swish():
    return s_whoosh(0.55, 200, 5000)


BANK = {'paper': s_paper, 'slap': s_slap, 'tear': s_tear, 'snip': s_snip, 'whoosh': s_whoosh, 'flip': s_flip,
        'marker': s_marker, 'scribble': s_scribble, 'stamp': s_stamp, 'boom': s_boom, 'pop': s_pop,
        'shutter': s_shutter, 'ding': s_ding, 'tick1': s_tick1, 'tape': s_tape, 'riser': s_riser, 'swish': s_swish}
GAIN = {'paper': .55, 'slap': .7, 'tear': .9, 'snip': .8, 'whoosh': .5, 'flip': .5, 'marker': .45, 'scribble': .5,
        'stamp': .95, 'boom': .9, 'pop': .45, 'shutter': .6, 'ding': .5, 'tick1': .4, 'tape': .8, 'riser': .55, 'swish': .5,
        'type': .55, 'tick': .5}


def build_sfx():
    L = np.zeros((N, 2))
    def put(x, t, g, pan=0.0):
        a = int(t * SR)
        if a < 0: x = x[-a:]; a = 0
        b = min(N, a + len(x)); x = x[:b - a] * g
        L[a:b, 0] += x * np.sqrt((1 - pan) / 2) * 1.414
        L[a:b, 1] += x * np.sqrt((1 + pan) / 2) * 1.414
    for e in SFX:
        ty, t = e['type'], e['t']
        g = GAIN.get(ty, .5) * (0.9 + 0.2 * rng.random())
        pan = (rng.random() - .5) * .5
        if ty == 'type':
            for i in range(e['n']):
                put(s_typeclick(), t + i * e['dur'] / e['n'] + rng.random() * .02, g, pan)
            put(s_ding() * .5, t + e['dur'] + .05, g * .6)
        elif ty == 'tick':
            for i in range(e['n']):
                put(s_tick1(), t + i * e['dur'] / e['n'], g)
        elif ty == 'riser':
            x = s_riser(); put(x, t - len(x) / SR + 0.05, g)
        elif ty == 'swish':
            x = s_swish(); a = int(t * SR)
            # 由右到左掃過
            n = len(x); p = np.linspace(.8, -.8, n)
            b = min(N, a + n); m = b - a
            L[a:b, 0] += x[:m] * g * np.sqrt((1 - p[:m]) / 2) * 1.414
            L[a:b, 1] += x[:m] * g * np.sqrt((1 + p[:m]) / 2) * 1.414
        else:
            put(BANK[ty](), t, g, pan)
    return L


# ---------------- 配樂（100 BPM，明亮 indie-lofi） ----------------
def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


def ep_note(f, d, vel=1.0):
    t = t_(d)
    x = np.sin(2 * np.pi * f * t) + .28 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6) + .1 * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t * 9)
    x *= np.minimum(1, t / 0.004) * np.exp(-t * 3.2) * (1 + .15 * np.sin(2 * np.pi * 5 * t))
    return x * vel


def build_music():
    from scipy.signal import lfilter
    bpm = 100; beat = 60 / bpm; bar = beat * 4
    M = np.zeros((N, 2))
    sc = {s['id']: s for s in TL['scenes']}
    t_data, t_outro = sc['data']['start'], sc['outro']['start']
    t_end = sc['outro']['start'] + 6.9  # 片尾卡
    # 和弦：Fmaj7 - G6 - Em7 - Am7（C 大調）
    prog = [[53, 57, 60, 64], [55, 59, 62, 64], [52, 55, 59, 62], [57, 60, 64, 67]]
    roots = [41, 43, 40, 45]
    nbars = int(DUR / bar) + 1

    def add(x, t, g=1.0, pan=0.0):
        a = int(t * SR)
        if a >= N: return
        b = min(N, a + len(x)); x = x[:b - a] * g
        M[a:b, 0] += x * (1 - pan) * .5 * 1.414 ** 0 * 1.0
        M[a:b, 1] += x * (1 + pan) * .5

    kick = None
    tk = t_(0.32); kick = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-tk * 30)) / SR) * np.exp(-tk * 9)
    tsn = t_(0.25); snare = bp(rng.standard_normal(len(tsn)), 1200, 7000) * np.exp(-tsn * 22) * .8 + np.sin(2 * np.pi * 190 * tsn) * np.exp(-tsn * 30) * .5
    th = t_(0.05); hat = hp(rng.standard_normal(len(th)), 7000) * np.exp(-th * 90)

    for i in range(nbars):
        t0 = i * bar
        if t0 > t_end + 4: break
        ch = prog[i % 4]; rt = roots[i % 4]
        full = t_data - 0.05 <= t0 < t_outro
        hook = t0 < t_data - 0.05
        outro = t0 >= t_outro
        # Pad
        dpad = bar + 0.3
        tp = t_(dpad)
        pad = sum(lp(np.sign(np.sin(2 * np.pi * midi(n) * tp + k)) * .2 + np.sin(2 * np.pi * midi(n) * 1.003 * tp), 1800) for k, n in enumerate(ch))
        pad *= np.minimum(1, tp / 0.4) * np.minimum(1, (dpad - tp) / 0.3)
        add(pad * (.10 if full else .14), t0, 1, (-.3 if i % 2 else .3))
        # EP 琶音（8 分音符）
        if not (hook and t0 < 4.8):
            pat = [0, 2, 1, 3, 2, 1, 3, 2] if i % 2 == 0 else [0, 1, 2, 3, 2, 3, 1, 2]
            for j, k in enumerate(pat):
                if hook and j % 2: continue
                n = ch[k] + 12
                add(ep_note(midi(n), 0.9, .9 - .1 * (j % 2)) * .11, t0 + j * beat / 2 + (0.012 if j % 2 else 0), 1, (k - 1.5) * .3)
        # 高音閃爍（設備幕之後）
        if full and t0 >= sc['lab']['start'] and i % 2 == 1:
            for j in range(4):
                add(ep_note(midi(ch[(j + 1) % 4] + 24), .5, .5) * .05, t0 + beat * (j + .5), 1, .5 - j * .3)
        # Bass
        if full or (outro and t0 < t_end):
            for pos, nn, dd in ((0, rt, beat * 1.4), (beat * 1.5, rt, beat * .45), (beat * 2, rt + 7, beat * .9), (beat * 3, rt + 12 if i % 2 else rt, beat * .9)):
                tb = t_(dd); fb = midi(nn + (0 if outro else 0))
                xb = np.tanh(2.2 * np.sin(2 * np.pi * fb * tb)) * np.minimum(1, tb / .01) * np.exp(-tb * 2.2) * np.minimum(1, (dd - tb) / .03)
                add(xb * (.22 if full else .14), t0 + pos)
        # Drums
        if full:
            for b4 in range(4):
                tb = t0 + b4 * beat
                if b4 in (0, 2): add(kick * .75, tb)
                if b4 == 2 and i % 2: add(kick * .45, tb + beat * .5)
                if b4 in (1, 3): add(snare * .32, tb, 1, .1)
                for h in (0, .5):
                    add(hat * (.16 if h == 0 else .1), tb + h * beat + (0.018 if h else 0), 1, -.35)
        elif hook:
            # 開場：時鐘般滴答＋低鳴，製造懸念
            for b4 in range(4):
                add(hat * .12, t0 + b4 * beat, 1, .3 * (1 if b4 % 2 else -1))
            if i % 2 == 0: add(kick * .35, t0)
        elif outro and t0 < sc['outro']['start'] + 6:
            add(kick * .4, t0)
    # 片尾大和弦
    tf = t_(5.0)
    fin = sum(ep_note(midi(n), 5.0, 1) for n in (48, 55, 60, 64, 67, 72)) * .12
    add(fin, t_end - 0.05)
    # 片段淡出
    fade = np.ones(N); fe = int((DUR - 2.5) * SR); fade[fe:] = np.linspace(1, 0, N - fe)
    M *= fade[:, None]
    # 開頭在第一幕「撕裂」前留有懸念：0~0.5s 淡入
    fi = int(.5 * SR); M[:fi] *= np.linspace(0, 1, fi)[:, None]
    return M


# ---------------- 配音 ----------------
def read_wav(p):
    with wave.open(p) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
    return x


def build_voice(lang):
    V = np.zeros(N)
    for c in TL['cues']:
        x = read_wav(c[f'{lang}_wav'])
        a = int(c['start'] * SR); b = min(N, a + len(x)); V[a:b] += x[:b - a]
    return V


def duck_gain(V):
    """旁白包絡 -> 音樂增益（約 -11 dB），攻擊 40ms、釋放 450ms"""
    from scipy.signal import lfilter
    env = np.sqrt(lfilter([1], [1, -0.999], V ** 2) * 0.001 + 1e-12)
    thr = 0.02
    target = np.where(env > thr, 0.28, 1.0)
    # 不對稱平滑
    g = np.empty(N); s = 1.0
    aa = np.exp(-1 / (0.04 * SR)); ar = np.exp(-1 / (0.45 * SR))
    # 降取樣計算以加速
    step = 48
    tg = target[::step]; out = np.empty(len(tg))
    aa2, ar2 = aa ** step, ar ** step
    for i, v in enumerate(tg):
        k = aa2 if v < s else ar2
        s = v + (s - v) * k; out[i] = s
    g = np.repeat(out, step)[:N]
    return g


def write_wav(p, X):
    X = np.clip(X, -1, 1)
    with wave.open(p, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((X * 32767).astype(np.int16).tobytes())


def loudnorm(src, dst, I=-15.0, TP=-1.5):
    r = subprocess.run([FF, '-hide_banner', '-i', src, '-af', f'loudnorm=I={I}:TP={TP}:LRA=11:print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='ignore')
    js = json.loads(re.findall(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr)[-1])
    af = (f"loudnorm=I={I}:TP={TP}:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    subprocess.run([FF, '-y', '-loglevel', 'error', '-i', src, '-af', af, '-ar', '48000', dst], check=True)


def measure(p):
    r = subprocess.run([FF, '-hide_banner', '-i', p, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='ignore')
    s = r.stderr[r.stderr.rfind('Summary'):]
    I = re.search(r'I:\s+(-?[\d.]+) LUFS', s).group(1); P = re.search(r'Peak:\s+(-?[\d.]+) dBFS', s).group(1)
    return float(I), float(P)


if __name__ == '__main__':
    print('合成音效…'); S = build_sfx()
    print('合成配樂…'); M = build_music()
    M = M / (np.max(np.abs(M)) + 1e-9) * 0.5
    S = S / (np.max(np.abs(S)) + 1e-9) * 0.6
    for lang in ('zh', 'en'):
        V = build_voice(lang)
        # 中英配音音量對齊：語音段 RMS -> -18 dBFS
        from scipy.ndimage import maximum_filter1d
        act = maximum_filter1d((np.abs(V) > 0.02).astype(np.uint8), size=SR // 5) > 0
        V *= 10 ** ((-18 - 20 * np.log10(np.sqrt(np.mean(V[act] ** 2)))) / 20)
        g = duck_gain(V)
        mix = np.stack([V, V], 1) * 0.95 + M * 0.65 * g[:, None] + S * 0.75
        raw = os.path.join(B, f'raw_{lang}.wav'); write_wav(raw, mix / max(1, np.max(np.abs(mix))))
        out = os.path.join(B, f'mix_{lang}.wav'); loudnorm(raw, out)
        I, P = measure(out)
        print(f'{lang}: Integrated {I} LUFS, True-peak-ish {P} dBFS')
        m4a = os.path.join(ROOT, 'output', 'interactive', 'audio', f'mix_{lang}.m4a')
        subprocess.run([FF, '-y', '-loglevel', 'error', '-i', out, '-c:a', 'aac', '-b:a', '160k', m4a], check=True)
    # 純音樂 / 音效檢查用
    write_wav(os.path.join(B, 'music_only.wav'), M); write_wav(os.path.join(B, 'sfx_only.wav'), S)
    print('done')
