"""
Logger service for tracking system events and document operations.
Provides functions for logging operations in a structured format.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Log paths
SYSTEM_LOG_PATH = "storage/logs/system.log"
AUDIT_LOG_PATH = "storage/logs/audit.log"
UPLOAD_LOG_PATH = "storage/logs/uploads.log"


def _ensure_log_dirs() -> None:
    """Ensure log directories exist."""
    os.makedirs(os.path.dirname(SYSTEM_LOG_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(UPLOAD_LOG_PATH), exist_ok=True)


def log_system_event(event_type: str, details: Dict[str, Any]) -> None:
    """
    Log a system event.
    
    Args:
        event_type: Type of event (e.g., "startup", "error")
        details: Event details
    """
    _ensure_log_dirs()
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        **details
    }
    
    try:
        with open(SYSTEM_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to system log: {e}")


def log_audit_event(user: str, action: str, resource: str, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an audit event for user actions.
    
    Args:
        user: User who performed the action
        action: Action performed (e.g., "update", "delete")
        resource: Resource affected (e.g., "document", "page")
        details: Optional additional details
    """
    _ensure_log_dirs()
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user": user,
        "action": action,
        "resource": resource,
        "details": details or {}
    }
    
    try:
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to audit log: {e}")


def log_upload(doc_id: str, filename: str, status: str) -> None:
    """
    Log a document upload event.
    
    Args:
        doc_id: Document identifier
        filename: Original filename
        status: Upload status (e.g., "success", "duplicate")
    """
    _ensure_log_dirs()
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "doc_id": doc_id,
        "filename": filename,
        "status": status
    }
    
    try:
        with open(UPLOAD_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to upload log: {e}")


def get_recent_uploads(limit: int = 100) -> list:
    """
    Get recent upload events.
    
    Args:
        limit: Maximum number of events to return
        
    Returns:
        List of upload events
    """
    _ensure_log_dirs()
    
    try:
        if not os.path.exists(UPLOAD_LOG_PATH):
            return []
            
        with open(UPLOAD_LOG_PATH, "r") as f:
            lines = f.readlines()
            
        # Parse JSON lines and reverse to get most recent first
        uploads = []
        for line in lines:
            try:
                upload = json.loads(line.strip())
                uploads.append(upload)
            except json.JSONDecodeError:
                pass
                
        # Return most recent entries up to limit
        return uploads[-limit:][::-1]
        
    except Exception as e:
        logger.error(f"Failed to read upload log: {e}")
        return []


def get_audit_events(user: Optional[str] = None, action: Optional[str] = None, limit: int = 100) -> list:
    """
    Get audit events, optionally filtered by user or action.
    
    Args:
        user: Filter by user
        action: Filter by action
        limit: Maximum number of events to return
        
    Returns:
        List of audit events
    """
    _ensure_log_dirs()
    
    try:
        if not os.path.exists(AUDIT_LOG_PATH):
            return []
            
        with open(AUDIT_LOG_PATH, "r") as f:
            lines = f.readlines()
            
        # Parse JSON lines and filter
        events = []
        for line in lines:
            try:
                event = json.loads(line.strip())
                
                # Apply filters
                if user and event.get("user") != user:
                    continue
                if action and event.get("action") != action:
                    continue
                    
                events.append(event)
            except json.JSONDecodeError:
                pass
                
        # Return most recent entries up to limit
        return events[-limit:][::-1]
        
    except Exception as e:
        logger.error(f"Failed to read audit log: {e}")
        return []