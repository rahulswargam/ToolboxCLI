#!/usr/bin/env python3
"""RAHUL'S TOOLBOX — launcher.

Thin entry point so the app can be started with a plain `python toolbox.py`.
The application itself lives in the `toolboxcli/` package.

Created & Built by Rahul Swargam.
"""

from toolboxcli.app import main

if __name__ == "__main__":
    raise SystemExit(main())
