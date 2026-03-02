import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template, request
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret')

DB_URL = os.environ.get('DATABASE_URL', 'sqlite:///contentpilot.db')
engine = create_engine(DB_URL, connect_args={'check_same_thread': False} if 'sqlite' in DB_URL else {})
Base = declarative_base()
SessionFactory = sessionmaker(bind=engine)


class Brand(Base):
    __tablename__ = 'brands'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    industry = Column(String(100))
    tone = Column(String(50), default='casual')
    audience = Column(String(500))
    keywords = Column(Text, default='[]')
    niche = Column(String(50), default='')
    posts = relationship('Post', back_populates='brand', cascade='all, delete-orphan')


class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True)
    brand_id = Column(Integer, ForeignKey('brands.id'))
    platform = Column(String(50))
    content_type = Column(String(100))
    caption = Column(Text)
    hashtags = Column(Text, default='')
    scheduled_date = Column(String(20))
    status = Column(String(20), default='draft')
    created_at = Column(DateTime, default=datetime.utcnow)
    brand = relationship('Brand', back_populates='posts')


@contextmanager
def get_db():
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


Base.metadata.create_all(engine)

ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
GENERATOR_MODEL = os.environ.get('GENERATOR_MODEL', 'claude-haiku-4-5-20251001')

TONE_GUIDE = {
    'professional': 'polished and authoritative — no slang or casual language',
    'casual': 'friendly, warm, and conversational',
    'bold': 'confident and attention-grabbing — use strong action words, be direct',
}

# Default week strategy (used when no niche is set)
WEEK_STRATEGY = [
    ('Monday',    'educational',       'share a useful tip or how-to'),
    ('Tuesday',   'product',           'highlight a specific product or service'),
    ('Wednesday', 'behind-the-scenes', 'show what happens behind the scenes'),
    ('Thursday',  'engagement',        'ask a question to spark conversation'),
    ('Friday',    'promotion',         'promote a special offer or deal'),
    ('Saturday',  'community',         'spotlight the community or prompt UGC'),
    ('Sunday',    'inspiration',       'share a motivational message or brand value'),
]

# Niche-specific strategies and messaging philosophy
NICHES = {
    'local-service': {
        'label': 'Local Service',
        'examples': 'salon, gym, med spa, dentist, auto shop',
        'tone': 'casual',
        'audience': 'local residents and neighborhood community',
        'keywords': ['local', 'community', 'professional', 'trusted', 'quality service'],
        'platforms': ['instagram', 'linkedin'],
        'week': [
            ('Monday',    'educational',      'share a care tip related to your service area'),
            ('Tuesday',   'service-spotlight','highlight a specific service and what makes it worthwhile'),
            ('Wednesday', 'behind-the-scenes','show your team, workspace, or tools in action'),
            ('Thursday',  'social-proof',     'share a client result or transformation (no names needed)'),
            ('Friday',    'promotion',        'weekend special or last-minute availability push'),
            ('Saturday',  'community',        'shoutout a local business or highlight a community event'),
            ('Sunday',    'brand-values',     'why you do what you do — your story and mission'),
        ],
        'notes': 'Local trust is the whole game. Lead with social proof and real results. Mention the neighborhood. CTAs should be booking or calling, never vague. Use "we" not "I". Specificity beats inspiration here.',
    },
    'real-estate': {
        'label': 'Real Estate',
        'examples': 'agent, broker, mortgage specialist, property manager',
        'tone': 'professional',
        'audience': 'homebuyers, sellers, local investors, and people planning to relocate',
        'keywords': ['local market', 'trusted agent', 'home buying', 'real estate', 'investment'],
        'platforms': ['instagram', 'linkedin'],
        'week': [
            ('Monday',    'market-update',   'local market stat or trend with your expert take on what it means'),
            ('Tuesday',   'listing-spotlight','feature a listing — focus on the lifestyle, not just the specs'),
            ('Wednesday', 'educational',     'buyer or seller tip (mortgage rate, staging, inspection, negotiation)'),
            ('Thursday',  'client-story',    'anonymized client win: the challenge, the solution, the outcome'),
            ('Friday',    'just-listed',     'new listing or recent close — celebrate the milestone'),
            ('Saturday',  'neighborhood',    'spotlight a neighborhood, school district, or local amenity'),
            ('Sunday',    'personal-brand',  'your why, your values, who you are beyond the transactions'),
        ],
        'notes': 'Personal brand IS the product in real estate. Specificity wins — generic market posts get ignored. Build local expertise through consistent, concrete content. Always include a clear next step: DM, link in bio, schedule a call.',
    },
    'restaurant': {
        'label': 'Restaurant / Café',
        'examples': 'restaurant, café, coffee shop, food truck, bar, bakery',
        'tone': 'casual',
        'audience': 'local food lovers, regulars, and neighborhood residents',
        'keywords': ['fresh', 'local', 'handcrafted', 'seasonal', 'community'],
        'platforms': ['instagram', 'twitter'],
        'week': [
            ('Monday',    'week-preview',    'build anticipation — what\'s new or special coming this week'),
            ('Tuesday',   'dish-spotlight',  'feature one dish or drink with rich sensory detail'),
            ('Wednesday', 'behind-the-scenes','kitchen prep, ingredient sourcing, or the story behind a recipe'),
            ('Thursday',  'engagement',      'ask about food preferences, memories, or favorite orders'),
            ('Friday',    'weekend-special', 'weekend feature, reservation push, or evening event'),
            ('Saturday',  'community',       'thank regulars, reshare customer photos, or spotlight a supplier'),
            ('Sunday',    'origin-story',    'the family, the mission, the reason behind the food'),
        ],
        'notes': 'Make people hungry and feel welcome before they walk in. Describe food with sensory language — taste, texture, warmth, smell. Locality and sourcing build trust. Every post should make someone want to visit today.',
    },
    'ecommerce': {
        'label': 'E-commerce / Product',
        'examples': 'online store, product brand, Shopify, Etsy seller',
        'tone': 'bold',
        'audience': 'online shoppers and fans of your product category',
        'keywords': ['quality', 'fast shipping', 'handpicked', 'limited edition', 'customer favorite'],
        'platforms': ['instagram', 'twitter'],
        'week': [
            ('Monday',    'product-drop',   'new arrival or restocked item — build excitement and urgency'),
            ('Tuesday',   'lifestyle',      'show the product in context: the life it enables, not just the item'),
            ('Wednesday', 'how-to',         'how to use, style, care for, or get the most from your product'),
            ('Thursday',  'social-proof',   'customer review, unboxing photo, or UGC testimonial'),
            ('Friday',    'promotion',      'weekend sale, bundle deal, or free shipping offer with real urgency'),
            ('Saturday',  'community',      'customer spotlight, tag campaign, or UGC reshare'),
            ('Sunday',    'brand-story',    'your founding story, your why, what the brand stands for'),
        ],
        'notes': 'Sell the outcome, not the product. Show what life looks like with it. Use urgency honestly — never fake scarcity. Social proof (real reviews, real photos) beats anything you write yourself. The CTA should always be one click away.',
    },
    'professional-services': {
        'label': 'Professional Services',
        'examples': 'accountant, lawyer, consultant, business coach, financial advisor',
        'tone': 'professional',
        'audience': 'business owners, professionals, and decision-makers in your sector',
        'keywords': ['expertise', 'results-driven', 'trusted advisor', 'strategy', 'growth'],
        'platforms': ['linkedin', 'twitter'],
        'week': [
            ('Monday',    'industry-insight', 'a trend, news item, or data point with your expert take'),
            ('Tuesday',   'how-to',           'a practical tip your audience can act on immediately'),
            ('Wednesday', 'case-study',       'anonymized client win: the problem, the approach, the result'),
            ('Thursday',  'myth-bust',        'debunk a common misconception in your field with facts'),
            ('Friday',    'week-wrap',        'key insight from the week or something to prepare for next week'),
            ('Saturday',  'personal',         'your values, your story, what drives you beyond the work'),
            ('Sunday',    'forward-looking',  'help your audience prepare mentally or practically for the week ahead'),
        ],
        'notes': 'Authority comes from consistency and specificity — never be vague. Give real, actionable information. Every post should make the reader feel they learned something or saved time. LinkedIn rewards depth; Twitter rewards clarity and hot takes.',
    },
    'fitness-wellness': {
        'label': 'Fitness & Wellness',
        'examples': 'personal trainer, yoga studio, nutritionist, physical therapist',
        'tone': 'bold',
        'audience': 'health-conscious individuals working toward their fitness and wellness goals',
        'keywords': ['transformation', 'consistency', 'results', 'community', 'progress'],
        'platforms': ['instagram', 'twitter'],
        'week': [
            ('Monday',    'motivation',     'kick off the week with energy, accountability, and a clear goal'),
            ('Tuesday',   'workout-tip',    'exercise technique, routine structure, or form correction'),
            ('Wednesday', 'nutrition',      'food, meal prep, hydration, or recovery strategy'),
            ('Thursday',  'client-win',     'a transformation story or milestone (with permission)'),
            ('Friday',    'challenge',      'give followers a weekend challenge or specific action to take'),
            ('Saturday',  'community',      'group energy, class shoutout, or community appreciation post'),
            ('Sunday',    'mindset',        'rest, recovery, and the mental and emotional side of health'),
        ],
        'notes': 'Your audience is working on themselves — honor that in every post. Make them feel capable, not inadequate. Vulnerability resonates more than perfection. Consistency and accountability messaging outperforms motivation-only content over time.',
    },
}


def seed_demo():
    with get_db() as db:
        if not db.query(Brand).first():
            db.add(Brand(
                name='Harbor Coffee Co.',
                industry='specialty coffee shop',
                tone='casual',
                audience='coffee lovers, young professionals, locals in Fells Point, Baltimore',
                keywords=json.dumps(['specialty coffee', 'local', 'community', 'artisan', 'sustainable']),
                niche='restaurant',
            ))


seed_demo()


def brand_to_dict(brand):
    return {
        'id': brand.id,
        'name': brand.name,
        'industry': brand.industry,
        'tone': brand.tone,
        'audience': brand.audience,
        'keywords': json.loads(brand.keywords or '[]'),
        'niche': brand.niche or '',
    }


def post_to_dict(post):
    day = None
    if post.scheduled_date:
        try:
            dt = datetime.strptime(post.scheduled_date, '%Y-%m-%d')
            day = dt.strftime('%A')
        except Exception:
            pass
    return {
        'id': post.id,
        'platform': post.platform,
        'content_type': post.content_type,
        'caption': post.caption or '',
        'hashtags': post.hashtags or '',
        'scheduled_date': post.scheduled_date,
        'day': day,
        'status': post.status,
    }


def generate_single(brand_data, platform, topic, content_type):
    from anthropic import Anthropic
    platform_guide = {
        'twitter':   'Twitter/X: max 280 total characters including hashtags. 1–2 hashtags only. Punchy and direct.',
        'instagram': 'Instagram: 1–2 engaging sentences of copy, then a blank line, then 6–8 hashtags.',
        'linkedin':  'LinkedIn: 2–3 professional sentences (150–300 chars), then 2–3 industry hashtags.',
    }
    niche_data = NICHES.get(brand_data.get('niche', ''), {})
    niche_notes = niche_data.get('notes', '')
    prompt = f"""You are writing social media content for {brand_data['name']}, a {brand_data['industry']} brand.
Tone: {TONE_GUIDE.get(brand_data.get('tone', 'casual'))}
Audience: {brand_data.get('audience', '')}
Keywords: {', '.join(brand_data.get('keywords', []))}
{f'Messaging philosophy: {niche_notes}' if niche_notes else ''}

Format: {platform_guide[platform]}
Topic: {topic}
Content type: {content_type}

Return ONLY the post text with hashtags. No quotes, labels, or explanation."""
    client = Anthropic(api_key=ANTHROPIC_KEY)
    msg = client.messages.create(
        model=GENERATOR_MODEL,
        max_tokens=400,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return msg.content[0].text.strip()


def generate_week(brand_data):
    from anthropic import Anthropic
    niche_data = NICHES.get(brand_data.get('niche', ''), {})
    week = niche_data.get('week', WEEK_STRATEGY)
    niche_notes = niche_data.get('notes', '')
    strategy_lines = '\n'.join(f'- {day} ({ctype}): {hint}' for day, ctype, hint in week)
    prompt = f"""Create a 7-day social media content calendar for {brand_data['name']}, a {brand_data['industry']} brand.
Tone: {TONE_GUIDE.get(brand_data.get('tone', 'casual'))}
Audience: {brand_data.get('audience', '')}
Keywords: {', '.join(brand_data.get('keywords', []))}
{f'Messaging philosophy: {niche_notes}' if niche_notes else ''}

Daily strategy:
{strategy_lines}

For each day write posts for all 3 platforms:
- twitter: max 280 total chars including hashtags, 1–2 hashtags
- instagram: 1–2 sentences of copy + blank line + 6–8 hashtags
- linkedin: 2–3 professional sentences + 2–3 hashtags

Return a JSON array of exactly 21 objects:
{{"day": "Monday", "platform": "twitter", "content_type": "educational", "caption": "full post text", "hashtags": "#Tag1 #Tag2"}}

Return ONLY the JSON array, no explanation."""
    client = Anthropic(api_key=ANTHROPIC_KEY)
    msg = client.messages.create(
        model=GENERATOR_MODEL,
        max_tokens=4096,
        messages=[{'role': 'user', 'content': prompt}],
    )
    text = msg.content[0].text.strip()
    match = re.search(r'\[[\s\S]*\]', text)
    return json.loads(match.group() if match else text)


def demo_single(brand_data, platforms, topic):
    name = brand_data.get('name', 'Our Brand')
    results = {}
    if 'twitter' in platforms:
        results['twitter'] = f"At {name}, every detail matters. {topic} — because you deserve nothing less. #LocalBusiness #QualityFirst"
    if 'instagram' in platforms:
        results['instagram'] = f"Every experience at {name} is crafted with care. {topic} — quality and community in every cup.\n\n#LocalBusiness #CommunityFirst #SmallBusiness #QualityMatters #ShopLocal #Crafted"
    if 'linkedin' in platforms:
        results['linkedin'] = f"At {name}, we're committed to the highest standard. {topic} reflects our dedication to the community we serve. Proud to do this work every day.\n\n#LocalBusiness #Community #Excellence"
    return results


def demo_week():
    return [
        {"day":"Monday","platform":"twitter","content_type":"educational","caption":"Pro tip: espresso pulls best at 9 bars for 25–30 seconds. That's the science behind every shot at Harbor Coffee ☕ #CoffeeFacts #Espresso","hashtags":"#CoffeeFacts #Espresso"},
        {"day":"Monday","platform":"instagram","content_type":"educational","caption":"Did you know grind size affects everything? Finer = stronger, coarser = smoother. We dial in every batch by hand.\n\n#CoffeeTips #BrewBetter #CoffeeEducation #SpecialtyCoffee #Barista #CoffeeCommunity #FellsPoint","hashtags":"#CoffeeTips #BrewBetter #CoffeeEducation #SpecialtyCoffee #Barista #CoffeeCommunity #FellsPoint"},
        {"day":"Monday","platform":"linkedin","content_type":"educational","caption":"Specialty coffee grows as consumers seek quality over convenience. At Harbor Coffee Co., education drives loyalty — customers who understand the craft keep coming back.\n\n#SpecialtyCoffee #SmallBusiness #CustomerExperience","hashtags":"#SpecialtyCoffee #SmallBusiness #CustomerExperience"},
        {"day":"Tuesday","platform":"twitter","content_type":"product","caption":"New: single-origin Ethiopian Yirgacheffe. Bright, floral, and unlike anything you've tasted. Limited bags available. #HarborCoffee #SingleOrigin","hashtags":"#HarborCoffee #SingleOrigin"},
        {"day":"Tuesday","platform":"instagram","content_type":"product","caption":"Meet our latest obsession: Ethiopian Yirgacheffe. Blueberry notes, jasmine finish, zero regrets. Grab a bag before it's gone.\n\n#NewArrival #EthiopianCoffee #SingleOrigin #SpecialtyCoffee #CoffeeLover #FellsPoint #Baltimore","hashtags":"#NewArrival #EthiopianCoffee #SingleOrigin #SpecialtyCoffee #CoffeeLover #FellsPoint #Baltimore"},
        {"day":"Tuesday","platform":"linkedin","content_type":"product","caption":"Thrilled to introduce our latest single-origin: Ethiopian Yirgacheffe from a family-owned cooperative. Traceable, transparent, exceptional in the cup.\n\n#DirectTrade #SpecialtyCoffee #SustainableBusiness","hashtags":"#DirectTrade #SpecialtyCoffee #SustainableBusiness"},
        {"day":"Wednesday","platform":"twitter","content_type":"behind-the-scenes","caption":"5am. Roaster warming up. The whole shop smells incredible before we even open. This is why we do it. #HarborCoffee #BehindTheScenes","hashtags":"#HarborCoffee #BehindTheScenes"},
        {"day":"Wednesday","platform":"instagram","content_type":"behind-the-scenes","caption":"Before the doors open — this is Harbor Coffee at 5am. The grind never stops (literally).\n\n#BehindTheScenes #EarlyMornings #CoffeeRoaster #SmallBusiness #CoffeeCulture #Baltimore #FellsPoint","hashtags":"#BehindTheScenes #EarlyMornings #CoffeeRoaster #SmallBusiness #CoffeeCulture #Baltimore #FellsPoint"},
        {"day":"Wednesday","platform":"linkedin","content_type":"behind-the-scenes","caption":"Running a small coffee shop means early mornings, constant calibration, and a team that genuinely cares. Here's what happens before we open at Harbor Coffee Co.\n\n#SmallBusiness #TeamWork #LocalBusiness","hashtags":"#SmallBusiness #TeamWork #LocalBusiness"},
        {"day":"Thursday","platform":"twitter","content_type":"engagement","caption":"Hot take: oat milk > almond milk in an iced latte. Agree or disagree? ⬇️ #CoffeeDebate #HarborCoffee","hashtags":"#CoffeeDebate #HarborCoffee"},
        {"day":"Thursday","platform":"instagram","content_type":"engagement","caption":"We need to settle this: what's your go-to milk alternative? Drop your answer in the comments 👇\n\n#CoffeePoll #OatMilk #AlmondMilk #CoffeeCommunity #LatteArt #HarborCoffee #FellsPoint","hashtags":"#CoffeePoll #OatMilk #AlmondMilk #CoffeeCommunity #LatteArt #HarborCoffee #FellsPoint"},
        {"day":"Thursday","platform":"linkedin","content_type":"engagement","caption":"We're always improving based on what our customers love. What's one thing you wish more coffee shops offered? We'd genuinely love to know.\n\n#CustomerFeedback #SmallBusiness #CoffeeIndustry","hashtags":"#CustomerFeedback #SmallBusiness #CoffeeIndustry"},
        {"day":"Friday","platform":"twitter","content_type":"promotion","caption":"Weekend deal: buy any bag of beans, get a free drip coffee. In-store only. See you soon ☕ #HarborCoffee #WeekendDeal","hashtags":"#HarborCoffee #WeekendDeal"},
        {"day":"Friday","platform":"instagram","content_type":"promotion","caption":"TGIF — celebrating with you. Buy any bag of whole beans this weekend, we'll throw in a free drip coffee. You deserve it.\n\n#FridayDeal #WeekendVibes #HarborCoffee #CoffeeLover #FellsPoint #Baltimore #LocalCoffee","hashtags":"#FridayDeal #WeekendVibes #HarborCoffee #CoffeeLover #FellsPoint #Baltimore #LocalCoffee"},
        {"day":"Friday","platform":"linkedin","content_type":"promotion","caption":"Heading into the weekend grateful for our incredible community. Stop by Harbor Coffee Co. this weekend for a special offer on our whole bean selection — our way of saying thank you.\n\n#WeekendOffer #SmallBusiness #CustomerAppreciation","hashtags":"#WeekendOffer #SmallBusiness #CustomerAppreciation"},
        {"day":"Saturday","platform":"twitter","content_type":"community","caption":"Tag us in your Harbor Coffee photos this weekend! Best shot gets reshared + a $15 gift card. #HarborCoffee #CommunityLove","hashtags":"#HarborCoffee #CommunityLove"},
        {"day":"Saturday","platform":"instagram","content_type":"community","caption":"We love seeing Harbor Coffee in your world. Tag us this weekend — our favorite shot gets reshared and wins a $15 gift card 📸\n\n#HarborCoffeeCommunity #UGC #TagUs #CoffeePhotography #Baltimore #FellsPoint #CoffeeLover","hashtags":"#HarborCoffeeCommunity #UGC #TagUs #CoffeePhotography #Baltimore #FellsPoint #CoffeeLover"},
        {"day":"Saturday","platform":"linkedin","content_type":"community","caption":"One of the best parts of running a local business is the community that grows around it. We're consistently inspired by the people who make Harbor Coffee their third place.\n\n#Community #LocalBusiness #ThirdPlace","hashtags":"#Community #LocalBusiness #ThirdPlace"},
        {"day":"Sunday","platform":"twitter","content_type":"inspiration","caption":"Coffee is ritual. Ritual is intention. Intention is everything. Happy Sunday ☀️ #SundayVibes #HarborCoffee","hashtags":"#SundayVibes #HarborCoffee"},
        {"day":"Sunday","platform":"instagram","content_type":"inspiration","caption":"Sundays are for slowing down, savoring your cup, and remembering why the small rituals matter most. See you tomorrow.\n\n#SundayMorning #SlowDown #CoffeeMoment #HarborCoffee #FellsPoint #MindfulMorning #CoffeeCulture","hashtags":"#SundayMorning #SlowDown #CoffeeMoment #HarborCoffee #FellsPoint #MindfulMorning #CoffeeCulture"},
        {"day":"Sunday","platform":"linkedin","content_type":"inspiration","caption":"Reflecting this Sunday on what drives us: a belief that quality, care, and community aren't just good business — they're a way of life. Wishing everyone a restful close to the week.\n\n#SundayReflection #SmallBusiness #Values","hashtags":"#SundayReflection #SmallBusiness #Values"},
    ]


# ── Routes ──

@app.get('/')
def index():
    with get_db() as db:
        brand = db.query(Brand).first()
        posts = db.query(Post).order_by(Post.scheduled_date, Post.id).all() if brand else []
        brand_data = brand_to_dict(brand) if brand else None
        posts_data = [post_to_dict(p) for p in posts]
    if not posts_data:
        posts_data = demo_week()
    niches_safe = {k: {
        'label': v['label'],
        'examples': v['examples'],
        'tone': v['tone'],
        'audience': v['audience'],
        'keywords': v['keywords'],
        'platforms': v['platforms'],
    } for k, v in NICHES.items()}
    return render_template('index.html',
        brand=brand_data,
        posts=posts_data,
        has_api_key=bool(ANTHROPIC_KEY),
        niches=niches_safe,
    )


@app.get('/api/niches')
def api_niches():
    return jsonify({k: {
        'label': v['label'],
        'examples': v['examples'],
        'tone': v['tone'],
        'audience': v['audience'],
        'keywords': v['keywords'],
        'platforms': v['platforms'],
    } for k, v in NICHES.items()})


@app.get('/api/brand')
def api_get_brand():
    with get_db() as db:
        brand = db.query(Brand).first()
        return jsonify(brand_to_dict(brand) if brand else None)


@app.post('/api/brand')
def api_save_brand():
    data = request.json
    with get_db() as db:
        brand = db.query(Brand).first()
        if not brand:
            brand = Brand()
            db.add(brand)
        brand.name = data['name']
        brand.industry = data['industry']
        brand.tone = data['tone']
        brand.audience = data['audience']
        brand.keywords = json.dumps(data.get('keywords', []))
        brand.niche = data.get('niche', '')
        db.flush()
        return jsonify({'id': brand.id, 'ok': True})


@app.post('/api/generate')
def api_generate():
    data = request.json
    brand_data = data['brand']
    platforms = data.get('platforms', ['twitter'])
    topic = data.get('topic', '').strip()
    content_type = data.get('content_type', 'general')
    if not topic:
        return jsonify({'error': 'Topic is required'}), 400
    if not ANTHROPIC_KEY:
        return jsonify({'results': demo_single(brand_data, platforms, topic), 'demo': True})
    try:
        results = {p: generate_single(brand_data, p, topic, content_type) for p in platforms}
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.post('/api/generate-week')
def api_generate_week():
    data = request.json
    brand_data = data['brand']
    week_start = data.get('week_start', datetime.now().strftime('%Y-%m-%d'))
    if not ANTHROPIC_KEY:
        return jsonify({'posts': demo_week(), 'demo': True})
    try:
        posts = generate_week(brand_data)
        with get_db() as db:
            brand = db.query(Brand).first()
            if brand:
                db.query(Post).filter_by(brand_id=brand.id).delete()
                week_start_dt = datetime.strptime(week_start, '%Y-%m-%d')
                day_map = {d: i for i, (d, _, _) in enumerate(WEEK_STRATEGY)}
                for p in posts:
                    offset = day_map.get(p.get('day', 'Monday'), 0)
                    date_str = (week_start_dt + timedelta(days=offset)).strftime('%Y-%m-%d')
                    db.add(Post(
                        brand_id=brand.id,
                        platform=p.get('platform', 'twitter'),
                        content_type=p.get('content_type', 'general'),
                        caption=p.get('caption', ''),
                        hashtags=p.get('hashtags', ''),
                        scheduled_date=date_str,
                        status='draft',
                    ))
        return jsonify({'posts': posts})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.patch('/api/posts/<int:post_id>/status')
def api_update_status(post_id):
    data = request.json
    with get_db() as db:
        post = db.query(Post).get(post_id)
        if post:
            post.status = data['status']
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(debug=True)
