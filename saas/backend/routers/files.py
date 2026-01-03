"""File serving endpoints."""

from fastapi import APIRouter, HTTPException, Request, Response

from ..storage.base import get_storage

router = APIRouter()


@router.get("/files/{file_path:path}")
async def serve_file(file_path: str) -> Response:
    """Serve a file from storage.
    
    For local storage, this returns the file directly.
    For cloud storage, this would redirect to a signed URL.
    
    Args:
        file_path: Path to the file in storage.
        
    Returns:
        File contents.
        
    Raises:
        HTTPException: If file not found.
    """
    storage = get_storage()
    
    try:
        if not await storage.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        data = await storage.get(file_path)
        metadata = await storage.get_metadata(file_path)
        
        return Response(
            content=data,
            media_type=metadata.get("content_type", "application/octet-stream"),
            headers={
                "Cache-Control": "public, max-age=3600",
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/files/{file_path:path}")
async def upload_file(file_path: str, request: Request) -> dict:
    """Upload a file to storage.
    
    This endpoint is used by the frontend to upload files directly
    when using local storage (presigned URLs point here).
    
    Args:
        file_path: Path to store the file.
        request: HTTP request with file body.
        
    Returns:
        Success status.
    """
    storage = get_storage()
    
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "application/octet-stream")
        await storage.put(file_path, body, content_type)
        return {"status": "ok", "storage_key": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))