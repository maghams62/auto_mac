#!/usr/bin/env python3
"""
Config Wiring Verification Script

Systematically verifies that every configuration setting in config.yaml
is properly loaded and used by the codebase.
"""

import yaml
import re
import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class ConfigWiringVerifier:
    """Verifies config.yaml settings are wired into codebase."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = project_root / config_path
        self.config = self._load_config()
        self.findings = {
            "wired": [],  # Configs that are properly used
            "unused": [],  # Configs defined but never read
            "hardcoded": [],  # Values that should come from config but are hardcoded
            "missing_checks": []  # Config flags that exist but aren't checked
        }
        self.codebase_files = self._find_python_files()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load config.yaml file."""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _find_python_files(self) -> List[Path]:
        """Find all Python files in src/ directory."""
        python_files = []
        src_dir = project_root / "src"
        if src_dir.exists():
            for py_file in src_dir.rglob("*.py"):
                python_files.append(py_file)
        return python_files
    
    def _flatten_config(self, config: Dict, prefix: str = "") -> List[Tuple[str, Any]]:
        """Flatten nested config dict into dot-separated paths."""
        items = []
        for key, value in config.items():
            full_path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                items.extend(self._flatten_config(value, full_path))
            else:
                items.append((full_path, value))
        return items
    
    def _search_in_file(self, file_path: Path, pattern: str) -> List[int]:
        """Search for pattern in file, return line numbers."""
        matches = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        matches.append(line_num)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
        return matches
    
    def _check_config_usage(self, config_path: str) -> Dict[str, Any]:
        """Check if a config path is used in codebase."""
        # Convert config path to search patterns
        patterns = [
            # Direct access: config.get("section", {}).get("key")
            rf'config\.get\(["\']{config_path.split(".")[0]}["\']',
            # Dot notation: config["section"]["key"]
            rf'config\[["\']{config_path.split(".")[0]}["\']',
            # ConfigAccessor: accessor.get("section.key")
            rf'\.get\(["\']{config_path}["\']',
            # Direct key access in nested dict
            rf'["\']{config_path.split(".")[-1]}["\']',
        ]
        
        # Also check for camelCase/snake_case variations
        key_parts = config_path.split(".")
        if len(key_parts) > 1:
            last_key = key_parts[-1]
            patterns.append(rf'\b{last_key}\b')
        
        found_in_files = []
        for py_file in self.codebase_files:
            for pattern in patterns:
                matches = self._search_in_file(py_file, pattern)
                if matches:
                    found_in_files.append({
                        "file": str(py_file.relative_to(project_root)),
                        "lines": matches,
                        "pattern": pattern
                    })
                    break  # Found in this file, no need to check other patterns
        
        return {
            "used": len(found_in_files) > 0,
            "files": found_in_files
        }
    
    def verify_performance_configs(self):
        """Verify performance optimization configs."""
        perf_config = self.config.get("performance", {})
        
        # Connection Pooling
        conn_pool = perf_config.get("connection_pooling", {})
        if conn_pool.get("enabled"):
            usage = self._check_config_usage("performance.connection_pooling")
            if not usage["used"]:
                self.findings["unused"].append({
                    "config": "performance.connection_pooling",
                    "issue": "Connection pooling enabled but config not read",
                    "files": []
                })
            else:
                # Check if values are actually used (not just checked)
                max_conn_usage = self._check_config_usage("performance.connection_pooling.max_connections")
                if not max_conn_usage["used"]:
                    self.findings["hardcoded"].append({
                        "config": "performance.connection_pooling.max_connections",
                        "issue": "max_connections value hardcoded instead of reading from config",
                        "expected_file": "src/utils/openai_client.py"
                    })
        
        # Rate Limiting
        rate_limit = perf_config.get("rate_limiting", {})
        if rate_limit.get("enabled"):
            usage = self._check_config_usage("performance.rate_limiting")
            if not usage["used"]:
                self.findings["unused"].append({
                    "config": "performance.rate_limiting",
                    "issue": "Rate limiting enabled but config not read",
                    "files": []
                })
        
        # Parallel Execution
        parallel = perf_config.get("parallel_execution", {})
        if parallel.get("enabled"):
            usage = self._check_config_usage("performance.parallel_execution")
            if not usage["used"]:
                self.findings["unused"].append({
                    "config": "performance.parallel_execution",
                    "issue": "Parallel execution enabled but config not read",
                    "files": []
                })
        
        # Batch Embeddings
        batch_emb = perf_config.get("batch_embeddings", {})
        if batch_emb.get("enabled"):
            usage = self._check_config_usage("performance.batch_embeddings")
            if not usage["used"]:
                self.findings["unused"].append({
                    "config": "performance.batch_embeddings",
                    "issue": "Batch embeddings enabled but config not read",
                    "files": []
                })
            else:
                # Check if batch_size is read from config
                batch_size_usage = self._check_config_usage("performance.batch_embeddings.batch_size")
                if not batch_size_usage["used"]:
                    self.findings["hardcoded"].append({
                        "config": "performance.batch_embeddings.batch_size",
                        "issue": "batch_size hardcoded to 100 instead of reading from config",
                        "expected_files": ["src/documents/indexer.py", "src/memory/user_memory_store.py"]
                    })
        
        # Caching
        caching = perf_config.get("caching", {})
        for cache_type in ["tool_catalog", "prompt_templates", "embeddings"]:
            if caching.get(cache_type):
                usage = self._check_config_usage(f"performance.caching.{cache_type}")
                if not usage["used"]:
                    self.findings["missing_checks"].append({
                        "config": f"performance.caching.{cache_type}",
                        "issue": f"Caching enabled for {cache_type} but flag not checked",
                        "files": []
                    })
        
        # Background Tasks
        bg_tasks = perf_config.get("background_tasks", {})
        for task_type in ["verification", "memory_updates", "logging"]:
            if bg_tasks.get(task_type):
                usage = self._check_config_usage(f"performance.background_tasks.{task_type}")
                if not usage["used"]:
                    self.findings["missing_checks"].append({
                        "config": f"performance.background_tasks.{task_type}",
                        "issue": f"Background task {task_type} enabled but flag not checked",
                        "files": []
                    })
    
    def verify_reasoning_configs(self):
        """Verify reasoning and memory feature configs."""
        # Reasoning Trace
        rt_config = self.config.get("reasoning_trace", {})
        if rt_config.get("enabled"):
            usage = self._check_config_usage("reasoning_trace.enabled")
            if not usage["used"]:
                self.findings["unused"].append({
                    "config": "reasoning_trace.enabled",
                    "issue": "Reasoning trace enabled but flag not checked",
                    "files": []
                })
        
        # Persistent Memory
        pm_config = self.config.get("persistent_memory", {})
        if pm_config.get("enabled"):
            usage = self._check_config_usage("persistent_memory.enabled")
            if not usage["used"]:
                self.findings["unused"].append({
                    "config": "persistent_memory.enabled",
                    "issue": "Persistent memory enabled but flag not checked",
                    "files": []
                })
            
            # Check other persistent_memory settings
            for key in ["directory", "embedding_model", "retention", "extraction", "search"]:
                if key in pm_config:
                    usage = self._check_config_usage(f"persistent_memory.{key}")
                    if not usage["used"]:
                        self.findings["unused"].append({
                            "config": f"persistent_memory.{key}",
                            "issue": f"Persistent memory {key} config not read",
                            "files": []
                        })
        
        # Atomic Prompts
        atomic_config = self.config.get("atomic_prompts", {})
        if atomic_config.get("enabled"):
            usage = self._check_config_usage("atomic_prompts")
            if not usage["used"]:
                self.findings["unused"].append({
                    "config": "atomic_prompts",
                    "issue": "Atomic prompts enabled but config not read",
                    "files": []
                })
        
        # Retry Logging
        retry_config = self.config.get("retry_logging", {})
        if retry_config.get("enabled"):
            usage = self._check_config_usage("retry_logging.enabled")
            if not usage["used"]:
                self.findings["unused"].append({
                    "config": "retry_logging.enabled",
                    "issue": "Retry logging enabled but flag not checked",
                    "files": []
                })
    
    def verify_feature_configs(self):
        """Verify feature-specific configs."""
        # Delivery
        delivery_config = self.config.get("delivery", {})
        usage = self._check_config_usage("delivery")
        if not usage["used"]:
            self.findings["unused"].append({
                "config": "delivery",
                "issue": "Delivery config not read",
                "files": []
            })
        
        # Playback
        playback_config = self.config.get("playback", {})
        usage = self._check_config_usage("playback")
        if not usage["used"]:
            self.findings["unused"].append({
                "config": "playback",
                "issue": "Playback config not read",
                "files": []
            })
        
        # Documents
        docs_config = self.config.get("documents", {})
        usage = self._check_config_usage("documents")
        if not usage["used"]:
            self.findings["unused"].append({
                "config": "documents",
                "issue": "Documents config not read",
                "files": []
            })
        
        # Search
        search_config = self.config.get("search", {})
        usage = self._check_config_usage("search")
        if not usage["used"]:
            self.findings["unused"].append({
                "config": "search",
                "issue": "Search config not read",
                "files": []
            })
        
        # Images
        images_config = self.config.get("images", {})
        if images_config.get("enabled"):
            usage = self._check_config_usage("images.enabled")
            if not usage["used"]:
                self.findings["unused"].append({
                    "config": "images.enabled",
                    "issue": "Images enabled but flag not checked",
                    "files": []
                })
    
    def verify_service_configs(self):
        """Verify service-specific configs."""
        services = ["openai", "email", "imessage", "discord", "reddit", "maps", 
                   "spotify_api", "browser", "twitter", "bluesky", "voice", 
                   "whatsapp", "weather", "notes", "reminders"]
        
        for service in services:
            if service in self.config:
                usage = self._check_config_usage(service)
                if not usage["used"]:
                    self.findings["unused"].append({
                        "config": service,
                        "issue": f"{service} config defined but not read",
                        "files": []
                    })
    
    def verify_special_configs(self):
        """Verify special configs (vision, writing, knowledge_providers, logging)."""
        # Vision
        vision_config = self.config.get("vision", {})
        if vision_config.get("enabled") is not None:
            usage = self._check_config_usage("vision")
            if not usage["used"]:
                self.findings["unused"].append({
                    "config": "vision",
                    "issue": "Vision config not read",
                    "files": []
                })
        
        # Writing
        writing_config = self.config.get("writing", {})
        usage = self._check_config_usage("writing")
        if not usage["used"]:
            self.findings["unused"].append({
                "config": "writing",
                "issue": "Writing config not read",
                "files": []
            })
        
        # Knowledge Providers
        kp_config = self.config.get("knowledge_providers", {})
        if kp_config.get("enabled"):
            usage = self._check_config_usage("knowledge_providers")
            if not usage["used"]:
                self.findings["unused"].append({
                    "config": "knowledge_providers",
                    "issue": "Knowledge providers enabled but config not read",
                    "files": []
                })
        
        # Logging
        logging_config = self.config.get("logging", {})
        usage = self._check_config_usage("logging")
        if not usage["used"]:
            self.findings["unused"].append({
                "config": "logging",
                "issue": "Logging config not read",
                "files": []
            })
    
    def check_hardcoded_values(self):
        """Check for hardcoded values that should come from config."""
        # Check openai_client.py for hardcoded connection pool values
        openai_client_file = project_root / "src/utils/openai_client.py"
        if openai_client_file.exists():
            with open(openai_client_file, 'r') as f:
                content = f.read()
                if 'max_keepalive_connections=20' in content or 'max_connections=50' in content:
                    self.findings["hardcoded"].append({
                        "config": "performance.connection_pooling",
                        "issue": "Connection pool limits hardcoded in openai_client.py",
                        "file": "src/utils/openai_client.py",
                        "hardcoded_values": {
                            "max_keepalive_connections": 20,
                            "max_connections": 50,
                            "keepalive_expiry": 60.0
                        }
                    })
        
        # Check for hardcoded batch_size=100
        for file_path in [project_root / "src/documents/indexer.py", 
                         project_root / "src/memory/user_memory_store.py"]:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    content = f.read()
                    if 'batch_size: int = 100' in content or 'batch_size=100' in content:
                        self.findings["hardcoded"].append({
                            "config": "performance.batch_embeddings.batch_size",
                            "issue": f"batch_size hardcoded to 100 in {file_path.name}",
                            "file": str(file_path.relative_to(project_root))
                        })
    
    def run_all_checks(self):
        """Run all verification checks."""
        print("🔍 Starting Config Wiring Verification...")
        print(f"📁 Config file: {self.config_path}")
        print(f"📂 Scanning {len(self.codebase_files)} Python files\n")
        
        print("1️⃣  Verifying Performance Configs...")
        self.verify_performance_configs()
        
        print("2️⃣  Verifying Reasoning & Memory Configs...")
        self.verify_reasoning_configs()
        
        print("3️⃣  Verifying Feature Configs...")
        self.verify_feature_configs()
        
        print("4️⃣  Verifying Service Configs...")
        self.verify_service_configs()
        
        print("5️⃣  Verifying Special Configs...")
        self.verify_special_configs()
        
        print("6️⃣  Checking for Hardcoded Values...")
        self.check_hardcoded_values()
        
        print("\n✅ Verification complete!\n")
    
    def generate_report(self) -> str:
        """Generate markdown report of findings."""
        report = ["# Config Wiring Audit Report\n"]
        report.append(f"Generated: {Path(__file__).stat().st_mtime}\n")
        report.append("## Summary\n\n")
        
        total_issues = (len(self.findings["unused"]) + 
                       len(self.findings["hardcoded"]) + 
                       len(self.findings["missing_checks"]))
        
        report.append(f"- **Total Issues Found**: {total_issues}\n")
        report.append(f"- **Unused Configs**: {len(self.findings['unused'])}\n")
        report.append(f"- **Hardcoded Values**: {len(self.findings['hardcoded'])}\n")
        report.append(f"- **Missing Checks**: {len(self.findings['missing_checks'])}\n")
        report.append(f"- **Properly Wired**: {len(self.findings['wired'])}\n\n")
        
        if self.findings["unused"]:
            report.append("## ❌ Unused Configs\n\n")
            for item in self.findings["unused"]:
                report.append(f"### `{item['config']}`\n")
                report.append(f"- **Issue**: {item['issue']}\n")
                if item.get("files"):
                    report.append(f"- **Files**: {', '.join(item['files'])}\n")
                report.append("\n")
        
        if self.findings["hardcoded"]:
            report.append("## ⚠️  Hardcoded Values\n\n")
            for item in self.findings["hardcoded"]:
                report.append(f"### `{item['config']}`\n")
                report.append(f"- **Issue**: {item['issue']}\n")
                if item.get("file"):
                    report.append(f"- **File**: {item['file']}\n")
                if item.get("hardcoded_values"):
                    report.append(f"- **Hardcoded Values**:\n")
                    for k, v in item["hardcoded_values"].items():
                        report.append(f"  - `{k}`: `{v}`\n")
                report.append("\n")
        
        if self.findings["missing_checks"]:
            report.append("## ⚠️  Missing Feature Flag Checks\n\n")
            for item in self.findings["missing_checks"]:
                report.append(f"### `{item['config']}`\n")
                report.append(f"- **Issue**: {item['issue']}\n")
                report.append("\n")
        
        return "".join(report)


def main():
    """Main entry point."""
    verifier = ConfigWiringVerifier()
    verifier.run_all_checks()
    
    report = verifier.generate_report()
    
    # Save report
    report_path = project_root / "CONFIG_WIRING_AUDIT_REPORT.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"📄 Report saved to: {report_path}\n")
    print(report)
    
    # Exit with error code if issues found
    total_issues = (len(verifier.findings["unused"]) + 
                   len(verifier.findings["hardcoded"]) + 
                   len(verifier.findings["missing_checks"]))
    
    if total_issues > 0:
        print(f"\n⚠️  Found {total_issues} issues. Please review the report.")
        sys.exit(1)
    else:
        print("\n✅ No issues found! All configs are properly wired.")
        sys.exit(0)


if __name__ == "__main__":
    main()

