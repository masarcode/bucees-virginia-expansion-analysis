"""Pipeline orchestrator.

Runs every stage script in dependency order, stopping on the first failure.
Each stage script is an ordinary module runnable on its own with
`python -m scripts.<package>.<module>`; this orchestrator simply sequences
them and reports status.

Usage:
    python -m scripts.run_pipeline               # run all available stages
    python -m scripts.run_pipeline --from clean  # start at a named group
    python -m scripts.run_pipeline --only acquire
"""

import argparse
import subprocess
import sys
from datetime import datetime

from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import PROJECT_ROOT

log = get_logger("pipeline")

# Ordered registry: (group, module). Modules are added as stages are built;
# missing files are reported as "not yet implemented" rather than errors so
# the pipeline stays runnable throughout development.
STAGES = [
    ("acquire", "scripts.acquire.fetch_tiger"),
    ("acquire", "scripts.acquire.fetch_acs"),
    ("acquire", "scripts.acquire.fetch_cbp"),
    ("acquire", "scripts.acquire.fetch_cpi"),
    ("acquire", "scripts.acquire.fetch_vdot"),
    ("acquire", "scripts.acquire.fetch_vdot_maintenance_geom"),
    ("acquire", "scripts.acquire.compile_bucees"),
    ("clean", "scripts.clean.clean_geography"),
    ("clean", "scripts.clean.clean_acs"),
    ("clean", "scripts.clean.clean_cbp"),
    ("clean", "scripts.clean.clean_vdot"),
    ("clean", "scripts.clean.clean_bucees"),
    ("database", "scripts.build_database"),
    ("analyze", "scripts.analyze.features"),
    ("analyze", "scripts.analyze.eda"),
    ("analyze", "scripts.analyze.scoring"),
    ("analyze", "scripts.analyze.scenarios"),
    ("analyze", "scripts.analyze.regions"),
    ("analyze", "scripts.analyze.recommendations"),
    ("export", "scripts.export_tableau"),
]


def module_exists(module: str) -> bool:
    return (PROJECT_ROOT / (module.replace(".", "/") + ".py")).exists()


def run_stage(module: str) -> bool:
    log.info("=== running %s ===", module)
    result = subprocess.run([sys.executable, "-m", module], cwd=PROJECT_ROOT)
    if result.returncode != 0:
        log.error("%s FAILED (exit %d)", module, result.returncode)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start_group", default=None,
                        help="start at this group (acquire/clean/database/analyze)")
    parser.add_argument("--only", dest="only_group", default=None,
                        help="run only this group")
    args = parser.parse_args()

    started = args.start_group is None
    log.info("pipeline start %s", datetime.now().isoformat(timespec="seconds"))
    ran, skipped = 0, []
    for group, module in STAGES:
        if not started:
            if group == args.start_group:
                started = True
            else:
                continue
        if args.only_group and group != args.only_group:
            continue
        if not module_exists(module):
            skipped.append(module)
            continue
        if not run_stage(module):
            log.error("pipeline stopped at %s", module)
            return 1
        ran += 1

    log.info("pipeline complete: %d stage script(s) ran", ran)
    if skipped:
        log.info("not yet implemented: %s", ", ".join(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
