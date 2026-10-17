"""Launch local Collector, unified dashboard and optional passive MQTT monitor.

No fake sensor, no training, no automatic AI publishing. Requires running
Mosquitto on localhost. Ctrl+C stops the processes started by this launcher.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commands(python=sys.executable, with_collector=True, with_monitor=False, port=8501):
    if not 1024 <= port <= 65535:
        raise ValueError("port must be between 1024 and 65535")
    result = []
    if with_collector:
        result.append(("MQTT Collector", [python, str(ROOT/"backend"/"collector.py")]))
    result.append(("Dashboard", [
        python, "-m", "streamlit", "run", str(ROOT/"dashboard"/"unified_app.py"),
        "--server.address", "127.0.0.1", "--server.port", str(port),
        "--browser.gatherUsageStats", "false"
    ]))
    if with_monitor:
        result.append(("MQTT quality monitor", [python, str(ROOT/"tools"/"monitor_mqtt_live.py")]))
    return result


def start():
    p=argparse.ArgumentParser(description="Run Project II software locally")
    p.add_argument("--port", type=int, default=8501)
    p.add_argument("--no-collector", action="store_true")
    p.add_argument("--monitor", action="store_true")
    a=p.parse_args()
    try:
        specs=commands(with_collector=not a.no_collector,with_monitor=a.monitor,port=a.port)
    except ValueError as exc:
        p.error(str(exc))
    processes=[]
    print("Check Mosquitto is already running on localhost:1883.")
    print("No simulated telemetry, model training or AI alerts will be started.")
    try:
        for name,cmd in specs:
            child=subprocess.Popen(cmd,cwd=ROOT)
            processes.append((name,child))
            print(f"Started {name}: PID={child.pid}",flush=True)
        print(f"Dashboard: http://localhost:{a.port} (Ctrl+C to stop)",flush=True)
        while True:
            for name,child in processes:
                rc=child.poll()
                if rc is not None:
                    raise RuntimeError(f"{name} exited with code {rc}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping local services...",flush=True)
    finally:
        for _,child in reversed(processes):
            if child.poll() is None:
                child.terminate()
        for name,child in reversed(processes):
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            print(f"Stopped {name}.",flush=True)


if __name__ == "__main__":
    start()
