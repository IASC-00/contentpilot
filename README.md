# Project 4: Social Media Automation Tool

## Live Demo
**[contentpilot-eq1y.onrender.com](https://contentpilot-eq1y.onrender.com)**

## Service Demonstrated
**Social Media Automation & Content Strategy** — clients get an AI-powered content
pipeline: brand-voice captions, post scheduling, hashtag research, and performance
guidance — without hiring a full-time social media manager.

## Goal
Build a demo tool that lets a user input their brand info once, then generate a
week of ready-to-post content across Instagram, X (Twitter), and LinkedIn — with
tone matching, hashtag suggestions, and a visual content calendar.

## Demo Deliverable
- Web app: "ContentPilot" demo
- Brand setup: name, industry, tone (professional/casual/bold), audience
- Content generator: pick platform + content type → AI writes post + hashtags
- Batch mode: generate 7-day content calendar in one click
- Content calendar view: weekly grid, color-coded by platform
- Export: copy to clipboard, download as CSV/JSON

## Tech Stack
- Python 3.12
- Flask (backend + API routes)
- Anthropic SDK (Claude Haiku — fast, low cost for caption generation)
- SQLite + SQLAlchemy (brand profiles + generated content storage)
- Vanilla JS (calendar UI, clipboard API)
- CSS Grid (calendar layout)
- No scheduling API needed for demo (generate + export, no actual posting)

---

## Roadmap

### Phase 1 — Brand Profile
- [ ] DB schema: `brands(id, name, industry, tone, audience, keywords, created_at)`
- [ ] DB schema: `posts(id, brand_id, platform, content_type, caption, hashtags, scheduled_date, status)`
- [ ] POST `/api/brand` — create/update brand profile
- [ ] GET `/api/brand/<id>` — retrieve profile
- [ ] Simple onboarding form: name, industry dropdown, tone radio, audience text, 5 keywords

### Phase 2 — Caption Generator
- [ ] POST `/api/generate` — accepts brand_id, platform, content_type, topic (optional)
- [ ] Platform-specific prompt variants:
  - Instagram: 125-150 chars, emojis optional, 5-10 hashtags
  - X/Twitter: ≤280 chars, punchy, 1-2 hashtags max
  - LinkedIn: 150-300 chars, professional, no hashtags (or 2-3 industry tags)
- [ ] Returns: `{caption, hashtags[], char_count, platform}`
- [ ] Regenerate button (same params, fresh output)
- [ ] Tone enforcement: system prompt varies by brand tone setting

### Phase 3 — Batch Calendar Generator
- [ ] POST `/api/generate-week` — brand_id + week start date
- [ ] Strategy:
  - Mon: educational/tip
  - Tue: product/service highlight
  - Wed: behind-the-scenes / story
  - Thu: engagement question
  - Fri: promotion or offer
  - Sat: community/UGC prompt
  - Sun: motivational / brand values
- [ ] Generates 3 posts/day (one per platform) = 21 posts total
- [ ] Saves all to DB with `status='draft'`
- [ ] Returns full week payload

### Phase 4 — Calendar UI
- [ ] Weekly grid: 7 columns (days) × 3 rows (platforms)
- [ ] Each cell: platform icon, content type label, first 60 chars of caption, "Edit" link
- [ ] Click cell → modal with full caption + hashtags + copy button
- [ ] Status badges: Draft / Approved / Scheduled
- [ ] "Approve All" button → marks week as approved
- [ ] Navigation: prev/next week arrows

### Phase 5 — Export & Polish
- [ ] Copy to clipboard: single post or full week
- [ ] Download CSV: date, platform, caption, hashtags, status
- [ ] Download JSON: full structured payload (for Zapier/Make integration)
- [ ] Mobile: calendar collapses to vertical list on small screens
- [ ] Demo mode: pre-populated brand "Harbor Coffee Co." with sample week
- [ ] Record demo GIF, add to portfolio
- [ ] Deploy to Render.com

---

## Success Criteria
- Generate a 7-day calendar for a test brand in < 30 seconds
- Each caption matches platform length constraints (validated client-side)
- Tone difference is clearly perceptible between professional/casual/bold outputs
- CSV export opens correctly in Google Sheets
- Calendar UI is scannable at a glance (color-coded, platform icons clear)

## Key Files
```
04-social-media-automation/
├── app.py                  # Flask routes
├── models.py               # Brand + Post SQLAlchemy models
├── generator.py            # Claude API caption generation logic
├── calendar_builder.py     # 7-day strategy + batch generation
├── prompts/
│   ├── instagram.txt
│   ├── twitter.txt
│   └── linkedin.txt
├── static/
│   ├── calendar.js         # grid UI + modal + export
│   └── style.css
├── templates/
│   ├── index.html          # onboarding + generator
│   └── calendar.html       # weekly calendar view
├── .env.example
└── requirements.txt
```

## Content Strategy Notes
The 7-day framework is based on proven social media principles:
- **Educate** (Mon/Thu): build authority, answer common questions
- **Promote** (Tue/Fri): drive conversions, highlight offers
- **Connect** (Wed/Sat/Sun): humanize brand, encourage engagement
Hashtag research uses curated seed lists per industry — no third-party API needed.
