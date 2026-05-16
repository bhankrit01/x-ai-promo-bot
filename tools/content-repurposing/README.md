# Content Repurposing Toolkit v2.0

**Turn any URL into 15+ pieces of multi-platform content in seconds.**

Transform articles, blog posts, and content into ready-to-post material for LinkedIn, Twitter/X, Instagram, Facebook, and your blog — all with a single command.

## 🚀 What It Does

| Input | Output |
|-------|--------|
| Any article URL | LinkedIn posts (3 styles: Story, Takeaways, Engagement) |
| Local text file | Twitter/X thread (8-10 tweets) |
| Batch URLs file | Instagram captions (3 styles: Educational, Storytelling, Viral) |
| | Facebook post (engagement-optimized) |
| | Complete blog article |

## ✨ Features

- **Zero API keys required** — Works entirely with template-based generation (no OpenAI/API costs)
- **Rich CLI interface** — Beautiful terminal output with `rich` library
- **4 tone profiles** — Professional, Casual, Viral, Thought-Leadership
- **Batch processing** — Process multiple URLs from a file
- **Export to CSV/JSON** — Integrate with your content calendar tools
- **Smart content extraction** — Pulls clean article text from any webpage
- **Portable** — Single Python file, easy to deploy anywhere

## 📦 Installation

```bash
# Recommended — Full features with rich formatting
pip install requests beautifulsoup4 rich

# Minimal — Works with just Python stdlib
# (No installation needed, but content extraction is limited)
```

## 🎯 Quick Start

```bash
# Generate all formats from a URL
python repurpose.py --url "https://example.com/your-article" --all-formats

# Generate only LinkedIn content with viral tone
python repurpose.py --url "https://example.com/your-article" --mode linkedin --tone viral

# Generate from a local text file
python repurpose.py --file my_article.txt --all-formats

# Process multiple URLs
python repurpose.py --batch urls.txt --all-formats

# Export results to CSV for your content calendar
python repurpose.py --url "https://example.com/article" --all-formats --export csv --output my_content
```

## 🎨 Tone Profiles

| Tone | Best For | Style |
|------|----------|-------|
| `professional` | LinkedIn, B2B | Polished, data-driven, formal |
| `casual` | Instagram, Facebook | Friendly, conversational, relatable |
| `viral` | Twitter/X, Instagram | Bold hooks, shareable, high-energy |
| `thought-leadership` | LinkedIn, Blog | Authority-building, opinion-driven |

## 📤 Output Examples

### LinkedIn Story Post
```
I've been diving deep into [topic].
Here's what stood out to me 👇
1. Key insight one...
2. Key insight two...
What's your take on this? Drop your thoughts below.
#ContentStrategy #DigitalMarketing #GrowthMindset
```

### Twitter/X Thread (8 tweets)
A complete thread structure with hooks, insights, and CTA.

### Instagram Captions (3 versions)
Educational, storytelling, and viral-style captions with optimized hashtags.

### Facebook Post
Engagement-focused post optimized for shares and comments.

### Blog Article
Complete 1000+ word article with introduction, sections, and conclusion.

## 💰 How to Monetize This Tool

### 1. Freelance Service (Fiverr / Upwork)
Offer "Social Media Content Repurposing" as a gig:
- **Basic ($50)** — Repurpose 1 URL into 5 platform posts
- **Standard ($100)** — Repurpose 3 URLs + tone customization
- **Premium ($200)** — Repurpose 10 URLs + CSV export + branding

### 2. Sell as Digital Product (Gumroad / CodeCanyon)
- Price: **$29–$97** (one-time purchase)
- Includes: repurpose.py + documentation + commercial license

### 3. Content Agency Package
- White-label for clients at **$200–$500/month**
- Automate content calendars for small businesses

## 📋 Requirements

- Python 3.8+
- Optional: `requests`, `beautifulsoup4`, `rich` (for full features)

## 📄 License

**Commercial License** — Full rights transferred to purchaser.
You may sell, modify, distribute, and use this tool commercially.

---

*Built with Hermes AI Agent — Ready for immediate commercial use.*
