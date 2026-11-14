# GisVocabulary.tsv attribution

Single words taken from the English terms of the term lists published by the
gis-glossary project (https://github.com/SylvainSouche/gis-glossary,
`published/` folder at commit 3a3940f0434010fc181d1bf36a113cad9559c373),
kept only when the BERT WordPiece vocabulary of potion-base-8M splits them
into pieces. Built by `evaluation/BuildGisVocabulary.py`. No definitions,
terms or phrases are reproduced; only individual words, with the sources each
was found in (`sources` column).

| source | provider and terms of reuse |
|---|---|
| `iso-mlgt` | ISO/TC 211 Multi-Lingual Glossary of Terms, © ISO/TC 211, via geolexica/isotc211-glossary commit e160ccc5; made freely available by the ISO/TC 211 TMG, no licence stated |
| `iate` | Download IATE, European Union, 2026; the legal notice states the download data is not copyright protected and may be reproduced, commercially or not |
| `qgis-gui` | QGIS translation catalogues, QGIS project and its translators, GNU GPL, commit 6fe9e8b4 |
| `qgis-manual` | QGIS User Guide section headings, QGIS project, GNU FDL 1.3 or later |
| `inspire` | Names in Commission Regulation (EU) No 1089/2010 (INSPIRE), © European Union, https://eur-lex.europa.eu; reuse authorised provided the source is acknowledged |
| `osm` | id-tagging-schema contributors and translators, OpenStreetMap; ISC licence |
| `gemet` | GEMET, GEneral Multilingual Environmental Thesaurus, European Environment Agency; CC BY 4.0 |
| `corine` | CORINE Land Cover nomenclature as published by NIBIO; the report states no licence, the same legend accompanies NIBIO's Corine Landcover Norge dataset under the Norwegian Licence for Open Government Data |

Not used: the Snorre termbase (all standards fields, not GIS-specific), the
Árni Magnússon Institute dictionaries (general language), and Kartverket
INT 1 (no reuse terms stated). None of the providers has reviewed or
endorsed this list.
