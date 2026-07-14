#!/usr/bin/env python3
"""
Unified Auto-Update Pipeline for Skills Manager
=================================================
Chains all update steps into one automated workflow:
  1. Discover new skills from GitHub
  2. Run security scanning
  3. Clean duplicates
  4. Rebuild index
  5. Generate statistics report
"""
import os
import sys
import json
import time
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CLI_DIR = PROJECT_ROOT / "cli"

# Status file to track last update times
STATUS_FILE = DATA_DIR / "update-status.json"


class UpdatePipeline:
    """Auto-update pipeline that chains all steps"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.steps: List[Dict] = []
        self.start_time = time.time()
        self.status = self._load_status()

    def _load_status(self) -> Dict:
        if STATUS_FILE.exists():
            try:
                return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "last_full_update": None,
            "last_discover": None,
            "last_build_index": None,
            "last_security_scan": None,
            "last_clean_duplicates": None,
            "total_updates": 0,
            "history": [],
        }

    def _save_status(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(
            json.dumps(self.status, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def log(self, msg: str):
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {msg}")

    def run_step(self, name: str, script: str, args: List[str] = None) -> bool:
        """Run a single pipeline step"""
        self.log(f"▶ Running: {name}...")
        step_start = time.time()
        step = {"name": name, "started_at": datetime.now().isoformat(), "success": False}

        out_path = err_path = None
        try:
            cmd = [sys.executable, script]
            if args:
                cmd.extend(args)

            # 设置 UTF-8 编码环境，避免子进程 print 中文/emoji 时编码错误
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["LC_ALL"] = "C.UTF-8"
            env["LANG"] = "C.UTF-8"

            # 使用临时文件保存子进程输出，避免后台线程中 pipe 被关闭导致输出丢失
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.out', encoding='utf-8') as out_f, \
                 tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.err', encoding='utf-8') as err_f:
                out_path = out_f.name
                err_path = err_f.name
                result = subprocess.run(
                    cmd,
                    cwd=PROJECT_ROOT,
                    stdout=out_f,
                    stderr=err_f,
                    text=True,
                    timeout=600,
                    env=env,
                )

            stdout_text = Path(out_path).read_text(encoding='utf-8') if out_path else ""
            stderr_text = Path(err_path).read_text(encoding='utf-8') if err_path else ""

            success = result.returncode == 0
            step["success"] = success
            step["duration"] = round(time.time() - step_start, 2)
            step["output"] = stdout_text[-500:] if stdout_text else ""
            step["error"] = stderr_text[-300:] if stderr_text else ""

            if success:
                self.log(f"  ✅ {name} completed ({step['duration']}s)")
            else:
                self.log(f"  ❌ {name} failed (exit code {result.returncode})")
                if stderr_text:
                    self.log(f"     Error: {stderr_text.strip()[-200:]}")

            self.steps.append(step)
            return success

        except subprocess.TimeoutExpired:
            self.log(f"  ⏰ {name} timed out (>600s)")
            step["success"] = False
            step["error"] = "Timeout (>600s)"
            step["duration"] = round(time.time() - step_start, 2)
            self.steps.append(step)
            return False

        except Exception as e:
            self.log(f"  💥 {name} error: {e}")
            step["success"] = False
            step["error"] = str(e)
            step["duration"] = round(time.time() - step_start, 2)
            self.steps.append(step)
            return False

        finally:
            # 清理临时文件
            try:
                if out_path:
                    os.unlink(out_path)
                if err_path:
                    os.unlink(err_path)
            except Exception:
                pass

    def run_discover(self, categories: List[str] = None, min_stars: int = 50) -> bool:
        """Step 1: Discover new skills from GitHub"""
        args = ["--discover", "--min-stars", str(min_stars)]
        if categories:
            for cat in categories:
                args.extend(["--category", cat])
        success = self.run_step("GitHub Discovery", CLI_DIR / "github_skills_discoverer.py", args)
        if success:
            self.status["last_discover"] = datetime.now().isoformat()
        return success

    def run_security_scan(self) -> bool:
        """Step 2: Run security scanning on all skills"""
        success = self.run_step(
            "Security Scan", CLI_DIR / "skills_security_scanner.py", ["--all"]
        )
        if success:
            self.status["last_security_scan"] = datetime.now().isoformat()
        return success

    def run_clean_duplicates(self) -> bool:
        """Step 3: Clean duplicate skills"""
        success = self.run_step(
            "Clean Duplicates", CLI_DIR / "clean-duplicates.py", ["-y"]
        )
        if success:
            self.status["last_clean_duplicates"] = datetime.now().isoformat()
        return success

    def run_build_index(self) -> bool:
        """Step 4: Rebuild the skills index"""
        success = self.run_step("Build Index", CLI_DIR / "build-index.py")
        if success:
            self.status["last_build_index"] = datetime.now().isoformat()
        return success

    def run_full_update(
        self,
        categories: List[str] = None,
        min_stars: int = 50,
        skip_discover: bool = False,
        skip_scan: bool = False,
        skip_clean: bool = False,
    ) -> Dict:
        """Run the full update pipeline"""
        self.log("=" * 50)
        self.log("Starting Full Auto-Update Pipeline")
        self.log("=" * 50)
        self.start_time = time.time()
        self.steps = []

        steps_to_run = [
            ("discover", not skip_discover, lambda: self.run_discover(categories, min_stars)),
            ("scan", not skip_scan, self.run_security_scan),
            ("clean", not skip_clean, self.run_clean_duplicates),
            ("build_index", True, self.run_build_index),
        ]

        all_success = True
        completed_steps = 0
        for step_name, should_run, step_fn in steps_to_run:
            if not should_run:
                self.log(f"  ⏭ Skipping: {step_name}")
                continue
            ok = step_fn()
            if not ok:
                all_success = False
                self.log(f"  ⚠ Pipeline continuing despite {step_name} failure")
            completed_steps += 1

        total_time = round(time.time() - self.start_time, 2)

        # Update global status
        self.status["last_full_update"] = datetime.now().isoformat()
        self.status["total_updates"] = self.status.get("total_updates", 0) + 1
        self.status["history"].append({
            "timestamp": datetime.now().isoformat(),
            "duration": total_time,
            "success": all_success,
            "steps": [s["name"] for s in self.steps if s["success"]],
            "failed_steps": [s["name"] for s in self.steps if not s["success"]],
        })
        # Keep only last 50 history entries
        if len(self.status["history"]) > 50:
            self.status["history"] = self.status["history"][-50:]
        self._save_status()

        # Summary
        self.log("=" * 50)
        self.log(f"Pipeline {'✅ COMPLETED' if all_success else '⚠️ COMPLETED WITH ERRORS'}")
        self.log(f"  Total time: {total_time}s")
        successful = sum(1 for s in self.steps if s["success"])
        self.log(f"  Steps: {successful}/{len(self.steps)} successful")
        self.log("=" * 50)

        return {
            "success": all_success,
            "total_duration": total_time,
            "steps_completed": successful,
            "steps_total": len(self.steps),
            "steps": self.steps,
        }

    def get_index_stats(self) -> Dict:
        """Get current index statistics"""
        stats = {
            "last_update": self.status.get("last_full_update"),
            "last_discover": self.status.get("last_discover"),
            "last_build_index": self.status.get("last_build_index"),
            "last_security_scan": self.status.get("last_security_scan"),
            "last_clean_duplicates": self.status.get("last_clean_duplicates"),
            "total_updates": self.status.get("total_updates", 0),
        }

        # Read current index stats
        index_file = DATA_DIR / "skills-index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text(encoding="utf-8"))
                stats["total_skills"] = data.get("total_skills", 0)
                stats["sources"] = data.get("source_stats", {})
                stats["index_generated_at"] = data.get("generated_at")
            except Exception:
                pass

        # Read security scan stats
        scan_file = PROJECT_ROOT / "security-scan-results.json"
        if scan_file.exists():
            try:
                scan_data = json.loads(scan_file.read_text(encoding="utf-8"))
                risk_levels = {}
                for name, result in scan_data.items():
                    level = result.get("risk_level", "unknown")
                    risk_levels[level] = risk_levels.get(level, 0) + 1
                stats["security"] = {
                    "total_scanned": len(scan_data),
                    "risk_levels": risk_levels,
                }
            except Exception:
                pass

        return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Skills Manager Auto-Update Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full update pipeline
  python cli/auto_update.py --full

  # Run full update skipping discovery
  python cli/auto_update.py --full --skip-discover

  # Only rebuild index
  python cli/auto_update.py --build-index

  # Show update status
  python cli/auto_update.py --status

  # Run full update with specific categories
  python cli/auto_update.py --full --categories ai_agent product
        """,
    )

    parser.add_argument("--full", action="store_true", help="Run full update pipeline")
    parser.add_argument("--discover", action="store_true", help="Run GitHub discovery only")
    parser.add_argument("--security-scan", action="store_true", help="Run security scan only")
    parser.add_argument("--clean", action="store_true", help="Clean duplicates only")
    parser.add_argument("--build-index", action="store_true", help="Rebuild index only")
    parser.add_argument("--status", action="store_true", help="Show update status")

    parser.add_argument("--skip-discover", action="store_true", help="Skip discovery in full update")
    parser.add_argument("--skip-scan", action="store_true", help="Skip security scan in full update")
    parser.add_argument("--skip-clean", action="store_true", help="Skip duplicate cleaning")
    parser.add_argument("--min-stars", type=int, default=50, help="Minimum stars for discovery")
    parser.add_argument("--categories", nargs="*", help="Categories to discover")

    args = parser.parse_args()
    pipeline = UpdatePipeline()

    if args.status:
        stats = pipeline.get_index_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    if args.full:
        result = pipeline.run_full_update(
            categories=args.categories,
            min_stars=args.min_stars,
            skip_discover=args.skip_discover,
            skip_scan=args.skip_scan,
            skip_clean=args.skip_clean,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.discover:
        success = pipeline.run_discover(args.categories, args.min_stars)
        sys.exit(0 if success else 1)

    if args.security_scan:
        success = pipeline.run_security_scan()
        sys.exit(0 if success else 1)

    if args.clean:
        success = pipeline.run_clean_duplicates()
        sys.exit(0 if success else 1)

    if args.build_index:
        success = pipeline.run_build_index()
        sys.exit(0 if success else 1)

    # Default: show status
    stats = pipeline.get_index_stats()
    print("Skills Manager Update Status")
    print("=" * 50)
    print(f"Last full update:       {stats.get('last_update', 'Never')}")
    print(f"Last discovery:         {stats.get('last_discover', 'Never')}")
    print(f"Last index build:       {stats.get('last_build_index', 'Never')}")
    print(f"Last security scan:     {stats.get('last_security_scan', 'Never')}")
    print(f"Last duplicate clean:   {stats.get('last_clean_duplicates', 'Never')}")
    print(f"Total updates:          {stats.get('total_updates', 0)}")
    print(f"Total skills:           {stats.get('total_skills', 'N/A')}")
    if "security" in stats:
        s = stats["security"]
        print(f"Scanned skills:         {s.get('total_scanned', 0)}")
        for level, count in s.get("risk_levels", {}).items():
            print(f"  {level}: {count}")


if __name__ == "__main__":
    main()