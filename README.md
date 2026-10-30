# Semantic Plugin Search for QGIS

**Find the QGIS plugin you need by describing what you want to do.**

There are more than 1500 QGIS plugins, and the plugin manager only finds
them by keyword. Semantic Plugin Search understands descriptions:

> *classify a drone orthophoto into land cover classes*
> *create contour lines from a DEM*
> *export my project to an interactive web map*

and ranks every plugin of the official repository by how well it matches.

## What it does

- **Search in plain language.** Results update as you type, and typing a
  plugin's name puts it first.
- **See everything about a plugin at a glance**: icon, description, version,
  compatibility, rating, links and its readme.
- **Know what you already have.** Installed plugins carry an *installed*
  badge, or *update* when a newer version exists.
- **Install, upgrade, reinstall or uninstall** from the same window. The
  standard QGIS plugin manager does the work, as usual.
- **Private by design.** What you type never leaves your computer.
- **Works offline** after the first launch, and stays up to date on its own:
  the plugin index is rebuilt every week.

## Get started

1. **Requirements:** QGIS 3.44 or later, or QGIS 4.x, and an internet
   connection on first launch (about 22 MB is downloaded once). Nothing else
   to install.
2. **Install:** download `SemanticPluginSearch.<version>.zip`, then in QGIS
   use *Plugins › Manage and Install Plugins… › Install from ZIP*.
3. **Open** *Plugins › Semantic Plugin Search*, or click its toolbar icon,
   and describe what you are looking for.

The [user guide](docs/UserGuide.md) covers search tips, reading the results,
offline use, privacy, settings and troubleshooting.

## Status

The plugin is **experimental**. It has been tested on QGIS 3.44 and QGIS 4.2.
Please report problems and suggestions on the
[issue tracker](https://github.com/SylvainSouche/qgis-semantic-plugin-search/issues).

## How it works, in one paragraph

Every week a GitHub Action downloads the official plugin catalogue and every
readme, turns each plugin into a vector with a compact, commercially
licensed text embedding model, and stores the result in this repository's
`embeddings` branch. The plugin
downloads that index and the model once, turns your description into a
vector locally, and ranks plugins by similarity, with a small boost for
plugins whose name or tags contain your words. No AI service is called and
nothing is uploaded.

## For developers

The [developer guide](docs/Developer.md) covers the architecture, the
pipeline, building, testing (`make test` runs without QGIS, and `make smoke`
runs inside a real QGIS) and releasing. The specification is generated
from the project model into [docs/Specification.md](docs/Specification.md).

## License

[MIT](LICENSE), compatible with the GPLv2-or-later requirement for QGIS
plugins. The search model is
[minishlab/potion-base-8M](https://huggingface.co/minishlab/potion-base-8M)
(MIT), distilled from all-MiniLM-L6-v2 (Apache-2.0).
