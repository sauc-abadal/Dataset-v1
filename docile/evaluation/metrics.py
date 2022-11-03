from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Sequence, Set

from docile.dataset.field import PCC, BBox, Field

# Small value for robust >= on floats.
EPS = 1e-6


@dataclass(frozen=True)
class MatchedPair:
    gold: Field
    pred: Field


@dataclass(frozen=True)
class FieldMatching:
    matches: Sequence[MatchedPair]
    extra: Sequence[Field]  # not matched predictions
    misses: Sequence[Field]  # not matched annotations


def pccs_covered(sorted_x_pccs: List[PCC], sorted_y_pccs: List[PCC], bbox: BBox) -> Set[PCC]:
    """Obtain which PCCs are under the given bbox."""

    i_l = bisect_left(sorted_x_pccs, bbox.left, key=lambda p: p.x)  # type: ignore
    i_r = bisect_right(sorted_x_pccs, bbox.right, key=lambda p: p.x)  # type: ignore
    x_subset = set(sorted_x_pccs[i_l:i_r])

    i_t = bisect_left(sorted_y_pccs, bbox.top, key=lambda p: p.y)  # type: ignore
    i_b = bisect_right(sorted_y_pccs, bbox.bottom, key=lambda p: p.y)  # type: ignore
    y_subset = set(sorted_y_pccs[i_t:i_b])

    return x_subset.intersection(y_subset)


def pccs_iou(
    sorted_x_pccs: List[PCC], sorted_y_pccs: List[PCC], gold_bbox: BBox, pred_bbox: BBox
) -> float:
    """Calculate IOU over Pseudo Character Boxes."""
    golds = pccs_covered(sorted_x_pccs, sorted_y_pccs, gold_bbox)
    preds = pccs_covered(sorted_x_pccs, sorted_y_pccs, pred_bbox)

    return len(golds.intersection(preds)) / len(golds.union(preds))


def get_matches(
    predictions: List[Field], annotations: List[Field], pccs: List[PCC], iou_threshold: float = 1
) -> FieldMatching:
    """
    Find matching between predictions and annotations.

    Parameters
    ----------
    predictions
        Either KILE fields from one page/document or LI fields from one line item. Notice
        that one line item can span multiple pages. These predictions are being matched in the
        sorted order by 'score' and in the original order if no score is given (or is equal for
        several predictions).
    annotations
        KILE or LI gold fields for the same page/document.
    pccs
        Pseudo-Character-Centers (PCCs) covering all pages that have any of the
        predictions/annotations fields.
    iou_threshold
        Necessary 'intersection / union' to accept a pair of fields as a match. The official
        evaluation uses threshold 1.0 but lower thresholds can be used for debugging.
    """
    page_to_pccs = defaultdict(list)
    for pcc in pccs:
        page_to_pccs[pcc.page].append(pcc)
    page_to_sorted_x_pccs = {
        page: sorted(page_pccs, key=lambda p: p.x) for page, page_pccs in page_to_pccs.items()
    }
    page_to_sorted_y_pccs = {
        page: sorted(page_pccs, key=lambda p: p.y) for page, page_pccs in page_to_pccs.items()
    }

    annotations_by_key_and_page = defaultdict(lambda: defaultdict(list))
    for a in annotations:
        annotations_by_key_and_page[a.fieldtype][a.page].append(a)

    predictions_by_key = defaultdict(list)
    for p in predictions:
        predictions_by_key[p.fieldtype].append(p)

    matched_pairs: List[MatchedPair] = []
    extra: List[Field] = []

    all_fieldtypes = set(annotations_by_key_and_page.keys()).union(predictions_by_key.keys())
    for fieldtype in all_fieldtypes:
        for pred in sorted(
            predictions_by_key[fieldtype],
            key=lambda pred: -pred.score if pred.score is not None else 0,
        ):
            matched_pair = None
            for gold_i, gold in enumerate(annotations_by_key_and_page[fieldtype][pred.page]):
                iou = pccs_iou(
                    sorted_x_pccs=page_to_sorted_x_pccs[pred.page],
                    sorted_y_pccs=page_to_sorted_y_pccs[pred.page],
                    gold_bbox=gold.bbox,
                    pred_bbox=pred.bbox,
                )
                if iou > iou_threshold - EPS:
                    matched_pair = MatchedPair(gold=gold, pred=pred)
                    annotations_by_key_and_page[fieldtype][pred.page].pop(gold_i)
                    break
            if matched_pair is None:
                extra.append(pred)
            else:
                matched_pairs.append(matched_pair)

    misses = [
        field
        for page_to_fields in annotations_by_key_and_page.values()
        for fields in page_to_fields.values()
        for field in fields
    ]

    return FieldMatching(
        matches=matched_pairs,
        extra=extra,
        misses=misses,
    )