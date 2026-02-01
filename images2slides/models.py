"""Data models for infographic layout representation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class BBoxPx:
    """Bounding box in pixel coordinates."""

    x: float
    y: float
    w: float
    h: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, data: dict) -> BBoxPx:
        """Create from dictionary."""
        return cls(
            x=float(data["x"]),
            y=float(data["y"]),
            w=float(data["w"]),
            h=float(data["h"]),
        )

    @property
    def area(self) -> float:
        """Calculate area in square pixels."""
        return self.w * self.h

    @property
    def center(self) -> tuple[float, float]:
        """Get center point (cx, cy)."""
        return (self.x + self.w / 2, self.y + self.h / 2)


@dataclass(frozen=True)
class TextStyle:
    """Text styling hints for a region."""

    font_family: str | None = None
    font_size_pt: float | None = None
    bold: bool | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "font_family": self.font_family,
            "font_size_pt": self.font_size_pt,
            "bold": self.bold,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> TextStyle | None:
        """Create from dictionary."""
        if data is None:
            return None
        return cls(
            font_family=data.get("font_family"),
            font_size_pt=data.get("font_size_pt"),
            bold=data.get("bold"),
        )


@dataclass(frozen=True)
class Region:
    """A detected region in the infographic."""

    id: str
    order: int
    type: Literal["text", "image"]
    bbox_px: BBoxPx
    text: str | None = None
    style: TextStyle | None = None
    crop_from_infographic: bool = False
    confidence: float = 1.0
    notes: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "order": self.order,
            "type": self.type,
            "bbox_px": self.bbox_px.to_dict(),
            "text": self.text,
            "style": self.style.to_dict() if self.style else None,
            "crop_from_infographic": self.crop_from_infographic,
            "confidence": self.confidence,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict, index: int = 0) -> Region:
        """Create from dictionary."""
        return cls(
            id=str(data["id"]),
            order=int(data.get("order", index + 1)),
            type=data["type"],
            bbox_px=BBoxPx.from_dict(data["bbox_px"]),
            text=data.get("text"),
            style=TextStyle.from_dict(data.get("style")),
            crop_from_infographic=bool(data.get("crop_from_infographic", False)),
            confidence=float(data.get("confidence", 1.0)),
            notes=data.get("notes"),
        )

    @property
    def is_text(self) -> bool:
        """Check if this is a text region."""
        return self.type == "text"

    @property
    def is_image(self) -> bool:
        """Check if this is an image region."""
        return self.type == "image"


@dataclass(frozen=True)
class ImageDimensions:
    """Image dimensions in pixels."""

    width: int
    height: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {"width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: dict) -> ImageDimensions:
        """Create from dictionary."""
        return cls(width=int(data["width"]), height=int(data["height"]))

    @property
    def aspect_ratio(self) -> float:
        """Get width/height aspect ratio."""
        return self.width / self.height if self.height > 0 else 0


@dataclass(frozen=True)
class Layout:
    """Complete layout extracted from an infographic."""

    image_px: ImageDimensions
    regions: tuple[Region, ...]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "image_px": self.image_px.to_dict(),
            "regions": [r.to_dict() for r in self.regions],
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> Layout:
        """Create from dictionary."""
        return cls(
            image_px=ImageDimensions.from_dict(data["image_px"]),
            regions=tuple(Region.from_dict(r, i) for i, r in enumerate(data.get("regions", []))),
        )

    @classmethod
    def from_json(cls, json_str: str) -> Layout:
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @property
    def text_regions(self) -> tuple[Region, ...]:
        """Get only text regions."""
        return tuple(r for r in self.regions if r.is_text)

    @property
    def image_regions(self) -> tuple[Region, ...]:
        """Get only image regions."""
        return tuple(r for r in self.regions if r.is_image)
