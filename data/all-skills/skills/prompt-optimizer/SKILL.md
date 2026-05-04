---
name: Prompt Optimizer
slug: prompt-optimizer
description: 分析和优化 AI Prompt，识别模糊表达、角色缺失、约束不足等问题，输出经过验证的高质量提示词。
category: ai-product
source: clawhub
---

# Prompt Optimizer

Prompt engineering skill. Use to **diagnose and improve AI prompts** — transforms vague instructions into precise, effective prompts.

## When to Use

- Your prompt gives inconsistent results
- Output doesn't match expectations
- Preparing prompts for production use
- Teaching prompt engineering best practices

## Diagnosis Framework

### Common Issues
| Issue | Example | Fix |
|-------|---------|-----|
| Vague role | "You are helpful" | "You are a senior backend engineer specializing in Python and distributed systems" |
| Missing context | "Fix this bug" | "Fix this bug in our FastAPI auth middleware. We use JWT tokens, Python 3.11, and must maintain backward compatibility" |
| Unclear format | "Summarize this" | "Summarize in 3 bullet points, each under 20 words, for a non-technical executive audience" |
| No constraints | "Write code" | "Write Python code: PEP 8 compliant, with type hints, docstrings, and error handling" |
| Missing examples | "Extract dates" | Provide 3 examples with expected output |

## Optimization Process

```
1. ANALYZE  → Identify the core task and success criteria
2. ROLE     → Define expert persona with specific background
3. CONTEXT  → Add relevant constraints and environment
4. TASK     → Clarify exactly what to do (action verb)
5. FORMAT   → Specify output format, length, structure
6. EXAMPLES → Add few-shot examples if needed
7. VALIDATE → Test with edge cases
```

## Before / After

**Before:**
```
Summarize the meeting notes.
```

**After:**
```
You are an executive assistant. Summarize the following meeting notes into:
1. Decision made (1 sentence each)
2. Action items (owner + deadline format)
3. Open questions needing follow-up

Be concise. Use bullet points. Maximum 200 words total.

Meeting notes:
[NOTES]
```

## Prompt Templates

- System prompt template
- Chain-of-thought template
- Few-shot learning template
- JSON output template
- Code generation template
