import requests
import re
import concurrent.futures
import argparse
import logging
from datetime import datetime
import urllib.parse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('m3u_check.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Default headers
default_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def parse_m3u(content):
    """Parse M3U content and extract stream details."""
    streams = []
    lines = content.splitlines()
    current_stream = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            try:
                # Extract channel name and attributes
                match = re.search(r'#EXTINF:-?\d+\s*(.*?)(?:,(.+))?$', line)
                if match:
                    attributes, name = match.group(1) or "", match.group(2) or "Unknown"
                    current_stream["name"] = name.strip()
                    
                    # Extract tvg-logo
                    logo_match = re.search(r'tvg-logo="([^"]*)"', attributes)
                    current_stream["logo"] = logo_match.group(1) if logo_match else "N/A"
                    
                    # Extract group-title
                    group_match = re.search(r'group-title="([^"]*)"', attributes)
                    current_stream["group"] = group_match.group(1) if group_match else "N/A"
            except Exception as e:
                logger.warning(f"Failed to parse EXTINF line '{line}': {str(e)}")
        elif line and not line.startswith("#"):
            try:
                # Parse URL and extract referer/user-agent if present
                current_stream["url"] = line
                current_stream["referer"] = None
                current_stream["user_agent"] = None
                
                # Handle |Referer= and |User-Agent= in URL
                if "|Referer=" in line:
                    current_stream["url"], current_stream["referer"] = line.split("|Referer=", 1)
                if "|User-Agent=" in current_stream["url"]:
                    parts = current_stream["url"].split("|User-Agent=", 1)
                    current_stream["url"], current_stream["user_agent"] = parts[0], parts[1]
                
                # Validate URL
                parsed_url = urllib.parse.urlparse(current_stream["url"])
                if not parsed_url.scheme or not parsed_url.netloc:
                    logger.warning(f"Invalid URL skipped: {current_stream['url']}")
                    current_stream = {}
                    continue
                
                streams.append(current_stream)
            except Exception as e:
                logger.warning(f"Failed to parse URL line '{line}': {str(e)}")
            current_stream = {}
    
    return streams

def check_url(stream, timeout=10):
    """Check if a stream URL is live and validate M3U8 content."""
    headers = default_headers.copy()
    if stream.get("referer"):
        headers["Referer"] = stream["referer"]
    if stream.get("user_agent"):
        headers["User-Agent"] = stream["user_agent"]
    
    try:
        response = requests.get(stream["url"], headers=headers, timeout=timeout, stream=True)
        if response.status_code != 200:
            return {
                "channel": stream.get("name", "Unknown"),
                "url": stream["url"],
                "status": f"Down (Status: {response.status_code})",
                "group": stream.get("group", "N/A"),
                "logo": stream.get("logo", "N/A"),
                "error": None
            }
        
        # Basic M3U8 validation
        content_type = response.headers.get("Content-Type", "").lower()
        content = response.text[:1024]  # Limit to first 1KB for efficiency
        is_m3u8 = content_type in ["application/x-mpegurl", "application/vnd.apple.mpegurl"] or content.startswith("#EXTM3U")
        segment_count = len(re.findall(r'\.ts\b', content)) if is_m3u8 else 0
        
        status = "Live" if is_m3u8 and segment_count > 0 else "Live (No segments)" if is_m3u8 else "Live (Not M3U8)"
        return {
            "channel": stream.get("name", "Unknown"),
            "url": stream["url"],
            "status": f"{status} (Segments: {segment_count})",
            "group": stream.get("group", "N/A"),
            "logo": stream.get("logo", "N/A"),
            "error": None
        }
    
    except requests.RequestException as e:
        return {
            "channel": stream.get("name", "Unknown"),
            "url": stream["url"],
            "status": "Down",
            "group": stream.get("group", "N/A"),
            "logo": stream.get("logo", "N/A"),
            "error": str(e)
        }

def main(playlist_url, output_file, max_workers=10, timeout=10):
    """Main function to process the M3U playlist."""
    logger.info(f"Fetching playlist from {playlist_url}")
    try:
        response = requests.get(playlist_url, headers=default_headers, timeout=timeout)
        if response.status_code != 200:
            logger.error(f"Failed to fetch playlist: Status {response.status_code}")
            return
        
        streams = parse_m3u(response.text)
        if not streams:
            logger.error("No valid streams found in the M3U playlist.")
            return
        
        logger.info(f"Found {len(streams)} streams to check.")
        results = []
        
        # Check URLs in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_stream = {executor.submit(check_url, stream, timeout): stream for stream in streams}
            for i, future in enumerate(concurrent.futures.as_completed(future_to_stream), 1):
                result = future.result()
                results.append(result)
                logger.info(f"Checked {i}/{len(streams)}: {result['channel']} - {result['status']}")
        
        # Format and save results
        output_lines = []
        for result in results:
            output_lines.append(
                f"Channel: {result['channel']}\n"
                f"URL: {result['url']}\n"
                f"Status: {result['status']}\n"
                f"Group: {result['group']}\n"
                f"Logo: {result['logo']}\n"
                f"Error: {result['error'] or 'None'}\n"
                f"---"
            )
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))
        logger.info(f"Results saved to {output_file}")
        
    except requests.RequestException as e:
        logger.error(f"Error fetching playlist: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check M3U playlist streams.")
    parser.add_argument("--url", default="https://raw.githubusercontent.com/moajzim47/moajzimofficials/9902d23e34d9c7a747ff2846d78e1c4151252df9/It's-Unique-Hex-MoAj-STREAMZ-PLAY.M3U",
                        help="URL of the M3U playlist")
    parser.add_argument("--output", default="m3u_playlist_check_results.txt",
                        help="Output file for results")
    parser.add_argument("--workers", type=int, default=10,
                        help="Number of concurrent workers")
    parser.add_argument("--timeout", type=int, default=10,
                        help="Timeout for HTTP requests in seconds")
    
    args = parser.parse_args()
    main(args.url, args.output, args.workers, args.timeout)
