"""自我檢查：在每一幕的每個畫面階段截圖並跑版面檢查（出界／重疊／碰標題線／字幕遮擋／字型）
用法：python shoot.py            -> 全部檢查點
      python shoot.py 12.5 30   -> 指定秒數
"""
import json, os, sys, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = (ROOT / 'output' / 'interactive' / 'index.html').as_uri() + '?render'
OUT = ROOT / 'build' / 'shots'
OUT.mkdir(parents=True, exist_ok=True)
sys.stdout.reconfigure(encoding='utf-8')


def checkpoints(page):
    tl = page.evaluate('window.TL')
    pts = []
    for sc in tl['scenes']:
        cs = [c for c in tl['cues'] if c['scene'] == sc['id']]
        for c in cs:
            pts.append(round(c['end'] - 0.05, 2))
        pts.append(round(sc['end'] - 0.5, 2))
    return sorted(set(pts))


with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge')
    pg = b.new_page(viewport={'width': 1920, 'height': 1080})
    pg.on('console', lambda m: print('CONSOLE', m.type, m.text) if m.type in ('error', 'warning') else None)
    pg.on('pageerror', lambda e: print('PAGEERROR', e))
    pg.goto(PAGE)
    pg.evaluate('window.ready')
    pg.wait_for_timeout(500)
    print('FONTS', pg.evaluate('fontCheck()'))
    times = [float(x) for x in sys.argv[1:]] or checkpoints(pg)
    nbad = 0
    for t in times:
        r = pg.evaluate(f'checkLayout({t})')
        pg.wait_for_timeout(30)
        f = OUT / f"{t:07.2f}_{r['scene']}.jpg"
        pg.screenshot(path=str(f), type='jpeg', quality=80)
        flag = '  OK' if not r['bad'] else '  !!'
        print(f"{t:7.2f} {r['scene']:9s}{flag}", '; '.join(r['bad']))
        nbad += len(r['bad'])
    print('TOTAL ISSUES', nbad)
    b.close()

