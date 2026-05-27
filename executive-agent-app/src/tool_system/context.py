import time

class ToolContext:
    def __init__(self):
        # Existing fields
        self.workspace_path = None
        self.session_id = None

        # Goal tracking (set by AgentLoop.run)
        self.goal: str = ""
        self.current_goal: str = ""

        # New fields needed
        self.user_profile = None
        self.job_answers = None
        self.active_agent = "commander"
        self.active_workflow = None
        self.current_app = None
        self.browser_session = None
        self.workflow_buffer: list = []
        self.workflow_recording = False

        from .permissions import PermissionManager
        self.permission_manager = PermissionManager()

        
    def load_profile(self, profile_store):
        self.user_profile = getattr(profile_store, "user_profile", {})
        self.job_answers = getattr(profile_store, "job_answers", {})
        
    def get(self, key, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key):
        return getattr(self, key)
        
    def __setitem__(self, key, value):
        setattr(self, key, value)
        
    def start_workflow_recording(self, name, category):
        self.workflow_recording = True
        self.active_workflow = {
            "name": name,
            "category": category,
            "steps": [],
            "started_at": time.time()
        }
        
    def record_step(self, action, params, result):
        if self.workflow_recording and self.active_workflow:
            self.active_workflow["steps"].append({
                "action": action,
                "params": params,
                "result": result,
                "timestamp": time.time()
            })
