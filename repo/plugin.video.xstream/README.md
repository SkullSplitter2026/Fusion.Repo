# Akisames xStream Mod

---

## Über dieses Projekt

Aki-xStream ist ein **unabhängiger Fork**. Dieses Projekt wird eigenständig
gepflegt und steht in keinem Zusammenhang mit dem ursprünglichen
xStream Dev-Team.

---

## Disclaimer

Aki-xStream ist ein Kodi-Addon, das Links zu Streams auf Drittanbieter-Seiten
findet und bündelt. Das Addon speichert, hostet und verteilt selbst keine
Inhalte — es zeigt nur, was auf externen Seiten ohnehin schon liegt.

Worauf du zugreifst und ob das in deinem Land erlaubt ist, liegt allein in
deiner Verantwortung.

**Nutzung auf eigene Verantwortung.**

---

## Credits & Danksagung

Ohne die Vorarbeit anderer gäbe es diesen Fork nicht.
Riesigen Respekt und Dank an:

**xStream Dev-Team Heptemar**
Für die ursprüngliche Codebase. Das gesamte Plugin-Gerüst, der
Site-Plugin-Mechanismus, die GUI-Architektur, die Hoster-Resolver-Integration
— alles steht auf dem Fundament das ihr über Jahre gebaut habt.

**xShip Dev-Team Kasi**
Für viele Patterns, Architektur-Ideen und konkrete Lösungen die in diesen
Fork eingeflossen sind. Trailer-Wiring, Cache-Strategien, Bookmark-Konzepte
und mehr haben hier ihre Spuren hinterlassen.

**michaz**
Für Pflege und Fixes über die Zeit.

**CarstenG2**
Danke für das Trailer-Base-File.

**ParanoidTeam**
Für moralische und tatkräftige Unterstützung.

**Alle weiteren Contributors** der xStream/xShip-Linie über die Jahre, und alle
die sich bis heute tatkräftig beteiligen — jeder Commit, jeder Bugfix, jedes
Pattern hat beigetragen.

### Externe Dienste & Bibliotheken

**[Gujal00 / ResolveURL](https://github.com/Gujal00)**
Hoster-Resolver-Backbone von Kodi. Ohne ResolveURL gäbe es kein
zuverlässiges Stream-Resolving für die aggregierten Hoster.

**[TMDB](https://www.themoviedb.org/)**
Metadaten-Quelle für Filme und Serien, Cover, Posters, Bewertungen,
Trailer-IDs. Das Plugin nutzt die offizielle TMDB-API. Dieses Projekt
wird nicht von TMDB gesponsert oder anderweitig unterstützt.

**[KinoCheck](https://kinocheck.de/)**
Deutschsprachige Trailer-API. Erste Anlaufstelle für DE-Trailer in der
Trailer-Pipeline.

**[Jikan](https://jikan.moe/)**
MyAnimeList-API für Anime-Trailer. Fängt all das ab was TMDB und KinoCheck
bei Anime-Inhalten oft übersehen.

---

## Hinweise für Site-Plugin-Bauer

Eine ausführliche Anleitung zum Aufbau eines neuen Site-Plugins liegt unter `sites/ScraperInfo.md`.

---

*Made with ❤️ — Open Source is love.*
