#!/usr/bin/env python3
"""
Content Repurposing Toolkit v2.0
=================================
Premium Python automation tool for generating multi-platform social media content
from articles, URLs, or raw text.

Features:
  - Extract article content from any URL
  - Generate LinkedIn posts (carousel, story, opinion)
  - Generate Twitter/X threads
  - Generate Instagram captions with hashtags
  - Generate Facebook posts
  - Generate blog article from source content
  - Batch mode: process multiple URLs at once
  - CSV/JSON export
  - Multiple tone profiles (professional, casual, viral, thought-leadership)

Usage:
  python repurpose.py --url "https://example.com/article"
  python repurpose.py --file input.txt --mode linkedin
  python repurpose.py --url "https://example.com" --all-formats
  python repurpose.py --batch urls.txt --export csv

Author: Built by Hermes AI Agent
License: Commercial License — Full rights transferred to purchaser
"""

import argparse
import csv
import json
import os
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# Color / terminal utilities
# ──────────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.progress import Progress, SpinnerColumn, TextColumn
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# ──────────────────────────────────────────────────────────────────────
# Console helpers
# ──────────────────────────────────────────────────────────────────────
c = Console() if HAS_RICH else None

def info(msg):
    if c: c.print(f"[bold blue]ℹ[/] {msg}")
    else: print(f"[INFO] {msg}")

def success(msg):
    if c: c.print(f"[bold green]✓[/] {msg}")
    else: print(f"[OK] {msg}")

def warn(msg):
    if c: c.print(f"[bold yellow]⚠[/] {msg}")
    else: print(f"[WARN] {msg}")

def error(msg):
    if c: c.print(f"[bold red]✗[/] {msg}", file=sys.stderr)
    else: print(f"[ERROR] {msg}", file=sys.stderr)

def header(text):
    if c:
        c.print(Panel(f"[bold cyan]{text}[/]", border_style="cyan"))
    else:
        print(f"\n{'='*60}\n{text}\n{'='*60}")

def print_result(label, content):
    if c:
        c.print(f"\n[bold yellow]── {label} ──[/]")
        c.print(Panel(content[:2000], border_style="green"))
    else:
        print(f"\n── {label} ──")
        print(content[:2000])

def show_banner():
    banner = """
╔══════════════════════════════════════════════╗
║     Content Repurposing Toolkit v2.0         ║
║  URL → Multi-Platform Content in Seconds     ║
╚══════════════════════════════════════════════╝
"""
    if c:
        c.print(f"[bold cyan]{banner}[/]")
    else:
        print(banner)


# ──────────────────────────────────────────────────────────────────────
# Content Extraction
# ──────────────────────────────────────────────────────────────────────
def extract_from_url(url: str) -> dict:
    """Extract article content from a URL. Falls back gracefully."""
    if not HAS_REQUESTS or not HAS_BS4:
        warn("requests/BeautifulSoup not installed. Using placeholder content.")
        return {
            "title": "Sample Article Title (install requests + beautifulsoup4 for live extraction)",
            "content": "This is sample content. Install dependencies with: pip install requests beautifulsoup4",
            "source": url,
            "word_count": 12,
        }

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove non-content elements
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)

        # Try common article containers
        article = soup.find("article")
        if not article:
            article = soup.find("main")
        if not article:
            article = soup.find("div", class_=re.compile(r"(content|post|article|entry)", re.I))
        if not article:
            article = soup.body

        paragraphs = []
        if article:
            for p in article.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]):
                text = p.get_text(strip=True)
                if len(text) > 15:
                    paragraphs.append(text)

        content = "\n\n".join(paragraphs[:80])  # limit to 80 paragraphs
        word_count = len(content.split())

        return {
            "title": title or "Untitled Article",
            "content": content or "Could not extract meaningful content from this URL.",
            "source": url,
            "word_count": word_count,
        }
    except requests.RequestException as e:
        error(f"Failed to fetch URL: {e}")
        return {
            "title": "Extraction Failed",
            "content": f"Could not fetch content from: {url}\nError: {e}",
            "source": url,
            "word_count": 0,
        }


def extract_from_file(path: str) -> dict:
    """Read content from a local text file."""
    p = Path(path)
    if not p.exists():
        error(f"File not found: {path}")
        return {"title": p.name, "content": "", "source": path, "word_count": 0}

    content = p.read_text(encoding="utf-8", errors="replace")
    return {
        "title": p.stem.replace("_", " ").replace("-", " ").title(),
        "content": content,
        "source": path,
        "word_count": len(content.split()),
    }


# ──────────────────────────────────────────────────────────────────────
# Content Generation Templates (Template-based, no API key needed)
# ──────────────────────────────────────────────────────────────────────
def generate_linkedin_posts(article: dict, tone: str = "professional") -> dict:
    """Generate LinkedIn-optimized posts."""
    title = article["title"]
    content = article["content"]
    sentences = content.replace("\n", " ").split(". ")
    key_points = [s.strip() for s in sentences[:8] if len(s.strip()) > 30]

    tones = {
        "professional": {
            "intro": "I've been diving deep into",
            "hook": "Here's what stood out to me 👇",
            "cta": "What's your take on this? Drop your thoughts below.",
        },
        "thought-leadership": {
            "intro": "Most people overlook this, but",
            "hook": "After analyzing this topic extensively, here's my perspective:",
            "cta": "I'd love to hear your experience. Comment below.",
        },
        "casual": {
            "intro": "Okay, so I came across",
            "hook": "And honestly? This blew my mind 🤯",
            "cta": "Agree or disagree? Let me know!",
        },
        "viral": {
            "intro": "🚨 HOT TAKE:",
            "hook": "Here's why this changes everything 👇",
            "cta": "Share this with someone who needs to see it. ♻️",
        },
    }
    t = tones.get(tone, tones["professional"])

    posts = {}

    # Post 1: Story / Insight
    body = f"""{t['intro']} {title}.

{t['hook']}

"""
    for i, pt in enumerate(key_points[:4], 1):
        body += f"{i}. {pt}\n\n"

    body += f"""The landscape is shifting fast, and those who adapt will come out ahead.

{t['cta']}

#ContentStrategy #DigitalMarketing #GrowthMindset #AI #Innovation"""

    posts["story_insight"] = body.strip()

    # Post 2: List / Carousel-style
    body = f"""📌 **{len(key_points[:6])} Key Takeaways from {title}**

"""
    for i, pt in enumerate(key_points[:6], 1):
        body += f"  {i}. {pt}\n\n"

    body += f"""Which of these resonates most with you?

{t['cta']}

#BusinessTips #Leadership #Productivity #FutureOfWork"""

    posts["key_takeaways"] = body.strip()

    # Post 3: Question / Engagement
    body = f"""💡 **One question about {title}**

Before I read this, I thought {key_points[0][:80].lower()}...

But after digging deeper, I realized the real opportunity is completely different.

Question for you: **{' '.join(key_points[1].split()[:15]) if len(key_points) > 1 else 'What is your biggest takeaway from this?'}**

{t['cta']}

#Strategy #Insights #Growth #Learning"""

    posts["question_engagement"] = body.strip()

    return posts


def generate_twitter_thread(article: dict, tone: str = "casual") -> str:
    """Generate a Twitter/X thread."""
    title = article["title"]
    content = article["content"]
    sentences = content.replace("\n", " ").split(". ")
    points = [s.strip() for s in sentences if 20 < len(s.strip()) < 280]

    tweets = []
    tweets.append(f"🧵 {title}\n\nA thread on what you need to know 👇")
    tweets.append(f"1/ The TL;DR:\n\n{points[0][:250] if points else 'This changes how we think about the space.'}")

    for i, pt in enumerate(points[1:8], 2):
        tweet = f"{i}/ {pt[:260]}"
        tweets.append(tweet)

    tweets.append(f"{len(tweets)}/ Bottom line: {' '.join(points[0].split()[:20]) if points else 'Adapt or get left behind.'} \n\nWhat do you think? RT if you found this valuable ♻️")

    return "\n\n".join(tweets)


def generate_instagram_captions(article: dict, tone: str = "casual") -> dict:
    """Generate Instagram captions with hashtags."""
    title = article["title"]
    content = article["content"]
    words = content.split()
    short_hook = " ".join(words[:15]) if words else title

    hashtags_pool = [
        "#contentmarketing", "#digitalmarketing", "#socialmedia", "#growth",
        "#marketingtips", "#businessgrowth", "#entrepreneur", "#startup",
        "#innovation", "#technology", "#future", "#success", "#strategy",
        "#productivity", "#leadership", "#marketingstrategy", "#contentcreation",
        "#branding", "#onlinemarketing", "#socialmediamarketing",
        "#businesstips", "#growthhacking", "#digitaltransformation", "#AI",
        "#automation", "#trending", "#viral", "#marketing", "#business",
    ]

    captions = {}

    # Educational caption
    captions["educational"] = f"""🔍 **{title}**

Here's what you need to know:

{short_hook[:200]}...

Save this post for later 📌 and follow for more insights like this.

{" ".join(hashtags_pool[:10])}"""

    # Storytelling caption
    captions["storytelling"] = f"""📖 **The Story Behind {title}**

I came across this and it completely shifted my perspective.

{short_hook[:180]}...

Double tap if this resonates ❤️
Share with someone who needs to see this 🔄

{" ".join(hashtags_pool[5:15])}"""

    # Viral-style caption
    captions["viral"] = f"""🚨 **STOP scrolling and read this 👇**

{title}

{short_hook[:150]}...

Tag someone who needs to see this 📌
Follow for daily insights ✅

{" ".join(hashtags_pool[10:20])}"""

    return captions


def generate_facebook_post(article: dict, tone: str = "casual") -> str:
    """Generate a Facebook-optimized post."""
    title = article["title"]
    content = article["content"]
    sentences = content.replace("\n", " ").split(". ")
    key_points = [s.strip() for s in sentences[:6] if len(s.strip()) > 30]

    post = f"""🔥 **{title}**

I just read something eye-opening and had to share.

{" ".join(key_points[:3])}

{' '.join(key_points[3:6]) if len(key_points) > 3 else ''}

💬 What's your experience with this? Drop a comment below.
👍 Like if you found this valuable.
🔗 Share with your network.

#ContentMarketing #DigitalStrategy #BusinessGrowth #Insights"""
    return post.strip()


def generate_blog_post(article: dict, tone: str = "professional") -> str:
    """Generate a complete blog post from source content."""
    title = article["title"]
    content = article["content"]
    sentences = content.replace("\n", " ").split(". ")
    points = [s.strip() for s in sentences if len(s.strip()) > 40]

    intro = points[0] if points else "This topic has been gaining significant attention recently."
    body_points = points[1:8] if len(points) > 1 else ["This is a crucial aspect to understand.", "Let's dive deeper into the implications."]

    blog = f"""# {title}

**Published:** {datetime.now().strftime('%B %d, %Y')}
**Reading time:** 5 min read

---

## Introduction

{intro}

{' '.join(points[1:3]) if len(points) > 2 else ''}

## Why This Matters Now

{body_points[0] if body_points else ''}

{' '.join(body_points[1:3]) if len(body_points) > 1 else ''}

## Key Insights

"""
    for i, pt in enumerate(body_points[:5], 1):
        blog += f"### {i}. {' '.join(pt.split()[:10])}...\n\n{pt}\n\n"

    blog += """## The Bottom Line

The landscape continues to evolve rapidly. Those who stay informed and adapt will find the most success.

---

*This article was generated from source content analysis.*

*Want more insights like this? Subscribe for updates.*"""

    return blog


# ──────────────────────────────────────────────────────────────────────
# Export functions
# ──────────────────────────────────────────────────────────────────────
def export_to_csv(data: list, output_path: str):
    """Export generated content to CSV."""
    fieldnames = ["format", "platform", "tone", "content"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    success(f"Exported to {output_path}")


def export_to_json(data: dict, output_path: str):
    """Export generated content to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    success(f"Exported to {output_path}")


# ──────────────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────────────
def process_url(url: str, all_formats: bool = False, mode: str = "all", tone: str = "professional"):
    """Process a single URL through the content pipeline."""
    header(f"Processing: {url}")

    article = extract_from_url(url)
    info(f"Title: {article['title']}")
    info(f"Word count: {article['word_count']}")

    if article["word_count"] < 10 and "install" in article["content"].lower():
        warn("Content extraction limited. Install dependencies for better results.")
        info("Run: pip install requests beautifulsoup4")

    results = {"source": url, "title": article["title"], "generated": []}

    formats = []
    if all_formats:
        formats = ["linkedin", "twitter", "instagram", "facebook", "blog"]
    elif mode != "all":
        formats = [mode]
    else:
        formats = ["linkedin", "twitter", "instagram", "facebook", "blog"]

    for fmt in formats:
        if fmt == "linkedin":
            posts = generate_linkedin_posts(article, tone)
            for post_type, post_content in posts.items():
                label = f"LinkedIn — {post_type.replace('_', ' ').title()}"
                print_result(label, post_content)
                results["generated"].append({
                    "format": "post",
                    "platform": "linkedin",
                    "tone": tone,
                    "type": post_type,
                    "content": post_content,
                })

        elif fmt == "twitter":
            thread = generate_twitter_thread(article, tone)
            print_result("Twitter/X Thread", thread)
            results["generated"].append({
                "format": "thread",
                "platform": "twitter",
                "tone": tone,
                "type": "thread",
                "content": thread,
            })

        elif fmt == "instagram":
            captions = generate_instagram_captions(article, tone)
            for cap_type, cap_content in captions.items():
                label = f"Instagram — {cap_type.title()}"
                print_result(label, cap_content)
                results["generated"].append({
                    "format": "caption",
                    "platform": "instagram",
                    "tone": tone,
                    "type": cap_type,
                    "content": cap_content,
                })

        elif fmt == "facebook":
            post = generate_facebook_post(article, tone)
            print_result("Facebook Post", post)
            results["generated"].append({
                "format": "post",
                "platform": "facebook",
                "tone": tone,
                "type": "standard",
                "content": post,
            })

        elif fmt == "blog":
            blog = generate_blog_post(article, tone)
            print_result("Blog Article", blog)
            results["generated"].append({
                "format": "article",
                "platform": "blog",
                "tone": tone,
                "type": "article",
                "content": blog,
            })

    return results


def main():
    show_banner()

    parser = argparse.ArgumentParser(
        description="Content Repurposing Toolkit — Turn any URL into multi-platform content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python repurpose.py --url "https://example.com/article"
              python repurpose.py --url "https://example.com" --all-formats
              python repurpose.py --url "https://example.com" --mode linkedin --tone viral
              python repurpose.py --file my_notes.txt --all-formats
              python repurpose.py --batch urls.txt --export csv
        """)
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="URL of the article/content to repurpose")
    source.add_argument("--file", help="Local text file to use as source")
    source.add_argument("--batch", help="Text file with one URL per line")

    parser.add_argument("--mode", choices=["linkedin", "twitter", "instagram", "facebook", "blog", "all"],
                       default="all", help="Output format (default: all)")
    parser.add_argument("--all-formats", action="store_true",
                       help="Generate all available formats")
    parser.add_argument("--tone", choices=["professional", "casual", "viral", "thought-leadership"],
                       default="professional", help="Content tone (default: professional)")
    parser.add_argument("--export", choices=["csv", "json"], help="Export results to file")
    parser.add_argument("--output", default="output", help="Output filename (without extension)")

    args = parser.parse_args()

    all_results = []

    if args.batch:
        if not os.path.exists(args.batch):
            error(f"Batch file not found: {args.batch}")
            sys.exit(1)
        with open(args.batch) as f:
            urls = [line.strip() for line in f if line.strip()]
        info(f"Processing {len(urls)} URLs from batch file")
        for url in urls:
            result = process_url(url, args.all_formats, args.mode, args.tone)
            all_results.append(result)
    elif args.url:
        result = process_url(args.url, args.all_formats, args.mode, args.tone)
        all_results.append(result)
    elif args.file:
        article = extract_from_file(args.file)
        header(f"File: {args.file}")
        info(f"Title: {article['title']}")
        info(f"Word count: {article['word_count']}")

        if article["word_count"] == 0:
            error("File is empty or could not be read.")
            sys.exit(1)

        # Wrap file content as URL result
        result = process_url(args.file, args.all_formats, args.mode, args.tone)
        all_results.append(result)

    if args.export:
        flat = []
        for r in all_results:
            for g in r["generated"]:
                flat.append(g)

        ext = args.export
        output_path = f"{args.output}.{ext}"
        if ext == "csv":
            export_to_csv(flat, output_path)
        else:
            export_to_json({"results": flat}, output_path)

    summary = sum(len(r["generated"]) for r in all_results)
    success(f"Done! Generated {summary} pieces of content across {len(all_results)} source(s).")
    success(f"Ready to post on: LinkedIn, Twitter/X, Instagram, Facebook, Blog")


if __name__ == "__main__":
    main()
