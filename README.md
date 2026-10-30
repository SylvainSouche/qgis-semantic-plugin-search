# Embeddings data branch

This branch holds only generated data and is rewritten by the
`BuildEmbeddings` workflow each run, as a single commit. Do not commit here.

- `index.json`: what the Semantic Plugin Search plugin reads first. It names
  the model and the per QGIS version databases, with checksums, sizes, build
  stamps and plugin counts.
- `EmbeddingModel.<hash>.npz`: the static token embedding model
  (potion-base-8M, MIT, distilled from all-MiniLM-L6-v2, Apache-2.0).
- `Embeddings-<universe>.<hash>.sqlite`: plugin metadata and embeddings for
  QGIS 3 and QGIS 4.
- `Readmes-<universe>.json.gz`: the readmes of the last run, reused while a
  plugin's version is unchanged so a weekly run only fetches new or updated
  plugins. Not used by the plugin.

File names carry a content hash, so a cached index never points at a
different file of the same name. The source code is on `main`.
