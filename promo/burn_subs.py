#!/usr/bin/env python3
"""用 moviepy 烧字幕 v2: caption模式自动换行, 防溢出"""
import json, sys
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip

P = "/Users/yasin/clawd/teleprompter/promo"
subs = json.load(open(f"{P}/out/subs.json"))

base = VideoFileClip(f"{P}/out/base.mp4")
vo = AudioFileClip(f"{P}/voiceover.mp3")
W, H = base.size

layers = [base]
for s in subs:
    txt = (TextClip(font="/System/Library/Fonts/Hiragino Sans GB.ttc",
                    text=s["text"], font_size=44, color="white",
                    stroke_color="black", stroke_width=2,
                    method="caption", size=(int(W * 0.86), None),  # 86%宽度自动换行
                    text_align="center")
           .with_position(("center", H - 170))
           .with_start(s["start"]).with_end(min(s["end"], base.duration)))
    layers.append(txt)

final = CompositeVideoClip(layers, size=(W, H)).with_audio(vo).with_duration(min(base.duration, vo.duration + 0.8))
final.write_videofile(f"{P}/叶哥提词器-宣传片.mp4", fps=30, codec="libx264",
                      audio_codec="aac", bitrate="6000k", preset="medium", logger=None)
print("✅ 完成")
