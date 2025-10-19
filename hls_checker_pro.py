import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

PLAYLIST_URL = "https://raw.githubusercontent.com/moajzim47/moajzimofficials/9902d23e34d9c7a747ff2846d78e1c4151252df9/It's-Unique-Hex-MoAj-STREAMZ-PLAY.M3U"

def fetch_playlist(url):
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return [line.strip() for line in resp.text.splitlines() if line and not line.startswith("#")]

def check_stream(url):
    try:
        r = requests.get(url, stream=True, timeout=10)
        if r.status_code == 200 and "mpegurl" in r.headers.get("content-type", "").lower():
            return url, True
    except Exception:
        pass
    return url, False

def main():
    print("🔍 Checking HLS links...")
    links = fetch_playlist(PLAYLIST_URL)
    live_links = []

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(check_stream, links))

    md_lines = [
        f"# 🎬 HLS Stream Check Report",
        f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "| # | Stream URL | Status |",
        "|---|-------------|--------|",
    ]

    for i, (url, ok) in enumerate(results, 1):
        status = "✅ Live" if ok else "❌ Dead"
        if ok:
            live_links.append(url)
        md_lines.append(f"| {i} | [{url}]({url}) | {status} |")

    # Save Markdown
    with open("hls_check_results.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # Save HTML
    html = f"""
    <html><head><meta charset="UTF-8"><title>HLS Report</title>
    <style>body{{font-family:sans-serif;background:#0d1117;color:#c9d1d9;}}
    table{{border-collapse:collapse;width:100%;}}
    th,td{{border:1px solid #30363d;padding:8px;text-align:left;}}
    tr:nth-child(even){{background:#161b22;}}</style></head><body>
    <h1>🎬 HLS Stream Check Report</h1>
    <p><b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    <table><tr><th>#</th><th>Stream URL</th><th>Status</th></tr>
    {''.join([f'<tr><td>{i}</td><td><a href="{url}">{url}</a></td><td>{"✅ Live" if ok else "❌ Dead"}</td></tr>' for i,(url,ok) in enumerate(results,1)])}
    </table></body></html>
    """
    with open("hls_check_results.html", "w", encoding="utf-8") as f:
        f.write(html)

    # Save only live links
    with open("live_links.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for link in live_links:
            f.write(f"#EXTINF:-1,Live Stream\n{link}\n")

    print(f"✅ Done! {len(live_links)} working links found out of {len(links)} total.")

if __name__ == "__main__":
    main()
