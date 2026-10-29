"""WordPiece tokenizer, faithful to the BERT uncased preprocessing.

The distributed static model is a matrix of token vectors keyed by a BERT
style vocabulary. The pipeline and the plugin must tokenize identically or
query vectors would not live in the same space as the stored vectors, so the
tokenization lives here once, in pure Python, and is shared by both sides.

This module is part of the Domain layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import unicodedata


class WordPieceTokenizer:
    """Greedy longest match first WordPiece over a BERT style vocabulary."""

    unkToken = "[UNK]"
    _continuationPrefix = "##"
    _maxInputCharsPerWord = 100
    # Ranges treated as punctuation by BERT basic tokenization.
    _punctuationRanges = ((33, 47), (58, 64), (91, 96), (123, 126))
    # CJK ideographs and related blocks are split per character.
    _cjkRanges = (
        (0x4E00, 0x9FFF),
        (0x3400, 0x4DBF),
        (0x20000, 0x2A6DF),
        (0x2A700, 0x2B73F),
        (0x2B740, 0x2B81F),
        (0x2B820, 0x2CEAF),
        (0xF900, 0xFAFF),
        (0x2F800, 0x2FA1F),
    )

    def __init__(self, vocabulary: dict[str, int]) -> None:
        self.vocabulary = vocabulary

    def encode(self, text: str) -> list[int]:
        """Return the token ids of the text, unknown tokens mapped to [UNK]."""
        ids: list[int] = []
        for token in self.tokenize(text):
            tokenId = self.vocabulary.get(token)
            if tokenId is None:
                tokenId = self.vocabulary.get(self.unkToken)
            if tokenId is not None:
                ids.append(tokenId)
        return ids

    def tokenize(self, text: str) -> list[str]:
        """Return the WordPiece tokens of the text (uncased, accents stripped)."""
        tokens: list[str] = []
        for chunk in self._basicChunks(text):
            tokens.extend(self._wordPiece(chunk))
        return tokens

    def _basicChunks(self, text: str) -> list[str]:
        chunks: list[str] = []
        for rawWord in text.split():
            for word in self._splitCjk(self._cleanWord(rawWord)):
                pieces = self._splitPunctuation(word)
                chunks.extend(piece for piece in pieces if piece)
        return chunks

    def _cleanWord(self, word: str) -> str:
        # Lowercase and strip accents, as BERT uncased does.
        decomposed = unicodedata.normalize("NFD", word.lower())
        stripped = "".join(
            character
            for character in decomposed
            if unicodedata.category(character) != "Mn"
        )
        return unicodedata.normalize("NFC", stripped)

    def _splitCjk(self, word: str) -> list[str]:
        words: list[str] = []
        current = ""
        for character in word:
            if self._inRanges(ord(character), self._cjkRanges):
                if current:
                    words.append(current)
                    current = ""
                words.append(character)
            else:
                current += character
        if current:
            words.append(current)
        return words

    def _splitPunctuation(self, word: str) -> list[str]:
        parts: list[str] = []
        current = ""
        for character in word:
            if self._isPunctuation(character):
                if current:
                    parts.append(current)
                    current = ""
                parts.append(character)
            else:
                current += character
        if current:
            parts.append(current)
        return parts

    def _wordPiece(self, word: str) -> list[str]:
        if not word:
            return []
        if len(word) > self._maxInputCharsPerWord:
            return [self.unkToken]
        pieces: list[str] = []
        start = 0
        while start < len(word):
            end = len(word)
            piece = None
            while start < end:
                candidate = word[start:end]
                if start > 0:
                    candidate = self._continuationPrefix + candidate
                if candidate in self.vocabulary:
                    piece = candidate
                    break
                end -= 1
            if piece is None:
                return [self.unkToken]
            pieces.append(piece)
            start = end
        return pieces

    def _isPunctuation(self, character: str) -> bool:
        codePoint = ord(character)
        if self._inRanges(codePoint, self._punctuationRanges):
            return True
        # Letters and marks that behave like punctuation in other scripts.
        return unicodedata.category(character).startswith("P")

    @staticmethod
    def _inRanges(value: int, ranges: tuple[tuple[int, int], ...]) -> bool:
        return any(low <= value <= high for low, high in ranges)
