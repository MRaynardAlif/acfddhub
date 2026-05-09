# -*- coding: utf-8 -*-
"""
Created on Sat May  9 05:07:33 2026

@author: Raynard
"""

import subprocess
import sys
import os


def main():
    print("Starting Reflex app...\n")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    process = None

    try:
        process = subprocess.Popen(
            ["reflex", "run"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            bufsize=1
        )

        for line in process.stdout:
            print(line, end="")
            sys.stdout.flush()

        process.wait()

    except KeyboardInterrupt:
        print("\nStopping Reflex app...")
        if process:
            process.terminate()
            process.wait()

    except Exception as e:
        print(f"Unexpected Error: {e}")


if __name__ == "__main__":
    main()