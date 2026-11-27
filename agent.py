"""Wohnungs-Agent: scannt WG-Gesucht + Kleinanzeigen, filtert, schickt Treffer per Telegram."""
import html
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import config as C

STATE_FILE = Path(__file__).with_name("seen.json")
TEMPLATE_FILE = Path(__file__).with_name("vorlage.txt")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"})
MONATE = {m: i for i, m in enumerate(["januar", "februar", "märz", "april", "mai", "juni", "juli", "august",
                                      "september", "oktober", "november", "dezember"], 1)}


@dataclass
class Inserat:
    quelle: str
    id: str
    url: str
    titel: str = ""
    preis: int | None = None
    groesse: str = ""
    art: str = ""                 # "1-Zimmer-Wohnung" | "WG-Zimmer"
    wg_personen: int | None = None
    ort: str = ""
    von: date | None = None
    bis: date | None = None
    kontakt: str = ""
    hinweise: list = field(default_factory=list)


# ---------- Helfer ----------
def get(url):
    time.sleep(C.PAUSE_SEKUNDEN)
    r = S.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


def d(s):
    return datetime.strptime(s, "%d.%m.%Y").date()


def ort_ok(ort, plz=None):
    if plz and plz in C.PLZ:
        return True
    o = ort.lower()
    return any(re.search(rf"(^|[\s\-/]){re.escape(s)}($|[\s\-/,])", o) for s in C.STADTTEILE)


def zeitraum_ok(i: Inserat):
    """True/False; fügt Hinweise hinzu."""
    if i.von is None:
        i.hinweise.append("⚠️ Einzugsdatum prüfen")
    elif not (C.EINZUG_FRUEHESTENS <= i.von <= C.EINZUG_SPAETESTENS):
        return False
    if i.bis is None:
        if not C.UNBEFRISTET_OK:
            return False
        if not any("Enddatum" in h for h in i.hinweise):
            i.hinweise.append("unbefristet (2. Wahl) oder Enddatum prüfen")
    elif i.bis < C.AUSZUG_FRUEHESTENS:
        return False
    return True


def vorname(kontakt):
    k = (kontakt or "").strip()
    if not k or re.search(r"gmbh|ug\b|ag\b|immobil|team|the |verwaltung|wohnen|living|apartment", k, re.I):
        return ""
    first = k.split()[0].strip(".")
    return first if len(first) > 1 else ""


# ---------- WG-Gesucht ----------
WGG_LISTEN = {
    "1-Zimmer-Wohnung": "https://www.wg-gesucht.de/1-zimmer-wohnungen-in-Muenchen.90.1.1.0.html"
                        "?offer_filter=1&city_id=90&noDeact=1&categories%5B%5D=1&rMax={max}&fur=1&sort_column=0&sort_order=0",
    "WG-Zimmer": "https://www.wg-gesucht.de/wg-zimmer-in-Muenchen.90.0.1.0.html"
                 "?offer_filter=1&city_id=90&noDeact=1&categories%5B%5D=0&rMax={max}&fur=1&sort_column=0&sort_order=0",
}


def wgg_liste():
    out = []
    for art, url in WGG_LISTEN.items():
        soup = BeautifulSoup(get(url.format(max=C.MAX_WARMMIETE)), "html.parser")
        for c in soup.select(".offer_list_item[data-id]"):
            t = txt(c)
            href = c.get("href") or (c.select_one("a[href*='.html']") or {}).get("href", "")
            i = Inserat("WG-Gesucht", "wgg-" + c["data-id"], "https://www.wg-gesucht.de" + href if href.startswith("/") else href, art=art)
            i.titel = txt(c.select_one(".card-offer-title-text")) or c.get("aria-label", "")
            if m := re.search(r"(\d[\d.]*)\s*€\s*/\s*Monat", t):
                i.preis = int(m.group(1).replace(".", ""))
            if m := re.search(r"([\d,]+)\s*m²", t):
                i.groesse = m.group(1) + " m²"
            if m := re.search(r"(\d+)er WG", t):
                i.wg_personen = int(m.group(1))
            if m := re.search(r"\bmap\s+(.+?)\s+location_on\s+(.+?)\s+calendar_today", t):
                i.ort = m.group(1).replace("München ", "") + " · " + m.group(2)
            if m := re.search(r"calendar_today\s+(\d\d\.\d\d\.\d{4})(?:\s*-\s*(\d\d\.\d\d\.\d{4}))?", t):
                i.von = d(m.group(1))
                i.bis = d(m.group(2)) if m.group(2) else None
            i.kontakt = txt(c.select_one(".user-name"))
            out.append(i)
        if not soup.select(".offer_list_item[data-id]"):
            raise RuntimeError(f"0 Inserate für {art} – evtl. blockiert/Captcha")
    return out


def wgg_detail(i: Inserat):
    t = txt(BeautifulSoup(get(i.url), "html.parser").body).lower()
    if m := re.search(r"gesamtmiete\s*:?\s*(\d[\d.]*)\s*€", t):
        i.preis = int(m.group(1).replace(".", ""))
    return t


# ---------- Kleinanzeigen ----------
KA_LISTE = "https://www.kleinanzeigen.de/s-auf-zeit-wg/muenchen/anzeige:angebote/preis::{max}/c199l6411"


def ka_liste():
    soup = BeautifulSoup(get(KA_LISTE.format(max=C.MAX_WARMMIETE)), "html.parser")
    out = []
    for a in soup.select("article[data-adid]"):
        t = txt(a)
        href = a.get("data-href") or (a.select_one("a[href*='/s-anzeige/']") or {}).get("href", "")
        i = Inserat("Kleinanzeigen", "ka-" + a["data-adid"], "https://www.kleinanzeigen.de" + href)
        i.titel = txt(a.select_one("h2")) or href.split("/")[-2].replace("-", " ")
        if m := re.search(r"\b(\d{5})\s+([A-ZÄÖÜ][\wäöüß\-]+(?:\s[a-z]{2,3}\s[A-ZÄÖÜ][\wäöüß]+)?)", t):
            i.ort = f"{m.group(1)} {m.group(2)}"
        prices = re.findall(r"(\d[\d.]*)\s*€", t)
        if prices:
            i.preis = int(prices[-1].replace(".", ""))
        if m := re.search(r"([\d,]+)\s*m²", t):
            i.groesse = m.group(1) + " m²"
        out.append(i)
    return out


def ka_monat(s):
    s = s.lower()
    if m := re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s):
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    if m := re.search(r"(" + "|".join(MONATE) + r")\s+(\d{4})", s):
        return date(int(m.group(2)), MONATE[m.group(1)], 1)
    return None


def ka_detail(i: Inserat):
    soup = BeautifulSoup(get(i.url), "html.parser")
    details = {}
    keys = ["Art der Unterkunft", "Mietart", "Verfügbar ab", "Verfügbar bis", "Zimmer", "Wohnfläche",
            "Warmmiete", "Kaltmiete", "Nebenkosten"]
    lis = [txt(li) for li in soup.find_all("li")]
    for t in lis:
        for k in keys:
            if t.startswith(k) and len(t) < 120 and k.lower() not in details:
                details[k.lower()] = t[len(k):].strip(" :")
    tags = " ".join(t for t in lis if len(t) < 40).lower()
    desc = txt(soup.select_one("#viewad-description-text"))
    i.titel = txt(soup.select_one("#viewad-title")) or i.titel
    page = txt(soup.body)
    m = re.search(r"\b[A-ZÄÖÜ]\s+([A-ZÄÖÜ][a-zäöüß]+)[^|]{0,20}?\s+Privater Nutzer", page)
    i.kontakt = m.group(1) if m else ""
    if w := re.search(r"(\d[\d.]*)", details.get("warmmiete", "")):
        i.preis = int(w.group(1).replace(".", ""))
    art = details.get("art der unterkunft", "").lower()
    if "geteilt" in art or "shared" in art:
        return None
    i.art = "WG-Zimmer" if "zimmer" in art and "gesamte" not in art else "1-Zimmer-Wohnung"
    if i.art == "1-Zimmer-Wohnung":
        z = details.get("zimmer", "1").replace(",", ".")
        try:
            if float(z) > 1.5:
                return None
        except ValueError:
            pass
    if "möbliert" not in tags and "möbliert" not in desc.lower() and "furnished" not in desc.lower():
        return None
    i.von = ka_monat(details.get("verfügbar ab", ""))
    if i.von and i.von.day == 1 and re.search(r"[a-zä]+\s+\d{4}", details.get("verfügbar ab", "").lower()):
        # nur Monat angegeben -> Januar 2027 zählt als passend
        if (i.von.year, i.von.month) == (C.EINZUG_FRUEHESTENS.year, C.EINZUG_FRUEHESTENS.month):
            i.von = C.EINZUG_FRUEHESTENS
            i.hinweise.append("Einzug nur als Monat angegeben")
    mietart = details.get("mietart", "").lower()
    bis = details.get("verfügbar bis") or details.get("frei bis")
    i.bis = ka_monat(bis) if bis else None
    if i.bis is None and "befristet" in mietart and "unbefristet" not in mietart:
        i.hinweise.append("befristet – Enddatum im Text prüfen")
    if m := re.search(r"(\d+)\s*er[\s-]?wg", desc.lower() + " " + i.titel.lower()):
        i.wg_personen = int(m.group(1))
    if "warmmiete" not in details and not re.search(r"warm|inkl|gesamtmiete|all.?in", desc.lower()):
        i.hinweise.append("⚠️ prüfen, ob Preis warm ist")
    return (desc + " " + i.titel).lower()


# ---------- Telegram ----------
def anfrage(i: Inserat):
    vorlage = os.environ.get("ANFRAGE_VORLAGE") or TEMPLATE_FILE.read_text(encoding="utf-8")
    name = vorname(i.kontakt)
    objekt = "deine Wohnung" if i.art == "1-Zimmer-Wohnung" else "euer WG-Zimmer"
    if not name:
        objekt = "die Wohnung" if i.art == "1-Zimmer-Wohnung" else "das WG-Zimmer"
    ort = i.ort.split(" · ")[0]
    ort = re.sub(r"^\d{5}\s+", "", ort)
    ort = {"Au": "der Au", "Au-Haidhausen": "Haidhausen"}.get(ort, ort)
    return (vorlage.replace("{gruss}", f"Hallo {name}!" if name else "Hallo!")
                   .replace("{objekt}", objekt)
                   .replace("{ort}", ort or "München")).strip()


def telegram(text):
    tok, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("---- (kein Telegram konfiguriert) ----\n" + text)
        return
    r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", timeout=30,
                      json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})
    if not r.ok:
        print("Telegram-Fehler:", r.status_code, r.text[:300])


def melde(i: Inserat):
    e = html.escape
    zr = f"{i.von:%d.%m.%Y}" if i.von else "?"
    zr += f" – {i.bis:%d.%m.%Y}" if i.bis else " – unbefristet/?"
    art = i.art + (f" ({i.wg_personen}er WG)" if i.wg_personen else "")
    lines = [f"🏠 <b>{e(i.titel[:120])}</b>",
             f"💶 {i.preis or '?'} € · {e(i.groesse)} · {e(art)}",
             f"📍 {e(i.ort)}", f"📅 {zr}", f"🔎 {i.quelle}"]
    if i.hinweise:
        lines.append("ℹ️ " + e("; ".join(i.hinweise)))
    lines.append(f'👉 <a href="{e(i.url)}">Zum Inserat</a>')
    telegram("\n".join(lines))
    telegram(f"<pre>{e(anfrage(i))}</pre>")


# ---------- Ablauf ----------
def main():
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {"seen": [], "errors": {}}
    seen = set(state["seen"])
    details_left = C.MAX_DETAILSEITEN_PRO_LAUF
    treffer = 0

    for name, liste, detail in [("WG-Gesucht", wgg_liste, wgg_detail), ("Kleinanzeigen", ka_liste, ka_detail)]:
        try:
            items = liste()
            print(f"{name}: {len(items)} Inserate gelesen")
            state["errors"][name] = 0
        except Exception as ex:  # noqa: BLE001
            n = state["errors"].get(name, 0) + 1
            state["errors"][name] = n
            print(f"{name}: Fehler {ex}")
            if n == 6:  # ~1 Stunde lang kaputt
                telegram(f"⚠️ Wohnungs-Agent: {name} liefert seit ca. 1 Stunde Fehler ({html.escape(str(ex)[:150])}).")
            continue

        for i in items:
            if i.id in seen:
                continue
            # Vorfilter ohne Detailseite
            plz = i.ort[:5] if i.ort[:5].isdigit() else None
            if i.preis and i.preis > C.MAX_WARMMIETE:
                seen.add(i.id); continue
            if i.ort and not ort_ok(i.ort, plz):
                seen.add(i.id); continue
            if i.quelle == "WG-Gesucht" and not zeitraum_ok(i):
                seen.add(i.id); continue
            if details_left <= 0:
                break  # nächster Lauf macht weiter (nicht als gesehen markiert)
            details_left -= 1
            try:
                text = detail(i)
            except Exception as ex:  # noqa: BLE001
                print("Detailfehler", i.url, ex)
                continue
            seen.add(i.id)
            if text is None:
                continue
            if i.quelle == "Kleinanzeigen" and not zeitraum_ok(i):
                continue
            if i.preis and i.preis > C.MAX_WARMMIETE:
                continue
            if i.art == "WG-Zimmer":
                if i.wg_personen and i.wg_personen > C.WG_MAX_PERSONEN:
                    continue
                if not i.wg_personen:
                    i.hinweise.append("WG-Größe prüfen")
                if not any(k in text for k in C.WG_STIL_KEYWORDS):
                    continue
            melde(i)
            treffer += 1

    print(f"Fertig: {treffer} Treffer gefunden")
    if not os.environ.get("TELEGRAM_TOKEN"):
        print("Testmodus (kein Telegram): gesehene Inserate werden nicht gespeichert.")
        return
    state["seen"] = list(seen)
    STATE_FILE.write_text(json.dumps(state, indent=0))


if __name__ == "__main__":
    sys.exit(main())
