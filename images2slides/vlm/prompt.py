"""VLM prompt templates for infographic region extraction."""

SYSTEM_PROMPT = """You are an expert at analyzing infographic images and extracting structured layout information for reconstruction in Google Slides.

Your task is to analyze the provided infographic image and output a JSON object describing all visual elements (text regions and image regions) with their precise bounding boxes.

CRITICAL REQUIREMENTS:
1. Output MUST be valid JSON only - no markdown, no commentary, no explanation
2. All bounding boxes MUST be in original image pixel coordinates
3. Extract ALL visible text accurately and completely
4. Group related text logically (e.g., a paragraph as one region, not line-by-line)
5. Identify non-text visual elements (icons, logos, charts, diagrams) as image regions
6. Use reading order: top to bottom, left to right for the `order` field
7. Ensure regions do not overlap unless absolutely necessary"""

EXTRACTION_PROMPT = """Analyze this infographic image and output a JSON object with the following structure:

{
  "image_px": {"width": <int>, "height": <int>},
  "regions": [
    {
      "id": "<unique_string_id>",
      "order": <int starting at 1>,
      "type": "text" | "image",
      "bbox_px": {"x": <number>, "y": <number>, "w": <number>, "h": <number>},
      "text": "<extracted text, required for type=text, omit for type=image>",
      "style": {
        "font_family": "<string or null>",
        "font_size_pt": <number or null>,
        "bold": <true|false|null>
      },
      "crop_from_infographic": <true|false>,
      "confidence": <number 0 to 1>,
      "notes": "<string or null>"
    }
  ]
}

FIELD RULES:
- id: Use descriptive names like "title", "subtitle", "heading_1", "body_text_1", "icon_logo", "chart_1"
- order: Integer starting at 1, following reading order (top-to-bottom, left-to-right)
- type: "text" for text regions, "image" for visual elements (icons, logos, charts, photos)
- bbox_px: Bounding box in pixels - x,y is top-left corner, w,h are width and height
- text: The exact text content (required for type="text", omit entirely for type="image")
- style: Best-effort guess at font styling (null values are acceptable if uncertain)
- crop_from_infographic: true if the image region should be cropped from the original infographic
- confidence: 0.0 to 1.0 indicating your confidence in the extraction accuracy
- notes: null unless you need to explain uncertainty or overlapping regions

IMPORTANT:
- The image dimensions (width, height) must match the actual image you're analyzing
- Be VERY precise with bounding boxes - they should TIGHTLY enclose ONLY the specific element
- For IMAGE regions (icons, logos, charts, diagrams):
  * Draw the bounding box around ONLY the visual graphic itself
  * EXCLUDE any text labels, titles, or captions that appear above, below, or around the image - those should be separate TEXT regions
  * Do NOT crop off any part of the actual graphic - include the full visual element
  * If there's a circular icon, the bbox should tightly fit just the circle, not any nearby text
  * The goal is to capture the complete image WITHOUT any surrounding text that can be extracted separately
- For TEXT regions: include only the text, not decorative backgrounds or containers
- Text and image regions should NOT overlap - if text appears next to an icon, they are separate regions
- Prefer fewer, larger regions over many small ones (group paragraphs together)

Return ONLY the JSON object, nothing else."""


def get_extraction_prompt() -> str:
    """Get the full extraction prompt for VLM."""
    return EXTRACTION_PROMPT


def get_system_prompt() -> str:
    """Get the system prompt for VLM."""
    return SYSTEM_PROMPT
