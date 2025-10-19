import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import re

PLAYLIST_URL = "https://raw.githubusercontent.com/moajzim47/moajzimofficials/9902d23e34d9c7a747ff2846d78e1c4151252df9/It's-Unique-Hex-MoAj-STREAMZ-PLAY.M3U"

def fetch_playlist(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    lines = r.text.splitlines()
    entries, current_info = [], None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            current_info = line
        elif line.startswith("http"):
            entries.append((current_info, line))
            current_info = None
    return entries

def check_stream(entry):
    info, url = entry
    headers = {}
    if "|Referer=" in url:
        url, ref = url.split("|Referer=")
        headers["Referer"] = ref.strip()
    try:
        r = requests.get(url, stream=True, headers=headers, timeout=10)
        ct = r.headers.get("content-type", "").lower()
        if r.status_code == 200 and ("mpegurl" in ct or "video" in ct):
            return info, url, headers.get("Referer", ""), True
    except Exception:
        pass
    return info, url, headers.get("Referer", ""), False

def main():
    print("🔍 Checking playlist...")
    entries = fetch_playlist(PLAYLIST_URL)
    live_entries = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(check_stream, entries))

    # Markdown table
    md = [
        f"# 📺 HLS Playlist Checker",
        f"**Checked:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "| # | Channel | Status | Referer | Link |",
        "|---|----------|--------|----------|------|",
    ]
    for i, (info, url, ref, ok) in enumerate(results, 1):
        name = re.search(r',(.+)', info or "")
        name = name.group(1).strip() if name else "Unknown"
        status = "✅ Live" if ok else "❌ Dead"
        if ok:
            live_entries.append((info, url, ref))
        md.append(f"| {i} | {name} | {status} | {ref or '-'} | [Link]({url}) |")

    with open("hls_check_results.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # HTML report
    html = f"""<html><head><meta charset='UTF-8'><title>HLS Report</title>
    <style>body{{background:#0d1117;color:#c9d1d9;font-family:sans-serif;padding:20px;}}
    table{{width:100%;border-collapse:collapse;}}
    td,th{{border:1px solid #30363d;padding:8px;}}
    tr:nth-child(even){{background:#161b22;}}
    a{{color:#58a6ff;}}</style></head><body>
    <h1>📺 HLS Playlist Checker</h1>
    <p>Checked: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    <table><tr><th>#</th><th>Channel</th><th>Status</th><th>Referer</th><th>Link</th></tr>"""
    for i, (info, url, ref, ok) in enumerate(results, 1):
        name = re.search(r',(.+)', info or "")
        name = name.group(1).strip() if name else "Unknown"
        html += f"<tr><td>{i}</td><td>{name}</td><td>{'✅ Live' if ok else '❌ Dead'}</td><td>{ref or '-'}</td><td><a href='{url}'>{url}</a></td></tr>"
    html += "</table></body></html>"
    with open("hls_check_results.html", "w", encoding="utf-8") as f:
        f.write(html)

    # Only working streams
    with open("live_links.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for info, url, ref in live_entries:
            if info:
                f.write(f"{info}\n")
            if ref:
                f.write(f"{url}|Referer={ref}\n")
            else:
                f.write(f"{url}\n")

    print(f"✅ Done! {len(live_entries)} working / {len(entries)} total streams.")

if __name__ == "__main__":
    main()
