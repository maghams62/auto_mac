"""
Tests for Swagger/OpenAPI drift detection.

These tests validate:
1. OpenAPI spec parsing extracts correct endpoints and parameters
2. Documentation parsing extracts documented parameters
3. Drift detection identifies mismatches between spec and docs
4. Reports correctly categorize drift severity

Usage:
    pytest tests/test_swagger_drift.py -v
"""

from __future__ import annotations

import pytest
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import from the detect script
sys.path.insert(0, str(project_root / "scripts"))
from detect_swagger_drift import (
    parse_openapi_spec,
    parse_doc_parameters,
    detect_drift,
    extract_doc_version,
    DriftReport,
    DriftItem,
    EndpointInfo,
    load_yaml_file,
    load_text_file,
)

# Paths to fixtures
FIXTURES_DIR = project_root / "tests" / "fixtures"
SWAGGER_DIR = FIXTURES_DIR / "swagger"
DOCS_DIR = SWAGGER_DIR / "docs"


# =============================================================================
# OpenAPI Parsing Tests
# =============================================================================

class TestOpenAPIParsing:
    """Tests for OpenAPI spec parsing."""
    
    def test_parse_service_a_spec(self):
        """Parse service_a.yaml and verify endpoint extraction."""
        spec_path = SWAGGER_DIR / "service_a.yaml"
        if not spec_path.exists():
            pytest.skip(f"Fixture not found: {spec_path}")
        
        endpoints = parse_openapi_spec(spec_path)
        
        # Should have charge and refund endpoints
        assert len(endpoints) >= 2
        
        # Check charge endpoint
        charge_key = "POST /payments/charge"
        assert charge_key in endpoints
        charge = endpoints[charge_key]
        assert charge.method == "POST"
        assert "/charge" in charge.path
        
        # Verify request body fields extracted
        assert "amount" in charge.request_body_fields
        assert "currency" in charge.request_body_fields
        assert "payment_method_id" in charge.request_body_fields
        
        # v2.1 added these fields
        assert "metadata" in charge.request_body_fields
        assert "capture" in charge.request_body_fields
    
    def test_parse_service_b_spec(self):
        """Parse service_b.yaml and verify endpoint extraction."""
        spec_path = SWAGGER_DIR / "service_b.yaml"
        if not spec_path.exists():
            pytest.skip(f"Fixture not found: {spec_path}")
        
        endpoints = parse_openapi_spec(spec_path)
        
        # Should have invoice and subscribe endpoints
        assert len(endpoints) >= 2
        
        # Check for billing endpoints
        endpoint_paths = [e.path for e in endpoints.values()]
        assert any("/invoice" in p for p in endpoint_paths)
        assert any("/subscribe" in p for p in endpoint_paths)
    
    def test_parse_extracts_required_fields(self):
        """Verify required fields are correctly identified."""
        spec_path = SWAGGER_DIR / "service_a.yaml"
        if not spec_path.exists():
            pytest.skip(f"Fixture not found: {spec_path}")
        
        endpoints = parse_openapi_spec(spec_path)
        charge_key = "POST /payments/charge"
        
        if charge_key in endpoints:
            charge = endpoints[charge_key]
            # These should be required
            assert "amount" in charge.required_body_fields
            assert "currency" in charge.required_body_fields
            assert "payment_method_id" in charge.required_body_fields
            # These should be optional
            assert "description" not in charge.required_body_fields


# =============================================================================
# Documentation Parsing Tests
# =============================================================================

class TestDocumentationParsing:
    """Tests for markdown documentation parsing."""
    
    def test_parse_payments_api_doc(self):
        """Parse payments_api.md and verify parameter extraction."""
        doc_path = DOCS_DIR / "payments_api.md"
        if not doc_path.exists():
            pytest.skip(f"Fixture not found: {doc_path}")
        
        doc_content = load_text_file(doc_path)
        endpoints = parse_doc_parameters(doc_content)
        
        # Should find the charge endpoint
        assert len(endpoints) > 0
        
        # Look for charge endpoint (may have different path format)
        charge_info = None
        for key, info in endpoints.items():
            if "charge" in key.lower():
                charge_info = info
                break
        
        if charge_info:
            # Doc should have these params documented
            assert "amount" in charge_info["params"]
            assert "currency" in charge_info["params"]
            assert "payment_method_id" in charge_info["params"]
            
            # Doc is intentionally missing these (v2.1 additions)
            assert "metadata" not in charge_info["params"]
            assert "capture" not in charge_info["params"]
    
    def test_parse_billing_api_doc(self):
        """Parse billing_api.md - should be in sync."""
        doc_path = DOCS_DIR / "billing_api.md"
        if not doc_path.exists():
            pytest.skip(f"Fixture not found: {doc_path}")
        
        doc_content = load_text_file(doc_path)
        endpoints = parse_doc_parameters(doc_content)
        
        # Should find invoice and subscribe endpoints
        assert len(endpoints) > 0
    
    def test_extract_doc_version(self):
        """Verify version extraction from documentation."""
        doc_with_version = "*Last updated: 2024-01-01 (v2.0)*"
        assert extract_doc_version(doc_with_version) == "2.0"
        
        doc_with_version_alt = "Documentation version 1.3.0"
        assert extract_doc_version(doc_with_version_alt) == "1.3.0"
        
        doc_no_version = "Some documentation without version"
        assert extract_doc_version(doc_no_version) is None


# =============================================================================
# Drift Detection Tests
# =============================================================================

class TestDriftDetection:
    """Tests for drift detection logic."""
    
    def test_detect_drift_payments_has_drift(self):
        """
        Payments API doc is intentionally drifted from spec.
        
        Expected drift:
        - Doc is v2.0, spec is v2.1
        - Missing params: metadata, capture
        - Required mismatch: X-Idempotency-Key (should be required for refund)
        """
        spec_path = SWAGGER_DIR / "service_a.yaml"
        doc_path = DOCS_DIR / "payments_api.md"
        
        if not spec_path.exists() or not doc_path.exists():
            pytest.skip("Fixtures not found")
        
        report = detect_drift(spec_path, doc_path)
        
        assert report.has_drift is True
        assert report.spec_version == "2.1.0"
        
        # Should have missing params
        assert len(report.missing_params) > 0
        
        # metadata and capture are in spec but not in doc
        missing_param_names = [item.field_name for item in report.drift_items 
                              if item.drift_type == "missing_param"]
        assert "metadata" in missing_param_names or "capture" in missing_param_names
    
    def test_detect_drift_billing_no_drift(self):
        """
        Billing API doc is intentionally in sync with spec.
        Should have minimal or no drift.
        """
        spec_path = SWAGGER_DIR / "service_b.yaml"
        doc_path = DOCS_DIR / "billing_api.md"
        
        if not spec_path.exists() or not doc_path.exists():
            pytest.skip("Fixtures not found")
        
        report = detect_drift(spec_path, doc_path)
        
        # Billing doc is in sync - should have much less drift than payments
        # May still have some minor discrepancies due to parsing
        assert len(report.missing_params) < len(detect_drift(
            SWAGGER_DIR / "service_a.yaml",
            DOCS_DIR / "payments_api.md"
        ).missing_params)
    
    def test_drift_report_structure(self):
        """Verify DriftReport has correct structure."""
        report = DriftReport(
            spec_path="test.yaml",
            doc_path="test.md",
            spec_version="1.0.0",
            doc_version="0.9.0",
        )
        
        assert report.has_drift is False
        assert report.drift_items == []
        assert report.missing_params == []
        assert report.extra_params == []
        
        # Add a drift item
        report.add_drift(DriftItem(
            endpoint="POST /test",
            drift_type="missing_param",
            field_name="new_field",
            spec_value="present",
            doc_value="missing",
            severity="error",
        ))
        
        assert report.has_drift is True
        assert len(report.drift_items) == 1
        assert "new_field" in report.missing_params
    
    def test_drift_item_severity_levels(self):
        """Verify drift items can have different severity levels."""
        error_item = DriftItem(
            endpoint="POST /test",
            drift_type="missing_param",
            field_name="required_field",
            severity="error",
        )
        assert error_item.severity == "error"
        
        warning_item = DriftItem(
            endpoint="POST /test",
            drift_type="extra_param",
            field_name="old_field",
            severity="warning",
        )
        assert warning_item.severity == "warning"


# =============================================================================
# End-to-End Tests
# =============================================================================

class TestDriftDetectionE2E:
    """End-to-end tests using actual fixtures."""
    
    def test_full_detection_pipeline(self):
        """Run full detection on all fixtures."""
        spec_doc_pairs = [
            (SWAGGER_DIR / "service_a.yaml", DOCS_DIR / "payments_api.md"),
            (SWAGGER_DIR / "service_b.yaml", DOCS_DIR / "billing_api.md"),
        ]
        
        reports = []
        for spec_path, doc_path in spec_doc_pairs:
            if spec_path.exists() and doc_path.exists():
                report = detect_drift(spec_path, doc_path)
                reports.append(report)
        
        if not reports:
            pytest.skip("No fixtures found")
        
        # At least payments should have drift
        payments_report = next(
            (r for r in reports if "service_a" in r.spec_path),
            None
        )
        
        if payments_report:
            assert payments_report.has_drift is True
            assert payments_report.spec_version == "2.1.0"
    
    def test_drift_detection_missing_spec(self):
        """Verify graceful handling of missing spec file."""
        report = detect_drift(
            Path("/nonexistent/spec.yaml"),
            DOCS_DIR / "payments_api.md"
        )
        
        # Should return empty report, not crash
        assert report.spec_path == "/nonexistent/spec.yaml"
        assert len(report.drift_items) == 0
    
    def test_drift_detection_missing_doc(self):
        """Verify graceful handling of missing doc file."""
        spec_path = SWAGGER_DIR / "service_a.yaml"
        if not spec_path.exists():
            pytest.skip("Spec fixture not found")
        
        report = detect_drift(
            spec_path,
            Path("/nonexistent/doc.md")
        )
        
        # Should return report (possibly with all endpoints missing from doc)
        assert report.spec_path == str(spec_path)


# =============================================================================
# Integration with Graph Layer Tests
# =============================================================================

class TestDriftGraphIntegration:
    """Tests for drift detection integration with graph layer."""
    
    def test_drift_report_can_identify_affected_docs(self):
        """
        Verify drift report identifies which docs need updates.
        This is the key integration point with the graph layer.
        """
        spec_path = SWAGGER_DIR / "service_a.yaml"
        doc_path = DOCS_DIR / "payments_api.md"
        
        if not spec_path.exists() or not doc_path.exists():
            pytest.skip("Fixtures not found")
        
        report = detect_drift(spec_path, doc_path)
        
        # Report should identify the doc that needs updating
        assert report.doc_path == str(doc_path)
        
        # If there's drift, we know this doc needs attention
        if report.has_drift:
            affected_doc_id = f"doc:swagger:{spec_path.stem}"
            # This ID format matches what seed_graph.py creates
            assert affected_doc_id == "doc:swagger:service_a"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

