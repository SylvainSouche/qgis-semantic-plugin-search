"""Lexical boost of the hybrid ranking, as a pure domain function."""
from __future__ import annotations

import numpy as np

from SemanticPluginSearch.Domain.Entities import PluginInfo
from SemanticPluginSearch.Domain.LexicalBoost import (
    DESCRIPTION_WEIGHT,
    EXACT_NAME_BOOST,
    NAME_WEIGHT,
    TAG_WEIGHT,
    LexicalIndex,
    terms,
)


def plugin(pluginId: int, name: str, tags=(), description: str = "") -> PluginInfo:  # noqa: ANN001
    return PluginInfo(pluginId=pluginId, name=name, tags=tuple(tags), description=description)


def test_terms_split_camel_case_and_drop_noise():
    words = terms("QuickWKT plugin for the QGIS2Web export")
    assert words == ["quick", "wkt", "qgis2", "web", "export"]
    assert terms("a an of") == []


def test_exact_name_gets_the_exact_boost_regardless_of_spacing_and_case():
    index = LexicalIndex([plugin(1, "QuickWKT"), plugin(2, "Quick Map Services")])
    boost = index.boosts("quick wkt")
    assert boost[0] >= EXACT_NAME_BOOST
    assert boost[0] > boost[1] > 0


def test_field_weights_order_name_over_tags_over_description():
    index = LexicalIndex(
        [
            plugin(1, "Contour Builder"),
            plugin(2, "Elevation", tags=("contour",)),
            plugin(3, "Terrain", description="Draws contour lines"),
            plugin(4, "Unrelated"),
        ]
    )
    boost = index.boosts("contour")
    assert boost[0] > boost[1] > boost[2] > boost[3] == 0
    assert np.isclose(boost[1], TAG_WEIGHT) and np.isclose(boost[2], DESCRIPTION_WEIGHT)


def test_prefix_matches_join_word_forms():
    index = LexicalIndex([plugin(1, "Parcel Digitizer")])
    assert index.boosts("digitize")[0] > 0


def test_boost_is_bounded():
    index = LexicalIndex(
        [plugin(1, "Contour", tags=("contour",), description="contour contour")]
    )
    ceiling = EXACT_NAME_BOOST + NAME_WEIGHT + TAG_WEIGHT + DESCRIPTION_WEIGHT
    assert index.boosts("contour")[0] <= ceiling + 1e-6


def test_missing_infos_are_tolerated():
    index = LexicalIndex([None, plugin(2, "Contour")])
    boost = index.boosts("contour")
    assert boost[0] == 0 and boost[1] > 0
