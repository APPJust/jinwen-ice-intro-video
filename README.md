# 景文科技大學 資訊與通訊系 介紹影片

JinWen University of Science and Technology — Department of Information and Communication Engineering

Vox 紙張拼貼風格招生介紹影片（1920×1080、30fps、約 180 秒），中英雙語配音與字幕。

作者：李振偉

## 內容

| 路徑 | 說明 |
|---|---|
| `output/interactive/` | 互動 HTML 版（播放／拖曳／章節／切換中英配音／字幕開關），開啟 `index.html` 即可 |
| `output/*.srt` | 字幕：雙語、中文、English |
| `src/` | 製作腳本 |
| Releases | 三支 MP4：中文配音、English、雙音軌 |

## 製作流程

需要 Python 3.11、`edge-tts`、`playwright`、`numpy`、`scipy`、`imageio-ffmpeg`、`Pillow`，以及 Microsoft Edge。

```bash
python src/tts.py      # edge-tts 中英配音 + 時間軸
python src/subs.py     # 字幕分段、timeline.js、SRT
python src/shoot.py    # 每幕每階段截圖 + 版面自檢
python src/audio.py    # 合成配樂與音效、ducking、-15 LUFS
python src/render.py   # 逐格渲染（15fps 定格）→ 30fps MP4
```

## 資料來源

- 104人力銀行《2025科技業人才報告書》
- 景文科大資通系招生資料（114 學年學雜費、校友就業實例、iPAS 鑑定成績）
- 新北大眾捷運公司（安坑輕軌）
