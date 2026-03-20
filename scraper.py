import requests
import time
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("distrotv_scraper")

class DistroTVScraper:
    def __init__(self):
        self.feed_url = "https://tv.jsrdn.com/tv_v5/getfeed.php"
        self.headers = {
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; AFTT Build/STT9.221129.002) GTV/AFTT DistroTV/2.0.9'
        }
        self.referrer = "https://www.distro.tv/"
        self.epg_url = "https://raw.githubusercontent.com/BuddyChewChew/distrotv/refs/heads/main/distrotv_epg.xml"  # Static, reliable

    def fetch_channels(self):
        try:
            logger.info("Fetching DistroTV feed...")
            ts = int(time.time())
            resp = requests.get(f"{self.feed_url}?t={ts}", headers=self.headers, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            channels = []
            for raw_id, ch_data in data.items():
                if not isinstance(ch_data, dict):
                    continue
                if ch_data.get("type") != "live":
                    continue

                try:
                    seasons = ch_data.get("seasons", [])
                    if not seasons:
                        continue
                    episodes = seasons[0].get("episodes", [])
                    if not episodes:
                        continue
                    content = episodes[0].get("content", {})
                    stream_url = content.get("url", "")
                    if not stream_url or "m3u8" not in stream_url.lower():
                        continue

                    title = ch_data.get("title", "").strip()
                    if not title:
                        continue

                    logo = ch_data.get("img_logo") or ch_data.get("img_poster", "")
                    genre = ch_data.get("genre", "DistroTV").replace(",", " / ")

                    channels.append({
                        'id': f"distrotv.{raw_id}",
                        'raw_id': raw_id,
                        'name': title,
                        'stream_url': stream_url,  # Full URL with ads params!
                        'logo': logo,
                        'group': genre,
                        'description': ch_data.get("description", "").strip()
                    })
                except Exception as e:
                    logger.debug(f"Skipped {raw_id}: {e}")
                    continue

            logger.info(f"Parsed {len(channels)} live channels.")
            return sorted(channels, key=lambda x: x['name'].lower())
        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            return []

    def generate_m3u(self, channels):
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        m3u_lines = [
            "#EXTM3U",
            f"#EXT-X-VERSION:3",
            "#EXT-X-ALLOW-CACHE:YES",
            "#EXT-X-TARGETDURATION:10",
            f'x-tvg-url="{self.epg_url}"',
            f"# Generated USA - Updated: {now} UTC"
        ]

        for ch in channels:
            inf = (
                f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-logo="{ch["logo"]}" '
                f'group-title="{ch["group"]}" '
                f'http-referrer="{self.referrer}" '
                f'http-origin="{self.referrer}" '
                f'http-user-agent="{self.headers["User-Agent"]}",{ch["name"]}'
            )
            m3u_lines.extend([
                inf,
                f'#EXTVLCOPT:http-referrer={self.referrer}',
                f'#EXTVLCOPT:http-origin={self.referrer}',
                f'#EXTVLCOPT:http-user-agent={self.headers["User-Agent"]}',
                ch["stream_url"]
            ])

        return "\n".join(m3u_lines)

if __name__ == "__main__":
    scraper = DistroTVScraper()
    channels = scraper.fetch_channels()

    if channels:
        # Write M3U
        with open("distrotv.m3u", "w", encoding="utf-8") as f:
            f.write(scraper.generate_m3u(channels))
        logger.info("distrotv.m3u written")

        # Optional: JSON dump for debug
        with open("distrotv_channels.json", "w", encoding="utf-8") as f:
            json.dump(channels, f, indent=4)
        logger.info("distrotv_channels.json written")

        # No EPG generation needed - using static reference
        # If you want an empty/placeholder distrotv_epg.xml:
        with open("distrotv_epg.xml", "w", encoding="utf-8") as f:
            f.write('<!-- Using external EPG: ' + scraper.epg_url + ' -->')
        logger.info("Placeholder distrotv_epg.xml written")

    else:
        logger.warning("No channels fetched - check network/feed")
