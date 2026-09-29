#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate an APTV-friendly curated M3U from vbskycn/iptv.
Keeps selected common channels and up to 3 URLs per channel.
"""
import re
import urllib.request
from collections import defaultdict
from urllib.parse import urlsplit, quote

UPSTREAM = "https://live.zbds.top/tv/iptv4.txt"
FALLBACK = "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt"
OUTPUT = "aptv_curated.m3u"

TARGETS = [
    *[f"CCTV{i}" for i in range(1, 18)],
    "CCTV5+",
    "CGTN",
    "北京卫视","东方卫视","湖南卫视","江苏卫视","浙江卫视","广东卫视",
    "深圳卫视","河北卫视","河南卫视","湖北卫视","山东卫视","安徽卫视",
    "辽宁卫视","黑龙江卫视","四川卫视","重庆卫视",
]

OFFICIALISH = (
    "cgtn.com", "cztv.com", "bestv.cn", "mgtv.com", "hljtv.com",
    "zohi.tv", "cnr.cn", "xntv.tv", "sdetv.com.cn",
)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")

def load_source():
    errors = []
    for url in (UPSTREAM, FALLBACK):
        try:
            return fetch(url), url
        except Exception as e:
            errors.append(f"{url}: {e}")
    raise RuntimeError("Unable to fetch upstream:\n" + "\n".join(errors))

def parse(text):
    data = defaultdict(list)
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ",#genre#" in line or "," not in line:
            continue
        name, url = line.split(",", 1)
        name, url = name.strip(), url.strip()
        if not url.startswith(("http://", "https://")):
            continue
        low = url.lower()
        if ".mp4" in low or "/udp/" in low or low.startswith("udp://"):
            continue
        if name in TARGETS:
            data[name].append(url)
    return data

def dedupe(urls):
    seen, out = set(), []
    for u in urls:
        p = urlsplit(u)
        key = (p.netloc.lower(), p.path.rstrip("/"), p.query.rstrip("?"))
        if key not in seen:
            seen.add(key)
            out.append(u)
    return out

def score(url):
    low = url.lower()
    host = urlsplit(url).netloc.lower()
    s = 0
    if low.startswith("https://"): s += 25
    if ".m3u8" in low: s += 20
    if "1080" in low: s += 12
    if "720" in low: s += 6
    if any(d in host for d in OFFICIALISH): s += 25
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+(?::\d+)?", host): s -= 6
    if ":9901" in host: s -= 4
    if "livekey=" in low or "auth_key=" in low: s -= 12
    if "360p" in low: s -= 10
    return s

def group_for(name):
    return "央视频道" if name.startswith("CCTV") or name == "CGTN" else "卫视频道"

def main():
    text, source = load_source()
    data = parse(text)
    lines = [
        '#EXTM3U x-tvg-url="https://epg.aptv.app/xml"',
        f'# Auto-generated from {source}',
        '# Same channel is listed as 主线/备用1/备用2 for manual fallback in APTV.',
    ]
    missing = []
    for name in TARGETS:
        urls = sorted(dedupe(data.get(name, [])), key=score, reverse=True)[:3]
        if not urls:
            missing.append(name)
            continue
        logo = f"https://tb.zbds.top/logo/{quote(name)}.png"
        for idx, url in enumerate(urls, 1):
            suffix = "主线" if idx == 1 else f"备用{idx-1}"
            lines.append(
                f'#EXTINF:-1 tvg-name="{name}" tvg-id="{name}" '
                f'tvg-logo="{logo}" group-title="{group_for(name)}",'
                f'{name} · {suffix}'
            )
            lines.append(url)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Wrote {OUTPUT}")
    if missing:
        print("Missing in upstream:", ", ".join(missing))

if __name__ == "__main__":
    main()
