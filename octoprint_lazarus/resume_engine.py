from __future__ import annotations

import io
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


DEFAULT_Z_MATCH_TOL = 0.05
DEFAULT_Z_FLOOR_TOL = 0.05
EXTRUSION_EPSILON = 1e-9
DEFAULT_LANDING_PARK_POSITION = dict(x=90.0, y=290.0, z=250.0)
LAYER_HEIGHT_PATTERNS = (
    re.compile(r"(?i)^\s*;\s*layer[_ ]height\s*[:=]\s*([-+]?\d*\.?\d+)\s*$"),
    re.compile(r"(?i)^\s*;\s*layerheight\s*[:=]\s*([-+]?\d*\.?\d+)\s*$"),
)
INITIAL_LAYER_HEIGHT_PATTERNS = (
    re.compile(r"(?i)^\s*;\s*initial[_ ]layer[_ ]height\s*[:=]\s*([-+]?\d*\.?\d+\s*%?)\s*$"),
    re.compile(r"(?i)^\s*;\s*first[_ ]layer[_ ]height\s*[:=]\s*([-+]?\d*\.?\d+\s*%?)\s*$"),
    re.compile(r"(?i)^\s*;\s*initial layer height\s*[:=]\s*([-+]?\d*\.?\d+\s*%?)\s*$"),
    re.compile(r"(?i)^\s*;\s*first layer height\s*[:=]\s*([-+]?\d*\.?\d+\s*%?)\s*$"),
)


@dataclass
class ResumeDatum:
    x: float
    y: float
    z: float


def _strip_comment(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _extract_float_param(line: str, letter: str) -> Optional[float]:
    if not line:
        return None
    code = line.split(";", 1)[0]
    m = re.search(rf"(?i)(?:^|\s){re.escape(letter)}\s*(?:=\s*)?([-+]?\d*\.?\d+)", code)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _is_motion(line: str) -> bool:
    s = line.lstrip().upper()
    return s.startswith("G0") or s.startswith("G1") or s.startswith("G2") or s.startswith("G3")


def _is_linear_motion(line: str) -> bool:
    s = line.lstrip().upper()
    return s.startswith("G0") or s.startswith("G1")


def is_real_printing_move(line: str) -> bool:
    if not _is_linear_motion(line):
        return False
    e = _extract_float_param(line, "E")
    if e is None or float(e) <= EXTRUSION_EPSILON:
        return False
    x = _extract_float_param(line, "X")
    y = _extract_float_param(line, "Y")
    z = _extract_float_param(line, "Z")
    return (x is not None) or (y is not None) or (z is not None)


def _extract_z_comment(line: str) -> Optional[float]:
    if not line:
        return None
    m = re.search(r"(?i)^\s*;\s*(?:Z|Z_HEIGHT)\s*:\s*([-+]?\d*\.?\d+)\s*$", line.strip())
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def should_strip_line(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return False
    up = s.upper()

    if up.startswith("G28") or up.startswith("G29") or up.startswith("G34"):
        return True
    if "BED_MESH_CALIBRATE" in up or "Z_TILT_ADJUST" in up:
        return True

    if up.startswith("START_PRINT") or up.startswith("PRINT_START"):
        return True
    if up.startswith("END_PRINT") or up.startswith("PRINT_END"):
        return True
    if up.startswith("CANCEL_PRINT"):
        return True

    if "SAVE_GCODE_STATE" in up or "RESTORE_GCODE_STATE" in up:
        return True

    return False


def normalize_alignment_side(alignment_side: Optional[str], quadrant: Optional[str] = None) -> str:
    side = (alignment_side or "").strip().lower()
    if side in ("left", "l"):
        return "left"
    if side in ("right", "r"):
        return "right"

    quadrant_value = (quadrant or "").strip().lower()
    if quadrant_value in ("fl", "bl"):
        return "left"
    if quadrant_value in ("fr", "br"):
        return "right"

    return "left"


def infer_resume_z(print_height_mm: float, layer_height_mm: float) -> float:
    if layer_height_mm <= 0:
        raise ValueError("Layer height must be > 0.")
    if print_height_mm < 0:
        raise ValueError("Print height must be >= 0.")
    k = int(round(print_height_mm / layer_height_mm))
    return max(0.0, k * layer_height_mm)


def infer_layer_height(original_gcode_text: str) -> float:
    comment_values = _collect_layer_height_comment_values(original_gcode_text)
    if comment_values:
        counts = Counter(comment_values)
        best_value, _ = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        return float(best_value)

    layer_z_values = _collect_layer_z_values(original_gcode_text, printing_only=True)
    if len(layer_z_values) < 2:
        layer_z_values = _collect_layer_z_values(original_gcode_text, printing_only=False)
    if len(layer_z_values) < 2:
        raise ValueError("Could not detect layer height from selected GCODE.")

    diffs = []
    for previous, current in zip(layer_z_values, layer_z_values[1:]):
        diff = round(current - previous, 5)
        if diff > 0:
            diffs.append(diff)

    if not diffs:
        raise ValueError("Could not detect layer height from selected GCODE.")

    counts = Counter(diffs)
    best_diff, _ = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return float(best_diff)


def _parse_height_value(raw_value: str, *, layer_height_mm: float) -> Optional[float]:
    value = (raw_value or "").strip()
    if not value:
        return None

    if value.endswith("%"):
        try:
            return layer_height_mm * (float(value[:-1].strip()) / 100.0)
        except Exception:
            return None

    try:
        return float(value)
    except Exception:
        return None


def infer_initial_layer_height(original_gcode_text: str, *, layer_height_mm: float) -> float:
    for raw in io.StringIO(original_gcode_text):
        stripped = raw.strip()
        for pattern in INITIAL_LAYER_HEIGHT_PATTERNS:
            match = pattern.match(stripped)
            if not match:
                continue
            parsed = _parse_height_value(match.group(1), layer_height_mm=layer_height_mm)
            if parsed is not None and parsed > 0:
                return float(parsed)

    layer_z_values = _collect_layer_z_values(original_gcode_text, printing_only=True)
    if not layer_z_values:
        layer_z_values = _collect_layer_z_values(original_gcode_text, printing_only=False)
    if layer_z_values:
        return float(layer_z_values[0])

    return float(layer_height_mm)


def infer_true_print_height(
    print_height_mm: float,
    *,
    layer_height_mm: float,
    initial_layer_height_mm: float,
) -> Dict[str, float]:
    layer_adjustment = float(initial_layer_height_mm) - float(layer_height_mm)
    normalized_height = max(0.0, float(print_height_mm) - layer_adjustment)
    rounded_normalized_height = infer_resume_z(
        print_height_mm=normalized_height,
        layer_height_mm=layer_height_mm,
    )
    true_print_height = max(0.0, rounded_normalized_height + layer_adjustment)

    return dict(
        layer_adjustment=round(layer_adjustment, 5),
        normalized_height=round(normalized_height, 5),
        rounded_normalized_height=round(rounded_normalized_height, 5),
        true_print_height=round(true_print_height, 5),
    )


def _collect_layer_height_comment_values(original_gcode_text: str) -> List[float]:
    values: List[float] = []

    for raw in io.StringIO(original_gcode_text):
        stripped = raw.strip()
        for pattern in LAYER_HEIGHT_PATTERNS:
            match = pattern.match(stripped)
            if not match:
                continue
            try:
                value = float(match.group(1))
            except Exception:
                continue
            if value > 0:
                values.append(round(value, 5))
            break

    return values


def _is_confirmed_print_move(line: str, *, detected_mode: str, last_e_abs: float) -> bool:
    code = _strip_comment(line)
    if not _is_linear_motion(code):
        return False

    e_value = _extract_float_param(code, "E")
    if e_value is None:
        return False

    has_motion = (
        _extract_float_param(code, "X") is not None
        or _extract_float_param(code, "Y") is not None
        or _extract_float_param(code, "Z") is not None
    )
    if not has_motion:
        return False

    extrusion_delta = float(e_value)
    if detected_mode == "absolute":
        extrusion_delta = float(e_value) - float(last_e_abs)

    return extrusion_delta > EXTRUSION_EPSILON


def _collect_layer_z_values(original_gcode_text: str, *, printing_only: bool) -> List[float]:
    current_z: Optional[float] = None
    detected_mode = "absolute"
    last_e_abs = 0.0
    seen = set()
    ordered: List[float] = []

    for raw in io.StringIO(original_gcode_text):
        zc = _extract_z_comment(raw)
        if zc is not None:
            current_z = float(zc)

        code = _strip_comment(raw)
        up = code.upper() if code else ""

        if up.startswith("M82"):
            detected_mode = "absolute"
        elif up.startswith("M83"):
            detected_mode = "relative"

        if _is_linear_motion(code):
            z = _extract_float_param(code, "Z")
            if z is not None:
                current_z = float(z)

        is_printing_move = _is_confirmed_print_move(
            code,
            detected_mode=detected_mode,
            last_e_abs=last_e_abs,
        )

        if up.startswith("G92"):
            e = _extract_float_param(code, "E")
            if e is not None:
                last_e_abs = float(e)
        elif detected_mode == "absolute" and _is_motion(code):
            e = _extract_float_param(code, "E")
            if e is not None:
                last_e_abs = float(e)

        if current_z is None or current_z <= 0:
            continue

        if printing_only:
            if not is_printing_move:
                continue
        elif not _is_linear_motion(code):
            continue

        rounded = round(current_z, 5)
        if rounded not in seen:
            seen.add(rounded)
            ordered.append(rounded)

    return ordered


def _collect_layer_points(
    original_gcode_text: str,
    *,
    target_z: float,
    z_match_tol: float,
) -> List[ResumeDatum]:
    points: List[ResumeDatum] = []
    current_x: Optional[float] = None
    current_y: Optional[float] = None
    current_z: Optional[float] = None

    for raw in io.StringIO(original_gcode_text):
        if should_strip_line(raw):
            continue

        zc = _extract_z_comment(raw)
        if zc is not None:
            current_z = float(zc)

        if not _is_linear_motion(raw):
            continue

        x = _extract_float_param(raw, "X")
        if x is not None:
            current_x = float(x)

        y = _extract_float_param(raw, "Y")
        if y is not None:
            current_y = float(y)

        z = _extract_float_param(raw, "Z")
        if z is not None:
            current_z = float(z)

        if current_z is None or abs(current_z - target_z) > z_match_tol:
            continue
        if current_x is None or current_y is None:
            continue

        points.append(ResumeDatum(x=float(current_x), y=float(current_y), z=float(target_z)))

    return points


def choose_alignment_datum(points: List[ResumeDatum], alignment_side: str, resume_z: float) -> ResumeDatum:
    if not points:
        raise ValueError("Could not find motion points at the computed resume layer.")

    normalized_side = normalize_alignment_side(alignment_side)
    target_x = min(point.x for point in points)
    if normalized_side == "right":
        target_x = max(point.x for point in points)

    matching_points = [point for point in points if abs(point.x - target_x) <= 0.00001]
    chosen_point = min(matching_points, key=lambda point: (point.y, point.x))

    return ResumeDatum(x=float(target_x), y=float(chosen_point.y), z=float(resume_z))


def _replace_e_value(line: str, new_e: float) -> str:
    if ";" in line:
        code_part, comment = line.split(";", 1)
        comment = ";" + comment
    else:
        code_part, comment = line, ""

    def repl(m: re.Match) -> str:
        return f"{m.group(1)}{new_e:.5f}"

    new_code = re.sub(
        r"(?i)(\bE\s*)(?:=\s*)?([-+]?\d*\.?\d+)",
        repl,
        code_part,
        count=1,
    ).rstrip()

    if comment:
        if not new_code.endswith(" "):
            new_code += " "
        new_code += comment.lstrip()
    return new_code


def _format_gcode_value(value: float, decimals: int = 3) -> str:
    formatted = ("{0:." + str(decimals) + "f}").format(float(value))
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def _is_layer_boundary_marker(line: str) -> bool:
    stripped = (line or "").strip()
    return (
        re.search(r"(?i)^\s*;\s*(?:CHANGE_LAYER|LAYER_CHANGE|BEFORE_LAYER_CHANGE|AFTER_LAYER_CHANGE)\b", stripped) is not None
        or re.search(r"(?i)^\s*;\s*LAYER\s*:\s*\d+\b", stripped) is not None
        or re.search(r"(?i)^\s*;\s*layer\s+num\s*/\s*total_layer_count\s*:", stripped) is not None
    )


def _parse_layer_number_marker(line: str) -> Optional[int]:
    stripped = (line or "").strip()
    patterns = (
        re.compile(r"(?i)^\s*;\s*LAYER\s*:\s*(\d+)\b"),
        re.compile(r"(?i)^\s*;\s*layer\s+num\s*/\s*total_layer_count\s*:\s*(\d+)\b"),
        re.compile(r"(?i)^\s*SET_PRINT_STATS_INFO\b.*\bCURRENT_LAYER\s*=\s*(\d+)\b"),
    )
    for pattern in patterns:
        match = pattern.search(stripped)
        if not match:
            continue
        try:
            return int(match.group(1))
        except Exception:
            return None
    return None


def _normalize_park_position(park_position: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    source = park_position or DEFAULT_LANDING_PARK_POSITION
    normalized: Dict[str, float] = {}
    for axis in ("x", "y", "z"):
        fallback = DEFAULT_LANDING_PARK_POSITION[axis]
        try:
            value = float(source.get(axis, fallback))
        except Exception:
            value = fallback
        normalized[axis] = round(value, 3)
    return normalized


def _parse_feature_state(line: str) -> Optional[Dict[str, str]]:
    stripped = (line or "").strip()
    if not stripped.startswith(";"):
        return None

    comment = stripped[1:].strip()
    tagged = re.match(r"(?i)^(?:TYPE|FEATURE)\s*:?\s*(.+)$", comment)
    support_only = re.match(
        r"(?i)^(SUPPORT(?:\s+MATERIAL|\s+INTERFACE|\s+INFILL|-INTERFACE)?.*)$",
        comment,
    )
    label = ((tagged or support_only).group(1) if (tagged or support_only) else "").strip()
    if not label:
        return None

    upper = label.upper().replace("_", " ")
    if "SUPPORT" in upper:
        return dict(
            kind="support-interface" if "INTERFACE" in upper else "support",
            label=label,
        )
    if any(
        token in upper
        for token in ("SKIRT", "BRIM", "PURGE", "PRIME TOWER", "WIPE TOWER", "CUSTOM")
    ):
        return dict(kind="ignored", label=label)
    return dict(kind="model", label=label)


def _parse_extrusion_segments(original_gcode_text: str) -> Dict[str, Any]:
    source_lines = original_gcode_text.splitlines()
    has_layer_boundaries = any(_is_layer_boundary_marker(line) for line in source_lines)
    segments: List[Dict[str, Any]] = []
    support_labels = set()

    current_feature = dict(kind="unclassified", label="Unclassified")
    current_x: Optional[float] = None
    current_y: Optional[float] = None
    current_z: Optional[float] = None
    current_feedrate: Optional[float] = None
    last_absolute_extrusion = 0.0
    position_mode = "absolute"
    extrusion_mode = "absolute"
    seen_layer_boundary = False

    for raw_line in source_lines:
        line = raw_line.rstrip("\r\n")
        if _is_layer_boundary_marker(line):
            seen_layer_boundary = True

        next_feature = _parse_feature_state(line)
        if next_feature:
            current_feature = next_feature
            if next_feature["kind"] in ("support", "support-interface"):
                support_labels.add(next_feature["label"])
            continue

        z_comment = _extract_z_comment(line)
        if z_comment is not None:
            current_z = float(z_comment)

        code = _strip_comment(line)
        upper = code.upper() if code else ""
        if not code:
            continue
        if upper.startswith("G90"):
            position_mode = "absolute"
            continue
        if upper.startswith("G91"):
            position_mode = "relative"
            continue
        if upper.startswith("M82"):
            extrusion_mode = "absolute"
            continue
        if upper.startswith("M83"):
            extrusion_mode = "relative"
            continue
        if upper.startswith("G92"):
            e_value = _extract_float_param(code, "E")
            if e_value is not None:
                last_absolute_extrusion = float(e_value)
            continue
        if not _is_linear_motion(code):
            continue

        x_value = _extract_float_param(code, "X")
        y_value = _extract_float_param(code, "Y")
        z_value = _extract_float_param(code, "Z")
        e_value = _extract_float_param(code, "E")
        feedrate = _extract_float_param(code, "F")
        if feedrate is not None and feedrate > 0:
            current_feedrate = float(feedrate)

        next_x = current_x if x_value is None else (
            float(x_value)
            if position_mode == "absolute"
            else float(current_x or 0.0) + float(x_value)
        )
        next_y = current_y if y_value is None else (
            float(y_value)
            if position_mode == "absolute"
            else float(current_y or 0.0) + float(y_value)
        )
        next_z = current_z if z_value is None else (
            float(z_value)
            if position_mode == "absolute"
            else float(current_z or 0.0) + float(z_value)
        )
        extrusion_delta: Optional[float] = None
        if e_value is not None:
            extrusion_delta = (
                float(e_value) - last_absolute_extrusion
                if extrusion_mode == "absolute"
                else float(e_value)
            )

        if (
            extrusion_delta is not None
            and extrusion_delta > EXTRUSION_EPSILON
            and current_x is not None
            and current_y is not None
            and next_x is not None
            and next_y is not None
            and next_z is not None
            and math.hypot(next_x - current_x, next_y - current_y) > EXTRUSION_EPSILON
        ):
            feature_kind = current_feature["kind"]
            if feature_kind == "unclassified" and has_layer_boundaries and not seen_layer_boundary:
                feature_kind = "ignored"
            segments.append(
                dict(
                    start_x=float(current_x),
                    start_y=float(current_y),
                    end_x=float(next_x),
                    end_y=float(next_y),
                    z=float(next_z),
                    extrusion=float(extrusion_delta),
                    feedrate=current_feedrate,
                    feature=feature_kind,
                    feature_label=current_feature["label"],
                )
            )

        current_x = next_x
        current_y = next_y
        current_z = next_z
        if e_value is not None and extrusion_mode == "absolute":
            last_absolute_extrusion = float(e_value)

    return dict(
        segments=segments,
        support_feature_labels=sorted(support_labels),
    )


def _segment_bounds(segment: Dict[str, Any]) -> Dict[str, float]:
    return dict(
        min_x=min(segment["start_x"], segment["end_x"]),
        max_x=max(segment["start_x"], segment["end_x"]),
        min_y=min(segment["start_y"], segment["end_y"]),
        max_y=max(segment["start_y"], segment["end_y"]),
    )


def _merge_bounds(left: Dict[str, float], right: Dict[str, float]) -> Dict[str, float]:
    return dict(
        min_x=min(left["min_x"], right["min_x"]),
        max_x=max(left["max_x"], right["max_x"]),
        min_y=min(left["min_y"], right["min_y"]),
        max_y=max(left["max_y"], right["max_y"]),
    )


def _expand_bounds(bounds: Dict[str, float], clearance: float) -> Dict[str, float]:
    return dict(
        min_x=bounds["min_x"] - clearance,
        max_x=bounds["max_x"] + clearance,
        min_y=bounds["min_y"] - clearance,
        max_y=bounds["max_y"] + clearance,
    )


def _segment_intersects_bounds(
    segment: Dict[str, Any],
    bounds: Dict[str, float],
) -> bool:
    # TODO: Replace this conservative bounding-box test with polygon/convex-hull
    # clipping once the preview can expose partial support-segment retention.
    dx = segment["end_x"] - segment["start_x"]
    dy = segment["end_y"] - segment["start_y"]
    minimum_t = 0.0
    maximum_t = 1.0
    clips = (
        (-dx, segment["start_x"] - bounds["min_x"]),
        (dx, bounds["max_x"] - segment["start_x"]),
        (-dy, segment["start_y"] - bounds["min_y"]),
        (dy, bounds["max_y"] - segment["start_y"]),
    )
    for direction, distance in clips:
        if abs(direction) <= EXTRUSION_EPSILON:
            if distance < 0:
                return False
            continue
        ratio = distance / direction
        if direction < 0:
            minimum_t = max(minimum_t, ratio)
        else:
            maximum_t = min(maximum_t, ratio)
        if minimum_t > maximum_t:
            return False
    return True


def _bounds_distance(left: Dict[str, float], right: Dict[str, float]) -> float:
    dx = max(0.0, left["min_x"] - right["max_x"], right["min_x"] - left["max_x"])
    dy = max(0.0, left["min_y"] - right["max_y"], right["min_y"] - left["max_y"])
    return math.hypot(dx, dy)


def _group_support_islands(
    segments: List[Dict[str, Any]],
    layer_tolerance: float,
    xy_tolerance: float,
) -> List[Dict[str, Any]]:
    layers: List[Dict[str, Any]] = []
    for segment in sorted(segments, key=lambda item: item["z"]):
        layer = next(
            (
                candidate
                for candidate in layers
                if abs(candidate["z"] - segment["z"]) <= layer_tolerance
            ),
            None,
        )
        if layer is None:
            layer = dict(z=segment["z"], segments=[])
            layers.append(layer)
        layer["segments"].append(segment)

    islands: List[Dict[str, Any]] = []
    for layer in layers:
        pending = list(layer["segments"])
        while pending:
            seed = pending.pop(0)
            cluster = [seed]
            cluster_bounds = _segment_bounds(seed)
            changed = True
            while changed:
                changed = False
                for index in range(len(pending) - 1, -1, -1):
                    candidate_bounds = _segment_bounds(pending[index])
                    if _bounds_distance(cluster_bounds, candidate_bounds) <= xy_tolerance:
                        candidate = pending.pop(index)
                        cluster.append(candidate)
                        cluster_bounds = _merge_bounds(cluster_bounds, candidate_bounds)
                        changed = True
            islands.append(
                dict(
                    z=layer["z"],
                    segments=cluster,
                    bounds=cluster_bounds,
                    connected_to_bed=False,
                )
            )
    return sorted(islands, key=lambda island: island["z"])


def _order_segments_by_nearest_neighbor(
    segments: List[Dict[str, Any]],
    start_x: Optional[float] = None,
    start_y: Optional[float] = None,
) -> List[Dict[str, Any]]:
    pending = [dict(segment) for segment in segments]
    ordered: List[Dict[str, Any]] = []
    current_x = start_x
    current_y = start_y

    while pending:
        best_index = 0
        reverse = False
        best_distance = float("inf")
        if current_x is not None and current_y is not None:
            for index, segment in enumerate(pending):
                start_distance = math.hypot(
                    segment["start_x"] - current_x,
                    segment["start_y"] - current_y,
                )
                end_distance = math.hypot(
                    segment["end_x"] - current_x,
                    segment["end_y"] - current_y,
                )
                if start_distance < best_distance:
                    best_index = index
                    reverse = False
                    best_distance = start_distance
                if end_distance < best_distance:
                    best_index = index
                    reverse = True
                    best_distance = end_distance

        selected = pending.pop(best_index)
        if reverse:
            selected["start_x"], selected["end_x"] = selected["end_x"], selected["start_x"]
            selected["start_y"], selected["end_y"] = selected["end_y"], selected["start_y"]
        ordered.append(selected)
        current_x = selected["end_x"]
        current_y = selected["end_y"]

    return ordered


def _append_tagged_supports(
    *,
    output_lines: List[str],
    original_gcode_text: str,
    first_layer_z: float,
    layer_height: float,
    support_build_height: float,
    support_clearance: float,
    include_support_interface: bool,
    require_bed_connected_supports: bool,
    insertion_side: str,
) -> Dict[str, Any]:
    parsed = _parse_extrusion_segments(original_gcode_text)
    if not parsed["support_feature_labels"]:
        # TODO: Add an explicitly opt-in geometry-inference mode; tagged-only
        # must continue to fail closed when slicer labels are unavailable.
        raise ValueError(
            "This G-code does not contain recognizable support feature labels. "
            "Support-only rebuild is unavailable for this file unless experimental geometry inference is enabled."
        )

    warnings: List[str] = []
    if insertion_side != "auto":
        warnings.append(
            "Directional insertion envelopes are not implemented yet; "
            "the safer vertical drop-in envelope was used."
        )

    model_segments = sorted(
        [
            segment
            for segment in parsed["segments"]
            if segment["feature"] in ("model", "unclassified")
            and segment["z"] <= support_build_height + DEFAULT_Z_MATCH_TOL
        ],
        key=lambda item: item["z"],
    )
    all_support_segments = sorted(
        [
            segment
            for segment in parsed["segments"]
            if (
                segment["feature"] == "support"
                or (
                    include_support_interface
                    and segment["feature"] == "support-interface"
                )
            )
            and segment["z"] <= support_build_height + DEFAULT_Z_MATCH_TOL
        ],
        key=lambda item: item["z"],
    )

    cumulative_model_bounds: Optional[Dict[str, float]] = None
    model_index = 0
    insertion_safe_segments: List[Dict[str, Any]] = []
    rejected_insertion_moves = 0
    for segment in all_support_segments:
        while (
            model_index < len(model_segments)
            and model_segments[model_index]["z"] <= segment["z"] + DEFAULT_Z_MATCH_TOL
        ):
            next_bounds = _segment_bounds(model_segments[model_index])
            cumulative_model_bounds = (
                _merge_bounds(cumulative_model_bounds, next_bounds)
                if cumulative_model_bounds
                else next_bounds
            )
            model_index += 1

        no_support_zone = (
            _expand_bounds(cumulative_model_bounds, max(0.0, support_clearance))
            if cumulative_model_bounds
            else None
        )
        if no_support_zone and _segment_intersects_bounds(segment, no_support_zone):
            rejected_insertion_moves += 1
            continue
        insertion_safe_segments.append(segment)

    layer_tolerance = max(DEFAULT_Z_MATCH_TOL, layer_height * 0.35)
    connectivity_tolerance = 1.5
    islands = _group_support_islands(
        insertion_safe_segments,
        layer_tolerance,
        connectivity_tolerance,
    )
    connected_islands: List[Dict[str, Any]] = []
    rejected_disconnected_moves = 0
    for island in islands:
        if not require_bed_connected_supports:
            island["connected_to_bed"] = True
        elif abs(island["z"] - first_layer_z) <= layer_tolerance:
            island["connected_to_bed"] = True
        else:
            island["connected_to_bed"] = any(
                island["z"] > lower["z"]
                and island["z"] - lower["z"]
                <= layer_height * 1.75 + layer_tolerance
                and _bounds_distance(island["bounds"], lower["bounds"])
                <= connectivity_tolerance
                for lower in connected_islands
            )

        if island["connected_to_bed"]:
            connected_islands.append(island)
        else:
            rejected_disconnected_moves += len(island["segments"])

    retained_segments = sorted(
        [
            segment
            for island in connected_islands
            for segment in island["segments"]
            if segment["z"] > first_layer_z + layer_tolerance
        ],
        key=lambda item: item["z"],
    )

    if not all_support_segments:
        warnings.append(
            "Support labels were found, but no support extrusion moves exist "
            "below the requested build height."
        )
    elif not retained_segments:
        warnings.append(
            "No insertion-safe, bed-connected support paths remained after filtering; "
            "only the landing pad was generated."
        )

    if retained_segments:
        output_lines.extend(
            [
                "; --- BEGIN COMPACT TAGGED SUPPORT REBUILD ---",
                "; Support build height: {height} mm".format(
                    height=_format_gcode_value(support_build_height)
                ),
                "; Insertion clearance: {clearance} mm".format(
                    clearance=_format_gcode_value(support_clearance)
                ),
                "; Recognized labels: {labels}".format(
                    labels=", ".join(parsed["support_feature_labels"])
                ),
                "G90 ; absolute positioning for extracted supports",
                "M83 ; relative extrusion for extracted supports",
                "G92 E0",
            ]
        )

        layers: List[Dict[str, Any]] = []
        for segment in retained_segments:
            layer = next(
                (
                    candidate
                    for candidate in layers
                    if abs(candidate["z"] - segment["z"]) <= layer_tolerance
                ),
                None,
            )
            if layer is None:
                layer = dict(z=segment["z"], segments=[])
                layers.append(layer)
            layer["segments"].append(segment)

        cursor_x: Optional[float] = None
        cursor_y: Optional[float] = None
        for layer in sorted(layers, key=lambda item: item["z"]):
            output_lines.append(
                "; --- EXTRACTED SUPPORT LAYER Z={z} ---".format(
                    z=_format_gcode_value(layer["z"])
                )
            )
            output_lines.append(
                "G0 Z{z} F600".format(z=_format_gcode_value(layer["z"]))
            )
            ordered = _order_segments_by_nearest_neighbor(
                layer["segments"],
                cursor_x,
                cursor_y,
            )
            for segment in ordered:
                output_lines.append(
                    "G0 X{x} Y{y} F6000".format(
                        x=_format_gcode_value(segment["start_x"]),
                        y=_format_gcode_value(segment["start_y"]),
                    )
                )
                output_lines.append(
                    "G1 X{x} Y{y} E{e} F{f}".format(
                        x=_format_gcode_value(segment["end_x"]),
                        y=_format_gcode_value(segment["end_y"]),
                        e=_format_gcode_value(segment["extrusion"], 5),
                        f=_format_gcode_value(segment.get("feedrate") or 1200.0),
                    )
                )
                cursor_x = segment["end_x"]
                cursor_y = segment["end_y"]
        output_lines.extend(
            [
                "G92 E0",
                "; --- END COMPACT TAGGED SUPPORT REBUILD ---",
            ]
        )

    return dict(
        candidate_move_count=len(
            [
                segment
                for segment in all_support_segments
                if segment["z"] > first_layer_z + layer_tolerance
            ]
        ),
        retained_move_count=len(retained_segments),
        rejected_insertion_move_count=rejected_insertion_moves,
        rejected_disconnected_move_count=rejected_disconnected_moves,
        feature_labels=parsed["support_feature_labels"],
        warnings=warnings,
    )


def build_landing_pad_gcode(
    original_gcode_text: str,
    *,
    park_position: Optional[Dict[str, Any]] = None,
    preview_lines: int = 60,
    include_supports: bool = False,
    include_support_interface: bool = True,
    support_build_height: Optional[float] = None,
    support_clearance_mm: float = 0.8,
    require_bed_connected_supports: bool = True,
    support_only_extraction_mode: str = "taggedOnly",
    insertion_side: str = "auto",
) -> Dict[str, Any]:
    """
    Pure engine: copies the first printable layer into a standalone landing pad.
    Does NOT move printer, does NOT write files.
    """
    resolved_layer_height = infer_layer_height(original_gcode_text)
    park = _normalize_park_position(park_position)
    copied_lines: List[str] = []

    current_x: Optional[float] = None
    current_y: Optional[float] = None
    current_z: Optional[float] = None
    last_absolute_extrusion = 0.0
    detected_position_mode = "absolute"
    detected_extrusion_mode = "absolute"
    first_layer_z: Optional[float] = None
    move_count = 0
    lines = original_gcode_text.splitlines()
    has_numbered_layer_markers = any(_parse_layer_number_marker(line) is not None for line in lines)
    has_generic_layer_markers = any(_is_layer_boundary_marker(line) for line in lines)
    first_layer_number: Optional[int] = None
    seen_generic_layer_boundary = False
    layer_move_count = 0

    for raw in lines:
        output_line = raw.rstrip("\r\n")
        layer_number = _parse_layer_number_marker(output_line)
        is_layer_boundary = _is_layer_boundary_marker(output_line)

        if has_generic_layer_markers and is_layer_boundary:
            if seen_generic_layer_boundary and layer_move_count > 0:
                break
            seen_generic_layer_boundary = True

        if has_numbered_layer_markers and layer_number is not None:
            if first_layer_number is None:
                first_layer_number = layer_number
            elif layer_number > first_layer_number and move_count > 0:
                break

        z_comment = _extract_z_comment(output_line)
        if z_comment is not None:
            current_z = float(z_comment)

        code = _strip_comment(output_line)
        up = code.upper() if code else ""

        if up.startswith("G90"):
            detected_position_mode = "absolute"
            copied_lines.append(output_line)
            continue
        elif up.startswith("G91"):
            detected_position_mode = "relative"
            copied_lines.append(output_line)
            continue
        elif up.startswith("M82"):
            detected_extrusion_mode = "absolute"
            copied_lines.append(output_line)
            continue
        elif up.startswith("M83"):
            detected_extrusion_mode = "relative"
            copied_lines.append(output_line)
            continue
        elif up.startswith("G92"):
            e_value = _extract_float_param(code, "E")
            if e_value is not None:
                last_absolute_extrusion = float(e_value)
            copied_lines.append(output_line)
            continue

        if not _is_linear_motion(code):
            copied_lines.append(output_line)
            continue

        x = _extract_float_param(code, "X")
        y = _extract_float_param(code, "Y")
        z = _extract_float_param(code, "Z")
        e_value = _extract_float_param(code, "E")

        next_x = current_x if x is None else (float(x) if detected_position_mode == "absolute" else float(current_x or 0.0) + float(x))
        next_y = current_y if y is None else (float(y) if detected_position_mode == "absolute" else float(current_y or 0.0) + float(y))
        next_z = current_z if z is None else (float(z) if detected_position_mode == "absolute" else float(current_z or 0.0) + float(z))

        extrusion_delta: Optional[float] = None
        if e_value is not None:
            extrusion_delta = (
                float(e_value) - float(last_absolute_extrusion)
                if detected_extrusion_mode == "absolute"
                else float(e_value)
            )

        has_motion = x is not None or y is not None or z is not None
        is_printing_move = (
            extrusion_delta is not None
            and extrusion_delta > EXTRUSION_EPSILON
            and has_motion
        )

        if (not has_numbered_layer_markers) and (not has_generic_layer_markers) and first_layer_z is not None:
            stop_z = first_layer_z + max(DEFAULT_Z_MATCH_TOL, resolved_layer_height * 0.5)
            if move_count > 0 and next_z is not None and next_z > stop_z:
                break

        copied_lines.append(output_line)

        if first_layer_z is None and is_printing_move and next_z is not None and next_z > 0:
            first_layer_z = float(next_z)
        if first_layer_z is not None and is_printing_move:
            move_count += 1
            if (not has_generic_layer_markers) or seen_generic_layer_boundary:
                layer_move_count += 1

        current_x = next_x
        current_y = next_y
        current_z = next_z
        if e_value is not None and detected_extrusion_mode == "absolute":
            last_absolute_extrusion = float(e_value)

    if first_layer_z is None or not copied_lines or move_count == 0:
        raise ValueError("Could not find a printable first layer to build a landing pad.")

    safe_park_z = max(float(park["z"]), float(first_layer_z) + 10.0)
    output_lines = [
        "; --- LOOSE-BED LANDING PAD (LAZARUS V2) ---",
        "; WARNING: confirm the build plate is clear before running this file.",
        "; Slicer start G-code and first-layer setup are copied from the selected file.",
        "; First printable layer Z: {z:.3f} mm".format(z=first_layer_z),
        "; Landing pad height offset for resume: {z:.3f} mm".format(z=first_layer_z),
        "; First-layer extrusion moves copied: {count}".format(count=move_count),
        "; --- BEGIN COPIED SLICER START + FIRST LAYER ---",
    ]
    output_lines.extend(copied_lines)
    support_result = dict(
        candidate_move_count=0,
        retained_move_count=0,
        rejected_insertion_move_count=0,
        rejected_disconnected_move_count=0,
        feature_labels=[],
        warnings=[],
    )
    if include_supports:
        if support_only_extraction_mode != "taggedOnly":
            raise ValueError(
                "Experimental geometry-inferred support extraction is not implemented yet."
            )
        try:
            resolved_support_build_height = float(support_build_height)
        except Exception:
            raise ValueError("Support build height must be above the landing pad height.")
        if resolved_support_build_height <= float(first_layer_z):
            raise ValueError("Support build height must be above the landing pad height.")
        support_result = _append_tagged_supports(
            output_lines=output_lines,
            original_gcode_text=original_gcode_text,
            first_layer_z=float(first_layer_z),
            layer_height=float(resolved_layer_height),
            support_build_height=resolved_support_build_height,
            support_clearance=max(0.0, float(support_clearance_mm or 0.0)),
            include_support_interface=bool(include_support_interface),
            require_bed_connected_supports=bool(require_bed_connected_supports),
            insertion_side=str(insertion_side or "auto"),
        )
    output_lines.extend([
        "; --- MOVE TOOLHEAD OUT OF GLUING AREA ---",
        "G90 ; absolute positioning for park move",
        "G0 Z{z} F1200".format(z=_format_gcode_value(safe_park_z)),
        "G0 X{x} Y{y} F6000".format(
            x=_format_gcode_value(park["x"]),
            y=_format_gcode_value(park["y"]),
        ),
        "; --- END LANDING PAD ---",
    ])

    return dict(
        ok=True,
        first_layer_z=round(float(first_layer_z), 3),
        landing_pad_height=round(float(first_layer_z), 3),
        landing_pad_text="\n".join(output_lines) + "\n",
        move_count=move_count,
        park_position=park,
        preview=output_lines[:preview_lines],
        support_candidate_move_count=support_result["candidate_move_count"],
        support_move_count=support_result["retained_move_count"],
        supports_included=support_result["retained_move_count"] > 0,
        rejected_insertion_support_moves=support_result["rejected_insertion_move_count"],
        rejected_disconnected_support_moves=support_result["rejected_disconnected_move_count"],
        support_feature_labels=support_result["feature_labels"],
        warnings=support_result["warnings"],
    )


def build_resumed_gcode(
    original_gcode_text: str,
    *,
    firmware: str,
    print_height_mm: float,
    height_offset_mm: float = 0.0,
    alignment_side: str = "left",
    layer_height_mm: Optional[float] = None,
    quadrant: Optional[str] = None,
    z_match_tol: float = DEFAULT_Z_MATCH_TOL,
    z_floor_tol: float = DEFAULT_Z_FLOOR_TOL,
    inject_last_motion_feedrate: bool = True,
    preview_lines: int = 50,
) -> Dict[str, Any]:
    """
    Pure engine: returns resumed_text + preview + metadata.
    Does NOT move printer, does NOT write files.
    """
    normalized_side = normalize_alignment_side(alignment_side, quadrant=quadrant)
    resolved_layer_height = float(layer_height_mm) if layer_height_mm is not None else infer_layer_height(original_gcode_text)
    resolved_initial_layer_height = infer_initial_layer_height(
        original_gcode_text,
        layer_height_mm=resolved_layer_height,
    )
    normalized_height_offset = max(0.0, float(height_offset_mm or 0.0))
    effective_print_height = max(0.0, float(print_height_mm) - normalized_height_offset)
    height_info = infer_true_print_height(
        print_height_mm=effective_print_height,
        layer_height_mm=resolved_layer_height,
        initial_layer_height_mm=resolved_initial_layer_height,
    )
    resume_z = float(height_info["true_print_height"])
    z_floor = resume_z - float(z_floor_tol)

    layer_points = _collect_layer_points(
        original_gcode_text,
        target_z=resume_z,
        z_match_tol=z_match_tol,
    )
    datum = choose_alignment_datum(layer_points, normalized_side, resume_z)

    detected_mode = "absolute"
    last_e_abs = 0.0
    last_motion_f: Optional[float] = None
    current_x: Optional[float] = None
    current_y: Optional[float] = None
    current_z: Optional[float] = None
    anchor_index: Optional[int] = None

    # PASS 1: find anchor + last E + last F
    for i, raw in enumerate(io.StringIO(original_gcode_text)):
        zc = _extract_z_comment(raw)
        if zc is not None:
            current_z = float(zc)

        code = _strip_comment(raw)
        up = code.upper() if code else ""

        if up.startswith("M82"):
            detected_mode = "absolute"
        elif up.startswith("M83"):
            detected_mode = "relative"

        is_printing_move = _is_confirmed_print_move(
            code,
            detected_mode=detected_mode,
            last_e_abs=last_e_abs,
        )

        if up.startswith("G92"):
            e = _extract_float_param(code, "E")
            if e is not None:
                last_e_abs = float(e)
        elif _is_motion(code) and detected_mode == "absolute":
            e = _extract_float_param(code, "E")
            if e is not None:
                last_e_abs = float(e)

        if _is_linear_motion(raw):
            x = _extract_float_param(raw, "X")
            if x is not None:
                current_x = float(x)

            y = _extract_float_param(raw, "Y")
            if y is not None:
                current_y = float(y)

            z = _extract_float_param(raw, "Z")
            if z is not None:
                current_z = float(z)

            f = _extract_float_param(raw, "F")
            if f is not None:
                last_motion_f = float(f)

        if current_z is not None and current_z >= (resume_z - z_match_tol):
            if (not should_strip_line(raw)) and is_printing_move:
                anchor_index = i
                break

    if anchor_index is None:
        raise ValueError("Could not find a resume anchor at/after computed resume height.")

    header: List[str] = []
    header.append("; --- RESUME FROM FAILURE (LAZARUS) ---")
    header.append(
        f"; Inputs: LH={resolved_layer_height:.5f}mm, ILH={resolved_initial_layer_height:.5f}mm, PH={print_height_mm:.3f}mm"
    )
    if normalized_height_offset > 0:
        header.append(
            f"; Landing pad height offset: {normalized_height_offset:.3f} mm | Effective failed-print height: {effective_print_height:.3f} mm"
        )
    header.append(
        f"; Adjusted print height: {height_info['normalized_height']:.5f} mm | Layer delta: {height_info['layer_adjustment']:.5f} mm"
    )
    header.append(f"; Computed resume height (RH): {resume_z:.3f} mm")
    header.append(f"; Alignment side: {normalized_side}")
    header.append(f"; Datum: X{datum.x:.3f} Y{datum.y:.3f} Z{datum.z:.3f}")
    header.append(f"; Anchor index: {anchor_index}")
    header.append(f"; Z-match tol: {z_match_tol:.3f} mm | Z-floor guard: Z >= {z_floor:.3f} mm")
    header.append(f"; Detected extrusion mode in source: {detected_mode.upper()}")
    header.append("G90 ; absolute positioning")
    header.append("G21 ; millimeters")
    header.append("M83 ; relative extrusion (Wizard-safe)")
    header.append("G92 E0 ; reset extruder")
    if inject_last_motion_feedrate and last_motion_f is not None:
        header.append(f"G1 F{last_motion_f:.3f} ; inherit slicer feedrate before anchor")
    header.append("; --- BEGIN RESUMED TOOLPATH ---")

    out_lines: List[str] = []
    preview_buf: List[str] = []

    def add(line: str) -> None:
        out_lines.append(line)
        if len(preview_buf) < preview_lines:
            preview_buf.append(line)

    for ln in header:
        add(ln)

    cur_abs_e = float(last_e_abs)

    # PASS 2: emit from anchor onward
    for i, raw in enumerate(io.StringIO(original_gcode_text)):
        if i < anchor_index:
            continue

        if should_strip_line(raw):
            continue

        if _is_motion(raw):
            z = _extract_float_param(raw, "Z")
            if z is not None and float(z) < z_floor:
                continue

        out_line = raw.rstrip("\n")

        if detected_mode == "absolute":
            code = _strip_comment(out_line)
            up = code.upper() if code else ""

            if up.startswith("G92"):
                e = _extract_float_param(code, "E")
                if e is not None:
                    cur_abs_e = float(e)
                    out_line = "G92 E0"
            elif _is_motion(code):
                e_abs = _extract_float_param(code, "E")
                if e_abs is not None:
                    e_abs = float(e_abs)
                    e_rel = e_abs - cur_abs_e
                    cur_abs_e = e_abs
                    out_line = _replace_e_value(out_line, e_rel)

        add(out_line)

    add("; --- END RESUMED FILE ---")

    return dict(
        ok=True,
        firmware=(firmware or "").lower(),
        layer_height=round(resolved_layer_height, 5),
        initial_layer_height=round(resolved_initial_layer_height, 5),
        adjusted_print_height=round(height_info["normalized_height"], 5),
        height_offset=round(normalized_height_offset, 3),
        measured_print_height=round(float(print_height_mm), 3),
        alignment_side=normalized_side,
        resume_z=round(resume_z, 3),
        datum=dict(
            x=float(datum.x),
            y=float(datum.y),
            z=float(datum.z),
            alignment_side=normalized_side,
        ),
        preview=preview_buf,
        resumed_text="\n".join(out_lines) + "\n",
    )
