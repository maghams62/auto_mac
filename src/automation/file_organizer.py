"""
LLM-driven file organization system.

This module uses LLM reasoning to organize files into folders based on:
- File names
- Document embeddings/content
- User intent

NO hardcoded file type matching or name patterns!
"""

import logging
import os
import shutil
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
import re


logger = logging.getLogger(__name__)


class FileOrganizer:
    """
    Organizes files into folders using LLM reasoning.

    Instead of hardcoded file type or name matching, uses LLM to:
    - Determine if a file belongs to a category
    - Decide folder structure
    - Handle naming conflicts
    """

    def __init__(self, config: dict):
        """
        Initialize the file organizer.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.llm = ChatOpenAI(
            model=config.get("openai", {}).get("model", "gpt-4o"),
            temperature=0.0  # Deterministic for file operations
        )

    def organize_files(
        self,
        category: str,
        target_folder: str,
        source_directory: str,
        search_engine: Any = None,
        move: bool = True
    ) -> Dict[str, Any]:
        """
        Organize files into a folder based on LLM-determined relevance.

        Args:
            category: Category description (e.g., "music notes", "work documents")
            target_folder: Target folder name or path
            source_directory: Source directory to scan
            search_engine: Optional search engine for embeddings
            move: If True, move files; if False, copy files

        Returns:
            Dictionary with results:
            {
                "success": bool,
                "files_moved": List[str],
                "files_skipped": List[str],
                "target_path": str,
                "reasoning": Dict[str, str]  # filename -> reason for inclusion/exclusion
            }
        """
        logger.info(f"Organizing files for category: '{category}' into '{target_folder}'")

        # Get all files from source directory
        all_files = self._scan_directory(source_directory)
        logger.info(f"Found {len(all_files)} files to evaluate")

        # Use LLM to determine which files belong to the category
        categorization = self._categorize_files(
            files=all_files,
            category=category,
            search_engine=search_engine
        )

        # Create target folder
        target_path = self._resolve_target_path(target_folder, source_directory)
        if not os.path.exists(target_path):
            os.makedirs(target_path)
            logger.info(f"Created target folder: {target_path}")

        # Move/copy files
        files_moved = []
        files_skipped = []
        reasoning = {}

        for file_info in categorization['files']:
            file_path = file_info['path']
            should_include = file_info['include']
            reason = file_info['reasoning']
            filename = os.path.basename(file_path)

            reasoning[filename] = reason

            if should_include:
                try:
                    destination = os.path.join(target_path, filename)

                    # Handle naming conflicts using LLM
                    if os.path.exists(destination):
                        conflict_resolution = self._resolve_conflict(
                            existing_file=destination,
                            new_file=file_path
                        )

                        if conflict_resolution['action'] == 'skip':
                            logger.info(f"Skipping {filename}: {conflict_resolution['reasoning']}")
                            files_skipped.append(filename)
                            reasoning[filename] += f" (Skipped: {conflict_resolution['reasoning']})"
                            continue
                        elif conflict_resolution['action'] == 'rename':
                            destination = conflict_resolution['new_path']

                    # Move or copy
                    if move:
                        shutil.move(file_path, destination)
                        logger.info(f"Moved: {filename} -> {target_path}")
                    else:
                        shutil.copy2(file_path, destination)
                        logger.info(f"Copied: {filename} -> {target_path}")

                    files_moved.append(filename)

                except Exception as e:
                    logger.error(f"Error moving {filename}: {e}")
                    files_skipped.append(filename)
                    reasoning[filename] += f" (Error: {e})"
            else:
                files_skipped.append(filename)
                logger.info(f"Skipped {filename}: {reason}")

        return {
            "success": True,
            "files_moved": files_moved,
            "files_skipped": files_skipped,
            "target_path": target_path,
            "reasoning": reasoning,
            "total_evaluated": len(all_files)
        }

    def _scan_directory(self, directory: str) -> List[Dict[str, Any]]:
        """
        Scan directory for files.

        Args:
            directory: Directory to scan

        Returns:
            List of file info dictionaries
        """
        files = []

        for root, dirs, filenames in os.walk(directory):
            for filename in filenames:
                # Skip hidden files and system files
                if filename.startswith('.'):
                    continue

                file_path = os.path.join(root, filename)
                files.append({
                    'path': file_path,
                    'filename': filename,
                    'extension': os.path.splitext(filename)[1],
                    'size': os.path.getsize(file_path)
                })

        return files

    def _categorize_files(
        self,
        files: List[Dict[str, Any]],
        category: str,
        search_engine: Any = None
    ) -> Dict[str, Any]:
        """
        Use LLM to categorize files based on category description.

        Args:
            files: List of file info dictionaries
            category: Category description
            search_engine: Optional search engine for content analysis

        Returns:
            Categorization result with reasoning
        """
        logger.info(f"LLM categorizing {len(files)} files for category: '{category}'")

        # Build prompt with file information
        prompt = self._build_categorization_prompt(files, category, search_engine)

        try:
            messages = [
                SystemMessage(content="""You are a file categorization expert. Your job is to determine which files belong to a specific category based on their names and optionally their content.

CRITICAL RULES:
1. Consider the ENTIRE filename context, not just isolated keywords
2. Use semantic understanding to determine relevance to the category
3. Analyze file naming patterns, extensions, and content clues
4. Consider industry/domain context (e.g., technical terms, dates, version numbers)
5. When ambiguous, prefer excluding files that don't CLEARLY match the category
6. Provide specific reasoning for each decision

Respond with ONLY valid JSON in this exact format:
{
  "files": [
    {"filename": "example.pdf", "include": true, "reasoning": "Clear explanation of why this matches the category"},
    {"filename": "other.pdf", "include": false, "reasoning": "Clear explanation of why this doesn't match"}
  ]
}"""),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)
            content = response.content.strip()

            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()

            result = json.loads(content)

            # Add full paths back
            for file_decision in result['files']:
                matching_file = next(
                    (f for f in files if f['filename'] == file_decision['filename']),
                    None
                )
                if matching_file:
                    file_decision['path'] = matching_file['path']

            logger.info(f"Categorization complete: {sum(1 for f in result['files'] if f['include'])} files to include")
            return result

        except Exception as e:
            logger.error(f"Error categorizing files: {e}")
            # Safe fallback: exclude all files
            return {
                "files": [
                    {
                        "filename": f['filename'],
                        "path": f['path'],
                        "include": False,
                        "reasoning": f"Error during categorization: {e}"
                    }
                    for f in files
                ]
            }

    def _build_categorization_prompt(
        self,
        files: List[Dict[str, Any]],
        category: str,
        search_engine: Any = None
    ) -> str:
        """Build prompt for file categorization."""

        prompt_parts = [
            f'CATEGORY: "{category}"',
            "",
            "FILES TO EVALUATE:",
        ]

        for file_info in files:
            prompt_parts.append(f"- {file_info['filename']} ({file_info['extension']}, {file_info['size']} bytes)")

        # Add content hints if search engine available
        if search_engine:
            prompt_parts.append("")
            prompt_parts.append("CONTENT ANALYSIS:")

            for file_info in files:
                # Try to get document summary from search engine
                try:
                    # Search for the document
                    results = search_engine.search(file_info['filename'], top_k=1)
                    if results and results[0]['path'] == file_info['path']:
                        # Get a snippet of content
                        snippet = results[0].get('text', '')[:200]
                        prompt_parts.append(f"{file_info['filename']}: \"{snippet}...\"")
                except:
                    pass

        prompt_parts.extend([
            "",
            "TASK: For each file, determine if it belongs to the specified category.",
            f"Consider: Does this file relate to '{category}'?",
            "",
            "Respond with JSON listing each file with 'include' (true/false) and 'reasoning'."
        ])

        return "\n".join(prompt_parts)

    def _resolve_target_path(self, target_folder: str, source_directory: str) -> str:
        """
        Resolve target folder path.

        Args:
            target_folder: Target folder name or path
            source_directory: Source directory

        Returns:
            Absolute path to target folder
        """
        # If absolute path, use as-is
        if os.path.isabs(target_folder):
            return target_folder

        # Otherwise, create relative to source directory
        return os.path.join(source_directory, target_folder)

    def _resolve_conflict(
        self,
        existing_file: str,
        new_file: str
    ) -> Dict[str, Any]:
        """
        Use LLM to resolve file naming conflicts.

        Args:
            existing_file: Path to existing file
            new_file: Path to new file

        Returns:
            {
                "action": "skip" | "rename" | "replace",
                "new_path": str (if action is "rename"),
                "reasoning": str
            }
        """
        prompt = f"""FILE CONFLICT:

Existing file: {os.path.basename(existing_file)} ({os.path.getsize(existing_file)} bytes)
New file: {os.path.basename(new_file)} ({os.path.getsize(new_file)} bytes)

TASK: Decide how to handle this conflict.

OPTIONS:
1. "skip" - Don't move the new file (keep existing)
2. "rename" - Rename the new file (e.g., add "_2" suffix)
3. "replace" - Replace existing file with new file

Consider:
- Are these likely the same file?
- Is one clearly newer or more complete?
- Should we preserve both?

Respond with JSON:
{{
  "action": "skip",
  "reasoning": "Files appear identical, keep existing"
}}"""

        try:
            messages = [
                SystemMessage(content="""You resolve file conflicts.
Respond with JSON: {"action": "skip"|"rename"|"replace", "reasoning": str, "new_path": str (only if rename)}"""),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)
            content = response.content.strip()

            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()

            result = json.loads(content)

            # If rename, generate new path
            if result['action'] == 'rename' and 'new_path' not in result:
                base, ext = os.path.splitext(existing_file)
                counter = 2
                while os.path.exists(f"{base}_{counter}{ext}"):
                    counter += 1
                result['new_path'] = f"{base}_{counter}{ext}"

            return result

        except Exception as e:
            logger.error(f"Error resolving conflict: {e}")
            return {
                "action": "skip",
                "reasoning": f"Error during conflict resolution: {e}"
            }
