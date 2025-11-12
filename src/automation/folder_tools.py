"""
Folder Management Tools - LLM-first design with security guardrails.

These tools are deterministic utilities that the LLM orchestrator uses
to perform folder operations. The LLM decides which tools to call and in
what order based on user intent.

Security invariant: All operations are sandboxed to allowedFolder.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import os
import shutil
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FolderPlan:
    """Represents a proposed folder reorganization plan."""
    current_name: str
    proposed_name: str
    reason: str
    is_safe: bool


class FolderSecurityError(Exception):
    """Raised when folder operation violates security constraints."""
    pass


class FolderTools:
    """
    Deterministic folder management utilities.

    All tools validate sandbox constraints before any operation.
    The LLM orchestrator decides which tools to use and when.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize folder tools with configuration.

        Args:
            config: Configuration dictionary with documents.folders list
        """
        self.config = config
        
        # Use config accessor to validate folder access
        from ..config_validator import ConfigAccessor
        self.config_accessor = ConfigAccessor(config)
        
        # Get user's allowed folders (validated)
        try:
            user_folders = self.config_accessor.get_user_folders()
            # Use first folder as primary sandbox
            self.allowed_folder = os.path.abspath(user_folders[0])
            self.all_user_folders = user_folders
        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Config validation failed: {e}")
            raise FolderSecurityError(
                f"Cannot initialize folder tools: {str(e)}. "
                "Please configure document folders in config.yaml"
            )

        logger.info(f"[FOLDER TOOLS] Initialized with sandbox: {self.allowed_folder}")
        logger.info(f"[FOLDER TOOLS] User has access to {len(self.all_user_folders)} folder(s)")

    def check_sandbox(self, path: str) -> Dict[str, Any]:
        """
        Verify a path is within the allowed sandbox.

        This is a deterministic security check. The LLM should call this
        to verify scope, but all tools also perform internal validation.

        Args:
            path: Path to validate

        Returns:
            Dictionary with is_safe (bool), message (str), resolved_path (str)
        """
        try:
            # Resolve to absolute path, following symlinks
            resolved = os.path.abspath(os.path.realpath(path))

            # Check against all user's allowed folders (from config)
            for allowed_folder in self.all_user_folders:
                allowed_abs = os.path.abspath(allowed_folder)
                try:
                    # This will raise ValueError if path is not relative to allowed_folder
                    relative = os.path.relpath(resolved, allowed_abs)

                    # Check for parent directory traversal
                    if relative.startswith('..'):
                        continue  # Try next allowed folder

                    # Path is within this allowed folder
                    return {
                        "is_safe": True,
                        "message": f"Path is within allowed folder: {allowed_folder}",
                        "resolved_path": resolved,
                        "allowed_folder": allowed_abs
                    }

                except ValueError:
                    continue  # Try next allowed folder

            # Path not in any allowed folder
            return {
                "is_safe": False,
                "message": f"Path outside all allowed folders: {path}",
                "resolved_path": resolved,
                "allowed_folders": self.all_user_folders
            }

        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Sandbox check error: {e}")
            return {
                "is_safe": False,
                "message": f"Sandbox validation failed: {str(e)}",
                "resolved_path": None,
                "allowed_folders": self.all_user_folders
            }

    def _validate_path(self, path: str) -> str:
        """
        Internal validation that raises exception if path is unsafe.

        Args:
            path: Path to validate

        Returns:
            Resolved absolute path

        Raises:
            FolderSecurityError: If path is outside sandbox
        """
        result = self.check_sandbox(path)
        if not result['is_safe']:
            raise FolderSecurityError(result['message'])
        return result['resolved_path']

    def list_folder(self, folder_path: Optional[str] = None) -> Dict[str, Any]:
        """
        List contents of a folder (non-recursive, alphabetically sorted).

        This is a deterministic read operation. The LLM uses this to
        understand current folder structure before planning changes.

        Args:
            folder_path: Path to list (defaults to sandbox root)

        Returns:
            Dictionary with items (list), total_count (int), folder_path (str)
            Each item has: name, type (file/dir), size, modified
        """
        try:
            # Default to sandbox root
            if folder_path is None:
                folder_path = self.allowed_folder

            # Validate path
            resolved_path = self._validate_path(folder_path)

            if not os.path.exists(resolved_path):
                return {
                    "error": True,
                    "error_type": "NotFoundError",
                    "error_message": f"Folder not found: {folder_path}",
                    "folder_path": folder_path
                }

            if not os.path.isdir(resolved_path):
                return {
                    "error": True,
                    "error_type": "NotADirectoryError",
                    "error_message": f"Path is not a directory: {folder_path}",
                    "folder_path": folder_path
                }

            # List items (non-recursive)
            items = []
            for entry_name in sorted(os.listdir(resolved_path)):
                entry_path = os.path.join(resolved_path, entry_name)

                # Skip hidden files
                if entry_name.startswith('.'):
                    continue

                try:
                    stat = os.stat(entry_path)
                    items.append({
                        "name": entry_name,
                        "type": "dir" if os.path.isdir(entry_path) else "file",
                        "size": stat.st_size if os.path.isfile(entry_path) else None,
                        "modified": stat.st_mtime,
                        "extension": Path(entry_name).suffix.lower() if os.path.isfile(entry_path) else None
                    })
                except OSError as e:
                    logger.warning(f"[FOLDER TOOLS] Cannot stat {entry_name}: {e}")
                    continue

            logger.info(f"[FOLDER TOOLS] Listed {len(items)} items in {resolved_path}")

            return {
                "items": items,
                "total_count": len(items),
                "folder_path": resolved_path,
                "relative_path": os.path.relpath(resolved_path, self.allowed_folder),
                "allowed_folders": self.all_user_folders
            }

        except FolderSecurityError as e:
            logger.error(f"[FOLDER TOOLS] Security error in list_folder: {e}")
            return {
                "error": True,
                "error_type": "SecurityError",
                "error_message": str(e),
                "folder_path": folder_path
            }
        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Error in list_folder: {e}")
            return {
                "error": True,
                "error_type": "ListError",
                "error_message": str(e),
                "folder_path": folder_path
            }

    def plan_folder_organization_alpha(
        self,
        folder_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a plan to normalize folder/file names alphabetically.

        This is a deterministic planning operation (NO writes).
        Proposes normalized names: lowercase, underscores, no special chars.

        The LLM can use this for dry-run before applying changes.

        Args:
            folder_path: Path to analyze (defaults to sandbox root)

        Returns:
            Dictionary with plan (list of FolderPlan), needs_changes (bool)
        """
        try:
            # Default to sandbox root
            if folder_path is None:
                folder_path = self.allowed_folder

            # Validate path
            resolved_path = self._validate_path(folder_path)

            # Get current listing
            listing = self.list_folder(resolved_path)
            if listing.get('error'):
                return listing

            # Generate normalization plan
            plans = []
            needs_changes = False

            for item in listing['items']:
                current = item['name']

                # Normalize: lowercase, spaces to underscores, remove special chars
                proposed = current.lower()
                proposed = proposed.replace(' ', '_')
                proposed = proposed.replace('-', '_')
                # Remove multiple underscores
                while '__' in proposed:
                    proposed = proposed.replace('__', '_')
                proposed = proposed.strip('_')

                # Keep extension case for readability
                if item['type'] == 'file' and item['extension']:
                    # Split extension and reattach
                    name_part = proposed.rsplit('.', 1)[0] if '.' in proposed else proposed
                    ext_part = item['extension'].lower()
                    proposed = f"{name_part}{ext_part}"

                is_safe = current == proposed  # No change needed

                if not is_safe:
                    needs_changes = True

                plans.append({
                    "current_name": current,
                    "proposed_name": proposed,
                    "reason": "Normalized to lowercase with underscores" if not is_safe else "Already normalized",
                    "needs_change": not is_safe,
                    "type": item['type']
                })

            logger.info(f"[FOLDER TOOLS] Generated plan with {len(plans)} items, {sum(1 for p in plans if p['needs_change'])} changes")

            return {
                "plan": plans,
                "needs_changes": needs_changes,
                "total_items": len(plans),
                "changes_count": sum(1 for p in plans if p['needs_change']),
                "folder_path": resolved_path
            }

        except FolderSecurityError as e:
            logger.error(f"[FOLDER TOOLS] Security error in plan_folder_organization_alpha: {e}")
            return {
                "error": True,
                "error_type": "SecurityError",
                "error_message": str(e),
                "folder_path": folder_path
            }
        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Error in plan_folder_organization_alpha: {e}")
            return {
                "error": True,
                "error_type": "PlanError",
                "error_message": str(e),
                "folder_path": folder_path
            }

    def apply_folder_plan(
        self,
        plan: List[Dict[str, Any]],
        folder_path: Optional[str] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Apply a folder reorganization plan (atomic renames).

        This is the ONLY write operation. Performs atomic renames
        based on a plan. Each rename is validated before execution.

        Args:
            plan: List of rename operations (from plan_folder_organization_alpha)
            folder_path: Base folder path (defaults to sandbox root)
            dry_run: If True, validate but don't execute (default: True)

        Returns:
            Dictionary with applied (list), skipped (list), errors (list)
        """
        try:
            # Default to sandbox root
            if folder_path is None:
                folder_path = self.allowed_folder

            # Validate base path
            resolved_path = self._validate_path(folder_path)

            applied = []
            skipped = []
            errors = []

            for item in plan:
                current_name = item.get('current_name')
                proposed_name = item.get('proposed_name')
                needs_change = item.get('needs_change', True)

                # Skip if no change needed
                if not needs_change:
                    skipped.append({
                        "name": current_name,
                        "reason": "No change needed"
                    })
                    continue

                current_path = os.path.join(resolved_path, current_name)
                proposed_path = os.path.join(resolved_path, proposed_name)

                # Validate both paths
                try:
                    self._validate_path(current_path)
                    self._validate_path(proposed_path)
                except FolderSecurityError as e:
                    errors.append({
                        "current_name": current_name,
                        "proposed_name": proposed_name,
                        "error": f"Security violation: {str(e)}"
                    })
                    continue

                # Check if source exists
                if not os.path.exists(current_path):
                    errors.append({
                        "current_name": current_name,
                        "proposed_name": proposed_name,
                        "error": "Source does not exist"
                    })
                    continue

                # Check if destination already exists
                if os.path.exists(proposed_path):
                    errors.append({
                        "current_name": current_name,
                        "proposed_name": proposed_name,
                        "error": "Destination already exists (conflict)"
                    })
                    continue

                # Perform rename (unless dry run)
                if not dry_run:
                    try:
                        os.rename(current_path, proposed_path)
                        applied.append({
                            "current_name": current_name,
                            "proposed_name": proposed_name,
                            "type": item.get('type', 'unknown')
                        })
                        logger.info(f"[FOLDER TOOLS] Renamed: {current_name} -> {proposed_name}")
                    except OSError as e:
                        errors.append({
                            "current_name": current_name,
                            "proposed_name": proposed_name,
                            "error": f"Rename failed: {str(e)}"
                        })
                else:
                    # Dry run - just record what would happen
                    applied.append({
                        "current_name": current_name,
                        "proposed_name": proposed_name,
                        "type": item.get('type', 'unknown'),
                        "dry_run": True
                    })

            logger.info(f"[FOLDER TOOLS] Plan execution: {len(applied)} applied, {len(skipped)} skipped, {len(errors)} errors (dry_run={dry_run})")

            return {
                "success": len(errors) == 0,
                "applied": applied,
                "skipped": skipped,
                "errors": errors,
                "dry_run": dry_run,
                "folder_path": resolved_path
            }

        except FolderSecurityError as e:
            logger.error(f"[FOLDER TOOLS] Security error in apply_folder_plan: {e}")
            return {
                "error": True,
                "error_type": "SecurityError",
                "error_message": str(e),
                "folder_path": folder_path
            }
        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Error in apply_folder_plan: {e}")
            return {
                "error": True,
                "error_type": "ApplyError",
                "error_message": str(e),
                "folder_path": folder_path
            }

    def organize_by_file_type(
        self,
        folder_path: Optional[str] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Organize files into subfolders based on file extension.

        Example: report.pdf → PDF/report.pdf, notes.txt → TXT/notes.txt

        Args:
            folder_path: Folder to organize (defaults to sandbox root)
            dry_run: If True, only generate plan (default); set to False to apply

        Returns:
            Dictionary with plan/applied moves, created folders, and summary
        """
        try:
            # Default to sandbox root
            if folder_path is None:
                folder_path = self.allowed_folder

            resolved_path = self._validate_path(folder_path)

            if not os.path.isdir(resolved_path):
                return {
                    "error": True,
                    "error_type": "NotADirectoryError",
                    "error_message": f"Path is not a directory: {folder_path}",
                    "folder_path": folder_path
                }

            entries = sorted(os.listdir(resolved_path))
            plan: List[Dict[str, Any]] = []
            applied: List[Dict[str, Any]] = []
            skipped: List[Dict[str, Any]] = []
            errors: List[Dict[str, Any]] = []
            created_folders: List[str] = []

            for name in entries:
                if name.startswith('.'):
                    continue  # Skip hidden/system files

                current_path = os.path.join(resolved_path, name)

                # Only operate on top-level files (ignore directories)
                if not os.path.isfile(current_path):
                    continue

                extension = Path(name).suffix.lower().lstrip('.')
                if not extension:
                    extension = "no_extension"

                target_folder = extension.upper()
                target_folder_path = os.path.join(resolved_path, target_folder)
                target_path = os.path.join(target_folder_path, name)

                # Skip if file already in the correct folder
                parent_dir = os.path.basename(os.path.dirname(current_path))
                if parent_dir.upper() == target_folder and os.path.dirname(current_path) != resolved_path:
                    skipped.append({
                        "file": name,
                        "reason": "Already inside matching type folder"
                    })
                    continue

                plan.append({
                    "file": name,
                    "current_path": current_path,
                    "target_folder": target_folder,
                    "target_path": target_path,
                    "action": "move",
                    "reason": f"Group {extension if extension != 'no_extension' else 'extensionless'} files together"
                })

                if dry_run:
                    continue

                try:
                    if not os.path.exists(target_folder_path):
                        os.makedirs(target_folder_path, exist_ok=True)
                        if target_folder_path not in created_folders:
                            created_folders.append(target_folder_path)

                    if os.path.exists(target_path):
                        skipped.append({
                            "file": name,
                            "reason": f"Target already exists: {target_path}"
                        })
                        continue

                    shutil.move(current_path, target_path)
                    applied.append({
                        "file": name,
                        "target_folder": target_folder,
                        "target_path": target_path
                    })

                except Exception as move_error:
                    errors.append({
                        "file": name,
                        "error": str(move_error)
                    })

            summary = {
                "total_files_considered": len(plan),
                "files_moved": len(applied),
                "files_skipped": len(skipped),
                "target_folders": sorted({item["target_folder"] for item in plan}),
                "dry_run": dry_run
            }

            return {
                "success": len(errors) == 0,
                "dry_run": dry_run,
                "folder_path": resolved_path,
                "plan": plan,
                "applied": applied,
                "skipped": skipped,
                "errors": errors,
                "created_folders": created_folders if not dry_run else [
                    os.path.join(resolved_path, item["target_folder"])
                    for item in plan
                    if not os.path.exists(os.path.join(resolved_path, item["target_folder"]))
                ],
                "summary": summary
            }

        except FolderSecurityError as e:
            logger.error(f"[FOLDER TOOLS] Security error in organize_by_file_type: {e}")
            return {
                "error": True,
                "error_type": "SecurityError",
                "error_message": str(e),
                "folder_path": folder_path
            }
        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Error in organize_by_file_type: {e}")
            return {
                "error": True,
                "error_type": "OrganizeByTypeError",
                "error_message": str(e),
                "folder_path": folder_path
            }

    def find_duplicates(
        self,
        folder_path: Optional[str] = None,
        recursive: bool = False
    ) -> Dict[str, Any]:
        """
        Find duplicate files by content hash (SHA-256).

        This is a deterministic read-only operation that identifies files
        with identical content, grouped by hash.

        Args:
            folder_path: Path to analyze (defaults to sandbox root)
            recursive: Whether to search subdirectories (default: False)

        Returns:
            Dictionary with:
            - duplicates: List of duplicate groups (each group has hash, size, files list)
            - total_duplicate_files: Count of duplicate files found
            - total_duplicate_groups: Count of duplicate groups
            - wasted_space_bytes: Total bytes wasted by duplicates
            - folder_path: Path that was analyzed
        """
        try:
            import hashlib
            from collections import defaultdict

            # Default to sandbox root
            if folder_path is None:
                folder_path = self.allowed_folder

            # Validate path
            resolved_path = self._validate_path(folder_path)

            logger.info(f"[FOLDER TOOLS] Finding duplicates in {resolved_path} (recursive={recursive})")

            # Collect all files with their hashes
            file_hashes = defaultdict(list)

            if recursive:
                # Recursive search
                for root, dirs, files in os.walk(resolved_path):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith('.')]

                    for filename in files:
                        # Skip hidden files
                        if filename.startswith('.'):
                            continue

                        file_path = os.path.join(root, filename)
                        try:
                            # Get file size
                            file_size = os.path.getsize(file_path)

                            # Compute SHA-256 hash
                            sha256 = hashlib.sha256()
                            with open(file_path, 'rb') as f:
                                for chunk in iter(lambda: f.read(8192), b''):
                                    sha256.update(chunk)
                            file_hash = sha256.hexdigest()

                            # Store file info
                            file_hashes[file_hash].append({
                                "path": file_path,
                                "relative_path": os.path.relpath(file_path, resolved_path),
                                "name": filename,
                                "size": file_size
                            })
                        except (OSError, IOError) as e:
                            logger.warning(f"[FOLDER TOOLS] Cannot read {filename}: {e}")
                            continue
            else:
                # Non-recursive (top-level only)
                try:
                    entries = os.listdir(resolved_path)
                except OSError as e:
                    return {
                        "error": True,
                        "error_type": "ListError",
                        "error_message": f"Cannot list directory: {str(e)}",
                        "folder_path": resolved_path
                    }

                for filename in entries:
                    file_path = os.path.join(resolved_path, filename)

                    # Skip directories and hidden files
                    if not os.path.isfile(file_path) or filename.startswith('.'):
                        continue

                    try:
                        # Get file size
                        file_size = os.path.getsize(file_path)

                        # Compute SHA-256 hash
                        sha256 = hashlib.sha256()
                        with open(file_path, 'rb') as f:
                            for chunk in iter(lambda: f.read(8192), b''):
                                sha256.update(chunk)
                        file_hash = sha256.hexdigest()

                        # Store file info
                        file_hashes[file_hash].append({
                            "path": file_path,
                            "relative_path": os.path.relpath(file_path, resolved_path),
                            "name": filename,
                            "size": file_size
                        })
                    except (OSError, IOError) as e:
                        logger.warning(f"[FOLDER TOOLS] Cannot read {filename}: {e}")
                        continue

            # Filter to only groups with duplicates (2+ files with same hash)
            duplicate_groups = []
            total_duplicate_files = 0
            wasted_space = 0

            for file_hash, files in file_hashes.items():
                if len(files) > 1:
                    # Sort by name for consistent ordering
                    files_sorted = sorted(files, key=lambda x: x['name'])

                    # Calculate wasted space (size * (count - 1))
                    file_size = files_sorted[0]['size']
                    wasted = file_size * (len(files_sorted) - 1)

                    duplicate_groups.append({
                        "hash": file_hash,
                        "size": file_size,
                        "count": len(files_sorted),
                        "wasted_bytes": wasted,
                        "files": files_sorted
                    })

                    total_duplicate_files += len(files_sorted)
                    wasted_space += wasted

            # Sort groups by wasted space (descending)
            duplicate_groups.sort(key=lambda x: x['wasted_bytes'], reverse=True)

            logger.info(
                f"[FOLDER TOOLS] Found {len(duplicate_groups)} duplicate groups, "
                f"{total_duplicate_files} files, {wasted_space} bytes wasted"
            )

            return {
                "duplicates": duplicate_groups,
                "total_duplicate_files": total_duplicate_files,
                "total_duplicate_groups": len(duplicate_groups),
                "wasted_space_bytes": wasted_space,
                "wasted_space_mb": round(wasted_space / (1024 * 1024), 2),
                "folder_path": resolved_path,
                "recursive": recursive
            }

        except FolderSecurityError as e:
            logger.error(f"[FOLDER TOOLS] Security error in find_duplicates: {e}")
            return {
                "error": True,
                "error_type": "SecurityError",
                "error_message": str(e),
                "folder_path": folder_path
            }
        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Error in find_duplicates: {e}")
            return {
                "error": True,
                "error_type": "DuplicateDetectionError",
                "error_message": str(e),
                "folder_path": folder_path
            }

    def summarize_folder(
        self,
        folder_path: Optional[str] = None,
        items: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive folder overview with statistics and insights.

        This is a read-only operation that analyzes folder contents and provides
        natural language summaries and actionable recommendations.
        """
        try:
            # Get folder contents if not provided
            if items is None:
                if folder_path is None:
                    folder_path = self.allowed_folder
                listing = self.list_folder(folder_path)
                if listing.get('error'):
                    return listing
                items = listing['items']
                folder_path = listing['folder_path']

            # Calculate statistics
            total_files = sum(1 for item in items if item['type'] == 'file')
            total_folders = sum(1 for item in items if item['type'] == 'dir')
            total_size = sum(item.get('size', 0) or 0 for item in items if item['type'] == 'file')

            # File type distribution
            file_types = {}
            for item in items:
                if item['type'] == 'file':
                    ext = item.get('extension', 'no_extension')
                    file_types[ext] = file_types.get(ext, 0) + 1

            # Age analysis
            import time
            current_time = time.time()
            oldest_item = min((item for item in items if item.get('modified')), key=lambda x: x.get('modified', current_time), default=None)
            newest_item = max((item for item in items if item.get('modified')), key=lambda x: x.get('modified', 0), default=None)

            # Generate insights
            insights = []
            recommendations = []

            if total_files == 0:
                insights.append("This folder is empty")
                recommendations.append("Consider adding files or removing the empty folder")
            else:
                # Size insights
                if total_size > 100 * 1024 * 1024:  # > 100MB
                    insights.append(f"Large folder ({total_size / (1024*1024):.1f} MB total)")
                    recommendations.append("Consider archiving old files to reduce size")

                # File type insights
                if len(file_types) > 5:
                    insights.append(f"Diverse content with {len(file_types)} different file types")
                elif len(file_types) <= 2:
                    insights.append(f"Focused content with {len(file_types)} file type(s)")

                # Age insights
                if oldest_item:
                    oldest_age_days = (current_time - oldest_item.get('modified', 0)) / (24 * 3600)
                    if oldest_age_days > 365:
                        insights.append(f"Contains files over a year old (oldest: {oldest_item['name']})")
                        recommendations.append("Archive files older than 1 year")

            # Generate natural language summary
            if total_files == 0:
                summary = "This folder is empty and contains no files or subfolders."
            else:
                type_summary = ", ".join([f"{count} {ext.upper() if ext != 'no_extension' else 'extensionless'}" for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:3]])
                summary = f"Your {Path(folder_path).name} folder contains {total_files} file{'s' if total_files != 1 else ''} and {total_folders} subfolder{'s' if total_folders != 1 else ''}, totaling approximately {total_size / (1024*1024):.1f} MB of data."

                if type_summary:
                    summary += f" The files are primarily {type_summary}."

            statistics = {
                "total_files": total_files,
                "total_folders": total_folders,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 1),
                "file_types": file_types,
                "oldest_file": oldest_item['name'] if oldest_item else None,
                "newest_file": newest_item['name'] if newest_item else None
            }

            return {
                "summary": summary,
                "statistics": statistics,
                "insights": insights,
                "recommendations": recommendations,
                "folder_path": folder_path
            }

        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Error in summarize_folder: {e}")
            return {
                "error": True,
                "error_type": "SummaryError",
                "error_message": str(e),
                "folder_path": folder_path
            }

    def sort_folder_by(
        self,
        folder_path: Optional[str] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        criteria: str = "name",
        direction: str = "ascending"
    ) -> Dict[str, Any]:
        """
        Sort folder contents by specified criteria with explanation.
        """
        try:
            # Get folder contents if not provided
            if items is None:
                if folder_path is None:
                    folder_path = self.allowed_folder
                listing = self.list_folder(folder_path)
                if listing.get('error'):
                    return listing
                items = listing['items']
                folder_path = listing['folder_path']

            # Sort the items
            reverse = direction == "descending"

            if criteria == "name":
                sorted_items = sorted(items, key=lambda x: x['name'].lower(), reverse=reverse)
                explanation = f"Files sorted alphabetically by name ({direction}). This helps you quickly find specific files or see naming patterns."
            elif criteria == "date":
                sorted_items = sorted(items, key=lambda x: x.get('modified', 0), reverse=reverse)
                explanation = f"Files sorted by modification date ({direction}). Newest files appear first when descending, helping you see recent activity."
            elif criteria == "size":
                sorted_items = sorted(items, key=lambda x: x.get('size', 0) or 0, reverse=reverse)
                explanation = f"Files sorted by size ({direction}). Largest files appear first when descending, helping you identify storage hogs."
            elif criteria == "type":
                sorted_items = sorted(items, key=lambda x: x.get('type', 'unknown'), reverse=reverse)
                explanation = f"Items sorted by type ({direction}). Groups files and folders together for easier organization."
            elif criteria == "extension":
                sorted_items = sorted(items, key=lambda x: x.get('extension', ''), reverse=reverse)
                explanation = f"Files sorted by extension ({direction}). Groups similar file types together for bulk operations."
            else:
                sorted_items = sorted(items, key=lambda x: x['name'].lower(), reverse=reverse)
                explanation = f"Files sorted by name (default criteria, {direction})."
                criteria = "name"

            # Generate insights
            insights = []
            import time
            current_time = time.time()

            if criteria == "date":
                recent_count = sum(1 for item in items if item.get('modified', 0) > current_time - (7 * 24 * 3600))
                old_count = sum(1 for item in items if item.get('modified', 0) < current_time - (365 * 24 * 3600))
                if recent_count > 0:
                    insights.append(f"{recent_count} items modified in the last week")
                if old_count > 0:
                    insights.append(f"{old_count} items haven't been touched in over a year")
            elif criteria == "size":
                large_files = [item for item in items if (item.get('size', 0) or 0) > 10 * 1024 * 1024]  # > 10MB
                if large_files:
                    insights.append(f"{len(large_files)} files larger than 10MB found")
            elif criteria == "extension":
                extensions = {}
                for item in items:
                    if item['type'] == 'file':
                        ext = item.get('extension', 'no_extension')
                        extensions[ext] = extensions.get(ext, 0) + 1
                dominant_ext = max(extensions.items(), key=lambda x: x[1]) if extensions else None
                if dominant_ext and dominant_ext[1] > len(items) * 0.5:
                    insights.append(f"Most files are {dominant_ext[0].upper()} ({dominant_ext[1]} files)")

            return {
                "sorted_items": sorted_items,
                "criteria": criteria,
                "direction": direction,
                "explanation": explanation,
                "insights": insights,
                "total_items": len(sorted_items),
                "folder_path": folder_path
            }

        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Error in sort_folder_by: {e}")
            return {
                "error": True,
                "error_type": "SortError",
                "error_message": str(e),
                "folder_path": folder_path
            }

    def explain_file(self, file_path: str) -> Dict[str, Any]:
        """
        Explain file content and purpose using cross-agent analysis.
        """
        try:
            # Validate file path
            resolved_path = self._validate_path(file_path)

            # Get basic file info
            import os
            from pathlib import Path

            stat = os.stat(resolved_path)
            file_size = stat.st_size
            modified_time = stat.st_mtime
            file_name = Path(resolved_path).name
            extension = Path(resolved_path).suffix.lower()

            # Basic explanation
            explanation = f"This is a {extension.upper() if extension else 'file'} file ({self._format_size(file_size)}) that you modified {self._format_time_ago(modified_time)}."

            # Cross-agent content analysis
            key_topics = []
            suggested_actions = []
            content_summary = ""

            try:
                # Try to get content preview using file agent
                from ..agent.agent_registry import AgentRegistry
                registry = AgentRegistry(self.config)
                file_agent = registry.get_agent('file')

                if file_agent:
                    # Search for this specific file
                    search_result = file_agent.execute('search_documents', {
                        'query': file_name,
                        'user_request': f'explain what {file_name} contains'
                    })

                    if not search_result.get('error') and search_result.get('content_preview'):
                        content_preview = search_result['content_preview']

                        # Use LLM to analyze content (this would be done by the writing agent in practice)
                        # For now, provide basic content-based insights
                        content_summary = f"Content preview: {content_preview[:200]}..."

                        # Extract basic topics (simplified)
                        if extension == '.pdf':
                            key_topics.extend(["Document", "PDF", "Report"])
                        elif extension == '.txt':
                            key_topics.extend(["Text", "Notes", "Plain text"])
                        elif extension in ['.docx', '.doc']:
                            key_topics.extend(["Document", "Word", "Formatted text"])
                        elif extension in ['.xlsx', '.xls']:
                            key_topics.extend(["Spreadsheet", "Excel", "Data"])

                        # Action suggestions based on file age and content
                        import time
                        age_days = (time.time() - modified_time) / (24 * 3600)

                        if age_days > 365:
                            suggested_actions.append("Consider archiving this older file")
                        if "report" in file_name.lower():
                            suggested_actions.append("This appears to be a report - consider sharing if relevant")
                        if "meeting" in file_name.lower():
                            suggested_actions.append("Meeting-related file - review action items if applicable")

            except Exception as e:
                logger.warning(f"[FOLDER TOOLS] Cross-agent analysis failed: {e}")
                # Continue with basic explanation

            return {
                "explanation": explanation,
                "key_topics": key_topics,
                "suggested_actions": suggested_actions,
                "content_summary": content_summary,
                "file_info": {
                    "name": file_name,
                    "size": file_size,
                    "size_formatted": self._format_size(file_size),
                    "modified": modified_time,
                    "modified_ago": self._format_time_ago(modified_time),
                    "extension": extension
                }
            }

        except FolderSecurityError as e:
            logger.error(f"[FOLDER TOOLS] Security error in explain_file: {e}")
            return {
                "error": True,
                "error_type": "SecurityError",
                "error_message": str(e),
                "file_path": file_path
            }
        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Error in explain_file: {e}")
            return {
                "error": True,
                "error_type": "ExplainError",
                "error_message": str(e),
                "file_path": file_path
            }

    def archive_old_files(
        self,
        folder_path: Optional[str] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        age_threshold_days: int = 180,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Archive old files to reduce folder clutter.
        """
        try:
            # Get folder contents if not provided
            if items is None:
                if folder_path is None:
                    folder_path = self.allowed_folder
                listing = self.list_folder(folder_path)
                if listing.get('error'):
                    return listing
                items = listing['items']
                folder_path = listing['folder_path']

            # Find old files
            import time
            current_time = time.time()
            threshold_time = current_time - (age_threshold_days * 24 * 3600)

            old_files = []
            for item in items:
                if item['type'] == 'file' and item.get('modified', 0) < threshold_time:
                    old_files.append({
                        "name": item['name'],
                        "size": item.get('size', 0),
                        "modified": item.get('modified', 0),
                        "reason": f"Not modified in {age_threshold_days} days"
                    })

            if not old_files:
                return {
                    "archive_plan": {
                        "files_to_archive": [],
                        "total_files_to_archive": 0,
                        "total_size_bytes": 0,
                        "total_size_mb": 0,
                        "archive_path": None,
                        "age_threshold_days": age_threshold_days
                    },
                    "summary": f"No files found older than {age_threshold_days} days.",
                    "dry_run": dry_run,
                    "needs_confirmation": False
                }

            # Create archive path
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y_%m_%d")
            archive_name = f"Archive_{timestamp}"
            archive_path = os.path.join(folder_path, archive_name)

            total_size = sum(f['size'] for f in old_files)

            if dry_run:
                return {
                    "archive_plan": {
                        "files_to_archive": old_files,
                        "total_files_to_archive": len(old_files),
                        "total_size_bytes": total_size,
                        "total_size_mb": round(total_size / (1024 * 1024), 1),
                        "archive_path": archive_path,
                        "age_threshold_days": age_threshold_days
                    },
                    "summary": f"Found {len(old_files)} files older than {age_threshold_days} days that could be archived, freeing up {round(total_size / (1024 * 1024), 1)} MB.",
                    "dry_run": True,
                    "needs_confirmation": True,
                    "confirmation_message": f"This will create an '{archive_name}' folder and move {len(old_files)} old files there. The files will still be accessible but organized separately. Proceed?"
                }

            # Execute archiving
            os.makedirs(archive_path, exist_ok=True)
            moved_files = []

            for file_info in old_files:
                source_path = os.path.join(folder_path, file_info['name'])
                dest_path = os.path.join(archive_path, file_info['name'])

                try:
                    shutil.move(source_path, dest_path)
                    moved_files.append({
                        "file": file_info['name'],
                        "from": source_path,
                        "to": dest_path
                    })
                except Exception as e:
                    logger.error(f"[FOLDER TOOLS] Failed to move {file_info['name']}: {e}")
                    continue

            return {
                "success": True,
                "files_moved": moved_files,
                "archive_created": archive_path,
                "total_moved": len(moved_files),
                "space_freed_mb": round(total_size / (1024 * 1024), 1),
                "dry_run": False
            }

        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Error in archive_old_files: {e}")
            return {
                "error": True,
                "error_type": "ArchiveError",
                "error_message": str(e),
                "folder_path": folder_path
            }

    def organize_by_category(
        self,
        folder_path: Optional[str] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        categorization: Optional[Dict[str, Any]] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Organize files into semantic categories based on content analysis.
        """
        try:
            # Get folder contents if not provided
            if items is None:
                if folder_path is None:
                    folder_path = self.allowed_folder
                listing = self.list_folder(folder_path)
                if listing.get('error'):
                    return listing
                items = listing['items']
                folder_path = listing['folder_path']

            # Get categorization if not provided (simplified - would use cross-agent analysis)
            if categorization is None:
                # Simplified categorization based on filename patterns
                # In practice, this would use file agent for content analysis
                categories = {}
                for item in items:
                    if item['type'] != 'file':
                        continue

                    name = item['name'].lower()

                    # Simple rule-based categorization
                    if any(word in name for word in ['report', 'summary', 'analysis']):
                        category = "Reports_Analysis"
                    elif any(word in name for word in ['meeting', 'minutes', 'agenda']):
                        category = "Meetings"
                    elif any(word in name for word in ['budget', 'finance', 'cost']):
                        category = "Financial"
                    elif any(word in name for word in ['project', 'plan', 'timeline']):
                        category = "Project_Management"
                    elif any(word in name for word in ['email', 'message', 'correspondence']):
                        category = "Correspondence"
                    else:
                        category = "General"

                    if category not in categories:
                        categories[category] = []
                    categories[category].append({
                        "name": item['name'],
                        "size": item.get('size', 0),
                        "reason": f"File name suggests {category.replace('_', ' ').lower()} content"
                    })

                categorization = {
                    "categories": categories,
                    "method": "filename_pattern_matching"
                }

            # Prepare organization plan
            categories = categorization.get('categories', {})
            new_structure = list(categories.keys())

            if dry_run:
                total_files = sum(len(files) for files in categories.values())
                return {
                    "categories": categories,
                    "new_structure": new_structure,
                    "total_files_to_organize": total_files,
                    "method": categorization.get('method', 'unknown'),
                    "dry_run": True,
                    "needs_confirmation": True,
                    "confirmation_message": f"This will create {len(new_structure)} category folders and organize {total_files} files by content theme. Each file will be moved to the most relevant category folder. Proceed with semantic organization?"
                }

            # Execute organization
            created_folders = []
            moved_files = []

            for category, files in categories.items():
                category_path = os.path.join(folder_path, category.replace('_', '_'))
                os.makedirs(category_path, exist_ok=True)
                created_folders.append(category_path)

                for file_info in files:
                    source_path = os.path.join(folder_path, file_info['name'])
                    dest_path = os.path.join(category_path, file_info['name'])

                    try:
                        shutil.move(source_path, dest_path)
                        moved_files.append({
                            "file": file_info['name'],
                            "category": category,
                            "from": source_path,
                            "to": dest_path
                        })
                    except Exception as e:
                        logger.error(f"[FOLDER TOOLS] Failed to move {file_info['name']}: {e}")
                        continue

            return {
                "success": True,
                "folders_created": created_folders,
                "files_moved": moved_files,
                "categories": categories,
                "total_organized": len(moved_files),
                "dry_run": False
            }

        except Exception as e:
            logger.error(f"[FOLDER TOOLS] Error in organize_by_category: {e}")
            return {
                "error": True,
                "error_type": "OrganizeByCategoryError",
                "error_message": str(e),
                "folder_path": folder_path
            }

    def _format_time_ago(self, timestamp: float) -> str:
        """Format a timestamp as a human-readable time ago string."""
        import time
        diff = time.time() - timestamp

        if diff < 60:
            return "just now"
        elif diff < 3600:
            return f"{int(diff / 60)} minutes ago"
        elif diff < 86400:
            return f"{int(diff / 3600)} hours ago"
        elif diff < 604800:
            return f"{int(diff / 86400)} days ago"
        elif diff < 2592000:
            return f"{int(diff / 604800)} weeks ago"
        elif diff < 31536000:
            return f"{int(diff / 2592000)} months ago"
        else:
            return f"{int(diff / 31536000)} years ago"

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
