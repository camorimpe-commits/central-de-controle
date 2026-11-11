import os
import time
import threading
from pathlib import Path
from core.config import UPLOADS_DIR
from core.data_processor import data_processor

class FileWatcher(threading.Thread):
    def __init__(self, watch_dir: Path = UPLOADS_DIR, check_interval: int = 3):
        super().__init__(daemon=True)
        self.watch_dir = watch_dir
        self.check_interval = check_interval
        self._running = False
        self._seen_files = {}
        self.last_event = None

    def run(self):
        self._running = True
        print(f"[WATCHER] Started automated folder watcher at {self.watch_dir}")
        
        # Initial scan to record existing files
        for f in self.watch_dir.glob("*.*"):
            if f.suffix.lower() in [".csv", ".xlsx", ".xls"]:
                self._seen_files[f.name] = f.stat().st_mtime

        while self._running:
            try:
                current_files = list(self.watch_dir.glob("*.*"))
                for f in current_files:
                    if f.suffix.lower() not in [".csv", ".xlsx", ".xls"]:
                        continue
                    mtime = f.stat().st_mtime
                    if f.name not in self._seen_files or self._seen_files[f.name] < mtime:
                        # Found new or updated file
                        print(f"[WATCHER] New dataset detected: {f.name}. Initiating automated processing...")
                        time.sleep(1.0) # ensure writing finished
                        res = data_processor.import_uploaded_file(f, f.name)
                        self._seen_files[f.name] = mtime
                        self.last_event = {
                            "timestamp": time.time(),
                            "filename": f.name,
                            "records": data_processor.total_records,
                            "status": "success" if res.get("success") else "error"
                        }
                        print(f"[WATCHER] Automated update complete for {f.name} ({data_processor.total_records} records).")
            except Exception as e:
                print(f"[WATCHER] Error in watch loop: {e}")
            
            time.sleep(self.check_interval)

    def stop(self):
        self._running = False

file_watcher = FileWatcher()
