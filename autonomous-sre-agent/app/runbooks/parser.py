import re
from typing import Any


def parse_runbook_markdown(content: str, filename: str = "") -> dict[str, Any]:
    """Parse a markdown runbook into structured sections."""
    lines = content.splitlines()
    title = ""
    sections: dict[str, list[str]] = {}
    current_section = "overview"
    sections[current_section] = []

    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            current_section = line[3:].strip().lower().replace(" ", "_")
            sections[current_section] = []
        else:
            sections[current_section].append(line)

    # Flatten sections to plain text
    flat_sections = {k: "\n".join(v).strip() for k, v in sections.items()}

    return {
        "title": title or filename,
        "filename": filename,
        "sections": flat_sections,
        "full_text": content,
        "has_steps": "steps" in flat_sections or "remediation_steps" in flat_sections,
        "tags": _extract_tags(content),
    }


def _extract_tags(content: str) -> list[str]:
    """Extract keywords/tags from runbook content."""
    keywords = [
        "crashloopbackoff", "oomkilled", "imagepullbackoff", "evicted",
        "node", "memory", "cpu", "disk", "network", "timeout",
        "restart", "rollback", "scale", "drain", "cordon",
    ]
    found = []
    lower = content.lower()
    for kw in keywords:
        if kw in lower:
            found.append(kw)
    return found


def extract_remediation_steps(runbook: dict[str, Any]) -> list[str]:
    """Extract ordered remediation steps from parsed runbook."""
    sections = runbook.get("sections", {})
    step_section = (
        sections.get("remediation_steps")
        or sections.get("steps")
        or sections.get("resolution")
        or sections.get("overview", "")
    )
    if not step_section:
        return []

    steps = []
    for line in step_section.splitlines():
        line = line.strip()
        # Match numbered or bulleted lines
        match = re.match(r"^(?:\d+[.)]\s*|[-*]\s+)(.+)", line)
        if match:
            steps.append(match.group(1).strip())
    return steps