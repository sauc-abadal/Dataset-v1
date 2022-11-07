import dataclasses
from typing import Any, List, Mapping, Optional, Tuple


@dataclasses.dataclass(frozen=True)
class BBox:
    left: float
    top: float
    right: float
    bottom: float

    def to_absolute_coords(self, width: float, height: float) -> "BBox":
        return BBox(
            self.left * width,
            self.top * height,
            self.right * width,
            self.bottom * height,
        )

    def to_tuple(self) -> Tuple[float, float, float, float]:
        return self.left, self.top, self.right, self.bottom

    def intersects(self, other: "BBox") -> bool:
        if self.left > other.right or other.left > self.right:
            return False
        if self.top > other.bottom or other.top > self.bottom:
            return False
        return True


@dataclasses.dataclass(slots=True, frozen=True)
class PCC:
    """Wrapper for a position in the document."""

    x: float
    y: float
    page: int


@dataclasses.dataclass(frozen=True)
class Field:
    bbox: BBox
    page: int
    score: Optional[float] = None
    text: Optional[str] = None
    fieldtype: Optional[str] = None
    line_item_id: Optional[int] = None
    pccs: List[PCC] = dataclasses.field(init=False, compare=False)

    def __post_init__(self) -> None:
        if self.text:
            pccs = self._calculate_pccs(self.bbox, self.text)
        else:
            pccs = []
        object.__setattr__(self, "pccs", pccs)

    @classmethod
    def from_annotation(cls, annotation_dict: Mapping[str, Any]) -> "Field":
        annotation_copy = dict(annotation_dict)
        bbox = BBox(*(annotation_copy.pop("bbox")))
        return cls(bbox=bbox, **annotation_copy)

    @classmethod
    def from_ocr(cls, ocr_dict: Mapping[str, Any], page: int) -> "Field":
        lt, rb = ocr_dict["geometry"]
        return cls(text=ocr_dict["value"], bbox=BBox(lt[0], lt[1], rb[0], rb[1]), page=page)

    def _calculate_pccs(self, bbox: BBox, text: str) -> List[PCC]:
        """Calculate Pseudo Character Boxes (PCCs) given bbox and text."""
        char_width = (bbox.right - bbox.left) / len(text)
        y_middle = (bbox.top + bbox.bottom) / 2
        return [
            PCC(x=bbox.left + (i + 1 / 2) * char_width, y=y_middle, page=self.page)
            for i in range(len(text))
        ]
