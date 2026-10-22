import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path

BASE = "https://www.virginradio.it/podcast/il-cavaliere-nero/"

# Copertina generale del podcast: nuova immagine
IMAGE = "https://img-api.cloud.mediaset.net/api/images/rd/v1/ita/aHR0cHM6Ly93d3cudmlyZ2lucmFkaW8uaXQvd3AtY29udGVudC91cGxvYWRzLzIwMjUvMTEvVmlyZ2luX0RKX0FudG9uZWxsby1QaXJvc29fRHItRmVlbGdvb2RfQWxsZWdyZXR0aS0xNzMwNzIzNzUwMTY4cG5nLS5wbmc/-/0/0?r=917706321d39d77fc139f51276147c12"

# Immagine originale del Cavaliere Nero, da mantenere per gli episodi
EPISODE_IMAGE = "https://img-api.cloud.mediaset.net/api/images/rd/v1/ita/aHR0cHM6Ly93d3cudmlyZ2lucmFkaW8uaXQvd3AtY29udGVudC91cGxvYWRzLzIwMjUvMTEvMjAyMC0wNS0xNF8xMF8xM18yNF8xNTM4NzI4NTE4MTkwLXBuZy0xNTg5NDQ0ODM5NDUycG5nLWlsX2NhdmFsaWVyZV9uZXJvLTEyMC5wbmc/-/0/0?r=51a1619f77c73c16ac8878115fd82337"

OUT = Path(__file__).resolve().parent / "feed.xml"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", errors="replace")


def get_episodes():
    episodes = {}

    for page in range(1, 4):
        url = f"{BASE}?current_page={page}&order=desc"

        try:
            html = fetch(url)
        except Exception as e:
            print(f"Errore pagina {page}: {e}")
            break

        links = set(re.findall(
            r'https://www\.virginradio\.it/podcast_item/[^"\?#]+/',
            html
        ))

        if not links:
            break

        new = 0

        for link in links:
            if link in episodes:
                continue

            try:
                doc = fetch(link)

                title_match = re.search(
                    r"<title>(.*?)</title>", doc, re.I | re.S
                )
                audio_match = re.search(
                    r'<audio[^>]+src=["\']([^"\']+)', doc, re.I
                )

                if not title_match or not audio_match:
                    print("Dati mancanti:", link)
                    continue

                title = unescape(
                    re.sub(r"\s+", " ", title_match.group(1))
                ).strip()
                audio = unescape(audio_match.group(1))

                if not audio.startswith("https://"):
                    continue

                episodes[link] = (title, audio)
                new += 1

                print("Trovata:", title)
                time.sleep(0.15)

            except Exception as e:
                print("Errore episodio:", link, e)

        print(f"Pagina {page}: {new} nuovi episodi")

        if new == 0 and page > 1:
            break

    return episodes


episodes = get_episodes()

ET.register_namespace(
    "itunes",
    "http://www.itunes.com/dtds/podcast-1.0.dtd"
)

rss = ET.Element("rss", {"version": "2.0"})
channel = ET.SubElement(rss, "channel")

ET.SubElement(channel, "title").text = "Il Cavaliere Nero – Virgin Radio"
ET.SubElement(channel, "link").text = BASE
ET.SubElement(channel, "description").text = (
    "Episodi de Il Cavaliere Nero pubblicati da Virgin Radio."
)
ET.SubElement(channel, "language").text = "it-IT"

# Copertina generale del feed
image = ET.SubElement(channel, "image")
ET.SubElement(image, "url").text = IMAGE
ET.SubElement(image, "title").text = "Il Cavaliere Nero – Virgin Radio"
ET.SubElement(image, "link").text = BASE

ET.SubElement(
    channel,
    "{http://www.itunes.com/dtds/podcast-1.0.dtd}image",
    {"href": IMAGE}
)

ET.SubElement(channel, "lastBuildDate").text = format_datetime(
    datetime.now().astimezone()
)

mesi = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12
}


def data_puntata(item):
    titolo = item[1][0].lower()

    m = re.search(
        r"(\d{1,2})\s+([a-zàèéìòù]+)\s+(\d{4})",
        titolo
    )

    if not m:
        return datetime.min

    giorno, mese, anno = m.groups()
    return datetime(int(anno), mesi[mese], int(giorno))


for link, (title, audio) in sorted(
    episodes.items(),
    key=data_puntata,
    reverse=True
):
    item = ET.SubElement(channel, "item")

    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "link").text = link
    ET.SubElement(
        item,
        "guid",
        {"isPermaLink": "true"}
    ).text = link
    ET.SubElement(item, "description").text = title

    data = data_puntata((link, (title, audio)))

    ET.SubElement(item, "pubDate").text = format_datetime(
        data.astimezone()
    )

    ET.SubElement(item, "enclosure", {
        "url": audio,
        "length": "0",
        "type": "audio/mpeg"
    })

    # Immagine specifica della singola puntata
    ET.SubElement(
        item,
        "{http://www.itunes.com/dtds/podcast-1.0.dtd}image",
        {"href": EPISODE_IMAGE}
    )

ET.indent(rss, space="  ")

ET.ElementTree(rss).write(
    OUT,
    encoding="utf-8",
    xml_declaration=True
)

print(f"\nFeed creato: {OUT}")
print(f"Episodi inseriti: {len(episodes)}")
