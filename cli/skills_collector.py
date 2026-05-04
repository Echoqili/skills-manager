#!/usr/bin/env python3
"""
高效 Skills 收集工作流 v2.0
支持多数据源：GitHub Trending、Awesome Lists、Gitee、HuggingFace、ProductHunt 等
"""
import os
import sys
import json
import time
import requests
import re
import feedparser
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from urllib.parse import quote, urlencode

load_dotenv(Path(__file__).parent.parent / ".env")

PROJECT_ROOT = Path(__file__).parent.parent
CANDIDATES_FILE = PROJECT_ROOT / "candidates.json"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_API_URL = os.environ.get("ZHIPU_API_URL", "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions")
ZHIPU_MODEL = os.environ.get("ZHIPU_MODEL", "kimi-k2.6")

# GitHub 代理列表（国内可用）
GITHUB_PROXIES = [
    "",  # 直连
    "https://ghproxy.com/",
    "https://mirror.ghproxy.com/",
    "https://gh-proxy.com/",
    "https://cors.isteed.cc/github.com",
]

# 请求配置
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2

HEADERS = {
    "Accept": "application/json, text/html, application/xml",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


@dataclass
class SkillCandidate:
    name: str
    full_name: str
    url: str
    stars: int
    description: str
    source: str
    category: str = "unknown"
    language: str = ""
    topics: List[str] = None
    
    def __post_init__(self):
        if self.topics is None:
            self.topics = []


def retry_request(url, headers=None, params=None, method="GET", json_data=None, max_retries=MAX_RETRIES, use_proxy=False):
    """带重试的请求"""
    headers = headers or HEADERS
    
    for attempt in range(max_retries):
        try:
            if use_proxy and "github.com" in url:
                for proxy in GITHUB_PROXIES:
                    try:
                        proxy_url = url.replace("https://github.com", proxy.rstrip("/") + "/github.com") if proxy else url
                        if method == "GET":
                            resp = requests.get(proxy_url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
                        else:
                            resp = requests.post(proxy_url, headers=headers, json=json_data, timeout=REQUEST_TIMEOUT)
                        if resp.status_code in [200, 201]:
                            return resp
                    except:
                        continue
            else:
                if method == "GET":
                    resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
                else:
                    resp = requests.post(url, headers=headers, json=json_data, timeout=REQUEST_TIMEOUT)
                
                if resp.status_code in [200, 201]:
                    return resp
                elif resp.status_code == 403:
                    time.sleep(60)
                elif resp.status_code == 404:
                    return None
                    
        except requests.exceptions.SSLError:
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY * 2)
        except Exception as e:
            break
    return None


class MultiSourceCollector:
    """多源收集器 v2.0"""
    
    def __init__(self, min_stars: int = 50):
        self.min_stars = min_stars
        self.collected: List[SkillCandidate] = []
        self.seen_urls: Set[str] = set()
        
    def collect_all(self) -> List[SkillCandidate]:
        print("🚀 开始多源收集 Skills v2.0...")
        
        # 顺序执行，避免并发问题
        sources = [
            ("GitHub Search", self.collect_github_search),
            ("GitHub Trending", self.collect_github_trending),
            ("Gitee Search", self.collect_gitee),
            ("HuggingFace", self.collect_huggingface),
            ("Awesome Lists", self.collect_awesome_lists),
            ("ProductHunt", self.collect_producthunt),
            ("Reddit RSS", self.collect_reddit),
            ("Dev.to", self.collect_devto),
            ("Known Skills", self.collect_known_skills),
        ]
        
        for name, func in sources:
            try:
                print(f"\n📡 {name}...")
                results = func()
                print(f"  ✅ {name}: {len(results)} candidates")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
            time.sleep(1)
        
        self._deduplicate()
        self._save_candidates()
        return self.collected
    
    def collect_github_search(self) -> List[SkillCandidate]:
        """GitHub 搜索"""
        results = []
        
        queries = [
            ("claude-code skill", 20),
            ("cursor rules", 20),
            ("copilot instructions", 20),
            ("ai agent skill", 15),
            ("llm prompt", 15),
            ("claude skill", 15),
            ("agentic workflow", 10),
        ]
        
        for query, per_page in queries:
            url = "https://api.github.com/search/repositories"
            params = {
                "q": f"{query} stars:>{self.min_stars}",
                "per_page": per_page,
                "sort": "stars",
                "order": "desc"
            }
            
            resp = retry_request(url, params=params, use_proxy=True)
            if resp:
                for item in resp.json().get("items", []):
                    candidate = self._parse_github_repo(item, "github-search")
                    if candidate and candidate.url not in self.seen_urls:
                        self.seen_urls.add(candidate.url)
                        self.collected.append(candidate)
                        results.append(candidate)
            
            time.sleep(2)
        
        return results
    
    def collect_github_trending(self) -> List[SkillCandidate]:
        """GitHub Trending（通过非官方API）"""
        results = []
        
        try:
            # 使用 GitHub Trending RSS
            url = "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml"
            resp = retry_request(url)
            if resp:
                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:30]:
                    # 解析仓库名
                    match = re.search(r'github\.com/([^/]+/[^/]+)', entry.link)
                    if match:
                        full_name = match.group(1)
                        repo_data = self._get_github_repo(full_name)
                        if repo_data:
                            candidate = self._parse_github_repo(repo_data, "github-trending")
                            if candidate and candidate.url not in self.seen_urls:
                                self.seen_urls.add(candidate.url)
                                self.collected.append(candidate)
                                results.append(candidate)
        except Exception as e:
            print(f"    Trending error: {e}")
        
        return results
    
    def collect_gitee(self) -> List[SkillCandidate]:
        """Gitee 搜索（国内可用）"""
        results = []
        
        queries = ["claude", "cursor", "copilot", "ai agent", "llm"]
        
        for query in queries:
            try:
                url = "https://gitee.com/api/v5/search/repositories"
                params = {
                    "q": query,
                    "sort": "stars_count",
                    "order": "desc",
                    "per_page": 10
                }
                
                resp = retry_request(url, params=params)
                if resp:
                    for item in resp.json().get("items", []):
                        candidate = SkillCandidate(
                            name=item.get("name", ""),
                            full_name=item.get("full_name", ""),
                            url=item.get("html_url", ""),
                            stars=item.get("stargazers_count", 0),
                            description=item.get("description", "") or "",
                            source="gitee",
                            language=item.get("language", "") or "",
                        )
                        if candidate.stars >= self.min_stars and candidate.url not in self.seen_urls:
                            self.seen_urls.add(candidate.url)
                            self.collected.append(candidate)
                            results.append(candidate)
            except Exception as e:
                print(f"    Gitee error: {e}")
            
            time.sleep(1)
        
        return results
    
    def collect_huggingface(self) -> List[SkillCandidate]:
        """HuggingFace Spaces/Models"""
        results = []
        
        try:
            # 搜索热门 Spaces
            url = "https://huggingface.co/api/spaces"
            params = {"author": "", "filter": "ai-agent", "limit": 20}
            
            resp = retry_request(url, params=params)
            if resp:
                for item in resp.json()[:20]:
                    if isinstance(item, dict):
                        candidate = SkillCandidate(
                            name=item.get("id", "").split("/")[-1],
                            full_name=item.get("id", ""),
                            url=f"https://huggingface.co/spaces/{item.get('id', '')}",
                            stars=item.get("likes", 0),
                            description=item.get("cardData", {}).get("title", "") or "",
                            source="huggingface",
                            category="ai-product",
                        )
                        if candidate.url not in self.seen_urls:
                            self.seen_urls.add(candidate.url)
                            self.collected.append(candidate)
                            results.append(candidate)
        except Exception as e:
            print(f"    HuggingFace error: {e}")
        
        return results
    
    def collect_awesome_lists(self) -> List[SkillCandidate]:
        """精选列表"""
        results = []
        
        awesome_sources = [
            # (仓库, 分类)
            ("sindresorhus/awesome", "superpowers"),
            ("steven2358/awesome-generative-ai", "ai-product"),
            ("e2b-dev/awesome-ai-agents", "ai-product"),
            ("AgentOps-AI/awesome-ai-agents", "ai-product"),
            ("mahseema/awesome-ai-tools", "ai-product"),
            ("humanloop/awesome-chatgpt", "ai-product"),
            ("openai/openai-cookbook", "ai-product"),
            ("anthropics/anthropic-cookbook", "ai-product"),
            ("langchain-ai/langchain", "ai-product"),
            ("microsoft/semantic-kernel", "ai-product"),
            ("public-apis/public-apis", "dev-workflow"),
            ("ripienaar/free-for-dev", "dev-workflow"),
            ("analysis-tools-dev/static-analysis", "dev-quality"),
            ("enaqx/awesome-react", "dev-quality"),
            ("vuejs/awesome-vue", "dev-quality"),
            ("bradtraversy/design-resources-for-developers", "design"),
        ]
        
        for full_name, category in awesome_sources:
            repo_data = self._get_github_repo(full_name)
            if repo_data:
                candidate = self._parse_github_repo(repo_data, "awesome-list")
                if candidate:
                    candidate.category = category
                    if candidate.url not in self.seen_urls:
                        self.seen_urls.add(candidate.url)
                        self.collected.append(candidate)
                        results.append(candidate)
            time.sleep(0.5)
        
        return results
    
    def collect_producthunt(self) -> List[SkillCandidate]:
        """ProductHunt AI 产品"""
        results = []
        
        try:
            # ProductHunt API (非官方)
            url = "https://www.producthunt.com/frontend/graphql"
            query = """
            query {
                posts(order: RANKING, first: 20, topic: "artificial-intelligence") {
                    edges {
                        node {
                            name
                            tagline
                            url
                            votesCount
                            website
                        }
                    }
                }
            }
            """
            
            resp = retry_request(url, method="POST", json_data={"query": query})
            if resp:
                data = resp.json()
                for edge in data.get("data", {}).get("posts", {}).get("edges", []):
                    node = edge.get("node", {})
                    candidate = SkillCandidate(
                        name=node.get("name", ""),
                        full_name=node.get("name", ""),
                        url=node.get("website", "") or node.get("url", ""),
                        stars=node.get("votesCount", 0),
                        description=node.get("tagline", "") or "",
                        source="producthunt",
                        category="ai-product",
                    )
                    if candidate.url not in self.seen_urls:
                        self.seen_urls.add(candidate.url)
                        self.collected.append(candidate)
                        results.append(candidate)
        except Exception as e:
            print(f"    ProductHunt error: {e}")
        
        return results
    
    def collect_reddit(self) -> List[SkillCandidate]:
        """Reddit RSS"""
        results = []
        
        subreddits = ["LocalLLaMA", "ChatGPT", "artificial", "MachineLearning"]
        
        for subreddit in subreddits:
            try:
                url = f"https://www.reddit.com/r/{subreddit}/hot.rss?limit=10"
                resp = retry_request(url)
                if resp:
                    feed = feedparser.parse(resp.content)
                    for entry in feed.entries[:10]:
                        # 查找 GitHub 链接
                        github_links = re.findall(r'github\.com/([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)', entry.summary)
                        for full_name in set(github_links):
                            repo_data = self._get_github_repo(full_name)
                            if repo_data:
                                candidate = self._parse_github_repo(repo_data, "reddit")
                                if candidate and candidate.url not in self.seen_urls:
                                    self.seen_urls.add(candidate.url)
                                    self.collected.append(candidate)
                                    results.append(candidate)
            except Exception as e:
                pass
            
            time.sleep(1)
        
        return results
    
    def collect_devto(self) -> List[SkillCandidate]:
        """Dev.to 文章"""
        results = []
        
        try:
            url = "https://dev.to/api/articles"
            params = {"tag": "ai", "per_page": 20, "top": 7}
            
            resp = retry_request(url, params=params)
            if resp:
                for article in resp.json():
                    # 查找 GitHub 链接
                    github_links = re.findall(r'github\.com/([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)', article.get("body_markdown", ""))
                    for full_name in set(github_links)[:3]:
                        repo_data = self._get_github_repo(full_name)
                        if repo_data:
                            candidate = self._parse_github_repo(repo_data, "devto")
                            if candidate and candidate.url not in self.seen_urls:
                                self.seen_urls.add(candidate.url)
                                self.collected.append(candidate)
                                results.append(candidate)
        except Exception as e:
            print(f"    Dev.to error: {e}")
        
        return results
    
    def collect_known_skills(self) -> List[SkillCandidate]:
        """已知的高质量 Skills 项目"""
        results = []
        
        known_skills = [
            # Claude Code Skills
            ("anthropics/anthropic-cookbook", "ai-product"),
            ("openai/openai-cookbook", "ai-product"),
            ("langchain-ai/langchain", "ai-product"),
            ("microsoft/semantic-kernel", "ai-product"),
            ("e2b-dev/awesome-ai-agents", "ai-product"),
            ("AgentOps-AI/awesome-ai-agents", "ai-product"),
            ("microsoft/playwright", "qa-testing"),
            ("puppeteer/puppeteer", "qa-testing"),
            ("vercel/next.js", "dev-workflow"),
            ("nestjs/nest", "dev-workflow"),
            ("tailwindlabs/tailwindcss", "design"),
            ("shadcn-ui/ui", "design"),
            ("prisma/prisma", "dev-workflow"),
            ("trpc/trpc", "dev-workflow"),
            ("vitest-dev/vitest", "qa-testing"),
            ("jestjs/jest", "qa-testing"),
            ("facebook/react", "dev-quality"),
            ("vuejs/vue", "dev-quality"),
            ("sveltejs/svelte", "dev-quality"),
            ("angular/angular", "dev-quality"),
        ]
        
        for full_name, category in known_skills:
            repo_data = self._get_github_repo(full_name)
            if repo_data:
                candidate = self._parse_github_repo(repo_data, "known-skills")
                if candidate:
                    candidate.category = category
                    if candidate.url not in self.seen_urls:
                        self.seen_urls.add(candidate.url)
                        self.collected.append(candidate)
                        results.append(candidate)
            time.sleep(0.3)
        
        return results
    
    def _get_github_repo(self, full_name: str) -> Optional[Dict]:
        """获取 GitHub 仓库信息"""
        url = f"https://api.github.com/repos/{full_name}"
        resp = retry_request(url, use_proxy=True)
        if resp:
            return resp.json()
        return None
    
    def _parse_github_repo(self, item: Dict, source: str) -> Optional[SkillCandidate]:
        """解析 GitHub 仓库"""
        try:
            return SkillCandidate(
                name=item.get("name", ""),
                full_name=item.get("full_name", ""),
                url=item.get("html_url", ""),
                stars=item.get("stargazers_count", item.get("stars", 0)),
                description=item.get("description", "") or "",
                source=source,
                language=item.get("language", "") or "",
                topics=item.get("topics", []) or []
            )
        except:
            return None
    
    def _deduplicate(self):
        """去重"""
        unique = {}
        for c in self.collected:
            if c.full_name not in unique:
                unique[c.full_name] = c
        self.collected = list(unique.values())
        self.collected.sort(key=lambda x: x.stars, reverse=True)
    
    def _save_candidates(self):
        """保存候选"""
        data = {
            "collected_at": datetime.now().isoformat(),
            "total": len(self.collected),
            "candidates": [asdict(c) for c in self.collected]
        }
        with open(CANDIDATES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 已保存 {len(self.collected)} 个候选到 {CANDIDATES_FILE}")


def classify_with_ai(candidates: List[SkillCandidate], top_k: int = 20) -> List[Dict]:
    """AI 分类"""
    if not ZHIPU_API_KEY:
        print("⚠️ ZHIPU_API_KEY 未配置，跳过 AI 分类")
        return []
    
    print(f"\n🤖 AI 分类 Top {top_k} 候选...")
    
    top_candidates = candidates[:top_k]
    candidate_list = "\n".join([
        f"- {c.full_name} ({c.stars}⭐): {c.description[:80]}"
        for c in top_candidates
    ])
    
    prompt = f"""分析以下 GitHub 仓库，判断哪些是 Claude/Cursor/AI 相关的 Skills 或 Rules 项目。

候选仓库：
{candidate_list}

请返回 JSON 数组，格式：
[{{"full_name": "owner/repo", "is_skill": true/false, "category": "dev-workflow/design/ai-product/superpowers/qa-testing", "reason": "简短理由"}}]

只返回 JSON，不要其他文字。"""

    try:
        resp = requests.post(
            ZHIPU_API_URL,
            headers={
                "Authorization": f"Bearer {ZHIPU_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": ZHIPU_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4000,
                "thinking": {"type": "disabled"}
            },
            timeout=60
        )
        
        if resp.status_code == 200:
            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                return json.loads(match.group())
    except Exception as e:
        print(f"AI 分类错误: {e}")
    
    return []


def main():
    import argparse
    parser = argparse.ArgumentParser(description="高效 Skills 收集工作流 v2.0")
    parser.add_argument("--min-stars", type=int, default=50, help="最小 stars 数")
    parser.add_argument("--classify", action="store_true", help="使用 AI 分类")
    parser.add_argument("--top-k", type=int, default=20, help="AI 分类数量")
    
    args = parser.parse_args()
    
    collector = MultiSourceCollector(min_stars=args.min_stars)
    candidates = collector.collect_all()
    
    print(f"\n📊 收集统计:")
    print(f"  总计: {len(candidates)} 个候选")
    
    by_source = {}
    for c in candidates:
        by_source[c.source] = by_source.get(c.source, 0) + 1
    for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {source}: {count}")
    
    print(f"\n🏆 Top 10 Stars:")
    for i, c in enumerate(candidates[:10], 1):
        print(f"  {i}. {c.full_name} ({c.stars:,}⭐)")
        print(f"     {c.description[:60]}...")
    
    if args.classify and candidates:
        classifications = classify_with_ai(candidates, args.top_k)
        if classifications:
            print(f"\n✅ AI 分类结果:")
            skill_count = sum(1 for c in classifications if c.get("is_skill"))
            print(f"  Skills: {skill_count}/{len(classifications)}")
            
            for c in classifications:
                if c.get("is_skill"):
                    print(f"  ✅ {c['full_name']} -> {c.get('category', 'unknown')}")
                    print(f"     {c.get('reason', '')}")


if __name__ == "__main__":
    main()
