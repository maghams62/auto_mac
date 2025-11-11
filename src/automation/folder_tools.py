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
