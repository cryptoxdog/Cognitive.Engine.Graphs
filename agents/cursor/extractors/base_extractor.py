"""
Base Extractor

Abstract base class for all L9 chat/artifact extractors.
"""

# ============================================================================
__dora_meta__ = {
    "component_name": "Base Extractor",
    "module_version": "1.0.0",
    "created_by": "L9 Agent",
    "created_at": "2026-02-02T23:30:00Z",
    "updated_at": "2026-02-02T23:30:00Z",
    "layer": "intelligence",
    "domain": "agent_execution",
    "module_name": "base_extractor",
    "type": "base_class",
    "status": "active",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": [],
        "memory_layers": [],
        "imported_by": ["agents.cursor.extractors.cursor_action_extractor"],
    },
}
# ============================================================================

from abc import ABC, abstractmethod
from pathlib import Path

import structlog


class BaseExtractor(ABC):
    """
    Abstract base class for all extractors.

    Provides common functionality:
    - Structured logging
    - Path handling
    - Abstract extract() method
    """

    def __init__(self, name: str | None = None):
        """
        Initialize the extractor.

        Args:
            name: Optional name for the extractor (defaults to class name)
        """
        self.name = name or self.__class__.__name__
        self.logger = structlog.get_logger(self.name)

    @abstractmethod
    def extract(self, input_path: Path, output_root: Path) -> dict:
        """
        Extract content from input and write to output.

        Args:
            input_path: Path to input file/directory
            output_root: Root directory for output

        Returns:
            dict with extraction results:
                - success: bool
                - files_extracted: int
                - output_path: str
                - manifest: dict
                - errors: list
        """

    def validate_input(self, input_path: Path) -> bool:
        """
        Validate that input path exists and is readable.

        Args:
            input_path: Path to validate

        Returns:
            True if valid, False otherwise
        """
        if not input_path.exists():
            self.logger.error("input_path_not_found", path=str(input_path))
            return False

        if not input_path.is_file() and not input_path.is_dir():
            self.logger.error("input_path_invalid", path=str(input_path))
            return False

        return True

    def ensure_output_dir(self, output_root: Path) -> bool:
        """
        Ensure output directory exists.

        Args:
            output_root: Output directory path

        Returns:
            True if directory exists or was created
        """
        try:
            output_root.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            self.logger.error("output_dir_creation_failed", path=str(output_root), error=str(e))
            return False


# ============================================================================
# DORA FOOTER META - AUTO-GENERATED - DO NOT EDIT MANUALLY
# ============================================================================
__dora_footer__ = {
    "component_id": "AGE-EXTR-001",
    "governance_level": "standard",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": ["structlog"],
    "tags": ["base-class", "extractor", "intelligence"],
    "keywords": ["extract", "base", "abstract"],
    "business_value": "Provides common base class for all extractors",
    "last_modified": "2026-02-02T23:30:00Z",
    "modified_by": "L9_Agent",
    "change_summary": "Initial creation - GMP-132",
}
# ============================================================================
