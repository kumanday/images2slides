# Evaluation Script

## Usage

Generate runs:

```bash
uv run evaluation.py -n 10 --provider google
```

Collate existing runs:

```bash
uv run evaluation.py --collate
```

Collation requires `polars` to be installed in the environment.

Required environment variables:

- `GOOGLE_API_KEY` (Gemini text + image generation)
- `GCS_BUCKET` (public bucket for component images and crops)
- `CLIENT_SECRET_PATH` or `SERVICE_ACCOUNT_PATH` (Slides API)

The script loads a `.env` file from the current directory or the nearest parent
containing `pyproject.toml`, so the same variables can be reused.

## Output Layout

```
evaluation/
  runs/
    <run_id>/
      run_meta.json
      gt_region.json
      image_prompts.json
      assets/
      gt.png
      pred_region.json
      metrics.csv
      debug/
        element_metrics.csv
```

## Metrics Columns

### Run Metadata

- `run_id`: unique run identifier
- `timestamp_utc`: UTC timestamp for the run
- `concept`: infographic concept string
- `provider`: VLM provider used for extraction
- `seed`: RNG seed

### Counts

- `n_gt_text`, `n_pred_text`, `n_match_text`, `n_fp_text`, `n_fn_text`
- `n_gt_img`, `n_pred_img`, `n_match_img`, `n_fp_img`, `n_fn_img`

### Recovery Rates

- `element_recovery_rate_text`
- `element_recovery_rate_img`
- `element_recovery_rate_all`

### Geometry

- `mean_iou_text`, `median_iou_text`
- `mean_iou_img`, `median_iou_img`
- `mean_center_offset_norm_text`, `mean_center_offset_px_text`
- `mean_center_offset_norm_img`, `mean_center_offset_px_img`

### Text Quality

- `mean_cer`, `median_cer`
- `mean_wer`, `median_wer`
- `character_recovery_rate`

### IoU Thresholds

For each threshold (0.5, 0.75, 0.9):

- `n_text_iou_ge_<thr>`, `frac_text_iou_ge_<thr>`
- `n_img_iou_ge_<thr>`, `frac_img_iou_ge_<thr>`
- `n_all_iou_ge_<thr>`, `frac_all_iou_ge_<thr>`

### Timing

- `t_vlm_s`: VLM extraction time (s)
- `t_slides_api_s`: slide reconstruction time (s)
- `t_total_s`: total run time (s)
