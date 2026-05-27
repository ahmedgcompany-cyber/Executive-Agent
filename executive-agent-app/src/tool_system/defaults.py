class ToolRegistry:
    def __init__(self):
        self.tools = {}
        
    def register_tool(self, name, func):
        self.tools[name] = func
        
    def get_tool(self, name):
        return self.tools.get(name)

def register_extended_tools(registry, runtime_context):
    """Register extended tools from the runtime context."""
    
    # Browser tools
    if "browser_tools" in runtime_context:
        bt = runtime_context["browser_tools"]
        if hasattr(bt, "browser_open"): registry.register_tool("browser_open", bt.browser_open)
        if hasattr(bt, "browser_click"): registry.register_tool("browser_click", bt.browser_click)
        if hasattr(bt, "browser_type"): registry.register_tool("browser_type", bt.browser_type)
        if hasattr(bt, "browser_select"): registry.register_tool("browser_select", bt.browser_select)
        if hasattr(bt, "browser_upload"): registry.register_tool("browser_upload", bt.browser_upload)
        if hasattr(bt, "browser_screenshot"): registry.register_tool("browser_screenshot", bt.browser_screenshot)
        if hasattr(bt, "browser_extract_fields"): registry.register_tool("browser_extract_fields", bt.browser_extract_fields)
        if hasattr(bt, "browser_wait_for"): registry.register_tool("browser_wait_for", bt.browser_wait_for)
        if hasattr(bt, "browser_navigate"): registry.register_tool("browser_navigate", bt.browser_navigate)
        
    # Desktop tools
    if "desktop_tools" in runtime_context:
        dt = runtime_context["desktop_tools"]
        if hasattr(dt, "launch_application"): registry.register_tool("launch_application", dt.launch_application)
        if hasattr(dt, "focus_window"): registry.register_tool("focus_window", dt.focus_window)
        if hasattr(dt, "list_controls"): registry.register_tool("list_controls", dt.list_controls)
        if hasattr(dt, "click_control"): registry.register_tool("click_control", dt.click_control)
        if hasattr(dt, "type_into_control"): registry.register_tool("type_into_control", dt.type_into_control)
        if hasattr(dt, "send_hotkey"): registry.register_tool("send_hotkey", dt.send_hotkey)
        if hasattr(dt, "capture_window"): registry.register_tool("capture_window", dt.capture_window)
        
    # Profile tools
    if "profile_tools" in runtime_context:
        pt = runtime_context["profile_tools"]
        if hasattr(pt, "get_profile_field"): registry.register_tool("get_profile_field", pt.get_profile_field)
        if hasattr(pt, "get_job_answer"): registry.register_tool("get_job_answer", pt.get_job_answer)
        if hasattr(pt, "get_default_resume"): registry.register_tool("get_default_resume", pt.get_default_resume)

    # Workflow tools
    if "workflow_tools" in runtime_context:
        wt = runtime_context["workflow_tools"]
        if hasattr(wt, "start_workflow_recording"): registry.register_tool("start_workflow_recording", wt.start_workflow_recording)
        if hasattr(wt, "save_workflow"): registry.register_tool("save_workflow", wt.save_workflow)
        if hasattr(wt, "load_workflow"): registry.register_tool("load_workflow", wt.load_workflow)
