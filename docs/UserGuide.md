# Semantic Plugin Search — User guide

Semantic Plugin Search helps you find the right QGIS plugin by describing
what you want to do, in your own words, instead of guessing the keyword a
plugin author happened to choose.

> *"classify a drone orthophoto into land cover classes"*
> *"create contour lines from a DEM"*
> *"export my layers to a web map"*

It ranks every plugin of the official QGIS repository against your
description and lets you install, upgrade, reinstall or uninstall the one
you pick, through the standard QGIS plugin manager.

**Contents**

1. [Requirements](#requirements)
2. [Installing](#installing)
3. [First launch](#first-launch)
4. [Searching](#searching)
5. [Reading the results](#reading-the-results)
6. [Plugin details](#plugin-details)
7. [Installing, upgrading and removing plugins](#installing-upgrading-and-removing-plugins)
8. [Updates and offline use](#updates-and-offline-use)
9. [Privacy](#privacy)
10. [Settings](#settings)
11. [Troubleshooting](#troubleshooting)

---

## Requirements

- **QGIS 3.44 or later, or QGIS 4.x.** The same plugin works on both.
- **An internet connection the first time** you open the search window, to
  download the search model (about 17 MB) and the plugin index for your QGIS
  version (about 5 MB). After that, search works offline.
- Nothing else to install: the plugin only uses what QGIS already ships
  (Python and numpy).

Downloads go through the QGIS network settings, so a proxy configured in
*Settings › Options › Network* is used automatically.

## Installing

**From a ZIP file** (current release):

1. Download `SemanticPluginSearch.<version>.zip`.
2. In QGIS, open *Plugins › Manage and Install Plugins… › Install from ZIP*.
3. Choose the file and click **Install Plugin**.

**From the official QGIS plugin repository** (once it is listed there): the
plugin is marked *experimental*, so first tick *Show also experimental
plugins* in the plugin manager's *Settings* tab, then search for
*Semantic Plugin Search*.

## First launch

<!-- UC-uc-refresh -->

Open the window from *Plugins › Semantic Plugin Search › Semantic Plugin
Search*, or click the toolbar icon.

On the very first launch the plugin downloads the search model and the plugin
index for your QGIS version. Progress messages appear in the QGIS message
bar, and you can start typing as soon as they finish, usually within a few
seconds. Both files are verified before they are used, and kept in your QGIS
profile for the next time.

## Searching

<!-- UC-uc-search -->
<!-- UC-uc-find-by-name -->

Type what you are trying to achieve in the search box. Results update as you
type: a space or punctuation mark searches immediately, and otherwise the
search runs after a short pause. **Enter** or the **Search** button searches
straight away.

Tips for good results:

- **Describe the task, not the tool.** *"digitize parcel boundaries from a
  cadastre map"* works better than *"digitizer"*.
- **Add the data you work with.** *DEM*, *orthophoto*, *GPX*, *PostGIS*,
  *WMS* and similar words help a lot.
- **Know the name? Type it.** A plugin's exact name, such as *QuickWKT* or
  *qgis2web*, puts that plugin first, and part of a name works too.
- **English works best.** Plugin descriptions are mostly in English, and so
  is the search model.

## Reading the results

<!-- UC-uc-see-installed -->

Each row shows the plugin icon, its name in bold and the start of its
description. On the right:

- **the relevance**, as a percentage: how well the plugin matches your
  description. Plugins whose name or tags literally contain your words get a
  small boost.
- **a badge** for plugins you already have: *installed*, or *update* when a
  newer version is available.
- **`[exp]` or `[dep]`** for experimental or deprecated plugins.

Experimental and deprecated plugins are hidden by default. Tick **Include
experimental** or **Include deprecated** above the list to show them. Your
choice is remembered.

The window remembers its size and the position of the divider between the
list and the details.

## Plugin details

<!-- UC-uc-inspect -->

Selecting a result shows its details on the right. The first result is
shown automatically.

- **Metadata** (default tab): version, compatible QGIS versions, author,
  tags, download count and rating, the full description, and links to the
  homepage, code repository, issue tracker and download. Links open in your
  web browser.
- **Readme**: the plugin's readme, loaded in the background, so the list
  never freezes. When a readme cannot be loaded, the tab says so and gives
  the plugin's repository address instead.

## Installing, upgrading and removing plugins

<!-- UC-uc-act -->
<!-- UC-uc-see-installed -->

The buttons at the bottom act on the selected plugin and are enabled
according to what is installed:

| Button | Enabled when |
|---|---|
| **Install** | the plugin is not installed |
| **Upgrade** | it is installed and a newer version exists |
| **Reinstall** | it is installed |
| **Uninstall** | it is installed |

Every action is carried out by the standard QGIS plugin manager, exactly as
if you had used *Manage and Install Plugins*, including its confirmation
questions. Afterwards the buttons and badges refresh to show the new state.

## Updates and offline use

The plugin index is rebuilt every week from the official repository (QGIS 3
on Mondays, QGIS 4 on Tuesdays). Each time you open the window, the plugin
first shows what it already has, then checks quietly for a newer index and
swaps it in when one is available. A failed or interrupted download never
replaces a working copy.

Without a connection, search keeps working with the last downloaded index.
Readmes and icons need the network, and are cached once seen.

## Privacy

- **What you type never leaves your computer.** Your description is turned
  into a search vector locally, inside QGIS.
- The plugin downloads the index and model from the project's GitHub
  repository, and, for the plugins you look at, their readme (from the
  plugin's code repository) and icon (from plugins.qgis.org). Those requests
  show which plugins you looked at, never what you searched for.
- Nothing is uploaded and there is no tracking.

## Settings

The plugin needs no configuration. For special set-ups (a company mirror, a
test repository), the index address can be changed in *Settings › Options ›
Advanced* under the key `SemanticPluginSearch/embeddings/indexUrl`.

Downloaded files live in the `semantic-search` folder of your QGIS profile
folder (*Settings › User Profiles › Open Active Profile Folder*). Deleting
that folder is safe: everything is downloaded again on the next launch.

## Troubleshooting

**"Preparing the search…" in the window's status line.**
The plugin is downloading its index (first launch, about 22 MB) or loading
it. Your query runs by itself as soon as it is ready, usually within
seconds. If it stays there, check your internet connection or your proxy
in *Settings › Options › Network*, then close and reopen the window.

**"Cannot refresh the embeddings assets … using cached data."**
The update check could not reach GitHub. Search keeps working with your
current copy, so nothing needs doing.

**"Downloaded embeddings asset failed its integrity check."**
A download did not match its published checksum and was discarded, and your
previous copy is still used. Reopen the window later. If it keeps happening,
please report it.

**Install, Upgrade or Uninstall does nothing, or the plugin manager opens.**
On some QGIS versions the plugin manager has to be opened once to load its
plugin list. Open *Plugins › Manage and Install Plugins…*, close it, and try
again.

**A plugin you expected is missing.**
It may be experimental or deprecated (tick the matching box), not yet in the
weekly index, or not compatible with your QGIS version.

Please report problems on the
[issue tracker](https://github.com/SylvainSouche/qgis-semantic-plugin-search/issues),
including your QGIS version and the message you saw.
