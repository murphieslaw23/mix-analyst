from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/notifications")
def list_notifications():
    """List notifications (stub: implemented later)."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/notifications/{id}/read")
def mark_notification_read(id: str):
    """Mark a notification as read (stub: implemented later)."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/notifications/{id}/dismiss")
def dismiss_notification(id: str):
    """Dismiss a notification (stub: implemented later)."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/push/subscriptions")
def create_push_subscription():
    """Create a push subscription (stub: implemented later)."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/push/subscriptions/{id}")
def delete_push_subscription(id: str):
    """Delete a push subscription (stub: implemented later)."""
    raise HTTPException(status_code=501, detail="Not implemented")
