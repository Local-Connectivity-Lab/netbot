import json
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
from threading import Lock

log = logging.getLogger(__name__)

QUEUE_FILE = Path("/home/scn/netbot-redacted/redaction_queue.json")


class RedactionQueue:
    """Manages redaction jobs from both IMAP and Discord edits"""
    
    def __init__(self):
        if Path("/app").exists():
            # Running in Docker container (netbot)
            self.queue_file = Path("/app/redaction_queue.json")
        else:
            # Running on host (threader-daemon)
            self.queue_file = Path("/home/scn/netbot-redacted/redaction_queue.json")
        self.lock = Lock()
        self._ensure_queue_file()
    
    def _ensure_queue_file(self):
        """Create queue file if it doesn't exist"""
        if not self.queue_file.exists():
            self._save_state({"queue": [], "locked_tickets": {}})
    
    def _load_state(self) -> Dict:
        """Load queue state from disk"""
        try:
            with open(self.queue_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            log.error(f"Error loading queue: {e}, resetting")
            return {"queue": [], "locked_tickets": {}}
    
    def _save_state(self, state: Dict):
        """Save queue state to disk"""
        with open(self.queue_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def add_edit_job(self, ticket_id: int, description: str, user_info: dict) -> str:
        """
        Add ticket edit to queue
        Returns: job_id
        """
        with self.lock:
            state = self._load_state()
            
            job_id = f"edit-{ticket_id}-{int(datetime.now().timestamp())}"
            job = {
                "id": job_id,
                "type": "edit",
                "ticket_id": ticket_id,
                "description": description,
                "user": user_info,
                "timestamp": datetime.now().isoformat(),
                "status": "pending"
            }
            
            state["queue"].append(job)
            self._save_state(state)
            
            log.info(f"Added edit job to queue: {job_id}")
            return job_id
    
    def get_next_job(self) -> Optional[Dict]:
        """Get next pending job (FIFO)"""
        with self.lock:
            state = self._load_state()
            log.info(f"Checking queue: {len(state['queue'])} total jobs")
            
            for job in state["queue"]:
                log.info(f"Job {job['id']}: status={job.get('status', 'NO STATUS')}")
                if job["status"] == "pending":
                    log.info(f"Found pending job: {job['id']}")
                    return job
            
            log.info("No pending jobs found")
            return None
    
    def mark_processing(self, job_id: str):
        """Mark job as processing"""
        with self.lock:
            state = self._load_state()
            
            for job in state["queue"]:
                if job["id"] == job_id:
                    job["status"] = "processing"
                    break
            
            self._save_state(state)
    
    def mark_complete(self, job_id: str):
        """Mark job as complete and remove from queue"""
        with self.lock:
            state = self._load_state()
            
            state["queue"] = [j for j in state["queue"] if j["id"] != job_id]
            self._save_state(state)
            
            log.info(f"Completed job: {job_id}")
    
    def mark_failed(self, job_id: str, error: str):
        """Mark job as failed"""
        with self.lock:
            state = self._load_state()
            
            for job in state["queue"]:
                if job["id"] == job_id:
                    job["status"] = "failed"
                    job["error"] = error
                    break
            
            self._save_state(state)
    
    def lock_ticket(self, ticket_id: int, job_type: str = "edit"):
        """Lock ticket during redaction"""
        with self.lock:
            state = self._load_state()
            
            state["locked_tickets"][str(ticket_id)] = {
                "locked_at": datetime.now().isoformat(),
                "type": job_type
            }
            
            self._save_state(state)
            log.info(f"Locked ticket #{ticket_id}")
    
    def unlock_ticket(self, ticket_id: int):
        """Unlock ticket after completion"""
        with self.lock:
            state = self._load_state()
            
            if str(ticket_id) in state["locked_tickets"]:
                del state["locked_tickets"][str(ticket_id)]
                self._save_state(state)
                log.info(f"Unlocked ticket #{ticket_id}")
    
    def is_locked(self, ticket_id: int) -> bool:
        """Check if ticket is currently being redacted"""
        state = self._load_state()
        return str(ticket_id) in state["locked_tickets"]
    
    def has_pending_jobs(self) -> bool:
        """Check if there are any pending jobs"""
        state = self._load_state()
        return any(j["status"] == "pending" for j in state["queue"])