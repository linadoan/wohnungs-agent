"""Alle Suchkriterien an einem Ort. Hier anpassen, der Rest läuft automatisch."""
from datetime import date

MAX_WARMMIETE = 900                     # € inkl. Nebenkosten
EINZUG_FRUEHESTENS = date(2027, 1, 1)
FREI_AB_FRUEHESTENS = date(2026, 12, 1)   # Angebote ab Dez. auch melden (Einzug 01.01. anfragen)
EINZUG_SPAETESTENS = date(2027, 1, 15)
AUSZUG_FRUEHESTENS = date(2027, 8, 31)  # befristete Angebote müssen mind. bis hier laufen
UNBEFRISTET_OK = True                   # unbefristet = zweite Wahl, wird markiert
WG_MAX_PERSONEN = 3                     # inkl. dir -> max. 2 Mitbewohner

# WG-Zimmer nur, wenn eins dieser Wörter im Inserat steht
WG_STIL_KEYWORDS = ["altbau", "saniert", "renoviert", "modern", "neubau", "erstbezug", "hochwertig", "stuck", "dielen"]

# Stadtteile mit max. ~30 Min Öffis zum Ostbahnhof / Werksviertel
STADTTEILE = [
    "au", "haidhausen", "au-haidhausen", "bogenhausen", "berg am laim", "ramersdorf", "perlach", "neuperlach",
    "giesing", "obergiesing", "untergiesing", "fasangarten", "harlaching", "trudering", "riem", "messestadt",
    "zamdorf", "steinhausen", "denning", "englschalking", "oberföhring", "daglfing",
    "altstadt", "lehel", "maxvorstadt", "ludwigsvorstadt", "isarvorstadt", "glockenbach", "gärtnerplatz",
    "schlachthof", "schwabing", "sendling", "westend", "schwanthalerhöhe", "theresienhöhe", "neuhausen",
    "nymphenburg", "laim", "pasing", "haar", "unterföhring", "zentrum",
]
# Postleitzahlen (für Kleinanzeigen) im selben Radius
PLZ = {
    "80331", "80333", "80335", "80336", "80337", "80339", "80469", "80538", "80539", "80634", "80636",
    "80637", "80639", "80686", "80687", "80689", "80796", "80797", "80798", "80799", "80801", "80802",
    "80803", "80804", "80805", "81241", "81369", "81371", "81373", "81377", "81379", "81539", "81541",
    "81543", "81545", "81547", "81549", "81667", "81669", "81671", "81673", "81675", "81677", "81679",
    "81735", "81737", "81739", "81825", "81827", "81829", "81925", "81927", "81929", "85540", "85774",
}

MAX_DETAILSEITEN_PRO_LAUF = 25          # schont die Seiten
PAUSE_SEKUNDEN = 2
