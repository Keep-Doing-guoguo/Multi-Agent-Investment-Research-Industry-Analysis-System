from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.models.agent_outputs import (
    ResearchDirection,
    ResearchType,
    RiskDecision,
    RiskFinding,
    RiskOutput,
    Severity,
    TriageOutput,
)


class AgentOutputsTest(unittest.TestCase):
    def test_triage_output_serializes_enums_to_json_values(self) -> None:
        output = TriageOutput(
            agent_name="TriageAgent",
            summary="识别为行业分析",
            research_type=ResearchType.INDUSTRY_ANALYSIS,
            target="新能源汽车行业",
            directions=[
                ResearchDirection(
                    name="竞争格局",
                    reason="行业分析需要比较主要参与者",
                )
            ],
        )

        self.assertEqual(
            output.to_dict(),
            {
                "agent_name": "TriageAgent",
                "summary": "识别为行业分析",
                "research_type": "industry_analysis",
                "target": "新能源汽车行业",
                "directions": [
                    {
                        "name": "竞争格局",
                        "reason": "行业分析需要比较主要参与者",
                    }
                ],
                "constraints": [],
                "required_tools": [],
            },
        )

    def test_risk_output_rejects_invalid_decision(self) -> None:
        with self.assertRaises(ValidationError):
            RiskOutput(
                agent_name="RiskAgent",
                summary="非法决策",
                decision="continue",
            )

    def test_agent_outputs_reject_extra_fields(self) -> None:
        with self.assertRaises(ValidationError):
            RiskOutput(
                agent_name="RiskAgent",
                summary="包含额外字段",
                decision=RiskDecision.PASS,
                unexpected_field=True,
            )

    def test_nested_outputs_reject_extra_fields(self) -> None:
        with self.assertRaises(ValidationError):
            RiskFinding(
                finding_type="evidence_gap",
                severity=Severity.HIGH,
                message="缺少数据",
                suggested_action="补充行业数据",
                extra_field="should fail",
            )


if __name__ == "__main__":
    unittest.main()
