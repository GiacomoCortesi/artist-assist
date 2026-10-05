"""Shared enums for ArtistAssist domain models."""

from enum import Enum


class FormatPreset(str, Enum):
    FEED_4X5 = "feed_4x5"
    SQUARE_1X1 = "square_1x1"
    STORY_9X16 = "story_9x16"
    LANDSCAPE_16X9 = "landscape_16x9"
