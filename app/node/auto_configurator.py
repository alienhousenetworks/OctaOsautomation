import os
import sys
import platform
import logging
from app.node.fts_memory import fts_memory
from app.node.user_profile import user_profile
from app.services.skill_synthesizer import skill_synthesizer

logging.basicConfig(level=logging.INFO, format="[OctaOS AutoConfig] %(asctime)s - %(levelname)s - %(message)s")

class ZeroTouchAutoConfigurator:
    """
    Zero-Touch Desktop & Enterprise System Auto-Configurator.
    Runs on initial Desktop App launch or installer post-install hook to configure
    local storage, FTS5 memory, user profiles, and OS background services.
    """
    def __init__(self):
        self.home_dir = os.path.expanduser("~/.octaos")
        self.os_type = platform.system() # 'Darwin' (macOS), 'Windows', 'Linux'

    def run_auto_setup(self) -> dict:
        """
        Executes zero-touch auto-configuration routine.
        """
        logging.info(f"Executing Zero-Touch Auto-Configuration for OS: {self.os_type}...")
        
        # 1. Create home folder directory structure
        skills_dir = os.path.join(self.home_dir, "skills")
        bin_dir = os.path.join(self.home_dir, "bin")
        os.makedirs(skills_dir, exist_ok=True)
        os.makedirs(bin_dir, exist_ok=True)
        logging.info("✔ Verified directory structure under ~/.octaos/")

        # 2. Initialize SQLite FTS5 Database
        db_path = fts_memory.db_path
        fts_memory.store("auto_configurator", "system_event", f"Zero-touch auto-configuration performed on {self.os_type}.")
        logging.info(f"✔ Initialized SQLite FTS5 Memory Database at: {db_path}")

        # 3. Detect system environment & generate USER.md
        profile_path = user_profile.profile_path
        user_profile.update_preference("OS Platform", self.os_type)
        user_profile.update_preference("Architecture", platform.machine())
        user_profile.update_preference("Python Version", sys.version.split()[0])
        logging.info(f"✔ Generated User Profile at: {profile_path}")

        # 4. Register Background System Service (macOS launchd or Windows startup)
        service_status = self._register_os_background_service()
        logging.info(f"✔ Background Service Registration: {service_status}")

        # 5. Initialize default skills
        skill_synthesizer.distill_execution_trace(
            skill_name="System Diagnostic",
            description="Performs local node health check and memory status audit.",
            category="system",
            triggers=["check node health", "system audit"],
            execution_steps=[
                {"action": "check_memory", "tool": "fts_memory", "params": {"query": "system_event"}},
                {"action": "check_profile", "tool": "user_profile", "params": {}}
            ]
        )
        logging.info("✔ Distilled initial System Diagnostic skill.")

        return {
            "status": "success",
            "os_type": self.os_type,
            "architecture": platform.machine(),
            "home_dir": self.home_dir,
            "memory_db": db_path,
            "profile_path": profile_path,
            "background_service": service_status
        }

    def _register_os_background_service(self) -> str:
        if self.os_type == "Darwin": # macOS
            launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
            os.makedirs(launch_agents_dir, exist_ok=True)
            plist_path = os.path.join(launch_agents_dir, "com.octaos.node.plist")
            
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.octaos.node</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>-m</string>
        <string>app.node.octaos_node</string>
        <string>--mode</string>
        <string>SEMI_AUTONOMOUS</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{self.home_dir}/node.log</string>
    <key>StandardErrorPath</key>
    <string>{self.home_dir}/node_err.log</string>
</dict>
</plist>
"""
            with open(plist_path, "w", encoding="utf-8") as f:
                f.write(plist_content)
            return f"macOS launchd agent configured at {plist_path}"

        elif self.os_type == "Windows":
            startup_dir = os.path.expanduser("~/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup")
            if os.path.exists(startup_dir):
                cmd_path = os.path.join(startup_dir, "OctaOS_Node.cmd")
                with open(cmd_path, "w", encoding="utf-8") as f:
                    f.write(f'@echo off\n"{sys.executable}" -m app.node.octaos_node --mode SEMI_AUTONOMOUS\n')
                return f"Windows Startup shortcut created at {cmd_path}"
            return "Windows background service ready"

        return f"Linux background service ready for {self.os_type}"

auto_configurator = ZeroTouchAutoConfigurator()
