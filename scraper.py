import requests
import time
import json
import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("distrotv_scraper")

class DistroTVScraper:
    def __init__(self):
        self.feed_url = "https://tv.jsrdn.com/tv_v5/getfeed.php"
        self.epg_url = "https://tv.jsrdn.com/epg/query.php"
        self.headers = {
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; AFTT Build/STT9.221129.002) GTV/AFTT DistroTV/2.0.9'
        }

    def fetch_channels(self) -> List[Dict[str, Any]]:
        """Scrapes the live channel list from DistroTV"""
        try:
            logger.info("Fetching live channel feed...")
            response = requests.get(self.feed_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            shows = data.get("shows", {})
            channels = []
            
            for ch_key, ch_data in shows.items():
                if ch_data.get("type") != "live":
                    continue
                    
                try:
                    # Navigate nested seasons -> episodes -> content -> url
                    seasons = ch_data.get("seasons", [])
                    if not seasons: continue
                    episodes = seasons[0].get("episodes", [])
                    if not episodes: continue
                    content = episodes[0].get("content", {})
                    stream_url = content.get("url", "")
                    if not stream_url: continue
                    
                    clean_url = stream_url.split('?', 1)[0]
                    channel_name = ch_data.get("name", "")
                    title = ch_data.get("title", "").strip()
                    
                    channels.append({
                        'id': f"distrotv-{channel_name}",
                        'raw_id': channel_name, # Needed for EPG query
                        'name': title,
                        'stream_url': clean_url,
                        'logo': ch_data.get("img_logo", ""),
                        'group': ch_data.get("genre", "DistroTV"),
                        'description': ch_data.get("description", "").strip()
                    })
                except Exception:
                    continue
            
            logger.info(f"Found {len(channels)} live channels.")
            return channels
        except Exception as e:
            logger.error(f"Failed to fetch feed: {e}")
            return []

    def generate_m3u(self, channels: List[Dict[str, Any]]):
        """Creates the M3U8 playlist content"""
        m3u = ["#EXTM3U"]
        for ch in sorted(channels, key=lambda x: x['name'].lower()):
            metadata = f'tvg-id="{ch["id"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}"'
            m3u.append(f'#EXTINF:-1 {metadata},{ch["name"]}')
            m3u.append(ch["stream_url"])
        return "\n".join(m3u)

    def generate_epg_xml(self, channels: List[Dict[str, Any]]):
        """Fetches program data and builds the XMLTV file"""
        root = ET.Element("tv", {
            "generator-info-name": "DistroTV-Scraper",
            "generator-info-url": "https://github.com/BuddyChewChew/distrotv"
        })

        # Add channel headers
        for ch in channels:
            c_node = ET.SubElement(root, "channel", id=ch['id'])
            ET.SubElement(c_node, "display-name").text = ch['name']
            ET.SubElement(c_node, "icon", src=ch['logo'])

        # Fetch programs for each channel
        logger.info("Fetching EPG listings for channels...")
        for ch in channels:
            try:
                params = {'ch': ch['raw_id']}
                resp = requests.get(self.epg_url, params=params, headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    listings = resp.json().get('listings', [])
                    for prog in listings:
                        start = datetime.fromtimestamp(int(prog['start'])).strftime("%Y%m%d%H%M%S +0000")
                        stop = datetime.fromtimestamp(int(prog['end'])).strftime("%Y%m%d%H%M%S +0000")
                        
                        p_node = ET.SubElement(root, "programme", {
                            "start": start,
                            "stop": stop,
                            "channel": ch['id']
                        })
                        ET.SubElement(p_node, "title", lang="en").text = prog.get('title', 'No Title')
                        ET.SubElement(p_node, "desc", lang="en").text = prog.get('description', '')
            except Exception:
                continue

        return minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")

if __name__ == "__main__":
    scraper = DistroTVScraper()
    
    # 1. Get the channels
    channels = scraper.fetch_channels()
    
    if channels:
        # 2. Save JSON
        with open("distrotv_channels.json", "w", encoding="utf-8") as f:
            json.dump(channels, f, indent=4)
            
        # 3. Save M3U
        with open("distrotv.m3u", "w", encoding="utf-8") as f:
            f.write(scraper.generate_m3u(channels))
            
        # 4. Save EPG
        with open("distrotv_epg.xml", "w", encoding="utf-8") as f:
            f.write(scraper.generate_epg_xml(channels))
            
        logger.info("All files (JSON, M3U, XML) updated successfully.")
    else:
        logger.error("No channels found. Files were not updated.")
