import json
import requests
import logging
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("distrotv_epg")

def format_xmltv_date(dt):
    """Formats datetime to XMLTV standard: YYYYMMDDHHMMSS +0000"""
    return dt.strftime("%Y%m%d%H%M%S +0000")

def generate_epg():
    # 1. Load your scraped channels
    try:
        with open('distrotv_channels.json', 'r') as f:
            channels = json.json.load(f)
    except FileNotFoundError:
        logger.error("distrotv_channels.json not found. Run scraper.py first.")
        return

    # Create root element
    root = ET.Element("tv", {
        "generator-info-name": "DistroTV-Scraper",
        "generator-info-url": "https://github.com/BuddyChewChew/distrotv"
    })

    # 2. Add Channels to XML
    for ch in channels:
        channel_node = ET.SubElement(root, "channel", id=ch['id'])
        ET.SubElement(channel_node, "display-name").text = ch['name']
        ET.SubElement(channel_node, "icon", src=ch['logo'])

    # 3. Fetch Program Data
    # DistroTV API usually requires a channel ID or name for the query.php endpoint
    # Note: DistroTV EPG API is often date-range based.
    epg_url = "https://tv.jsrdn.com/epg/query.php"
    headers = {'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; AFTT Build/STT9.221129.002) GTV/AFTT DistroTV/2.0.9'}

    logger.info(f"Generating EPG for {len(channels)} channels...")

    for ch in channels:
        try:
            # Most DistroTV implementations query by channel name or ID
            params = {'ch': ch['id'].replace('distrotv-', '')}
            resp = requests.get(epg_url, params=params, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                programs = resp.json().get('listings', [])
                for prog in programs:
                    # Parse DistroTV timestamps (usually UTC seconds)
                    start_ts = datetime.fromtimestamp(int(prog['start']))
                    end_ts = datetime.fromtimestamp(int(prog['end']))

                    programme_node = ET.SubElement(root, "programme", {
                        "start": format_xmltv_date(start_ts),
                        "stop": format_xmltv_date(end_ts),
                        "channel": ch['id']
                    })
                    ET.SubElement(programme_node, "title", lang="en").text = prog.get('title', 'No Title')
                    ET.SubElement(programme_node, "desc", lang="en").text = prog.get('description', '')
        except Exception as e:
            logger.debug(f"Could not fetch EPG for {ch['name']}: {e}")

    # 4. Save to File
    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    with open("distrotv_epg.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)
    logger.info("Successfully saved distrotv_epg.xml")

if __name__ == "__main__":
    generate_epg()
