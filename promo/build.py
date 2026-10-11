#!/usr/bin/env python3
"""叶哥提词器宣传片合成: 帧序列 → 场景分段 → 按口播时间轴拼接 → 烧字幕 → 混音"""
import subprocess, os, json, math

P = "/Users/yasin/clawd/teleprompter/promo"
F = f"{P}/frames"
OUT = f"{P}/out"
os.makedirs(OUT, exist_ok=True)
W, H, FPS = 1920, 1080, 30
VO = f"{P}/voiceover.mp3"

# ---------- 1. 读字幕时间轴 (whisper对齐不可用时按字符占比估算) ----------
lines = [l.strip() for l in open(f"{P}/script.txt", encoding="utf-8") if l.strip()]
total_dur = float(subprocess.check_output(
    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", VO]).decode().strip())
GAP = 0.55  # 每句间停顿
speech = total_dur - GAP * (len(lines) - 1)
chars = [len(l) for l in lines]
total_chars = sum(chars)
# 均匀分配
subs, t = [], 0.0
for i, l in enumerate(lines):
    d = speech * chars[i] / total_chars
    subs.append({"text": l, "start": round(t, 2), "end": round(t + d, 2)})
    t += d + GAP
json.dump(subs, open(f"{OUT}/subs.json", "w"), ensure_ascii=False, indent=1)
print(f"总时长 {total_dur:.1f}s, {len(lines)}句字幕")

# ---------- 2. 场景时间轴 (与字幕语义对齐, 以实际切句为准) ----------
# 0开场问+忘词  1低头+订阅痛点  2我做了开源  3核心能力+念到哪跟到哪  4多稿库+扫码同步
# 5 iPad  6零订阅+一个网页  7 GitHub地址+slogan
sc = [
    ("card_hook.png",   subs[0]["start"],  subs[1]["start"] - GAP),  # 开场问+忘词
    ("card_pain.png",   subs[1]["start"],  subs[2]["start"] - GAP),  # 低头+订阅痛点
    ("FOLLOW",          subs[2]["start"],  subs[4]["start"] - GAP),  # 引出产品+核心能力(语音跟随演示)
    ("LIB",             subs[4]["start"],  subs[5]["start"] - GAP),  # 多稿库+存本地+扫码
    ("IPAD",            subs[5]["start"],  subs[6]["start"] - GAP),  # iPad
    ("QR",              subs[6]["start"],  subs[7]["start"] - GAP),  # 零订阅+一个网页(扫码/地址条展示)
    ("follow_last.png", subs[6]["start"],  subs[7]["start"] - GAP),  # (占位被上一行覆盖)
    ("card_end.png",    subs[7]["start"],  total_dur + 1.0),         # GitHub+slogan收尾
]
sc = sc[:6] + [sc[7]]  # 去掉占位行, 保留: hook/pain/FOLLOW/LIB/IPAD/QR/end
sc[5] = ("card_https.png", subs[6]["start"], subs[7]["start"] - GAP)  # 零订阅段用https卡

def scene_frames(spec):
    """返回该场景的帧文件列表(按时间顺序)"""
    name, start, end = spec
    dur = end - start
    n = max(2, int(dur * FPS))
    if name.endswith(".png"):
        return [name] * n
    if name == "FOLLOW":
        fs = sorted(f for f in os.listdir(F) if f.startswith("follow_"))
    elif name == "LIB":
        fs = sorted(f for f in os.listdir(F) if f.startswith("lib_")) + \
             sorted(f for f in os.listdir(F) if f.startswith("libload_"))
    elif name == "QR":
        fs = sorted(f for f in os.listdir(F) if f.startswith("qr_"))
    elif name == "IPAD":
        fs = sorted(f for f in os.listdir(F) if f.startswith("ipad_"))
    elif name == "follow_last.png":
        return [f"{F}/follow_{sorted(x for x in os.listdir(F) if x.startswith('follow_'))[-1]}"] * n
    else:
        return [name] * n
    # 帧循环/截断到需要的数量, 30fps
    out = []
    for i in range(n):
        out.append(fs[min(int(i / n * len(fs)), len(fs) - 1)])
    return out

# ---------- 3. 逐场景生成视频片段(带缩放pad到1920x1080) ----------
os.makedirs(f"{OUT}/segs", exist_ok=True)
seg_files = []
for idx, spec in enumerate(sc):
    name, start, end = spec
    dur = end - start
    frames = scene_frames(spec)
    n = len(frames)
    with open(f"{OUT}/segs/s{idx}.txt", "w") as f:
        for fr in frames:
            path = fr if os.path.isabs(fr) else os.path.join(F, fr)
            card = os.path.join(P, "cards.html")  # cards是png已截好
            f.write(f"file '{path}'\nduration {1/FPS}\n")
    vf = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30,format=yuv420p"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", f"{OUT}/segs/s{idx}.txt", "-vf", vf,
                        "-c:v", "libx264", "-preset", "fast", "-t", f"{dur:.2f}", f"{OUT}/segs/seg{idx}.mp4"])
    assert r.returncode == 0, f"seg{idx} fail"
    seg_files.append(f"{OUT}/segs/seg{idx}.mp4")
    print(f"seg{idx}: {name} {dur:.1f}s ✓")

# ---------- 4. 拼接 ----------
with open(f"{OUT}/concat.txt", "w") as f:
    for s in seg_files:
        f.write(f"file '{s}'\n")
r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", f"{OUT}/concat.txt", "-c", "copy", f"{OUT}/base.mp4"])
assert r.returncode == 0

# ---------- 5. 烧字幕 + 混音 ----------
def esc(t):
    return t.replace("'", "\\'").replace(":", "\\:")
sub_lines = "\n".join(
    f"{i}\n{s['start']:.2f} --> {s['end']:.2f}\n{{\\an2}}{s['text']}\n"
    for i, s in enumerate(subs))
open(f"{OUT}/subs.srt", "w", encoding="utf-8").write(sub_lines)

vf = (f"subtitles={OUT}/subs.srt:force_style='FontName=PingFang SC,FontSize=15,"
      f"PrimaryColour=&H00FFFFFF,OutlineColour=&HAA000000,BorderStyle=1,Outline=2,Shadow=1,MarginV=42'")
r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{OUT}/base.mp4", "-i", VO,
                    "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", f"{P}/叶哥提词器-宣传片.mp4"])
assert r.returncode == 0, "final fail"
print("✅ 成片:", f"{P}/叶哥提词器-宣传片.mp4")
