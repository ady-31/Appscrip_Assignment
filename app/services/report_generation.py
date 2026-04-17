from app.core.schemas import Stage1Summary, Stage2Trends, Stage3TradeView


class ReportGenerationService:
    """Build final markdown output consumed by API clients."""

    @staticmethod
    def build_markdown(
        sector: str,
        stage1: Stage1Summary,
        stage2: Stage2Trends,
        stage3: Stage3TradeView,
        warnings: list[str],
    ) -> str:
        lines: list[str] = [
            "# Sector Intelligence Report",
            "",
            f"Analyzed Sector: **{sector.replace('_', ' ').title()}**",
            "",
            "## Market Summary",
            stage1.market_summary,
            "",
            "## Key Trends",
        ]

        if stage2.trends:
            for trend in stage2.trends:
                lines.extend(
                    [
                        f"- **{trend.title}**",
                        f"  - Reasoning: {trend.reasoning}",
                        f"  - Confidence: {trend.confidence:.1f}%",
                        f"  - Source: {trend.source_reference}",
                    ]
                )
        else:
            lines.append("- No high-confidence trends were identified from available signals.")

        lines.extend(
            [
                "",
                "## Trade Opportunities (with reasoning + confidence)",
            ]
        )

        if stage3.opportunities:
            for item in stage3.opportunities:
                lines.extend(
                    [
                        f"- **{item.title}**",
                        f"  - Reasoning: {item.reasoning}",
                        f"  - Confidence: {item.confidence:.1f}%",
                        f"  - Source: {item.source_reference}",
                    ]
                )
        else:
            lines.append("- No opportunities met the confidence threshold.")

        lines.extend(
            [
                "",
                "## Risk Factors",
            ]
        )

        if stage3.risks:
            for item in stage3.risks:
                lines.extend(
                    [
                        f"- **{item.title}**",
                        f"  - Reasoning: {item.reasoning}",
                        f"  - Confidence: {item.confidence:.1f}%",
                        f"  - Source: {item.source_reference}",
                    ]
                )
        else:
            lines.append("- No critical risks were surfaced from current data.")

        lines.extend(
            [
                "",
                "## Final Recommendation",
                stage3.recommendation,
            ]
        )

        if warnings:
            lines.extend(["", "## Warnings"])
            for warning in warnings:
                lines.append(f"- {warning}")

        return "\n".join(lines)
