"""互動 HTML 播放器測試：拖曳→播放→切換語言，確認音訊與畫面同步"""
import pathlib, sys
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding='utf-8')
ROOT = pathlib.Path(__file__).resolve().parent.parent
u = (ROOT / 'output' / 'interactive' / 'index.html').as_uri()
JS = "[document.getElementById('aud').src.slice(-10), +document.getElementById('aud').currentTime.toFixed(2), window.__t, document.getElementById('time').textContent]"
with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge', args=['--autoplay-policy=no-user-gesture-required'])
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    pg.on('pageerror', lambda e: print('PAGEERROR', e))
    pg.goto(u); pg.evaluate('window.ready'); pg.wait_for_timeout(800)
    pg.evaluate("(()=>{const s=document.querySelector('#seek'); s.value=97; s.dispatchEvent(new Event('input'))})()")
    print('seek   ', pg.evaluate(JS))
    pg.click('#play'); pg.wait_for_timeout(2500)
    print('play   ', pg.evaluate(JS))
    pg.select_option('#lang', 'en'); pg.wait_for_timeout(2000)
    print('lang en', pg.evaluate(JS))
    pg.click('#subbtn'); pg.wait_for_timeout(300)
    print('subs hidden', pg.evaluate("document.getElementById('subs').classList.contains('hide')"))
    pg.click('#subbtn')
    pg.screenshot(path=str(ROOT / 'build' / 'ui_test.jpg'))
    b.close()
