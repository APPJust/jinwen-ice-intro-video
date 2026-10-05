"""逐格渲染動畫頁（15 fps 定格）→ 30 fps H.264，再與中／英混音合成 MP4"""
import os, pathlib, subprocess, sys, time
import imageio_ffmpeg
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
PAGE = (ROOT / 'output' / 'interactive' / 'index.html').as_uri() + '?render'
B = ROOT / 'build'; O = ROOT / 'output'
FPS = 15
sys.stdout.reconfigure(encoding='utf-8')

MUX_ONLY = '--mux-only' in sys.argv
if not MUX_ONLY:
  with sync_playwright() as p:
      br = p.chromium.launch(channel='msedge')
      pg = br.new_page(viewport={'width': 1920, 'height': 1080})
      pg.goto(PAGE); pg.evaluate('window.ready'); pg.wait_for_timeout(800)
      dur = pg.evaluate('TL.duration')
      n = int(dur * FPS)
      enc = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-',
                              '-vf', 'fps=30,scale=in_range=pc:out_range=tv,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-maxrate', '10M', '-bufsize', '20M', '-tune', 'grain', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-movflags', '+faststart',
                              '-r', '30', str(B / 'video.mp4')], stdin=subprocess.PIPE)
      t0 = time.time()
      for i in range(n):
          pg.evaluate(f'renderAt({i / FPS + 1e-4})')
          enc.stdin.write(pg.screenshot(type='jpeg', quality=93))
          if i % 150 == 0:
              print(f'{i}/{n}  {time.time() - t0:.0f}s', flush=True)
      enc.stdin.close(); enc.wait(); br.close()
  
names = {'zh': '中文配音', 'en': 'English'}
for lang in ('zh', 'en'):
    subprocess.run([FF, '-y', '-loglevel', 'error', '-i', str(B / 'video.mp4'), '-i', str(B / f'mix_{lang}.wav'),
                    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest',
                    '-metadata', 'title=景文科技大學 資訊與通訊系介紹', '-metadata', 'artist=李振偉',
                    str(O / f'景文資通系介紹_{names[lang]}.mp4')], check=True)
# 雙音軌版（中文預設、English 第二音軌）
subprocess.run([FF, '-y', '-loglevel', 'error', '-i', str(B / 'video.mp4'), '-i', str(B / 'mix_zh.wav'), '-i', str(B / 'mix_en.wav'),
                '-map', '0:v', '-map', '1:a', '-map', '2:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                '-metadata:s:a:0', 'language=chi', '-metadata:s:a:0', 'title=中文配音',
                '-metadata:s:a:1', 'language=eng', '-metadata:s:a:1', 'title=English',
                '-disposition:a:0', 'default', '-disposition:a:1', '0', '-metadata', 'artist=李振偉', '-shortest',
                str(O / '景文資通系介紹_雙音軌.mp4')], check=True)
print('DONE')
