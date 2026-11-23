"""FastAPI route for Audit Logs with dedicated table and filtering."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.audit_history_ops import audit_logs_statistics, list_audit_logs as query_audit_logs
from routes.auth import get_current_admin

router = APIRouter(tags=["audit-logs"])


@router.get("/api/audit-logs")
def list_audit_logs(
    search: Optional[str] = Query(default=None, max_length=200),
    actor: Optional[str] = Query(default=None, max_length=100),
    action: Optional[str] = Query(default=None, max_length=80),
    category: Optional[str] = Query(default=None, max_length=50),
    days: Optional[int] = Query(default=7, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0, le=10000),
    current_admin: dict = Depends(get_current_admin),
):
    """Get audit logs with deep filtering capabilities."""
    # Check admin access
    if current_admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    
    # Validate days parameter
    if days is not None and (days < 1 or days > 365):
        raise HTTPException(status_code=422, detail="Days must be between 1 and 365")
    
    # Calculate date range
    from datetime import timedelta
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    try:
        payload = query_audit_logs(
            start_iso=start_date.isoformat(),
            end_iso=end_date.isoformat(),
            search=search,
            actor=actor,
            action=action,
            category=category,
            limit=limit,
            offset=offset,
        )
        return {
            **payload,
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/audit-logs/statistics")
def get_audit_logs_statistics(
    days: Optional[int] = Query(default=7, ge=1, le=365),
    current_admin: dict = Depends(get_current_admin),
):
    """Get statistics for audit logs dashboard."""
    if current_admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    
    from datetime import timedelta
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    try:
        stats = audit_logs_statistics(
            start_iso=start_date.isoformat(),
            end_iso=end_date.isoformat(),
        )
        return {
            **stats,
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/audit-logs/export")
def export_audit_logs(
    format: str = Query(default="csv", max_length=4),
    search: Optional[str] = Query(default=None, max_length=200),
    actor: Optional[str] = Query(default=None, max_length=100),
    action: Optional[str] = Query(default=None, max_length=80),
    category: Optional[str] = Query(default=None, max_length=50),
    days: Optional[int] = Query(default=7, ge=1, le=365),
    current_admin: dict = Depends(get_current_admin),
):
    """Export audit logs as CSV or JSON."""
    if current_admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    
    if format not in ("csv", "json"):
        raise HTTPException(status_code=422, detail="Format must be csv or json")
    
    # Get the data
    import json as json_module
    from fastapi.responses import Response
    
    logs_response = list_audit_logs(
        search=search, actor=actor, action=action, category=category, days=days, 
        limit=10000, offset=0, current_admin=current_admin
    )
    
    events = logs_response["events"]
    
    if format == "csv":
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = ["ID", "Timestamp", "Actor", "Action", "Category", "Status", "Description"]
        writer.writerow(headers)
        
        # Write data
        for event in events:
            row = [
                event.get("id", ""),
                event.get("timestamp", ""),
                event.get("actor", ""),
                event.get("action", ""),
                event.get("category", ""),
                event.get("status", ""),
                event.get("description", "")
            ]
            writer.writerow(row)
        
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=audit-logs.csv",
                "Content-Type": "text/csv"
            }
        )
    else:  # JSON
        return Response(
            content=json_module.dumps(events, indent=2, default=str),
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=audit-logs.json",
                "Content-Type": "application/json"
            }
        )


