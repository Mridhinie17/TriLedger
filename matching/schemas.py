"""
Pydantic Schemas for 3-Way Reconciliation Results, Discrepancies, and Anomaly Scores.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DiscrepancyDetail(BaseModel):
    check_type: str = Field(
        ..., description="Check identifier (e.g. QUANTITY_MISMATCH, PRICE_TOLERANCE)"
    )
    severity: str = Field("HIGH", description="HIGH, MEDIUM, LOW")
    message: str = Field(..., description="Human-readable explanation of discrepancy")
    variance: Optional[Dict[str, Any]] = Field(None, description="Detailed numerical variance")


class MatchResult(BaseModel):
    invoice_number: str
    is_matched: bool = Field(
        ..., description="True if passed all deterministic checks within tolerance"
    )
    overall_status: str = Field(..., description="MATCHED or DISCREPANCY")
    detected_defect_types: List[str] = Field(
        default_factory=list, description="Defect types detected"
    )
    discrepancies: List[DiscrepancyDetail] = Field(default_factory=list)

    # Specific module outputs
    fx_validation: Optional[Dict[str, Any]] = None
    duplicate_info: Optional[Dict[str, Any]] = None
    isolation_forest_anomaly: bool = False
    isolation_forest_score: float = 0.0

    # Line item variances
    line_item_variances: List[Dict[str, Any]] = Field(default_factory=list)
