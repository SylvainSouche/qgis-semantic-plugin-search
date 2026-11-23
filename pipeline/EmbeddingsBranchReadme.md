# Embeddings data branch

This branch holds only generated data and is rewritten by the
`BuildEmbeddings` workflow each run, as a single commit. Do not commit here.

Two data sets live side by side, rebuilt in the same run:

- `index-ml.json`: what the Semantic Plugin Search plugin reads first, from
  the multilingual version on. It names the model and the per QGIS version
  databases, with checksums, sizes, build stamps and plugin counts.
- `EmbeddingModel-ml.<hash>.npz`: the static token embedding model
  (sentence-transformers/static-similarity-mrl-multilingual-v1, Apache-2.0,
  first 256 dimensions, int8).
- `Embeddings-ml-<universe>.<hash>.sqlite` (float32) and
  `Embeddings-ml-<universe>-q8.<hash>.sqlite` (int8): plugin metadata and
  embeddings for QGIS 3 and QGIS 4.
- `index.json`, `EmbeddingModel.<hash>.npz`, `Embeddings-<universe>[-q8].<hash>.sqlite`:
  the same with potion-base-8M (MIT, English), kept for the released plugin
  versions up to 0.4.8.
- `Readmes-<universe>.json.gz`: the readmes of the last run, reused while a
  plugin's version is unchanged so a weekly run only fetches new or updated
  plugins. Not used by the plugin.

File names carry a content hash, so a cached index never points at a
different file of the same name. The source code is on `main`.
