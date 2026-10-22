import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from datetime import datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

BASE = "https://www.virginradio.it/podcast/il-cavaliere-nero/"

# Copertina generale del podcast: nuova immagine
IMAGE = "https://img-api.cloud.mediaset.net/api/images/rd/v1/ita/aHR0cHM6Ly93d3cudmlyZ2lucmFkaW8uaXQvd3AtY29udGVudC91cGxvYWRzLzIwMjUvMTEvVmlyZ2luX0RKX0FudG9uZWxsby1QaXJvc29fRHItRmVlbGdvb2RfQWxsZWdyZXR0aS0xNzMwNzIzNzUwMTY4cG5nLS5wbmc/-/0/0?r=917706321d39d77fc139f51276147c12"

# Immagine originale del Cavaliere Nero per gli episodi
EPISODE_IMAGE = "https://img-api.cloud.mediaset.net/api/images/rd/v1/ita/aHR0cHM6Ly93d3cudmlyZ2lucmFkaW8uaXQvd3AtY29udGVudC91cGxvYWRzLzIwMjUvMTEvMjAyMC0wNS0xNF8xMF8xM18yNF8xNTM4NzI4NTE4MTkwLXBuZy0xNTg5NDQ0ODM5NDUycG5nLWlsX2NhdmFsaWVyZV9uZXJvLTEyMC5wbmc/-/0/0?r=51a1619f77c73c16ac8878115fd82337"

OUT = Path(__file__).resolve().parent / "feed.xml"
HEADERS = {"User-Agent": "Mozilla/5.0"}

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
    "dicembre": 12,
}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", errors="replace")


def get_episodes():
    episodes = {}

    # Manteniamo l'ordine di pubblicazione mostrato dal sito.
    for page in range(1, 4):
        url = f"{BASE}?current_page={page}&order=desc"

        try:
            html = fetch(url)
        except Exception as e:
            print(f"Errore pagina {page}: {e}")
            break

        links = list(dict.fromkeys(re.findall(
            r'https://www\.virginradio\.it/podcast_item/[^"?#]+/',
            html
        )))

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


def estrai_data(titolo):
    """Restituisce giorno, mese e anno; l'anno può mancare."""
    titolo = titolo.lower()

    match = re.search(
        r"\b(\d{1,2})\s+([a-zàèéìòù]+)"
        r"(?:\s+(\d{4}))?\b",
        titolo
    )

    if not match:
        return None

    giorno, nome_mese, anno = match.groups()

    if nome_mese not in mesi:
        return None

    try:
        return (
            int(giorno),
            mesi[nome_mese],
            int(anno) if anno else None
        )
    except ValueError:
        return None


def calcola_date(episodes):
    """
    1. Conserva le date complete.
    2. Se manca l'anno, lo ricava dalle date note più vicine.
    3. Se manca completamente la data, usa la data della puntata
       cronologicamente precedente più un giorno.
    """
    elementi = list(episodes.items())
    oggi = datetime.now().date()

    # Prima individuiamo tutte le date complete.
    date_complete = []

    for indice, (link, (titolo, audio)) in enumerate(elementi):
        parti = estrai_data(titolo)

        if parti and parti[2] is not None:
            giorno, mese, anno = parti

            try:
                data = datetime(anno, mese, giorno).date()
                date_complete.append((indice, data))
            except ValueError:
                print("Data non valida nel titolo:", titolo)

    date_calcolate = [None] * len(elementi)

    # Le date complete non vengono modificate.
    for indice, data in date_complete:
        date_calcolate[indice] = data

    # Completiamo le date con giorno e mese ma senza anno.
    for indice, (link, (titolo, audio)) in enumerate(elementi):
        if date_calcolate[indice] is not None:
            continue

        parti = estrai_data(titolo)

        if not parti:
            continue

        giorno, mese, anno = parti

        if anno is not None:
            continue

        anni_candidati = {
            data.year + scarto
            for _, data in date_complete
            for scarto in (-1, 0, 1)
            if 1 <= data.year + scarto <= 9999
        }

        if not anni_candidati:
            anni_candidati = {oggi.year}

        candidate = []

        for anno_candidato in anni_candidati:
            try:
                candidate.append(
                    datetime(anno_candidato, mese, giorno).date()
                )
            except ValueError:
                pass

        if not candidate:
            print("Impossibile ricostruire la data:", titolo)
            continue

        if date_complete:
            # Scegliamo l'anno che colloca la puntata più vicino
            # alle date complete già trovate sul sito.
            data_scelta = min(
                candidate,
                key=lambda candidata: min(
                    abs((candidata - nota).days)
                    for _, nota in date_complete
                )
            )
        else:
            data_scelta = min(
                candidate,
                key=lambda candidata: abs((candidata - oggi).days)
            )

        date_calcolate[indice] = data_scelta
        print(f"Anno ricostruito: {titolo} -> {data_scelta}")

    # Il sito mostra le puntate dalla più recente alla più vecchia.
    # Procediamo al contrario, dalla più vecchia alla più recente.
    for indice in range(len(elementi) - 1, -1, -1):
        if date_calcolate[indice] is not None:
            continue

        data_precedente = None

        # Cerchiamo la puntata cronologicamente precedente.
        for j in range(indice + 1, len(elementi)):
            if date_calcolate[j] is not None:
                data_precedente = date_calcolate[j]
                break

        if data_precedente is not None:
            data_calcolate[indice] = data_precedente + timedelta(days=1)
            print(
                f"Data ricostruita: {elementi[indice][1][0]} "
                f"-> {date_calcolate[indice]} "
                "(giorno successivo alla puntata precedente)"
            )
        else:
            # Se non esiste alcuna data di riferimento, usiamo
            # una data valida e segnaliamo il caso.
            data_calcolate[indice] = oggi
            print(
                "ATTENZIONE: nessuna data di riferimento per",
                elementi[indice][1][0],
                "- usata la data odierna."
            )

    return {
        link: data_calcolate[indice]
        for indice, (link, _) in enumerate(elementi)
    }


episodes = get_episodes()
date_episodi = calcola_date(episodes)

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

# Ordiniamo le puntate dalla più recente alla più vecchia.
episodi_ordinati = sorted(
    episodes.items(),
    key=lambda elemento: date_episodi[elemento[0]],
    reverse=True
)

for link, (title, audio) in episodi_ordinati:
    item = ET.SubElement(channel, "item")

    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "link").text = link

    ET.SubElement(
        item,
        "guid",
        {"isPermaLink": "true"}
    ).text = link

    ET.SubElement(item, "description").text = title

    data = datetime.combine(
        date_episodi[link],
        datetime.min.time()
    ).astimezone()

    ET.SubElement(item, "pubDate").text = format_datetime(data)

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
