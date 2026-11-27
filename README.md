# Wohnungs-Agent München

Scannt alle 10 Minuten WG-Gesucht und Kleinanzeigen nach möblierten 1-Zimmer-Wohnungen und WG-Zimmern
(Jan–Aug 2027, max. 900 € warm, max. ~30 Min Öffis zum Ostbahnhof) und schickt Treffer samt vorgeschriebener
Anfrage per Telegram. Gesendet wird nichts automatisch.

- Kriterien: `config.py`
- Secrets: `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `ANFRAGE_VORLAGE` (Platzhalter: `{gruss}`, `{objekt}`, `{ort}`)
- Manuell starten: Actions → Wohnungssuche → Run workflow
- Pausieren: Actions → Wohnungssuche → ⋯ → Disable workflow
