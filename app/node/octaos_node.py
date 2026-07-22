import sys
import os
import time
import argparse
import logging
from app.node.fts_memory import fts_memory
from app.node.user_profile import user_profile
from app.core.command_sanitizer import sanitizer, ExecutionMode

logging.basicConfig(level=logging.INFO, format="[OctaOS Node] %(asctime)s - %(levelname)s - %(message)s")

class OctaOSNodeDaemon:
    """
    OctaOS Local Node Daemon (`octaos-node`).
    Runs as a lightweight background service on host machines with local SQLite FTS5 memory,
    USER.md dynamic context, and zero-trust security guardrails.
    """
    def __init__(self, mode: ExecutionMode = ExecutionMode.SEMI_AUTONOMOUS):
        self.mode = mode
        self.is_running = False

    def start(self):
        logging.info(f"Starting OctaOS Local Node Daemon in {self.mode.value} mode...")
        logging.info(f"Loaded User Profile from: {user_profile.profile_path}")
        logging.info(f"Initialized SQLite FTS5 Memory at: {fts_memory.db_path}")
        self.is_running = True
        
        # Log node start event into local FTS memory
        fts_memory.store("system", "daemon_lifecycle", "OctaOS Node Daemon started successfully.")
        
        try:
            while self.is_running:
                # Main background event loop
                time.sleep(5)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        logging.info("Stopping OctaOS Node Daemon...")
        self.is_running = False
        fts_memory.store("system", "daemon_lifecycle", "OctaOS Node Daemon stopped gracefully.")
        logging.info("Daemon stopped.")

    def run_command(self, cmd: str) -> dict:
        is_allowed, reason, requires_approval = sanitizer.inspect_command(cmd, self.mode)
        if not is_allowed:
            logging.warning(f"Command blocked: {reason}")
            return {"status": "blocked", "reason": reason}
            
        if requires_approval:
            logging.info(f"Command requires confirmation: {cmd}")
            return {"status": "requires_approval", "cmd": cmd, "reason": reason}

        logging.info(f"Executing command: {cmd}")
        # Store execution event in FTS memory
        fts_memory.store("user_command", "terminal", f"Executed: {cmd}")
        return {"status": "executing", "cmd": cmd}

def main():
    parser = argparse.ArgumentParser(description="OctaOS Enterprise Local Node Daemon")
    parser.add_argument("--mode", choices=["READ_ONLY", "SEMI_AUTONOMOUS", "FULLY_AUTONOMOUS"], default="SEMI_AUTONOMOUS")
    args = parser.parse_args()
    
    node = OctaOSNodeDaemon(mode=ExecutionMode(args.mode))
    node.start()

if __name__ == "__main__":
    main()
