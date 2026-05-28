"""Tests for risk assessment module"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk_assessment import RiskAssessor, RiskLevel


def test_risk_levels():
    """Test risk level thresholds"""
    assessor = RiskAssessor()
    
    # Low density + low anomaly = Low risk
    risk, score = assessor.assess_risk(max_density=2, anomaly_score=0.1)
    assert risk == RiskLevel.LOW
    print(f"[✓] Low risk test: {risk.value} (score: {score:.1f})")
    
    # Medium density = Medium risk
    risk, score = assessor.assess_risk(max_density=20, anomaly_score=0.3)
    assert risk == RiskLevel.MEDIUM
    print(f"[✓] Medium risk test: {risk.value} (score: {score:.1f})")
    
    # High density = High risk
    risk, score = assessor.assess_risk(max_density=35, anomaly_score=0.8)
    assert risk == RiskLevel.HIGH
    print(f"[✓] High risk test: {risk.value} (score: {score:.1f})")


if __name__ == "__main__":
    test_risk_levels()
    print("\n[✓] All risk assessment tests passed!")