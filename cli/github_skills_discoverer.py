#!/usr/bin/env python3
"""
GitHub Skills Discoverer - 自动发现和收集 GitHub 上的优质 Skills

功能:
- 搜索 GitHub 上的 Skills 相关仓库
- 质量评估（stars、文件结构、更新频率）
- AI 智能推荐（智谱 GLM）
- 候选队列管理（待用户审批）
- 自动克隆已审批的仓库
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from enum import Enum

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


ZHIPU_API_URL = os.environ.get("ZHIPU_API_URL", "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions")
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_MODEL = os.environ.get("ZHIPU_MODEL", "kimi-k2.6")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Skills-Discoverer/1.0"
}
if GITHUB_TOKEN:
    GITHUB_HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

PROJECT_ROOT = Path(__file__).parent.parent
CANDIDATES_FILE = PROJECT_ROOT / "candidates.json"
SKILLS_ROOT = PROJECT_ROOT / "all-skills"

SEARCH_QUERIES = {
    "ai_agent": [
        "claude skills site:github.com",
        "cursor skills site:github.com",
        "agent skills claude site:github.com",
    ],
    "product": [
        "product manager skills site:github.com",
        "prd template site:github.com",
        "user story skills site:github.com",
    ],
    "agile": [
        "scrum skills site:github.com",
        "sprint planning template site:github.com",
        "agile workflow site:github.com",
    ],
    "qa_testing": [
        "playwright template site:github.com",
        "e2e testing skills site:github.com",
        "automation testing template site:github.com",
    ],
    "architecture": [
        "ddd skills site:github.com",
        "architecture template site:github.com",
        "hexagonal architecture site:github.com",
    ],
    "dev_workflow": [
        "tdd template site:github.com",
        "clean code guidelines site:github.com",
        "git workflow site:github.com",
    ],
}


class CandidateStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class CandidateRepo:
    name: str
    full_name: str
    description: str
    stars: int
    url: str
    language: str
    updated_at: str
    category: str
    discovered_at: str
    status: str = CandidateStatus.PENDING.value
    quality_score: int = 0
    skill_files: List[str] = None
    rejection_reason: str = ""

    def __post_init__(self):
        if self.skill_files is None:
            self.skill_files = []
        if self.rejection_reason is None:
            self.rejection_reason = ""


class SkillsDiscoverer:
    def __init__(self, min_stars: int = 50):
        self.min_stars = min_stars
        self.candidates: List[CandidateRepo] = []
        self._load_candidates()

    def _load_candidates(self):
        if CANDIDATES_FILE.exists():
            try:
                data = json.loads(CANDIDATES_FILE.read_text(encoding='utf-8'))
                self.candidates = [
                    CandidateRepo(**c) for c in data.get("candidates", [])
                ]
            except Exception as e:
                print(f"Warning: Failed to load candidates: {e}")
                self.candidates = []

    def _save_candidates(self):
        CANDIDATES_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "candidates": [asdict(c) for c in self.candidates],
            "last_updated": datetime.now().isoformat()
        }
        CANDIDATES_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    def search_github(self, query: str, per_page: int = 30) -> List[Dict]:
        url = "https://api.github.com/search/repositories"
        params = {
            "q": query,
            "per_page": min(per_page, 100),
            "sort": "stars",
            "order": "desc"
        }

        headers_to_use = dict(GITHUB_HEADERS)
        if GITHUB_TOKEN:
            headers_to_use["Authorization"] = f"token {GITHUB_TOKEN}"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = requests.get(
                    url,
                    headers=headers_to_use,
                    params=params,
                    timeout=60,
                    verify=True
                )

                if resp.status_code == 401:
                    print(f"⚠️ GitHub token invalid, retrying without auth...")
                    headers_to_use.pop("Authorization", None)
                    time.sleep(1)
                    continue

                if resp.status_code == 403:
                    reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
                    wait_time = max(0, reset_time - time.time()) + 5
                    print(f"Rate limited. Wait {wait_time:.0f}s")
                    time.sleep(min(wait_time, 60))
                    return []

                if resp.status_code != 200:
                    print(f"GitHub API error: {resp.status_code}")
                    return []

                return resp.json().get("items", [])

            except requests.exceptions.SSLError:
                if attempt < max_retries - 1:
                    print(f"⚠️ SSL error, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(2)
                    continue
                print(f"⚠️ GitHub search SSL error after retries")
                return []
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"⚠️ Timeout, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(3)
                    continue
                print(f"⚠️ GitHub search timeout after retries")
                return []
            except Exception as e:
                print(f"Search error: {e}")
                return []

        print(f"⚠️ GitHub search unavailable. Using local skills for recommendations instead.")
        return []

    def check_skill_files(self, repo_full_name: str) -> tuple:
        has_skill_md = False
        has_plugin = False
        skill_files = []

        preview_url = f"https://api.github.com/repos/{repo_full_name}/contents"
        try:
            resp = requests.get(preview_url, headers=GITHUB_HEADERS, timeout=10)
            if resp.status_code == 200:
                contents = resp.json()
                for item in contents:
                    name = item.get("name", "").lower()
                    if name == "skill.md":
                        has_skill_md = True
                        skill_files.append(item["path"])
                    elif any(x in name for x in [".claude", ".cursor", ".cursor-plugin", "skills"]):
                        has_plugin = True
                        skill_files.append(item["path"])
        except Exception:
            pass

        return has_skill_md, has_plugin, skill_files

    def evaluate_quality(self, repo: Dict, skill_files: List[str]) -> int:
        score = 0

        stars = repo.get("stargazers_count", 0)
        if stars >= 10000:
            score += 40
        elif stars >= 1000:
            score += 30
        elif stars >= 100:
            score += 20
        elif stars >= 50:
            score += 10

        if skill_files:
            score += 30

        updated_at = repo.get("updated_at", "")
        if updated_at:
            try:
                update_date = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                days_ago = (datetime.now() - update_date.replace(tzinfo=None)).days
                if days_ago < 30:
                    score += 15
                elif days_ago < 180:
                    score += 10
                elif days_ago < 365:
                    score += 5
            except Exception:
                pass

        has_description = bool(repo.get("description"))
        if has_description:
            score += 5

        return min(score, 100)

    def discover(self, categories: List[str] = None, max_per_category: int = 20) -> List[CandidateRepo]:
        if categories is None:
            categories = list(SEARCH_QUERIES.keys())

        new_candidates = []
        existing_urls = {c.url for c in self.candidates}

        for cat_key in categories:
            queries = SEARCH_QUERIES.get(cat_key, [])
            for query in queries:
                repos = self.search_github(query, max_per_category)

                for repo in repos:
                    repo_url = repo.get("html_url", "")
                    if repo_url in existing_urls:
                        continue

                    stars = repo.get("stargazers_count", 0)
                    if stars < self.min_stars:
                        continue

                    has_skill, has_plugin, skill_files = self.check_skill_files(
                        repo.get("full_name", "")
                    )

                    if not has_skill and not has_plugin:
                        continue

                    quality_score = self.evaluate_quality(repo, skill_files)

                    candidate = CandidateRepo(
                        name=repo.get("name", ""),
                        full_name=repo.get("full_name", ""),
                        description=repo.get("description", "") or "",
                        stars=stars,
                        url=repo_url,
                        language=repo.get("language", "") or "",
                        updated_at=repo.get("updated_at", "")[:10],
                        category=cat_key,
                        discovered_at=datetime.now().strftime("%Y-%m-%d"),
                        quality_score=quality_score,
                        skill_files=skill_files
                    )

                    new_candidates.append(candidate)
                    existing_urls.add(repo_url)

                    if len(new_candidates) >= max_per_category:
                        break

                time.sleep(1)

        new_candidates.sort(key=lambda x: -x.quality_score)
        self.candidates.extend(new_candidates)
        self._save_candidates()

        return new_candidates

    def get_pending(self) -> List[CandidateRepo]:
        return [c for c in self.candidates if c.status == CandidateStatus.PENDING.value]

    def get_by_category(self, category: str) -> List[CandidateRepo]:
        return [c for c in self.candidates if c.category == category]

    def call_zhipu_ai(self, prompt: str) -> Optional[str]:
        if not ZHIPU_API_KEY:
            print("Warning: ZHIPU_API_KEY not set, skipping AI recommendation")
            return None

        headers = {
            "Authorization": f"Bearer {ZHIPU_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": ZHIPU_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 2000,
            "temperature": 0.7
        }

        try:
            resp = requests.post(ZHIPU_API_URL, headers=headers, json=data, timeout=60)
            if resp.status_code == 200:
                result = resp.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                print(f"AI API error: {resp.status_code} - {resp.text}")
                return None
        except Exception as e:
            print(f"AI call failed: {e}")
            return None

    def discover_with_ai(self, user_requirement: str = None) -> List[CandidateRepo]:
        if not user_requirement:
            user_requirement = "我需要一个帮助软件开发团队的 AI Agent Skills，应该包含哪些方面的技能？"

        existing = [f"{c.full_name} (⭐{c.stars})" for c in self.candidates if c.status == CandidateStatus.APPROVED.value]
        existing_str = "\n".join(existing) if existing else "暂无已批准的 Skills"

        prompt = f"""你是一个 GitHub Skills 专家。根据以下需求，推荐适合的 GitHub 仓库：

需求：{user_requirement}

已批准的 Skills：
{existing_str}

请推荐 3-5 个 GitHub 仓库，格式如下：
仓库名 | 描述 | Stars 预估 | 适合原因

只推荐真实存在的、有较高质量的仓库。"""

        ai_response = self.call_zhipu_ai(prompt)

        if not ai_response:
            print("AI 推荐失败，使用默认搜索")
            return self.discover()

        new_candidates = []
        existing_urls = {c.url for c in self.candidates}

        repo_patterns = [
            r'([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)',
        ]

        import re
        for match in re.finditer(r'([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)', ai_response):
            full_name = match.group(0)

            if full_name in existing_urls:
                continue

            try:
                url = f"https://api.github.com/repos/{full_name}"
                resp = requests.get(url, headers=GITHUB_HEADERS, timeout=10)
                if resp.status_code == 200:
                    repo = resp.json()
                    stars = repo.get("stargazers_count", 0)

                    if stars < self.min_stars:
                        continue

                    has_skill, has_plugin, skill_files = self.check_skill_files(full_name)

                    quality_score = self.evaluate_quality(repo, skill_files)

                    candidate = CandidateRepo(
                        name=repo.get("name", ""),
                        full_name=repo.get("full_name", ""),
                        description=repo.get("description", "") or "",
                        stars=stars,
                        url=repo.get("html_url", ""),
                        language=repo.get("language", "") or "",
                        updated_at=repo.get("updated_at", "")[:10],
                        category="ai_agent",
                        discovered_at=datetime.now().strftime("%Y-%m-%d"),
                        quality_score=quality_score,
                        skill_files=skill_files
                    )

                    new_candidates.append(candidate)
                    existing_urls.add(full_name)

            except Exception as e:
                print(f"Error fetching {full_name}: {e}")
                continue

        if new_candidates:
            new_candidates.sort(key=lambda x: -x.quality_score)
            self.candidates.extend(new_candidates)
            self._save_candidates()

        return new_candidates

    def approve(self, full_name: str) -> Optional[CandidateRepo]:
        for candidate in self.candidates:
            if candidate.full_name == full_name:
                candidate.status = CandidateStatus.APPROVED.value
                self._save_candidates()
                return candidate
        return None

    def reject(self, full_name: str, reason: str = "") -> bool:
        for candidate in self.candidates:
            if candidate.full_name == full_name:
                candidate.status = CandidateStatus.REJECTED.value
                candidate.rejection_reason = reason
                self._save_candidates()
                return True
        return False

    def get_approved(self) -> List[CandidateRepo]:
        return [c for c in self.candidates if c.status == CandidateStatus.APPROVED.value]

    def recommend_skills_with_ai(self, requirement: str, top_k: int = 5) -> List[Dict]:
        if not ZHIPU_API_KEY:
            print("Error: ZHIPU_API_KEY not configured")
            return []

        index_path = PROJECT_ROOT / "skills-index.json"
        skill_list = []
        if index_path.exists():
            try:
                import json
                index_data = json.loads(index_path.read_text(encoding='utf-8'))
                for cat_key, cat_info in index_data.get("by_category", {}).items():
                    for skill in cat_info.get("skills", []):
                        skill_list.append({
                            "name": skill.get("name", ""),
                            "category": cat_key,
                            "description": skill.get("description", "")[:100]
                        })
            except Exception:
                pass

        if not skill_list:
            skill_list_text = "Available categories: product, scrum, agile, qa-testing, indie-hacker, dev-workflow, superpowers, ai-product, ai-safety"
        else:
            skill_list_text = "\n".join([
                f"- {s['name']} ({s['category']}): {s['description']}"
                for s in skill_list[:50]
            ])
            if len(skill_list) > 50:
                skill_list_text += f"\n... and {len(skill_list) - 50} more skills"

        system_prompt = f"""You are a skilled product manager and software development expert. 
Given a user's requirement, recommend the most suitable skills from the available skill library.

Available skills:
{skill_list_text}

Return a JSON array of recommended skills with this format:
[{{"name": "skill-name", "category": "category", "reason": "why this skill matches"}}]
Respond with ONLY the JSON array, no other text."""

        user_prompt = f"User requirement: {requirement}\n\nRecommend the top {top_k} skills that would be most helpful. Return ONLY JSON."

        try:
            response = requests.post(
                ZHIPU_API_URL,
                headers={
                    "Authorization": f"Bearer {ZHIPU_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": ZHIPU_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4000,
                    "thinking": {"type": "disabled"}
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                import re
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    recommendations = json.loads(json_match.group())
                    return recommendations
                else:
                    print(f"Failed to parse AI response: {content[:200]}")
                    return []
            else:
                print(f"AI API error: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            print(f"AI recommendation error: {e}")
            return []


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GitHub Skills Discoverer")
    parser.add_argument("--discover", action="store_true", help="Run discovery")
    parser.add_argument("--category", choices=list(SEARCH_QUERIES.keys()), help="Specific category")
    parser.add_argument("--min-stars", type=int, default=50, help="Minimum stars")
    parser.add_argument("--list", action="store_true", help="List pending candidates")
    parser.add_argument("--approve", metavar="FULL_NAME", help="Approve a candidate")
    parser.add_argument("--reject", nargs=2, metavar=("FULL_NAME", "REASON"), help="Reject a candidate")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--recommend", metavar="REQUIREMENT", help="AI-powered skill recommendation")
    parser.add_argument("--top-k", type=int, default=5, help="Number of recommendations (default: 5)")

    args = parser.parse_args()
    discoverer = SkillsDiscoverer(min_stars=args.min_stars)

    if args.discover:
        categories = [args.category] if args.category else None
        print(f"🔍 Discovering skills (min_stars={args.min_stars})...")
        new = discoverer.discover(categories)
        print(f"✅ Found {len(new)} new candidates")
        for c in new[:10]:
            print(f"  [{c.quality_score}] {c.full_name} (⭐{c.stars})")

    elif args.list:
        pending = discoverer.get_pending()
        print(f"📋 Pending candidates: {len(pending)}")
        for c in pending:
            print(f"  [{c.quality_score}] {c.full_name} ({c.category}) - ⭐{c.stars}")

    elif args.approve:
        result = discoverer.approve(args.approve)
        if result:
            print(f"✅ Approved: {result.full_name}")
        else:
            print(f"❌ Not found: {args.approve}")

    elif args.reject:
        full_name, reason = args.reject
        if discoverer.reject(full_name, reason):
            print(f"❌ Rejected: {full_name} ({reason})")
        else:
            print(f"❌ Not found: {full_name}")

    elif args.stats:
        all_cands = discoverer.candidates
        by_status = {}
        for c in all_cands:
            by_status[c.status] = by_status.get(c.status, 0) + 1

        print("📊 Statistics:")
        print(f"  Total candidates: {len(all_cands)}")
        for status, count in by_status.items():
            print(f"  {status}: {count}")

        by_cat = {}
        for c in all_cands:
            by_cat[c.category] = by_cat.get(c.category, 0) + 1
        print("\n  By category:")
        for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {count}")

    elif args.recommend:
        print(f"🤖 AI recommending skills for: {args.recommend}")
        recommendations = discoverer.recommend_skills_with_ai(args.recommend, top_k=args.top_k)
        if recommendations:
            print(f"\n✅ Top {len(recommendations)} recommended skills:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. [{rec.get('category', 'unknown')}] {rec.get('name', 'unknown')}")
                print(f"     Reason: {rec.get('reason', 'N/A')}")
        else:
            print("❌ No recommendations returned")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
