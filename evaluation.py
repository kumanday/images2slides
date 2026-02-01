from __future__ import annotations

import argparse
import base64
import csv
import functools
import hashlib
import json
import logging
import math
import os
import random
import re
import shutil
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from images2slides.auth import get_slides_service_oauth, get_slides_service_sa
from images2slides.build_slide import (
    SlidesAPIError,
    build_slide,
    create_presentation,
    delete_initial_slide,
)
from images2slides.models import BBoxPx, Layout, Region
from images2slides.postprocess import compute_bbox_iou, postprocess_layout
from images2slides.uploader import GCSUploader, UploadError, get_file_hash
from images2slides.validator import LayoutValidationError, validate_layout
from images2slides.vlm import VLMConfig, VLMExtractionError, extract_layout_from_image

LOGGER = logging.getLogger("evaluation")

DEFAULT_OUT_DIR = "evaluation/runs"
MAX_RANDOM_SEED = 2**31 - 1
TOPIC_MAX_CHARS = 200
DEFAULT_NUM_RUNS = 1

CANVAS_WIDTH = 1600
CANVAS_HEIGHT = 900

GT_TEXT_MODEL = "gemini-3-pro-preview"
GT_IMAGE_MODEL = "gemini-3-pro-image-preview"

METRICS_COLUMNS = [
    "run_id",
    "timestamp_utc",
    "concept",
    "provider",
    "seed",
    "n_gt_text",
    "n_pred_text",
    "n_match_text",
    "n_fp_text",
    "n_fn_text",
    "n_gt_img",
    "n_pred_img",
    "n_match_img",
    "n_fp_img",
    "n_fn_img",
    "element_recovery_rate_text",
    "element_recovery_rate_img",
    "element_recovery_rate_all",
    "mean_iou_text",
    "median_iou_text",
    "mean_iou_img",
    "median_iou_img",
    "mean_center_offset_norm_text",
    "mean_center_offset_px_text",
    "mean_center_offset_norm_img",
    "mean_center_offset_px_img",
    "mean_cer",
    "median_cer",
    "mean_wer",
    "median_wer",
    "character_recovery_rate",
    "n_text_iou_ge_0_5",
    "frac_text_iou_ge_0_5",
    "n_text_iou_ge_0_75",
    "frac_text_iou_ge_0_75",
    "n_text_iou_ge_0_9",
    "frac_text_iou_ge_0_9",
    "n_img_iou_ge_0_5",
    "frac_img_iou_ge_0_5",
    "n_img_iou_ge_0_75",
    "frac_img_iou_ge_0_75",
    "n_img_iou_ge_0_9",
    "frac_img_iou_ge_0_9",
    "n_all_iou_ge_0_5",
    "frac_all_iou_ge_0_5",
    "n_all_iou_ge_0_75",
    "frac_all_iou_ge_0_75",
    "n_all_iou_ge_0_9",
    "frac_all_iou_ge_0_9",
    "t_vlm_s",
    "t_postprocess_s",
    "t_slides_api_s",
    "t_total_s",
]


def _load_env_file() -> None:
    current = Path.cwd()

    env_path = current / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
        return

    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            env_path = parent / ".env"
            if env_path.exists():
                load_dotenv(env_path, override=False)
            return


_load_env_file()


class EvaluationError(Exception):
    """Raised when evaluation pipeline fails."""


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def utc_now_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")


def get_git_commit() -> str | None:
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        return None
    return None


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(text)


def parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            return json.loads(match.group())
    raise EvaluationError("Failed to parse JSON from Gemini response")


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.lower().strip().split())


def edit_distance(seq_a: Iterable[Any], seq_b: Iterable[Any]) -> int:
    a = list(seq_a)
    b = list(seq_b)
    if not a:
        return len(b)
    if not b:
        return len(a)
    dp = list(range(len(b) + 1))
    for i, item_a in enumerate(a, start=1):
        prev = dp[0]
        dp[0] = i
        for j, item_b in enumerate(b, start=1):
            current = dp[j]
            if item_a == item_b:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j - 1], current)
            prev = current
    return dp[-1]


def similarity_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    dist = edit_distance(a, b)
    return max(0.0, 1.0 - dist / max_len)


def bbox_center_offset_norm(a: BBoxPx, b: BBoxPx) -> float:
    ax, ay = a.center
    bx, by = b.center
    dx = ax - bx
    dy = ay - by
    return (dx * dx + dy * dy) ** 0.5


def normalize_bbox(bbox: BBoxPx, width: float, height: float) -> BBoxPx:
    return BBoxPx(
        x=bbox.x / width,
        y=bbox.y / height,
        w=bbox.w / width,
        h=bbox.h / height,
    )


def linear_sum_assignment(cost_matrix: list[list[float]]) -> tuple[list[int], list[int]]:
    if not cost_matrix:
        return [], []
    num_rows = len(cost_matrix)
    num_cols = len(cost_matrix[0])
    if num_rows == 0 or num_cols == 0:
        return [], []

    if num_rows <= num_cols:
        rows, cols = _assignment_dp(cost_matrix)
        return rows, cols

    transposed = list(map(list, zip(*cost_matrix, strict=False)))
    cols, rows = _assignment_dp(transposed)
    return rows, cols


def _assignment_dp(cost_matrix: list[list[float]]) -> tuple[list[int], list[int]]:
    num_rows = len(cost_matrix)
    num_cols = len(cost_matrix[0])
    if num_cols > 24:
        LOGGER.warning("Large assignment problem (%d cols). Performance may degrade.", num_cols)

    @functools.cache
    def solve(row: int, used_mask: int) -> tuple[float, tuple[int, ...]]:
        if row == num_rows:
            return 0.0, ()
        best_cost = float("inf")
        best_assign: tuple[int, ...] = ()
        for col in range(num_cols):
            if used_mask & (1 << col):
                continue
            cost = cost_matrix[row][col]
            next_cost, next_assign = solve(row + 1, used_mask | (1 << col))
            total = cost + next_cost
            if total < best_cost:
                best_cost = total
                best_assign = (col,) + next_assign
        return best_cost, best_assign

    _, assignment = solve(0, 0)
    rows = list(range(num_rows))
    cols = list(assignment)
    return rows, cols


def get_default_provider() -> str:
    return os.environ.get("VLM_PROVIDER", "google")


def get_default_model() -> str | None:
    return os.environ.get("VLM_MODEL")


def get_google_api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise EvaluationError("GOOGLE_API_KEY is required for Gemini calls")
    return key


def get_slides_service() -> Any:
    client_secret = os.environ.get("CLIENT_SECRET_PATH")
    service_account = os.environ.get("SERVICE_ACCOUNT_PATH")
    if service_account:
        return get_slides_service_sa(service_account)
    if client_secret:
        return get_slides_service_oauth(client_secret)
    raise EvaluationError("CLIENT_SECRET_PATH or SERVICE_ACCOUNT_PATH is required")


def get_gcs_bucket() -> str:
    bucket = os.environ.get("GCS_BUCKET")
    if not bucket:
        raise EvaluationError("GCS_BUCKET is required to upload component images")
    return bucket


def build_plan_prompt(topic: str | None) -> str:
    schema = """
Region schema (regions array):
{
  "id": "<unique_string_id>",
  "order": <int starting at 1>,
  "type": "text" | "image",
  "bbox_px": {"x": <number>, "y": <number>, "w": <number>, "h": <number>},
  "text": "<text, required for type=text>",
  "style": {"font_family": <string|null>, "font_size_pt": <number|null>, "bold": <true|false|null>},
  "crop_from_infographic": <true|false>,
  "confidence": <number 0..1>,
  "notes": <string|null>
}
"""

    prompt = """
Create a 16:9 infographic layout on a 1600x900 canvas. Use 3-6 panels. Each panel includes one image
and 1-2 text blocks (captions must be separate text regions). Include a top title text region.

Topic: {topic}

Output JSON with keys:
- concept (short string)
- regions (list of regions matching the schema below)
- image_prompts (object mapping image region id -> detailed image-generation prompt)

Constraints:
- Provide bbox_px as {\"x\":..., \"y\":..., \"w\":..., \"h\":...} in pixels (0..1600 x 0..900)
- Do not overlap regions
- Keep >= 20px margin from slide edges
- Text regions must include non-empty text
- Captions must be separate text regions (not embedded in image regions)

{schema}

Return JSON only. No markdown or commentary.
"""
    topic_text = topic.strip() if topic else ""
    return prompt.replace("{schema}", schema).replace("{topic}", topic_text).strip()


def build_topics_prompt(num_topics: int) -> str:
    return (
        "Generate a JSON array with exactly "
        f"{num_topics} unique infographic topics. Each topic must be a single sentence with up to "
        f"{TOPIC_MAX_CHARS} characters. Make topics diverse across industries and subjects. Return "
        "JSON only."
    )


def call_gemini_text(
    prompt: str,
    model: str,
    system_prompt: str | None = None,
    temperature: float = 0.4,
) -> Any:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=get_google_api_key())
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )
    ]
    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=8192,
        system_instruction=system_prompt or "Return JSON only.",
    )
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    return parse_json_response(response.text)


def validate_plan_payload(payload: dict) -> tuple[Layout | None, list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return None, ["Payload is not a JSON object"]
    regions = payload.get("regions")
    if not isinstance(regions, list):
        errors.append("regions must be a list")
        return None, errors
    image_prompts = payload.get("image_prompts")
    if not isinstance(image_prompts, dict):
        errors.append("image_prompts must be an object")
    layout_data = {
        "image_px": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT},
        "regions": regions,
    }
    layout: Layout | None = None
    try:
        layout = validate_layout(layout_data)
    except LayoutValidationError as exc:
        errors.append(str(exc))
    if layout:
        text_regions = [r for r in layout.regions if r.type == "text"]
        image_regions = [r for r in layout.regions if r.type == "image"]
        if not (3 <= len(image_regions) <= 6):
            errors.append("Expected 3-6 image regions for panels")
        for region in text_regions:
            if not region.text or not region.text.strip():
                errors.append(f"Text region {region.id} missing text")
        for region in layout.regions:
            if region.bbox_px.x < 20 or region.bbox_px.y < 20:
                errors.append(f"Region {region.id} violates 20px margin")
            if region.bbox_px.x + region.bbox_px.w > CANVAS_WIDTH - 20:
                errors.append(f"Region {region.id} violates right margin")
            if region.bbox_px.y + region.bbox_px.h > CANVAS_HEIGHT - 20:
                errors.append(f"Region {region.id} violates bottom margin")
        if layout:
            for i, region_a in enumerate(layout.regions):
                for region_b in layout.regions[i + 1 :]:
                    if compute_bbox_iou(region_a.bbox_px, region_b.bbox_px) > 0.01:
                        errors.append(f"Regions {region_a.id} and {region_b.id} overlap")
                        break
        if isinstance(image_prompts, dict):
            missing = [r.id for r in image_regions if r.id not in image_prompts]
            if missing:
                errors.append(f"image_prompts missing ids: {', '.join(missing)}")
    return layout, errors


def validate_topics(payload: Any, num_topics: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, list):
        return ["Topics payload is not a JSON list"]
    if len(payload) != num_topics:
        errors.append(f"Expected {num_topics} topics, got {len(payload)}")
    normalized: list[str] = []
    for idx, topic in enumerate(payload, start=1):
        if not isinstance(topic, str) or not topic.strip():
            errors.append(f"Topic {idx} is not a non-empty string")
            continue
        if len(topic) > TOPIC_MAX_CHARS:
            errors.append(f"Topic {idx} exceeds {TOPIC_MAX_CHARS} characters")
        normalized.append(normalize_text(topic))
    if len(set(normalized)) != len(normalized):
        errors.append("Topics must be unique")
    return errors


def generate_topics(num_topics: int) -> list[str]:
    prompt = build_topics_prompt(num_topics)
    payload = call_gemini_text(prompt, GT_TEXT_MODEL, temperature=0.7)
    errors = validate_topics(payload, num_topics)
    if errors:
        repair_prompt = (
            "Fix the following JSON list so it contains exactly "
            f"{num_topics} unique topics, each <= {TOPIC_MAX_CHARS} characters. "
            "Return JSON only. Previous output:\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        payload = call_gemini_text(repair_prompt, GT_TEXT_MODEL, temperature=0.7)
        errors = validate_topics(payload, num_topics)
        if errors:
            raise EvaluationError("Topic generation failed: " + "; ".join(errors))
    return [topic.strip() for topic in payload]


def generate_infographic_plan(debug_dir: Path, topic: str) -> tuple[dict, Layout]:
    prompt = build_plan_prompt(topic)
    write_text(debug_dir / "gt_prompt.txt", prompt)
    payload = call_gemini_text(prompt, GT_TEXT_MODEL)
    layout, errors = validate_plan_payload(payload)
    if errors:
        repair_prompt = (
            prompt
            + "\n\nThe previous JSON failed validation with these errors:\n- "
            + "\n- ".join(errors)
            + "\n\nReturn corrected JSON only."
        )
        write_text(debug_dir / "gt_prompt_repair.txt", repair_prompt)
        payload = call_gemini_text(repair_prompt, GT_TEXT_MODEL)
        layout, errors = validate_plan_payload(payload)
        if errors:
            raise EvaluationError("; ".join(errors))
    if not layout:
        raise EvaluationError("Failed to validate GT layout")
    return payload, layout


def extract_image_bytes_from_response(response: Any) -> bytes:
    if hasattr(response, "generated_images") and response.generated_images:
        image = response.generated_images[0]
        if hasattr(image, "image") and hasattr(image.image, "image_bytes"):
            return image.image.image_bytes
        if hasattr(image, "image_bytes"):
            return image.image_bytes
    if hasattr(response, "candidates"):
        for candidate in response.candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                inline_data = getattr(part, "inline_data", None)
                if inline_data and hasattr(inline_data, "data"):
                    data = inline_data.data
                    if isinstance(data, bytes):
                        return data
                    if isinstance(data, str):
                        return base64.b64decode(data)
                data = getattr(part, "data", None)
                if isinstance(data, bytes):
                    return data
                if isinstance(data, str):
                    return base64.b64decode(data)
    raise EvaluationError("No image bytes found in Gemini response")


def generate_component_image(prompt: str) -> bytes:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=get_google_api_key())
    generate_images = getattr(client.models, "generate_images", None)
    if generate_images:
        config_cls = getattr(types, "GenerateImagesConfig", None)
        if config_cls:
            try:
                response = generate_images(
                    model=GT_IMAGE_MODEL,
                    prompt=prompt,
                    config=config_cls(number_of_images=1),
                )
                return extract_image_bytes_from_response(response)
            except Exception:
                pass

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )
    ]
    config = types.GenerateContentConfig(
        temperature=0.4,
        max_output_tokens=2048,
        response_modalities=["IMAGE"],
    )
    response = client.models.generate_content(
        model=GT_IMAGE_MODEL,
        contents=contents,
        config=config,
    )
    return extract_image_bytes_from_response(response)


def download_thumbnail(content_url: str, output_path: Path) -> None:
    req = Request(content_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req) as resp:
        data = resp.read()
    output_path.write_bytes(data)


def save_metrics_csv(path: Path, metrics: dict, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerow(metrics)


def save_element_metrics(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def match_text_regions(
    gt_regions: list[Region],
    pred_regions: list[Region],
    width: float,
    height: float,
) -> tuple[list[dict], set[int], set[int]]:
    if not gt_regions or not pred_regions:
        return [], set(), set()
    cost_matrix: list[list[float]] = []
    text_sims: dict[tuple[int, int], float] = {}
    ious: dict[tuple[int, int], float] = {}
    for i, gt in enumerate(gt_regions):
        row = []
        gt_text = normalize_text(gt.text)
        gt_bbox = normalize_bbox(gt.bbox_px, width, height)
        for j, pred in enumerate(pred_regions):
            pred_text = normalize_text(pred.text)
            pred_bbox = normalize_bbox(pred.bbox_px, width, height)
            iou = compute_bbox_iou(gt_bbox, pred_bbox)
            text_sim = similarity_ratio(gt_text, pred_text)
            cost = 0.7 * (1 - iou) + 0.3 * (1 - text_sim)
            row.append(cost)
            text_sims[(i, j)] = text_sim
            ious[(i, j)] = iou
        cost_matrix.append(row)
    row_idx, col_idx = linear_sum_assignment(cost_matrix)
    matches: list[dict] = []
    matched_gt: set[int] = set()
    matched_pred: set[int] = set()
    for r, c in zip(row_idx, col_idx, strict=False):
        iou = ious[(r, c)]
        text_sim = text_sims[(r, c)]
        if iou < 0.1 and text_sim < 0.8:
            continue
        gt = gt_regions[r]
        pred = pred_regions[c]
        gt_bbox_norm = normalize_bbox(gt.bbox_px, width, height)
        pred_bbox_norm = normalize_bbox(pred.bbox_px, width, height)
        offset_norm = bbox_center_offset_norm(gt_bbox_norm, pred_bbox_norm)
        dx_px = (gt_bbox_norm.center[0] - pred_bbox_norm.center[0]) * width
        dy_px = (gt_bbox_norm.center[1] - pred_bbox_norm.center[1]) * height
        offset_px = (dx_px * dx_px + dy_px * dy_px) ** 0.5
        gt_text = normalize_text(gt.text)
        pred_text = normalize_text(pred.text)
        cer = 0.0
        wer = 0.0
        if gt_text:
            cer = edit_distance(gt_text, pred_text) / max(len(gt_text), 1)
        gt_tokens = gt_text.split() if gt_text else []
        pred_tokens = pred_text.split() if pred_text else []
        if gt_tokens:
            wer = edit_distance(gt_tokens, pred_tokens) / max(len(gt_tokens), 1)
        matches.append(
            {
                "gt_id": gt.id,
                "pred_id": pred.id,
                "iou": iou,
                "text_sim": text_sim,
                "center_offset_norm": offset_norm,
                "center_offset_px": offset_px,
                "cer": cer,
                "wer": wer,
                "gt_text": gt.text or "",
                "pred_text": pred.text or "",
            }
        )
        matched_gt.add(r)
        matched_pred.add(c)
    return matches, matched_gt, matched_pred


def match_image_regions(
    gt_regions: list[Region],
    pred_regions: list[Region],
    width: float,
    height: float,
) -> tuple[list[dict], set[int], set[int]]:
    if not gt_regions or not pred_regions:
        return [], set(), set()
    cost_matrix: list[list[float]] = []
    ious: dict[tuple[int, int], float] = {}
    for i, gt in enumerate(gt_regions):
        row = []
        gt_bbox = normalize_bbox(gt.bbox_px, width, height)
        for j, pred in enumerate(pred_regions):
            pred_bbox = normalize_bbox(pred.bbox_px, width, height)
            iou = compute_bbox_iou(gt_bbox, pred_bbox)
            row.append(1 - iou)
            ious[(i, j)] = iou
        cost_matrix.append(row)
    row_idx, col_idx = linear_sum_assignment(cost_matrix)
    matches: list[dict] = []
    matched_gt: set[int] = set()
    matched_pred: set[int] = set()
    for r, c in zip(row_idx, col_idx, strict=False):
        iou = ious[(r, c)]
        if iou < 0.1:
            continue
        gt = gt_regions[r]
        pred = pred_regions[c]
        gt_bbox_norm = normalize_bbox(gt.bbox_px, width, height)
        pred_bbox_norm = normalize_bbox(pred.bbox_px, width, height)
        offset_norm = bbox_center_offset_norm(gt_bbox_norm, pred_bbox_norm)
        dx_px = (gt_bbox_norm.center[0] - pred_bbox_norm.center[0]) * width
        dy_px = (gt_bbox_norm.center[1] - pred_bbox_norm.center[1]) * height
        offset_px = (dx_px * dx_px + dy_px * dy_px) ** 0.5
        matches.append(
            {
                "gt_id": gt.id,
                "pred_id": pred.id,
                "iou": iou,
                "center_offset_norm": offset_norm,
                "center_offset_px": offset_px,
            }
        )
        matched_gt.add(r)
        matched_pred.add(c)
    return matches, matched_gt, matched_pred


def safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def safe_median(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 == 1:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2


def evaluate_layouts(
    gt_layout: Layout,
    pred_layout: Layout,
    width: float,
    height: float,
) -> tuple[dict, list[dict]]:
    gt_text = [r for r in gt_layout.regions if r.type == "text"]
    pred_text = [r for r in pred_layout.regions if r.type == "text"]
    gt_img = [r for r in gt_layout.regions if r.type == "image"]
    pred_img = [r for r in pred_layout.regions if r.type == "image"]

    text_matches, _matched_gt_text, _matched_pred_text = match_text_regions(
        gt_text, pred_text, width, height
    )
    img_matches, _matched_gt_img, _matched_pred_img = match_image_regions(
        gt_img, pred_img, width, height
    )

    n_gt_text = len(gt_text)
    n_pred_text = len(pred_text)
    n_match_text = len(text_matches)
    n_gt_img = len(gt_img)
    n_pred_img = len(pred_img)
    n_match_img = len(img_matches)

    metrics: dict[str, Any] = {
        "n_gt_text": n_gt_text,
        "n_pred_text": n_pred_text,
        "n_match_text": n_match_text,
        "n_fp_text": max(0, n_pred_text - n_match_text),
        "n_fn_text": max(0, n_gt_text - n_match_text),
        "n_gt_img": n_gt_img,
        "n_pred_img": n_pred_img,
        "n_match_img": n_match_img,
        "n_fp_img": max(0, n_pred_img - n_match_img),
        "n_fn_img": max(0, n_gt_img - n_match_img),
    }

    text_ious = [m["iou"] for m in text_matches]
    img_ious = [m["iou"] for m in img_matches]
    text_offsets_norm = [m["center_offset_norm"] for m in text_matches]
    text_offsets_px = [m["center_offset_px"] for m in text_matches]
    img_offsets_norm = [m["center_offset_norm"] for m in img_matches]
    img_offsets_px = [m["center_offset_px"] for m in img_matches]
    cers = [m["cer"] for m in text_matches]
    wers = [m["wer"] for m in text_matches]

    metrics.update(
        {
            "mean_iou_text": safe_mean(text_ious),
            "median_iou_text": safe_median(text_ious),
            "mean_iou_img": safe_mean(img_ious),
            "median_iou_img": safe_median(img_ious),
            "mean_center_offset_norm_text": safe_mean(text_offsets_norm),
            "mean_center_offset_px_text": safe_mean(text_offsets_px),
            "mean_center_offset_norm_img": safe_mean(img_offsets_norm),
            "mean_center_offset_px_img": safe_mean(img_offsets_px),
            "mean_cer": safe_mean(cers),
            "median_cer": safe_median(cers),
            "mean_wer": safe_mean(wers),
            "median_wer": safe_median(wers),
        }
    )

    metrics["element_recovery_rate_text"] = n_match_text / n_gt_text if n_gt_text else 0.0
    metrics["element_recovery_rate_img"] = n_match_img / n_gt_img if n_gt_img else 0.0
    total_gt = n_gt_text + n_gt_img
    total_match = n_match_text + n_match_img
    metrics["element_recovery_rate_all"] = total_match / total_gt if total_gt else 0.0

    thresholds = [0.5, 0.75, 0.9]
    for thr in thresholds:
        text_count = sum(1 for iou in text_ious if iou >= thr)
        img_count = sum(1 for iou in img_ious if iou >= thr)
        metrics[f"n_text_iou_ge_{str(thr).replace('.', '_')}"] = text_count
        metrics[f"frac_text_iou_ge_{str(thr).replace('.', '_')}"] = (
            text_count / n_match_text if n_match_text else 0.0
        )
        metrics[f"n_img_iou_ge_{str(thr).replace('.', '_')}"] = img_count
        metrics[f"frac_img_iou_ge_{str(thr).replace('.', '_')}"] = (
            img_count / n_match_img if n_match_img else 0.0
        )
        all_count = text_count + img_count
        metrics[f"n_all_iou_ge_{str(thr).replace('.', '_')}"] = all_count
        metrics[f"frac_all_iou_ge_{str(thr).replace('.', '_')}"] = (
            all_count / total_match if total_match else 0.0
        )

    correct_chars = 0
    total_chars = 0
    for match in text_matches:
        gt_text = normalize_text(match["gt_text"])
        pred_text = normalize_text(match["pred_text"])
        dist = edit_distance(gt_text, pred_text)
        correct_chars += max(0, len(gt_text) - dist)
        total_chars += len(gt_text)
    metrics["character_recovery_rate"] = correct_chars / total_chars if total_chars else 0.0

    element_rows: list[dict] = []
    for match in text_matches:
        row = {
            "type": "text",
            **match,
        }
        element_rows.append(row)
    for match in img_matches:
        row = {
            "type": "image",
            **match,
        }
        element_rows.append(row)

    return metrics, element_rows


@dataclass
class RunContext:
    run_id: str
    run_dir: Path
    debug_dir: Path
    temp_dir: Path
    keep_temp: bool


def build_run_id(out_dir: Path, base_timestamp: str, counter: int) -> str:
    while True:
        run_id = f"{base_timestamp}_{counter:04d}"
        if not (out_dir / run_id).exists():
            return run_id
        counter += 1


def create_run_context(
    out_dir: Path, base_timestamp: str, counter: int, keep_temp: bool
) -> RunContext:
    run_id = build_run_id(out_dir, base_timestamp, counter)
    run_dir = out_dir / run_id
    debug_dir = run_dir / "debug"
    temp_dir = run_dir / "temp"
    run_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    return RunContext(
        run_id=run_id, run_dir=run_dir, debug_dir=debug_dir, temp_dir=temp_dir, keep_temp=keep_temp
    )


def run_single_evaluation(
    ctx: RunContext,
    provider: str,
    seed: int,
    topic: str,
) -> dict:
    run_meta: dict[str, Any] = {
        "run_id": ctx.run_id,
        "timestamp_utc": utc_now_str(),
        "seed": seed,
        "provider": provider,
        "topic": topic,
        "gt_plan_model": GT_TEXT_MODEL,
        "gt_image_model": GT_IMAGE_MODEL,
        "status": "running",
        "git_commit": get_git_commit(),
    }
    write_json(ctx.run_dir / "run_meta.json", run_meta)

    start_total = time.perf_counter()
    slides_service = get_slides_service()
    gcs_bucket = get_gcs_bucket()

    LOGGER.info("Generating GT plan for run %s", ctx.run_id)
    payload, gt_layout = generate_infographic_plan(ctx.debug_dir, topic)
    gt_prompt_path = ctx.debug_dir / "gt_prompt.txt"
    if gt_prompt_path.exists():
        run_meta["gt_prompt_sha256"] = hashlib.sha256(gt_prompt_path.read_bytes()).hexdigest()
    concept = payload.get("concept")
    image_prompts = payload.get("image_prompts") or {}
    run_meta["concept"] = concept
    run_meta["image_prompt_count"] = len(image_prompts)
    image_prompts_path = ctx.run_dir / "image_prompts.json"
    write_json(image_prompts_path, image_prompts)
    run_meta["image_prompts_sha256"] = hashlib.sha256(
        json.dumps(image_prompts, sort_keys=True).encode("utf-8")
    ).hexdigest()

    gt_layout = postprocess_layout(gt_layout)
    gt_region_path = ctx.run_dir / "gt_region.json"
    write_json(gt_region_path, json.loads(gt_layout.to_json()))

    assets_dir = ctx.run_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    assets_meta: dict[str, Any] = {}
    image_paths: dict[str, Path] = {}

    for image_id, prompt in image_prompts.items():
        LOGGER.info("Generating image %s", image_id)
        image_bytes = generate_component_image(prompt)
        local_path = assets_dir / f"{image_id}.png"
        local_path.write_bytes(image_bytes)
        image_paths[image_id] = local_path
        assets_meta[image_id] = {
            "prompt": prompt,
            "model": GT_IMAGE_MODEL,
            "created_at": utc_now_str(),
        }

    write_json(ctx.run_dir / "assets_meta.json", assets_meta)

    uploader = GCSUploader(gcs_bucket)
    image_urls: dict[str, str] = {}
    for image_id, path in image_paths.items():
        object_name = f"evaluation/{ctx.run_id}/{image_id}_{get_file_hash(str(path))}.png"
        image_urls[image_id] = uploader.upload_png(str(path), object_name)

    gt_slide_id = f"GT_{ctx.run_id}"
    gt_presentation_id, _, _ = create_presentation(
        slides_service,
        title=f"Evaluation GT {ctx.run_id}",
        page_size="WIDESCREEN_16_9",
    )
    delete_initial_slide(slides_service, gt_presentation_id)
    build_slide(
        service=slides_service,
        presentation_id=gt_presentation_id,
        layout=gt_layout,
        slide_id=gt_slide_id,
        infographic_public_url=None,
        cropped_url_by_region_id=image_urls,
        place_background=False,
    )

    run_meta["gt_presentation_id"] = gt_presentation_id
    run_meta["gt_page_object_id"] = gt_slide_id

    LOGGER.info("Exporting GT thumbnail")
    thumb = None
    for mime_type in ("image/png", "PNG"):
        try:
            thumb = (
                slides_service.presentations()
                .pages()
                .getThumbnail(
                    presentationId=gt_presentation_id,
                    pageObjectId=gt_slide_id,
                    thumbnailProperties_mimeType=mime_type,
                    thumbnailProperties_thumbnailSize="LARGE",
                )
                .execute()
            )
            break
        except Exception:
            continue
    if not thumb:
        raise EvaluationError("Failed to fetch slide thumbnail")

    content_url = thumb.get("contentUrl")
    if not content_url:
        raise EvaluationError("Thumbnail contentUrl missing")
    gt_png_path = ctx.run_dir / "gt.png"
    download_thumbnail(content_url, gt_png_path)

    gt_width = int(thumb.get("width", CANVAS_WIDTH))
    gt_height = int(thumb.get("height", CANVAS_HEIGHT))
    run_meta["gt_png_width"] = gt_width
    run_meta["gt_png_height"] = gt_height

    LOGGER.info("Running VLM extraction on GT raster")
    start_vlm = time.perf_counter()
    vlm_provider = provider or get_default_provider()
    vlm_model = get_default_model()
    vlm_config = VLMConfig(provider=vlm_provider, model=vlm_model)
    pred_layout = extract_layout_from_image(gt_png_path, vlm_config)
    vlm_duration = time.perf_counter() - start_vlm
    run_meta["vlm_provider"] = vlm_provider
    run_meta["vlm_model"] = vlm_config.get_model()
    run_meta["t_vlm_s"] = vlm_duration

    start_post = time.perf_counter()
    pred_layout = postprocess_layout(pred_layout)
    run_meta["t_postprocess_s"] = time.perf_counter() - start_post

    pred_region_path = ctx.run_dir / "pred_region.json"
    write_json(pred_region_path, json.loads(pred_layout.to_json()))

    LOGGER.info("Reconstructing slide from predicted layout")
    start_slide = time.perf_counter()
    pred_presentation_id, _, _ = create_presentation(
        slides_service,
        title=f"Evaluation Recon {ctx.run_id}",
        page_size="WIDESCREEN_16_9",
    )
    delete_initial_slide(slides_service, pred_presentation_id)
    cropped_urls = {}
    if pred_layout.image_regions:
        cropped_urls = crop_and_upload_predicted_regions(gt_png_path, pred_layout, uploader, ctx)
    recon_slide_id = f"RECON_{ctx.run_id}"
    build_slide(
        service=slides_service,
        presentation_id=pred_presentation_id,
        layout=pred_layout,
        slide_id=recon_slide_id,
        infographic_public_url=None,
        cropped_url_by_region_id=cropped_urls,
        place_background=False,
    )
    run_meta["recon_presentation_id"] = pred_presentation_id
    run_meta["recon_page_object_id"] = recon_slide_id
    run_meta["t_slides_api_s"] = time.perf_counter() - start_slide

    metrics, element_rows = evaluate_layouts(gt_layout, pred_layout, gt_width, gt_height)

    metrics.update(
        {
            "run_id": ctx.run_id,
            "timestamp_utc": run_meta["timestamp_utc"],
            "concept": concept or "",
            "provider": vlm_provider,
            "seed": seed,
        }
    )
    if "t_vlm_s" in run_meta:
        metrics["t_vlm_s"] = run_meta["t_vlm_s"]
    if "t_postprocess_s" in run_meta:
        metrics["t_postprocess_s"] = run_meta["t_postprocess_s"]
    if "t_slides_api_s" in run_meta:
        metrics["t_slides_api_s"] = run_meta["t_slides_api_s"]
    run_meta["t_total_s"] = time.perf_counter() - start_total
    metrics["t_total_s"] = run_meta["t_total_s"]

    string_cols = {"run_id", "timestamp_utc", "concept", "provider"}
    metrics_row = {}
    for col in METRICS_COLUMNS:
        if col in string_cols:
            metrics_row[col] = metrics.get(col, "")
        else:
            metrics_row[col] = metrics.get(col, 0.0)
    metrics_path = ctx.run_dir / "metrics.csv"
    save_metrics_csv(metrics_path, metrics_row, METRICS_COLUMNS)
    save_element_metrics(ctx.debug_dir / "element_metrics.csv", element_rows)

    run_meta["status"] = "success"
    write_json(ctx.run_dir / "run_meta.json", run_meta)

    if not ctx.keep_temp:
        shutil.rmtree(ctx.temp_dir, ignore_errors=True)

    return run_meta


def crop_and_upload_predicted_regions(
    infographic_path: Path,
    layout: Layout,
    uploader: GCSUploader,
    ctx: RunContext,
) -> dict[str, str]:
    from images2slides.uploader import crop_and_upload_regions

    cropped_urls = crop_and_upload_regions(
        infographic_path=str(infographic_path),
        layout=layout,
        uploader=uploader,
        prefix=f"{ctx.run_id}_",
        temp_dir=str(ctx.temp_dir),
    )
    return cropped_urls


def collate_runs(out_dir: Path) -> None:
    try:
        import polars as pl
        import polars.selectors as cs
    except ImportError as exc:
        raise EvaluationError("polars is required for --collate") from exc

    run_dirs = [p for p in out_dir.iterdir() if p.is_dir()]
    frames = []
    string_cols = {"run_id", "timestamp_utc", "concept", "provider"}
    for run_dir in run_dirs:
        meta_path = run_dir / "run_meta.json"
        if meta_path.exists():
            meta = load_json(meta_path)
            if meta.get("status") != "success":
                continue
        metrics_path = run_dir / "metrics.csv"
        if metrics_path.exists():
            frame = pl.read_csv(metrics_path)
            for col in METRICS_COLUMNS:
                if col not in frame.columns:
                    default = "" if col in string_cols else 0.0
                    frame = frame.with_columns(pl.lit(default).alias(col))
            frame = frame.select([col for col in METRICS_COLUMNS if col in frame.columns])
            frames.append(frame)
    if not frames:
        print("No metrics.csv files found to collate")
        return

    df = pl.concat(frames, how="vertical")
    eval_dir = out_dir.parent
    eval_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = eval_dir / "evaluation-metrics.csv"
    df.write_csv(metrics_path)

    numeric_cols = df.select(cs.numeric()).columns

    def build_summary(frame: pl.DataFrame, label: str | None = None) -> pl.DataFrame:
        agg_exprs = []
        for col in numeric_cols:
            agg_exprs.append(pl.col(col).mean().alias(f"{col}_mean"))
            agg_exprs.append(pl.col(col).std().alias(f"{col}_std"))
        summary = frame.select(agg_exprs)
        if label is not None:
            summary = summary.with_columns(pl.lit(label).alias("provider"))
        return summary

    summary_all = build_summary(df, "all")
    if "provider" in df.columns:
        summary_by = df.group_by("provider").agg(
            [pl.col(col).mean().alias(f"{col}_mean") for col in numeric_cols]
            + [pl.col(col).std().alias(f"{col}_std") for col in numeric_cols]
        )
        summary_by = summary_by.select(summary_all.columns)
        summary = pl.concat([summary_all, summary_by], how="vertical")
    else:
        summary = summary_all

    summary_path = eval_dir / "evaluation-summary.csv"
    summary.write_csv(summary_path)

    def compute_global_fracs(frame: pl.DataFrame) -> list[tuple[str, float]]:
        results: list[tuple[str, float]] = []
        thresholds = ["0_5", "0_75"]
        for thr in thresholds:
            text_sum = frame.get_column(f"n_text_iou_ge_{thr}").sum()
            img_sum = frame.get_column(f"n_img_iou_ge_{thr}").sum()
            match_text = frame.get_column("n_match_text").sum()
            match_img = frame.get_column("n_match_img").sum()
            text_frac = text_sum / match_text if match_text else 0.0
            img_frac = img_sum / match_img if match_img else 0.0
            threshold_label = thr.replace("_", ".")
            results.append((f"Global text IoU ≥ {threshold_label}", text_frac))
            results.append((f"Global image IoU ≥ {threshold_label}", img_frac))
        return results

    global_fracs = compute_global_fracs(df)
    run_count = df.height
    summary_row = summary_all.to_dicts()[0]

    def format_stat(value: float) -> str:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "nan"
        return f"{value:.3f}"

    def humanize_metric(col: str) -> str:
        def label_kind(kind: str) -> str:
            return {
                "text": "Text",
                "img": "Image",
                "all": "Overall",
            }.get(kind, kind.title())

        if col == "seed":
            return "Seed"
        if col.startswith("n_gt_"):
            return f"GT {label_kind(col[5:])} count"
        if col.startswith("n_pred_"):
            return f"Predicted {label_kind(col[7:])} count"
        if col.startswith("n_match_"):
            return f"Matched {label_kind(col[8:])} count"
        if col.startswith("n_fp_"):
            return f"False positives ({label_kind(col[5:])})"
        if col.startswith("n_fn_"):
            return f"False negatives ({label_kind(col[5:])})"
        if col.startswith("element_recovery_rate_"):
            suffix = col.replace("element_recovery_rate_", "")
            return f"Element recovery rate ({label_kind(suffix)})"
        if col.startswith("mean_center_offset_norm_"):
            suffix = col.replace("mean_center_offset_norm_", "")
            return f"Mean center offset (normalized, {label_kind(suffix)})"
        if col.startswith("mean_center_offset_px_"):
            suffix = col.replace("mean_center_offset_px_", "")
            return f"Mean center offset (px, {label_kind(suffix)})"
        if col.startswith("mean_iou_"):
            suffix = col.replace("mean_iou_", "")
            return f"Mean IoU ({label_kind(suffix)})"
        if col.startswith("median_iou_"):
            suffix = col.replace("median_iou_", "")
            return f"Median IoU ({label_kind(suffix)})"
        if col.startswith("mean_cer"):
            return "Mean CER"
        if col.startswith("median_cer"):
            return "Median CER"
        if col.startswith("mean_wer"):
            return "Mean WER"
        if col.startswith("median_wer"):
            return "Median WER"
        if col == "character_recovery_rate":
            return "Character recovery rate"
        if col.startswith("t_") and col.endswith("_s"):
            label = col.replace("t_", "").replace("_s", "")
            return {
                "vlm": "VLM time (s)",
                "postprocess": "Postprocess time (s)",
                "slides_api": "Slides API time (s)",
                "total": "Total time (s)",
            }.get(label, f"{label.replace('_', ' ').title()} time (s)")

        match = re.match(r"n_(text|img|all)_iou_ge_(\d_\d+)", col)
        if match:
            kind, thr = match.groups()
            return f"{label_kind(kind)} IoU ≥ {thr.replace('_', '.')} (count)"
        match = re.match(r"frac_(text|img|all)_iou_ge_(\d_\d+)", col)
        if match:
            kind, thr = match.groups()
            return f"{label_kind(kind)} IoU ≥ {thr.replace('_', '.')} (fraction)"

        return col.replace("_", " ").title()

    print(f"Runs: {run_count}")
    print(
        "Overall recovery rate (mean ± std): "
        f"{format_stat(summary_row.get('element_recovery_rate_all_mean'))} ± "
        f"{format_stat(summary_row.get('element_recovery_rate_all_std'))}"
    )
    print(
        "Mean IoU (text) (mean ± std): "
        f"{format_stat(summary_row.get('mean_iou_text_mean'))} ± "
        f"{format_stat(summary_row.get('mean_iou_text_std'))}"
    )
    print(
        "Mean IoU (image) (mean ± std): "
        f"{format_stat(summary_row.get('mean_iou_img_mean'))} ± "
        f"{format_stat(summary_row.get('mean_iou_img_std'))}"
    )
    print(
        "Mean CER (mean ± std): "
        f"{format_stat(summary_row.get('mean_cer_mean'))} ± "
        f"{format_stat(summary_row.get('mean_cer_std'))}"
    )
    print(
        "Mean WER (mean ± std): "
        f"{format_stat(summary_row.get('mean_wer_mean'))} ± "
        f"{format_stat(summary_row.get('mean_wer_std'))}"
    )
    for label, value in global_fracs:
        print(f"{label}: {value:.3f}")

    def is_zero(value: float | None) -> bool:
        if value is None:
            return True
        if isinstance(value, float) and math.isnan(value):
            return True
        return math.isclose(float(value), 0.0, abs_tol=1e-12)

    def should_skip_metric(col: str, mean_val: float | None, std_val: float | None) -> bool:
        if "_0_9" in col:
            return True
        return False

    def format_metric(col: str, mean_val: float | None, std_val: float | None) -> str:
        if col == "t_total_s":
            return f"{humanize_metric(col)}: {format_stat(mean_val)}"
        return f"{humanize_metric(col)}: {format_stat(mean_val)} ± {format_stat(std_val)}"

    metric_groups = [
        ["n_gt_text", "n_pred_text", "n_match_text", "n_fp_text", "n_fn_text"],
        ["n_gt_img", "n_pred_img", "n_match_img", "n_fp_img", "n_fn_img"],
        [
            "element_recovery_rate_text",
            "element_recovery_rate_img",
            "element_recovery_rate_all",
        ],
        ["mean_iou_text", "median_iou_text", "mean_iou_img", "median_iou_img"],
        [
            "mean_center_offset_norm_text",
            "mean_center_offset_px_text",
            "mean_center_offset_norm_img",
            "mean_center_offset_px_img",
        ],
        ["mean_cer", "median_cer", "mean_wer", "median_wer", "character_recovery_rate"],
        [
            "n_text_iou_ge_0_5",
            "frac_text_iou_ge_0_5",
            "n_text_iou_ge_0_75",
            "frac_text_iou_ge_0_75",
            "n_img_iou_ge_0_5",
            "frac_img_iou_ge_0_5",
            "n_img_iou_ge_0_75",
            "frac_img_iou_ge_0_75",
            "n_all_iou_ge_0_5",
            "frac_all_iou_ge_0_5",
            "n_all_iou_ge_0_75",
            "frac_all_iou_ge_0_75",
        ],
        ["t_vlm_s", "t_slides_api_s", "t_total_s"],
    ]

    print("\nMetric summary (mean ± std):")
    divider = "-" * 40
    for group in metric_groups:
        lines: list[str] = []
        for col in group:
            if col in string_cols:
                continue
            mean_key = f"{col}_mean"
            std_key = f"{col}_std"
            if mean_key not in summary_row:
                continue
            mean_val = summary_row.get(mean_key)
            std_val = summary_row.get(std_key)
            if should_skip_metric(col, mean_val, std_val):
                continue
            lines.append(format_metric(col, mean_val, std_val))
        if not lines:
            continue
        print(divider)
        for line in lines:
            print(line)
        print(divider)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluation pipeline for images2slides")
    parser.add_argument("-n", "--num-runs", type=int, default=DEFAULT_NUM_RUNS)
    parser.add_argument("--out-dir", type=str, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Fixed seed for all runs (omit to randomize per run)",
    )
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--collate", action="store_true")
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    out_dir = Path(args.out_dir)

    if args.collate:
        collate_runs(out_dir)
        return 0

    try:
        topics = generate_topics(args.num_runs)
    except EvaluationError as exc:
        LOGGER.error("Topic generation failed: %s", exc)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    base_timestamp = utc_now_str()
    seed_rng = random.Random(args.seed) if args.seed is not None else random.SystemRandom()
    failures = 0
    for i, topic in enumerate(topics, start=1):
        ctx = create_run_context(out_dir, base_timestamp, i, args.keep_temp)
        run_seed = args.seed if args.seed is not None else seed_rng.randrange(MAX_RANDOM_SEED)
        try:
            random.seed(run_seed)
            run_single_evaluation(
                ctx,
                args.provider or get_default_provider(),
                run_seed,
                topic,
            )
        except (EvaluationError, SlidesAPIError, VLMExtractionError, UploadError) as exc:
            failures += 1
            LOGGER.error("Run %s failed: %s", ctx.run_id, exc)
            run_meta = load_json(ctx.run_dir / "run_meta.json")
            run_meta["status"] = "failed"
            run_meta["error"] = str(exc)
            write_json(ctx.run_dir / "run_meta.json", run_meta)
        except Exception as exc:
            failures += 1
            LOGGER.exception("Run %s failed with unexpected error", ctx.run_id)
            run_meta = load_json(ctx.run_dir / "run_meta.json")
            run_meta["status"] = "failed"
            run_meta["error"] = str(exc)
            write_json(ctx.run_dir / "run_meta.json", run_meta)

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
