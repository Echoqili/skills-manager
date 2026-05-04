# Hallucination Detection

## Purpose

Detect and mitigate hallucinations in LLM outputs. Use this skill when building AI applications where factual accuracy is critical, integrating model outputs with external systems, or requiring high-reliability AI responses.

**Applicable scenarios:**
- AI applications providing factual information
- RAG systems with retrieval-augmented generation
- Medical, legal, or financial AI advice
- Customer-facing AI with factual claims
- Any production AI system requiring accuracy

## Key Concepts

### Hallucination Types

| Type | Description | Example |
|------|-------------|---------|
| Factual Fabrication | False facts presented as truth | "Einstein won the Nobel in 1990" |
| Entity Confusion | Wrong attributes or relationships | "Python is a company founded in 1991" |
| Temporal Errors | Wrong dates, sequences | "The iPhone was released in 2005" |
| Overconfident Errors | Low confidence presented as fact | "This is definitely the only solution" |
| Citation Fabrication | Fake references, links, quotes | "According to Smith et al. 2020..." |

### Detection Strategies

1. **Self-Consistency Checking** - Generate multiple responses, compare consistency
2. **Cross-Reference Verification** - Check against trusted sources
3. **Uncertainty Signaling** - Detect hedge words and confidence markers
4. **Factual Grounding** - Anchor responses in retrieved context
5. **Output Formatting** - Structured output with confidence levels

## Application

### 1. Self-Consistency Checker

```python
from typing import List, Dict, Tuple
import re

def extract_facts(text: str) -> List[str]:
    """Extract factual statements from text"""
    # Simple sentence splitting (use NLP library for production)
    sentences = re.split(r'[.!?]+', text)
    facts = []

    for sent in sentences:
        sent = sent.strip()
        # Filter out questions, opinions, hedge statements
        if len(sent) > 20:
            if not sent.startswith(("I think", "Maybe", "Perhaps", "Probably")):
                facts.append(sent)

    return facts

def check_consistency(responses: List[str]) -> Dict:
    """Check consistency across multiple model responses"""

    all_facts = []
    for response in responses:
        all_facts.extend(extract_facts(response))

    # Find contradictions
    contradictions = []
    for i, fact1 in enumerate(all_facts):
        for fact2 in all_facts[i+1:]:
            if are_contradictory(fact1, fact2):
                contradictions.append((fact1, fact2))

    return {
        "consistent": len(contradictions) == 0,
        "total_facts": len(all_facts),
        "contradictions": contradictions,
        "consistency_score": 1.0 - (len(contradictions) / max(len(all_facts), 1))
    }

def are_contradictory(fact1: str, fact2: str) -> bool:
    """Detect contradictory facts"""
    # Simple negation detection
    negations = ["not", "never", "no ", "don't", "doesn't", "didn't", "won't"]

    fact1_lower = fact1.lower()
    fact2_lower = fact2.lower()

    for neg in negations:
        if neg in fact1_lower and neg not in fact2_lower:
            # Check for entity overlap
            if share_entities(fact1, fact2):
                return True

    return False

def share_entities(fact1: str, fact2: str) -> bool:
    """Check if two facts share the same entities"""
    # Extract words (simplified - use NER for production)
    words1 = set(re.findall(r'\b[A-Z][a-z]+\b', fact1))
    words2 = set(re.findall(r'\b[A-Z][a-z]+\b', fact2))
    return len(words1 & words2) > 1
```

### 2. Uncertainty Detection

```python
from typing import Dict, List

UNCERTAINTY_MARKERS = {
    "high": ["maybe", "perhaps", "possibly", "might", "could be", "not sure"],
    "medium": ["probably", "likely", "I think", "seems", "appears"],
    "low": ["typically", "usually", "often", "generally"]
}

def detect_uncertainty(text: str) -> Dict:
    """Detect uncertainty levels in text"""

    text_lower = text.lower()
    found_uncertainty = {"high": [], "medium": [], "low": []}

    for level, markers in UNCERTAINTY_MARKERS.items():
        for marker in markers:
            if marker in text_lower:
                found_uncertainty[level].append(marker)

    # Calculate uncertainty score
    uncertainty_score = (
        len(found_uncertainty["high"]) * 1.0 +
        len(found_uncertainty["medium"]) * 0.5 +
        len(found_uncertainty["low"]) * 0.2
    ) / max(len(text.split()), 1) * 10

    return {
        "markers": found_uncertainty,
        "score": min(uncertainty_score, 1.0),
        "level": "high" if uncertainty_score > 0.5 else "medium" if uncertainty_score > 0.2 else "low"
    }

def flag_confident_fabrications(text: str) -> List[str]:
    """Flag statements that are overly confident but may be fabricated"""

    flags = []

    # Check for factual claims without uncertainty markers
    factual_claim_patterns = [
        r"\b[A-Z][a-z]+ (is|was|are|were) \d{4}\b",  # Dates
        r"\b[A-Z][a-z]+ founded in \d{4}\b",  # Founded dates
        r"\bAccording to [A-Z][a-z]+ et al\.\b",  # Citations
        r"\bstudies show\b",
        r"\bresearch proves\b",
    ]

    for pattern in factual_claim_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            uncertainty = detect_uncertainty(text)
            if uncertainty["score"] < 0.1:  # Very low uncertainty
                flags.append(f"Over-confident claim: {match}")

    return flags
```

### 3. RAG Hallucination Prevention

```python
from typing import Optional

class RAGHallucinationChecker:
    def __init__(self, retrieval_threshold: float = 0.7):
        self.retrieval_threshold = retrieval_threshold

    def check_attribution(self, response: str, context: str) -> Dict:
        """Check if response is properly grounded in retrieved context"""

        # Extract claims from response
        response_claims = extract_facts(response)
        context_lower = context.lower()

        unattributed_claims = []
        for claim in response_claims:
            # Check if claim is supported by context
            # Simplified: check keyword overlap
            claim_words = set(claim.lower().split())
            context_words = set(context_lower.split())

            overlap = len(claim_words & context_words) / len(claim_words)
            if overlap < self.retrieval_threshold:
                unattributed_claims.append(claim)

        return {
            "attributed": len(unattributed_claims) == 0,
            "unattributed_claims": unattributed_claims,
            "attribution_score": 1.0 - (len(unattributed_claims) / max(len(response_claims), 1))
        }

    def validate_response(self, response: str, context: Optional[str] = None) -> Dict:
        """Comprehensive response validation"""

        result = {
            "valid": True,
            "warnings": [],
            "confidence": 1.0
        }

        # Check uncertainty
        uncertainty = detect_uncertainty(response)
        if uncertainty["score"] < 0.1:
            result["warnings"].append("Response has very low uncertainty - may be hallucinating")
            result["confidence"] -= 0.3

        # Check attribution if context provided
        if context:
            attribution = self.check_attribution(response, context)
            if not attribution["attributed"]:
                result["valid"] = False
                result["warnings"].append("Response contains claims not supported by retrieved context")
                result["confidence"] -= 0.4

        # Check for fabrication flags
        fabrications = flag_confident_fabrications(response)
        if fabrications:
            result["warnings"].extend(fabrications)
            result["confidence"] -= 0.2 * len(fabrications)

        return result
```

## Examples

### Hallucination Detection Results

| Response | Issue | Detection |
|----------|-------|-----------|
| "Einstein won the Nobel Prize in Physics in 1921 and died in 1955" | Factual (correct) | ✅ Consistent |
| "Einstein won the Nobel Prize in 1990" | Factual Fabrication | ❌ Wrong date |
| "Python was founded by Guido van Rossum in 1991" | Factual (correct) | ✅ Consistent |
| "I think JavaScript was created in 1995" | Uncertainty present | ✅ Safe |
| "Studies show this is always the best approach" | Overconfident | ⚠️ Needs verification |

### Good: Grounded RAG Response

```
Context: "According to the 2024 AI Safety Report, current LLMs have a 15% hallucination rate..."

Response: "Based on the 2024 AI Safety Report, current large language models have approximately a 15% hallucination rate. However, this varies significantly by domain and application context."

Confidence: High (properly attributed)
```

### Bad: Hallucinated Response

```
Context: "The product launch is scheduled for Q2 2024."

Response: "According to the Q3 2024 financial report, the product launch is scheduled for Q2 2024 and will exceed revenue projections by 40%."

Issues:
- Contradiction: Q2 vs Q3
- Fabrication: Specific revenue projection
- No attribution for numerical claims
```

## Common Pitfalls

1. **Over-reliance on Self-Consistency**: Models can be consistently wrong
2. **Ignoring Uncertainty Markers**: dismissing low-confidence outputs
3. **No Grounding**: Allowing responses without retrieved context
4. **Missing Attribution Tracking**: not linking claims to sources
5. **Static Thresholds**: not adapting to different risk levels

## Defense Checklist

- [ ] Uncertainty detection and signaling
- [ ] Self-consistency checking
- [ ] Cross-reference verification
- [ ] RAG attribution validation
- [ ] Confidence scoring on outputs
- [ ] Human-in-the-loop for high-risk claims
- [ ] Monitoring and logging
- [ ] Regular accuracy audits

## References

- [The Citadel - LLM Pentesting](https://github.com/The- Citadel)
- [AI Guardrails](https://github.com/edward-playground/aidefense-framework)
- [UpTrain - Hallucination Detection](https://github.com/uptrain-ai/uptrain)
