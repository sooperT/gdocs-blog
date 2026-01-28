/**
 * TomBot RAG Content Parser
 *
 * Parses the markdown content files and generates structured chunks
 * ready for embedding and database loading.
 *
 * Usage: node parse-content.js
 * Output: chunks.json
 */

import { readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DOCS_DIR = join(__dirname, '../../docs/tombot/RAG');

// ============================================================================
// PARSING FUNCTIONS
// ============================================================================

/**
 * Parse roles from career content file
 */
function parseRoles(content) {
  const chunks = [];

  // Company contexts for baking into role content
  const companyContexts = {
    'Novo Nordisk': 'Global pharmaceutical company, best known for pioneering treatments in obesity and diabetes.',
    'LEO Innovation Lab': 'Independent healthtech incubator established by LEO Pharma. A melting pot of ideas and innovation where product leads were essentially mini-CEOs for each venture.',
    'TwentyThree': 'Integrated video marketing platform built for digital marketers.',
    'Opbeat': 'Developer tools SaaS startup providing application performance monitoring. Backed by the cofounders of Facebook, Spotify, and Instagram. Later acquired by Elastic.',
    'EuroDNS': 'ICANN-accredited international domain registrar, specialising in excellent service and unusual domain extensions. Customers included MailChimp, Lotus F1, and Time Warner.',
    'UK2 Group': 'International web hosting company serving primarily SMBs. 200-250 staff with offices in UK, US & Ukraine.',
    'Host Europe Group': "Europe's largest privately-owned web hosting provider. Later acquired by GoDaddy for $1.82 billion.",
    'Pipex Internet': "UK's 4th largest broadband provider.",
    'TextualHealing.com': 'SMS marketing startup sending mobile barcode tickets and coupons via MMS.',
    'Independent Consultant': 'Freelance consultancy across various clients including Host Europe Group, EuroDNS, and Everplaces.'
  };

  // Role definitions extracted from the career content
  const roles = [
    {
      id: 'role_R16',
      title: 'Associate Product Director',
      company: 'Novo Nordisk',
      years_start: 2022,
      years_end: 2024,
      content: `Associate Product Director at Novo Nordisk (2022-2024)

${companyContexts['Novo Nordisk']}

Senior IC product role working across silos on complex, high-impact initiatives.

Key achievements:
- Consumer lead for Wegovy Pill launch, rethought user journey to drive prescription growth
- Pitched & built a GenAI proof of concept for automating compliance reviews (MLR)
- Led six-month discovery programme for top drug asset, securing funded portfolio of digital initiatives
- Introduced digital incubation model shifting org from output to outcomes
- Head of product operations, established quality standards across product org
- Thought partner to Product VP, shifted cross-functional VPs from product sceptics to advocates
- Coached product teams to connect work to value and ground decisions in market intelligence`
    },
    {
      id: 'role_R15',
      title: 'Product Manager - Wegovycare',
      company: 'Novo Nordisk',
      years_start: 2020,
      years_end: 2022,
      content: `Product Manager - Wegovycare at Novo Nordisk (2020-2022)

${companyContexts['Novo Nordisk']}

Built a retention-focused digital service to accompany the company's blockbuster GLP-1 obesity medicine.

Key achievements:
- Led full product lifecycle using data and user research to identify journey friction
- Persuaded senior stakeholders to adopt product operating model
- Introduced product discovery, user research, prototyping & iterative development to the organisation
- Automated documentation and shifted release cycles from yearly to bi-monthly in high-regulation environment
- Built a weight-loss prediction algorithm from concept to prototype, later spun out into API product
- Achieved 10% penetration in first national market, validating demand and product approach`
    },
    {
      id: 'role_R14',
      title: 'PM/GM - Diagnosis App',
      company: 'LEO Innovation Lab',
      years_start: 2018,
      years_end: 2020,
      content: `PM/GM - Diagnosis App at LEO Innovation Lab (2018-2020)

${companyContexts['LEO Innovation Lab']}

Led a machine learning product team building a prototype skin diagnosis app.

Key achievements:
- Led 10-person team of machine learning and computer vision specialists
- Achieved >80% accuracy across 3 skin conditions via machine learning
- Designed pipeline for data collection and analysis; doubled labelling throughput
- Evaluated go-to-market for a moonshot ML prototype; identified seven paths to market`
    },
    {
      id: 'role_R13',
      title: 'PM/GM - Skincoach',
      company: 'LEO Innovation Lab',
      years_start: 2018,
      years_end: 2018,
      content: `PM/GM - Skincoach at LEO Innovation Lab (2018)

${companyContexts['LEO Innovation Lab']}

Built a patient-support app for terminal cancer patients in partnership with Amgen, one of the world's largest biotech companies.

Key achievements:
- Built app under strict regulatory and ethical constraints
- Completed full product lifecycle in 8 months, on time & on budget
- Managed stakeholders & negotiated novel partnership model later adopted by Amgen core business as exemplar for innovation
- Live pilot launched in Spain & France`
    },
    {
      id: 'role_R12',
      title: 'PM/GM - TREAT',
      company: 'LEO Innovation Lab',
      years_start: 2016,
      years_end: 2017,
      content: `PM/GM - TREAT at LEO Innovation Lab (2016-2017)

${companyContexts['LEO Innovation Lab']}

TREAT was a pioneering app addressing underlying causes of inflammatory conditions via personalised nutrition advice. First product launched by LEO Innovation Lab. It was underperforming.

Key achievements:
- Parachuted into underperforming flagship product with 6-month mandate to stabilise and assess viability
- Brought team onside and established clear focus & experiment-led work rhythm
- Defined product value proposition & integrated KPIs into daily workflow
- Halved customer acquisition costs, increased customer activation by 7x
- Recommended business be closed, preventing further sunk investment. Successfully wound down the project`
    },
    {
      id: 'role_R11',
      title: 'Head of Marketing',
      company: 'TwentyThree',
      years_start: 2016,
      years_end: 2016,
      content: `Head of Marketing (contract) at TwentyThree (2016)

${companyContexts['TwentyThree']}

Key achievements:
- Stabilised a 10-12 person marketing team
- Rescued global launch on a 6-week deadline
- Introduced lightweight reporting and planning structure
- Secured quid pro quo streaming rights for TechCrunch Disrupt`
    },
    {
      id: 'role_R10',
      title: 'Head of Marketing',
      company: 'Opbeat',
      years_start: 2014,
      years_end: 2016,
      content: `Head of Marketing at Opbeat (2014-2016)

${companyContexts['Opbeat']}

Key achievements:
- Built the brand, marketing strategy, team & channels from scratch
- Defined product proposition and developer narrative - factual, nuanced messaging that earned loyalty among engineers
- Introduced marketing processes, KPIs, reporting & budgeting
- Used data-driven marketing to treble traffic and sign-ups in 12 months
- Blended experimentation, growth hacks & activation tactics
- Successfully grew the business to complete a $2M bridge-funding round`
    },
    {
      id: 'role_R09',
      title: 'Marketing Director',
      company: 'EuroDNS',
      years_start: 2013,
      years_end: 2014,
      content: `Marketing Director at EuroDNS (2013-2014)

${companyContexts['EuroDNS']}

A turnaround project. Hybrid remote setup - mostly worked from Copenhagen, visited Luxembourg office every 2 weeks for 3 days.

Key achievements:
- Restructured marketing department (4 direct reports), implemented KPIs, rebooted all marketing channels in under 8 months
- Reversed a 4-year decline in traffic and online sales
- Doubled organic traffic in 12 months
- Halved bounce rate (from ~60% to ~30%)
- Implemented remediation for black-hat SEO damage
- Analysed user flow and redesigned website & ecommerce funnels
- Launched over 500 new domain extensions
- First provider to offer a free SSL certificate with every domain`
    },
    {
      id: 'role_R08',
      title: 'Independent Consultant',
      company: 'Independent Consultant',
      years_start: 2010,
      years_end: 2013,
      content: `Independent Internet Consultant (2010-2013)

${companyContexts['Independent Consultant']}

Freelance consultancy to finance relocation to Denmark and Danish language studies (completed Prøve i Dansk 3).

Key work:
- Wireframing & storyboarding order funnels to improve conversion
- Creating, pitching and developing products
- Producing user stories, specifications, storyboards and wireframes
- High-level strategy for updating & integrating legacy websites
- Briefing senior management, product managers, designers & marketers
- Remotely managing teams (UK, Luxembourg & Romania) & coaching individuals
- Online marketing, analytics & optimisation`
    },
    {
      id: 'role_R07',
      title: 'Head of Group Strategy',
      company: 'UK2 Group',
      years_start: 2008,
      years_end: 2010,
      content: `Head of Group Strategy at UK2 Group (2008-2010)

${companyContexts['UK2 Group']}

Troubleshooter for the CEO across all brands, markets & departments.

Key achievements:
- Worked across all brands, countries & departments finding synergies and encouraging best practice
- Linked people, products and projects across UK, US, and Ukraine offices
- Rebuilt the underperforming US Marketing department before recruiting a US-based successor
- Reversed a downward revenue trend in 6 months in underperforming business unit
- Reduced bounce rate by ~15% and nearly doubled sales conversion
- Created product roadmap and successfully launched 8 products in 10 months
- Managed development of a new domain platform, responsible for over 500,000 customer domains`
    },
    {
      id: 'role_R06',
      title: 'Head of New Media',
      company: 'Host Europe Group',
      years_start: 2006,
      years_end: 2008,
      content: `Head of New Media at Host Europe Group (2006-2008)

${companyContexts['Host Europe Group']}

Key achievements:
- Created the New Media department from scratch. Line manager of a team of 5-6
- Member of the Senior Management Team and on-call duty rota
- Managed all online channels: ecommerce portals, SEO, branding, UX, email marketing, blog
- Established KPIs and web metrics to optimise business performance
- 123-reg.co.uk becomes first company to register over 1 million .uk domain names
- Initiated and led the GX Networks rebranding project - successfully renamed the company in 5 weeks
- Prioritised development roadmap and briefed development teams`
    },
    {
      id: 'role_R05',
      title: 'Group Design Manager',
      company: 'Pipex Internet',
      years_start: 2005,
      years_end: 2006,
      content: `Group Design Manager at Pipex Internet (2005-2006)

${companyContexts['Pipex Internet']}

Key achievements:
- Managed web design output; coordinated a team of designers and developers across multiple offices
- Created project & campaign briefs`
    },
    {
      id: 'role_R04',
      title: 'Web Designer',
      company: 'Host Europe Group',
      years_start: 2004,
      years_end: 2005,
      content: `Web Designer at Host Europe / Pipex (2004-2005)

${companyContexts['Host Europe Group']}

Key achievements:
- 123-reg.co.uk reaches 2 million unique visitors each month
- Hands-on ecommerce design and development
- Reinvented the domain search process, increasing new revenue by 20% overnight. First use of AJAX in the stack. This innovation later became the industry standard`
    },
    {
      id: 'role_R03',
      title: 'Sales Executive',
      company: 'Host Europe Group',
      years_start: 2003,
      years_end: 2004,
      content: `Sales Executive at Host Europe (2003-2004)

${companyContexts['Host Europe Group']}

Key achievements:
- Winner of the annual sales competition
- First job: learnt how to listen to customers by answering the telephone
- Made an alternative company website in free time; sales went up, moved to web team the next week`
    },
    {
      id: 'role_R02',
      title: 'Co-founder',
      company: 'TextualHealing.com',
      years_start: 2002,
      years_end: 2004,
      content: `Co-founder / Web Director at TextualHealing.com (2002-2004)

${companyContexts['TextualHealing.com']}

Co-founded an SMS marketing startup. Good idea, too early, never launched.

Learning: You need to launch and iterate - we aimed for perfect and didn't launch.`
    },
    {
      id: 'role_R01',
      title: 'Freelance Web Designer',
      company: 'Various',
      years_start: 2001,
      years_end: 2004,
      content: `Freelance Web Designer (2001-2004)

Freelance web design work alongside studies and early career.`
    }
  ];

  for (const role of roles) {
    chunks.push({
      id: role.id,
      chunk_type: 'role',
      title: `${role.title} at ${role.company} (${role.years_start}-${role.years_end})`,
      content: role.content,
      company_name: role.company,
      role_title: role.title,
      years_start: role.years_start,
      years_end: role.years_end,
      tags: [],
      source_file: 'cv-chatbot-career-content-mega-v3.md'
    });
  }

  return chunks;
}

/**
 * Parse stories from key stories file
 */
function parseStories(content) {
  const stories = [
    {
      id: 'story_S01',
      title: 'Career Arc - How I Got Into Product',
      good_for: ['Walk me through your career', 'How did you get into product?', 'Tell me about yourself'],
      content: `Late 80s: First computer. Dad spent a month's salary on a home computer. Typing out BASIC from a magazine, syntax errors. Stayed hobby level for a while.

Late 90s: Studying biology at university. The Internet happened - dot.com boom. Before that, the coolest thing was an under-construction GIF or a hit counter. Now there was disruption - competition between search engines, online shopping, travel reservations. Kids in bedrooms and garages were reshaping entire bricks and mortar industries. I had to get involved.

Started learning to make websites, design and code. Completed my degree, took a one-year Masters in IT.

2001-2004: Graduated just as the dot.com bubble popped. No jobs. Freelance web design. Co-founded TextualHealing.com - mobile barcode tickets via MMS. Good idea, too early, never launched. Learning: ship in small increments, don't polish forever.

2003: Eventually got a foot in the door answering phones at a web hosting company. Good at it (won the annual sales competition), but not my passion. Attracted by reach and impact - I wanted to do web. In evenings and weekends I made an alternative website, convinced a manager to try it out, sales went up. Next week I was in the web design team.

2004-2008: Six months later, I was leading the web design team. Reinvented the domain search process - first use of AJAX - revenue up 20% overnight. Became industry standard. Via acquisitions, became part of Pipex (UK's 4th largest broadband provider). Then Head of New Media at Host Europe Group, managing all online channels. Member of Senior Management Team. Still in my 20s.

2008-2010: Switched to UK2 Group - another hosting company with interesting Danish CEO with disruptive mindset (JustEat, Zetland). By now doing a mix of web, marketing and product - wherever the opportunity was. Troubleshooter to CEO across UK, US, Ukraine offices.

2010: Met a girl on a ski slope and moved to Denmark. Went to school to learn Danish (Prøve i Dansk 3). Independent consulting - mix of web, ecommerce, marketing, growth.

2013-2016: EuroDNS turnaround (reversed 4-year decline). Then Opbeat - SaaS startup backed by Facebook/Instagram cofounders. Built brand from scratch, trebled traffic. Later acquired by Elastic. Then rescued TwentyThree global launch on 6-week deadline.

2016-2020: Fell into health-tech as "the last place to be disrupted by web." LEO Innovation Lab - super interesting place. Arms-length product incubator. Move fast. Accelerated learning. Formative career moment. TREAT, Skincoach, Diagnosis App.

2020-2024: Novo Nordisk. Built Wegovycare, convinced business to start with problem not solution. Created incubation model. Invited onto Wegovy Pill launch. Head of product operations. Built GenAI proof of concept.

2026: AI changes everything. Same feeling as the 90s.`
    },
    {
      id: 'story_S02',
      title: 'Skincoach: The Most Meaningful Work',
      good_for: ["What's the most important thing you've accomplished?", 'Tell me about meaningful work', 'How do you handle sensitive projects?'],
      content: `At LEO Innovation Lab (2018), I led a project building an app for terminally ill cancer patients - a partnership with Amgen, one of the world's largest biotech companies. The app was designed to help patients manage side effects from their treatment.

It was a really difficult project, intense and emotionally demanding. I remember sitting at my desk, headphones on, listening to patient interviews and crying.

It made me think about product work completely differently. Every decision had to be intentional and judged with sensitivity. We couldn't "move fast and break things" - we had to get it right.

Worked under challenging compliance constraints. Managed stakeholders and negotiated a novel partnership model.

The app meaningfully improved quality of life in terminally ill cancer patients. It made their final months better, and in some cases allowed them to stay on treatment for longer - gaining additional months to spend with their families, settle their affairs and say goodbye.

It only launched to a limited pilot audience in Spain and France, but it really helped those who used it. The partnership model was later adopted by Amgen core business as an exemplar for innovation.

Completed the full product lifecycle in 8 months, on time and on budget.

Learning: Not every product is about growth metrics or conversion funnels. Sometimes it's about doing something that genuinely matters, even at small scale.`
    },
    {
      id: 'story_S03',
      title: 'Domain Search Innovation',
      good_for: ['Tell me about a product win', 'Describe an innovation you drove', 'How do you identify opportunities?'],
      content: `At Host Europe (2004-2005), I worked for a domain registrar that's now part of GoDaddy. The industry standard for domain search was clunky: enter name, pick extension from dropdown, hit search. Separate API call per registry meant users searched one domain at a time.

Users could only search for one domain at a time and kept running into domains that were already taken. Frustrating experience, poor conversion.

I reinvented the process: simple text field, interpret input, search all extensions asynchronously. First use of AJAX in our stack. This sped up the search process and drastically increased the likelihood of finding a good domain name.

Result: Revenue increased 20% overnight. This approach became the industry standard - if you search for a domain anywhere today, this is how it works.

Learning: The best innovations come from questioning assumptions baked into technical constraints. The API limitation was real, but didn't have to define the user experience.`
    },
    {
      id: 'story_S04',
      title: 'Wegovycare: Starting with the Problem',
      good_for: ['Tell me about your biggest product win', 'How do you approach a new problem?', 'Describe a time you changed how a team worked'],
      content: `Applied for a SaMD product role at Novo Nordisk, but the fit wasn't right - they thought I would be too constrained. Instead, they put me forward as a candidate to build a digital solution for a then unheard-of weight loss medicine (Wegovy).

The brief was solution-first: "build us an app that does X."

In my final round job interview, I convinced the business to set aside their solution-first brief and start with the problem instead. I used this as a mandate to completely reinvent their ways of working: running discovery, prototyping, patient interviews, iterative development.

Shifted release cycles from yearly to bi-monthly in a high-regulation environment. Identified a key growth lever and built a weight-loss prediction algorithm from concept to prototype.

Created a meaningful product that resonated with patients and affiliates. Achieved 10% penetration in our first national market. The product is still live today.

Asked to scale this way of working across the organisation. Created an incubation model. Moved the business toward a product operating model.

The algorithm was later spun out into a new API product.

Learning: The poor decision is anchoring on your own ideas and locking out the possibility of better alternatives. Once I learnt to detach from ego, everything changed. It's not about who has the best idea - it's about being a facilitator of hypotheses, staying humble, and creating space for learning.`
    },
    {
      id: 'story_S05',
      title: 'Knowing When to Ship (Failure Story)',
      good_for: ['Tell me about a failure', 'What did you learn from a mistake?', 'How do you think about shipping?'],
      content: `Fresh out of university (2002-2004), I co-founded TextualHealing.com - a startup sending mobile barcode tickets and coupons via MMS. The idea was good, but we were way too early and lacked experience.

We wanted perfect, and kept polishing instead of shipping. We dreamt of a multi-sided marketplace, but had no go-to-market plan and no viable first iteration.

We never launched.

Years later, I worked with a CEO whose motto was "launch crap, but launch."

My approach is informed by both:
- Ship in small viable increments to capture value and learn early and often
- But don't ship junk. If you need to learn fast, run a test (junk doesn't generate meaningful value)`
    },
    {
      id: 'story_S06',
      title: 'Prioritising Ideas Over Learning',
      good_for: ["What's a poor decision that shaped your approach?", 'How do you handle disagreements?', 'How do you validate ideas?'],
      content: `My first job, twenty years ago (around 2003-2004), was in a PRINCE2 waterfall setup. I recall a passionate argument between me and a graphic designer, each convinced that our idea was right. Neither of us knew about testing.

Fast-forward a decade later and a similar discussion between me and a product designer. He preferred A, I preferred B. We quickly agreed to test it.

Later that afternoon we discovered that users preferred something entirely different - option C.

Learning: The poor decision was anchoring on our own ideas and locking out the possibility of better alternatives. Once I learnt to detach from ego, everything changed. It was liberating.
- It's not about who has the best idea
- It's more about being a facilitator of hypotheses - staying humble, and creating a space for learning`
    },
    {
      id: 'story_S07',
      title: 'TREAT: Making the Hard Call',
      good_for: ['Tell me about a failure', 'Describe a difficult decision', 'How do you handle underperforming products?'],
      content: `TREAT was LEO Innovation Lab's flagship product (2016-2017) - a pioneering app addressing underlying causes of inflammatory conditions via personalised nutrition advice. It was underperforming. I was parachuted in with a 6-month mandate to stabilise and assess viability.

Brought the team onside and established a clear focus and experiment-led work rhythm. Defined product value proposition and integrated KPIs into daily workflow.

Halved customer acquisition costs. Increased customer activation by 7x.

Despite the improved metrics, the fundamentals weren't there. I recommended the business be closed. Successfully wound down the project.

Learning: Turning around the metrics isn't the same as proving viability. Sometimes the right call is to stop, even when you've made things better. The sunk cost fallacy is real.`
    },
    {
      id: 'story_S08',
      title: 'TREAT: Bringing the Team Onside',
      good_for: ['Tell me about a difficult leadership situation', 'How do you handle taking over an existing team?', 'Describe a time you built trust'],
      content: `I was brought in to troubleshoot the flagship product of LEO Innovation Lab (2016-2017). TREAT was the first product to launch and had received significant coverage, but behind the scenes it was in trouble: massive tech debt, no prioritisation, flaky metrics, no roadmap, unclear reporting structure, massive churn, no pathway to profitability.

The product had an existing team of about 15 people, including a product lead and product manager. They were both passionate about the product, but were unfortunately in over their heads.

We needed to be delicate. We wanted to keep their passion and expertise, but help them out.

I started as a consultant for the first month to see how we got along. After that month, it was proposed that I become the lead, with them reporting to me.

This required trust and humility from everyone. I appreciated it could be difficult for them, so I gave them the option to veto it - I would consult elsewhere, no hard feelings. But we went ahead.

What followed was intense. Lots of fires, lots of chaos, blurred reporting lines, people problems, management issues, inconsistent and misleading data. It culminated in the bold decision to pause the service so we could refactor faster.

Team morale hit rock bottom. Really tough.

But we kept the faith. New cadences, new ways of working. We went through the tough time together, and came out the other side not only intact, but better and stronger - with real trust.

We halved acquisition costs and increased activation 7x. And when I ultimately recommended closing the product, the team understood why. That's only possible when there's trust.

Learning: You can't turn around a product without bringing the people with you. The metrics matter, but the team comes first. Give people agency, be honest about what you're seeing, and go through the hard stuff together. Trust and mutual respect.`
    },
    {
      id: 'story_S09',
      title: 'How I Approach Building Software',
      good_for: ['How do you approach a new problem?', "What's your product process?", 'How do you differ from other PMs?'],
      content: `A typical PM might write: "I partner closely with engineering and design to deliver customer-focused solutions. I prioritize based on data, customer insights, and business impact."

This isn't necessarily bad, but it sometimes misses the point.

My approach is less rote and more adaptive. It's about doing whatever's needed to find and follow the opportunity.

When working on something new, I usually start from first principles. I try to deeply understand the outcomes we're trying to achieve, the system relationships, and ultimately where to build and why.

This generally involves talking to a bunch of people, and asking a bunch of obvious questions. I read, sketch, observe, and listen. I keep layering in viewpoints and complexity; it will feel really uncomfortable until suddenly it doesn't.

Once you can trace across a system, the opportunities, levers and amplifiers tend to present themselves. I'll sketch hypotheses on paper, test with colleagues and see what holds up.

From here, we switch into execution, and initiate the first learning loop.`
    },
    {
      id: 'story_S10',
      title: "LEO Innovation Lab: Why 'Disrupt from Arm's Length' Didn't Work",
      good_for: ['Tell me about a failure', 'What did you learn about innovation?', 'How do you think about organisational change?'],
      content: `LEO Pharma could see digital disruption coming to healthcare. Their response was to create an arm's-length innovation lab (2016-2020) - better we disrupt ourselves than let a competitor do it.

The logic for keeping it separate made sense: to be truly innovative, you need completely different thinking, different ways of working. If you stay too close to the mothership, you just replicate what already exists.

So they brought in experts from all sorts of fields - only a few pharma people in key positions. A true melting pot.

And it worked - in isolation. LEO Innovation Lab was incredibly agile, with rapid learning cycles and brilliant peers to learn from. It was a formative career moment for me.

But the parent ship continued sailing unchanged. We were too remote. The innovations we created struggled to find a home back in the core business.

The Lab was super innovative, but it didn't create the impact it needed to.

Learning: You can't outsource disruption to a separate unit and graft it back on later. The parent organisation has to change too.

At Novo Nordisk, I took the much harder path: innovate and disrupt from within. Create small victories and use them to accelerate change. It's slower and harder, but much more likely to create lasting impact.`
    },
    {
      id: 'story_S11',
      title: 'The Alternative Website',
      good_for: ['Tell me about a time you showed initiative', 'How did you get into web/product?'],
      content: `At Host Europe (2003-2004), I'd got my foot in the door answering phones at a web hosting company. I was good at it - won the annual sales competition - but it wasn't my passion. I was attracted by reach and impact. I wanted to do web.

The existing website was dated and a bit naff. The marketing material did a poor job of explaining the "why" of the product, it was busy and cluttered, and it lacked focus and a core funnel.

I thought I could do better.

In evenings and weekends, I built an alternative version of the website. Then I reached out to the brand manager - we knew each other a bit from customer service questions. I booked a meeting, made my pitch, and showed her what I'd made and why.

She could see I'd thought about it deeply. Her response was simply: "Well, let's try it out then."

Sales went up. Next week I was in the web design team. Six months later, I was leading it.

Learning: I really appreciate the break she gave me. Looking back, I can see it was a risk on her part - the website had a million visitors a month. But she backed a bet on someone who'd shown initiative and done the work upfront. I try to do the same for others when I can.

And: you can create your own path. I've been doing that ever since.`
    },
    {
      id: 'story_S12',
      title: 'GenAI Proof of Concept',
      good_for: ["What's your experience with AI?", 'Tell me about something you built recently', 'How do you approach new technology?'],
      content: `At Novo Nordisk (2022-2024), when developing health software, every release needs to undergo extensive review by medical, legal and regulatory experts (MLR). The process was designed for simple marketing materials like patient pamphlets, not sophisticated software - but it hadn't evolved.

In practice, this meant every screen of an application had to be captured in PDF format and reviewed individually. The result: significant delays (backlogs could mean months before review), huge documentation overhead, and an anti-pattern where you had to fully develop everything before getting formal sign-off. It creates the "CD-ROM software" pattern - ship once, never iterate.

At Wegovycare, I'd partly addressed this by automating documentation and informally reviewing prototypes with the review team. That got us from annual releases to every two months.

But if you want to win any software race, velocity is key. GenAI presented a new opportunity.

I used an internal LLM sandbox to create a RAG model that captured the various guidelines and regulations. Now we could automatically document and review each submission with a full audit trail - the review team only had to rubber-stamp the release.

I also built a prototype agent that plugged into Figma, so designers could query the guidelines before investing too much effort. This allowed product teams to shift left - they could fail something in design, not at review, reducing unnecessary feedback loops.

The product teams loved it. It validated the approach and demonstrated what was possible. Organisational priorities later shifted and the project was handed to another team, but the proof of concept showed a clear path to dramatically faster release cycles.

Learning: Sometimes you build the right thing at the wrong time. The value of a proof of concept isn't always immediate adoption - it's planting a seed and showing what's possible.`
    },
    {
      id: 'story_S13',
      title: 'EuroDNS: Remote Leadership That Worked',
      good_for: ['How do you manage remote teams?', "What's your approach to hybrid working?", 'How do you delegate effectively?'],
      content: `I was Marketing Director at EuroDNS (2013-2014), but based in Copenhagen while the team was in Luxembourg. I travelled there every two weeks for three days.

Like any long-distance relationship, you need to trust each other.

I created a natural cadence: fortnightly face-to-face meetings and plenum discussions when I was in the office, then space to focus and get on with it during the remainder. Of course I was available for ad-hoc calls as needed, but I wasn't hovering.

It worked really well. The rhythm gave structure without micromanagement. The team had clarity on direction and autonomy on execution.

Learning: This setup taught me about managing by outcomes, not prescriptive tasks. When you're not in the room every day, you have to delegate properly - you can't control the how, only align on the what. It forced good habits that I've carried into every leadership role since.`
    },
    {
      id: 'story_S14',
      title: 'GX Networks: Renaming the Company in 5 Weeks',
      good_for: ['Tell me about delivering under pressure', 'How do you get things done fast?', 'Describe a time you led a cross-functional project'],
      content: `At Host Europe Group (2006-2008), we needed to rename the company. Not sure why it landed on my desk - I managed online, not brand - but I guess I was known for getting things done.

We had 5 weeks.

The hardest part was getting everyone to agree on the name. Fortunately, as an old internet company, I found a bunch of domain names and trademarks lying around. That gave us options.

Once we had agreement, the rest was execution: quick brand identity, corporate website, office signage, stationery, email signatures, spoke to lawyers, and pushed the change through.

This was a Plc - a publicly listed company - so it included changing the stock market ticker. Not your typical rebrand.

Done in 5 weeks. Company renamed, brand live, stock ticker updated, signage up, stationery printed.

Learning: Most of the time on big initiatives isn't spent doing the work - it's spent getting alignment. Once you have agreement, execution can move fast. The trick is knowing where the real blockers are.`
    }
  ];

  return stories.map(story => ({
    id: story.id,
    chunk_type: 'story',
    title: story.title,
    content: story.content,
    good_for: story.good_for,
    company_name: null,
    role_title: null,
    years_start: null,
    years_end: null,
    tags: [],
    source_file: 'cv-chatbot-key-stories-v2.md'
  }));
}

/**
 * Parse tricky questions
 */
function parseTrickyQuestions(content) {
  const questions = [
    {
      id: 'tq_TQ01',
      question: 'Why are you leaving Novo Nordisk?',
      answer: `Novo Nordisk underwent a giant restructuring in Autumn 2024, impacting 9,000 roles globally, 5,000 of which were in Denmark. Digital was heavily impacted and my role was one of those.

I'm using this as an opportunity to return to my tech-roots and look for my next challenge. I originally chose health-tech as it was the last industry to be disrupted by digital. But now AI is changing everything. It's the same energy as the dot-com era - everything is up for grabs again. And I want to be back on that frontier.`
    },
    {
      id: 'tq_TQ02',
      question: 'Why the gap / what have you been doing?',
      answer: `I'm currently on garden leave, spending time with my family, coding with AI (Claude Code, ChatGPT, Gemini), reading, writing, and networking. This chatbot is one of those projects.`
    },
    {
      id: 'tq_TQ03',
      question: 'What are you looking for?',
      answer: `My compass is impact, learning, and fun. So I'm looking for the potential, not the job title.

I like challenging product problems with a big upside - the kind where there's no playbook and you have to figure it out. I enjoy working with smart colleagues who like getting stuff done. And ideally, I'd like to work in an organisation that's willing to lean-in to AI.

I've deliberately moved across industries my whole career - web hosting, SaaS, health-tech - because I pick up new domains quickly and love learning.`
    },
    {
      id: 'tq_TQ04',
      question: "You've jumped around a lot - are you a job hopper?",
      answer: `I don't think so. I worked at Novo for 6 years, and before that LEO Innovation Lab for ~3.5 years.

I have worked in lots of product-adjacent roles, but this is about following the impact: I started answering phones in sales, but realised I could drive more scale through ecommerce. So I made an alternative company website in my free time, persuaded a manager to launch it, sales went up, and the next week I'm in the web team.

Later, I realised the bottleneck was reach, not conversion - so I moved into marketing. Then I saw customers signing up but not activating - so I moved into product. And so on.

I'm motivated by creating impact, not job titles.`
    },
    {
      id: 'tq_TQ05',
      question: "Aren't you a pharma PM now?",
      answer: `Ironically, my value at Novo was precisely that I wasn't a typical pharma PM. I was brought in to bring non-pharma thinking - digital, product, startup ways of working - to a very traditional industry. That's why they put me on high-stakes projects like the Wegovy Pill launch. They needed someone who could think differently.

I've deliberately moved across industries my whole career - ecommerce, SaaS, health-tech - because I pick up new domains quickly and love learning. The skills and underlying principles are largely the same. The fun bit is finding the exceptions and applying learnings from one industry to another.`
    },
    {
      id: 'tq_TQ06',
      question: 'Why did you get into pharma?',
      answer: `I'm fascinated by digital disruption. I deliberately targeted health-tech because it was the last industry waiting to be disrupted - regulation, barriers, the lot.

But now AI is changing everything. It's the same energy as the dot-com era - everything is up for grabs again. And I want to be back on that frontier.`
    },
    {
      id: 'tq_TQ07',
      question: 'Where do you see yourself in 5 years?',
      answer: `5 years is a long time in tech - I wonder how AI will have matured in 5 years? What will be the exciting use cases?

Technologies have come and gone, but my compass has stayed the same - so I'll most likely be working on an impactful challenge, with good people, having learnt some new tricks.`
    },
    {
      id: 'tq_TQ08',
      question: 'Are you technical?',
      answer: `Yes and no.

I'm technical enough to lead machine learning teams and build prototypes, but my value is in bridging disciplines, not writing production code.

I have a lifelong love of technology, a postgrad degree in IT, and I started my career making websites. But I quickly realised I could create more impact by bridging and translating across disciplines than by staying purely technical.

I think logically, grasp technical concepts quickly, and can still write code when needed. At LEO I led ML and computer vision teams. At Novo I built a GenAI proof of concept and a weight-loss prediction algorithm. Right now I'm building with Claude Code, GitHub and Netlify.

I'm not a specialist engineer. My value is in understanding enough to ask the right questions, spot opportunities, and provide counterbalance.`
    },
    {
      id: 'tq_TQ09',
      question: "What's your management experience?",
      answer: `I've led teams of 5-12 across multiple roles. It's something I can do and enjoy, but managing people or climbing levels is not my primary motivation.

I'm motivated by creating impact, and sometimes that means being a people manager. Other times it works best through informal leadership or hands-on building.

I've found that informal leadership - built on trust, mutual respect, and objective reasoning - can actually be more impactful in certain contexts. You stay closer to the product and the customer, you can bridge silos more easily, and you avoid getting pulled into organisational politics.

That said, I'm not opposed to management. It depends on the role and where I can drive the most impact.`
    },
    {
      id: 'tq_TQ10',
      question: "What's your biggest weakness?",
      answer: `Aha, the classic interview question!

When I get excited about ideas, I can talk too fast and interrupt. I've got a post-it on my monitor that reminds me to listen. I'm getting better, but in high-energy discussions I still catch myself jumping in before someone's finished.

The upside is I bring a lot of energy and enthusiasm to the work, and it's always well-intentioned. But I'm conscious the quieter voices in the room sometimes have the most important things to say.`
    },
    {
      id: 'tq_TQ11',
      question: "What's your ideal work setup - office/hybrid/remote?",
      answer: `Flexible - it depends on the organisational culture.

I've successfully worked remotely and managed teams across countries (UK→US, DK→Luxembourg, DK→Romania). I enjoy the buzz of working with a team in-person, but also appreciate the opportunity for deep focus when working from home.`
    },
    {
      id: 'tq_TQ12',
      question: "What's your salary expectation?",
      answer: `I'd prefer to understand the role and scope first before discussing numbers. Happy to share expectations once we're further along.`
    },
    {
      id: 'tq_TQ13',
      question: 'What was your salary at Novo?',
      answer: `I'm a chatbot, so I can't really answer that one. I suggest you reach out to Tom for coffee instead.`
    },
    {
      id: 'tq_TQ14',
      question: 'When can you start?',
      answer: `I'm a chatbot, so I can't really answer that one. I suggest you reach out to Tom for coffee instead.`
    },
    {
      id: 'tq_TQ15',
      question: "What's your notice period?",
      answer: `I'm a chatbot, so I can't really answer that one. I suggest you reach out to Tom for coffee instead.`
    },
    {
      id: 'tq_TQ16',
      question: 'Are you willing to relocate?',
      answer: `I'm based in Copenhagen, Denmark - I really like it here. But I'm able to work remotely and have some flexibility with travel.`
    },
    {
      id: 'tq_TQ17',
      question: 'Why do you want to work for [company]?',
      answer: `I'm a chatbot, so I can't really answer that one. I suggest you reach out to Tom for coffee instead.`
    },
    {
      id: 'tq_TQ18',
      question: 'Are you interviewing elsewhere?',
      answer: `I'm a chatbot, so I can't really answer that one. I suggest you reach out to Tom for coffee instead.`
    },
    {
      id: 'tq_TQ19',
      question: 'Why should we hire you?',
      answer: `To be honest, I don't know that you should. I'm a chatbot and I don't know what role you're proposing or what organisation you're representing!

What I can tell you is that Tom is motivated by impact, learning and fun. This means he drives results, stays curious and creates momentum. He likes challenging product problems with big potential and working with smart colleagues.

If this sounds like your organisation, get in touch!`
    }
  ];

  return questions.map(q => ({
    id: q.id,
    chunk_type: 'tricky_question',
    title: q.question,
    content: q.answer,
    question_text: q.question,
    company_name: null,
    role_title: null,
    years_start: null,
    years_end: null,
    tags: [],
    source_file: 'tricky-questions-final.md'
  }));
}

/**
 * Parse competencies
 */
function parseCompetencies() {
  const competencies = [
    {
      id: 'comp_C01',
      title: 'Summary - General Product',
      content: `I'm a product leader, fixer, maker and doer. I enjoy high-impact work, and I find the simplest moves that drive the biggest business outcomes. I get results by bringing the right people together, building trust, and creating momentum. My compass is impact, learning, and fun.

Professional competencies: Product Management (Senior IC, outcome focus, end-to-end ownership), Growth (decade of acquisition/activation/retention), Discovery & Incubation (problem-first exploration), Fixing things (called when something's broken), Informal leadership (help people think differently).

Personal competencies: Outcome oriented, Systems thinker, Deep-end swimmer, Hands-on, Trusted.`
    },
    {
      id: 'comp_C02',
      title: 'Summary - Growth / Consumer',
      content: `Product leader, fixer, maker and doer with 20+ years spanning product, marketing & ecommerce. My work is rooted in systems thinking, and I love finding small shifts that unlock outsized impact. I work comfortably across levels, from shaping product strategy to unblocking delivery. My compass is impact, learning, and fun.

Professional competencies: Growth (decade of acquisition/activation/retention), Product Management (Senior IC, outcome focus, end-to-end ownership), Discovery (problem-first exploration), Fixing things (called when something's broken).

Personal competencies: Outcome oriented, Systems thinker, Hands-on, Trusted.`
    },
    {
      id: 'comp_C03',
      title: 'Summary - Enablement / Product Ops',
      content: `Product leader who elevates product thinking & process in complex, regulated organisations - not by importing a playbook, but by applying first principles, and meeting people where they are. For the past four years I've been a thought partner to senior leaders & PMs: shaping strategy and helping product teams create real impact. I do this through trust, transparency and objective reasoning. My compass is impact, learning, and fun.

Professional competencies: Strategic Partnership (thought partner to leadership), Product Operations (standards, artefacts, ways of working), Coaching (helping people think differently).

Personal competencies: Outcome oriented, Systems thinker, Deep-end swimmer, Grounded, Trusted.`
    },
    {
      id: 'comp_C04',
      title: 'Summary - Hands-on / Technical',
      content: `I'm a hands-on senior product manager with broad experience across product, incubation and commercial. I enjoy complex problems (the more complicated the better), and apply systems thinking and experience to find the simplest moves that create the biggest outcomes. I'm comfortable bridging strategy and technology, working directly with both engineers and stakeholders, and can pick up new domains quickly to make informed product decisions. My compass is impact, learning, and fun.`
    },
    {
      id: 'comp_C05',
      title: 'Summary - Developer-focused',
      content: `Experienced product manager, maker, fixer and doer, with an energy for everything tech. I toggle between macro & micro, finding small shifts that unlock outsized impact. I draw upon a broad base of experience from developer platforms, to healthtech and enterprise transformation. But at its core, my work is about creating personal relationships and bringing the right people together. My compass is impact, learning, and fun.`
    },
    {
      id: 'comp_C06',
      title: 'Summary - Transformation',
      content: `Growth-focused product thinker, fixer and doer - blending product management and business transformation. Strongly results orientated, I have been recognised for my ability to overcome the status quo and drive results through others. I have a broad base of experience to draw upon, but understand that at its core it's all about creating personal relationships and bringing the right people together. My compass is impact, learning, and fun.`
    }
  ];

  return competencies.map(c => ({
    id: c.id,
    chunk_type: 'competency',
    title: c.title,
    content: c.content,
    company_name: null,
    role_title: null,
    years_start: null,
    years_end: null,
    tags: [],
    source_file: 'cv-chatbot-career-content-mega-v3.md'
  }));
}

/**
 * Parse themes
 */
function parseThemes() {
  const themes = [
    {
      id: 'theme_TH01',
      title: 'Turnaround Specialist',
      content: `I get called when something's broken or stuck. Track record across multiple companies:

- EuroDNS (2013-2014): Reversed 4-year decline in traffic and sales, halved bounce rate from 60% to 30%, doubled organic traffic
- UK2 Group (2008-2010): Reversed downward revenue trend in 6 months through reporting, ecommerce & product strategy
- TREAT at LEO (2016-2017): Parachuted into underperforming flagship, halved acquisition costs, increased activation 7x, then recommended closure
- TwentyThree (2016): Rescued global launch on 6-week deadline, stabilised 10-12 person team`
    },
    {
      id: 'theme_TH02',
      title: 'Growth & Conversion',
      content: `Consistent track record of improving funnels, reducing bounce rates, increasing activation and conversion:

- Host Europe (2004-2005): Reinvented domain search process, increasing new revenue by 20% overnight
- EuroDNS (2013-2014): Halved bounce rate (60% → 30%), doubled organic traffic in 12 months
- UK2 Group (2008-2010): Reduced bounce rate by ~15%, nearly doubled sales conversion, launched 8 products in 10 months
- Opbeat (2014-2016): Trebled traffic and sign-ups in 12 months
- TREAT at LEO (2016-2017): Halved acquisition costs, increased activation 7x
- Wegovycare (2020-2022): Achieved 10% penetration in first national market`
    },
    {
      id: 'theme_TH03',
      title: 'Building From Scratch',
      content: `Creating teams, departments, and ways of working where none existed:

- Host Europe (2006-2008): Created the New Media department from scratch
- Opbeat (2014-2016): Built brand, marketing strategy, team & channels from zero
- Wegovycare (2020-2022): Introduced outcome-focused ways of working; shifted release cycles from yearly to bi-monthly
- Novo Nordisk (2022-2024): Introduced a digital incubation model that shifted the organisation from output to outcomes`
    },
    {
      id: 'theme_TH04',
      title: 'Bridging Technical and Commercial',
      content: `Started hands-on (design, code), progressed to strategy and leadership, maintained technical fluency throughout:

- Host Europe (2003-2008): Sales exec → Web designer → Head of New Media (built Java/XML app at university)
- LEO Innovation Lab (2018-2020): Led machine learning and computer vision teams; designed data pipelines
- Novo Nordisk (2020-2024): Built GenAI proof of concept; built weight-loss prediction algorithm
- Current: Building with Claude Code, GitHub, Netlify`
    },
    {
      id: 'theme_TH05',
      title: 'International Experience',
      content: `Worked across multiple countries, managed remote and distributed teams:

- UK: Host Europe, UK2 Group (London, Nottingham) - 2003-2010
- Luxembourg: EuroDNS (hybrid Copenhagen + Luxembourg) - 2013-2014
- Denmark: LEO, Novo Nordisk, Opbeat, TwentyThree - 2010-2024
- Remote teams: Managed teams across UK, US, Ukraine, Romania`
    }
  ];

  return themes.map(t => ({
    id: t.id,
    chunk_type: 'theme',
    title: t.title,
    content: t.content,
    company_name: null,
    role_title: null,
    years_start: null,
    years_end: null,
    tags: [],
    source_file: 'cv-chatbot-career-content-mega-v3.md'
  }));
}

/**
 * Parse basic info
 */
function parseBasicInfo() {
  const basicInfo = [
    {
      id: 'info_BI01',
      title: 'Contact Information',
      content: `Tom Traberg Stenson
Location: Copenhagen, Denmark
Email: tomstenson@gmail.com
LinkedIn: linkedin.com/in/tomstenson
Blog: takenbyninjas.com
Nationality: British (Danish resident since 2010, permanent residency status, no work visa required for working in Denmark)`
    },
    {
      id: 'info_BI02',
      title: 'Education',
      content: `MA Information Technology - University of Nottingham, UK (2001-2002)
- Masters dissertation: Built a multi-threaded client-server application using Java & XML

BSc (Hons) Biological Sciences - University of Birmingham, UK (1998-2001)`
    },
    {
      id: 'info_BI03',
      title: 'Languages',
      content: `English (native)
Danish (conversational - Prøve i Dansk 3, certified 2012)`
    },
    {
      id: 'info_BI04',
      title: 'Certifications',
      content: `- IDEO U Human-Centred Systems Thinking / Leading Complex Projects (2024)
- Certified Scrum Product Owner (CSPO)
- Prøve i Dansk 3 (Danish language certification, 2012)`
    },
    {
      id: 'info_BI05',
      title: 'Tools & Tech Stack',
      content: `Tools: Pen & paper, Miro (top 1% power user), Jira, Azure DevOps, Trello, Linear

Tech Stack: Claude Code, ChatGPT, Gemini, GitHub, Netlify`
    },
    {
      id: 'info_BI06',
      title: 'Interests',
      content: `Snowboarding, playing vinyl, reading, cooking, great design`
    },
    {
      id: 'info_BI07',
      title: 'Personal',
      content: `Married to Danish wife
2 kids: son (11 years old), daughter (7 years old)
1 rabbit (3 years old, called "Bunbun")`
    }
  ];

  return basicInfo.map(info => ({
    id: info.id,
    chunk_type: 'basic_info',
    title: info.title,
    content: info.content,
    company_name: null,
    role_title: null,
    years_start: null,
    years_end: null,
    tags: [],
    source_file: 'cv-chatbot-career-content-mega-v3.md'
  }));
}

/**
 * Generate aliases lookup
 */
function generateAliases() {
  return [
    { alias: 'Novo', canonical_name: 'Novo Nordisk', alias_type: 'company' },
    { alias: 'NN', canonical_name: 'Novo Nordisk', alias_type: 'company' },
    { alias: 'LEO', canonical_name: 'LEO Innovation Lab', alias_type: 'company' },
    { alias: 'iLab', canonical_name: 'LEO Innovation Lab', alias_type: 'company' },
    { alias: 'Innovation Lab', canonical_name: 'LEO Innovation Lab', alias_type: 'company' },
    { alias: '123-reg', canonical_name: 'Host Europe Group', alias_type: 'company' },
    { alias: '123reg', canonical_name: 'Host Europe Group', alias_type: 'company' },
    { alias: 'Pipex', canonical_name: 'Host Europe Group', alias_type: 'company' },
    { alias: 'GX Networks', canonical_name: 'Host Europe Group', alias_type: 'company' },
    { alias: 'Host Europe', canonical_name: 'Host Europe Group', alias_type: 'company' },
    { alias: 'UK2', canonical_name: 'UK2 Group', alias_type: 'company' },
    { alias: 'Wegovy', canonical_name: 'Wegovycare', alias_type: 'product' },
    { alias: 'TREAT', canonical_name: 'TREAT app', alias_type: 'product' },
    { alias: 'Skincoach', canonical_name: 'Skincoach app', alias_type: 'product' },
    { alias: 'TwentyThree', canonical_name: 'TwentyThree', alias_type: 'company' },
    { alias: '23', canonical_name: 'TwentyThree', alias_type: 'company' },
    { alias: 'Opbeat', canonical_name: 'Opbeat', alias_type: 'company' },
    { alias: 'EuroDNS', canonical_name: 'EuroDNS', alias_type: 'company' },
    { alias: 'TextualHealing', canonical_name: 'TextualHealing.com', alias_type: 'company' }
  ];
}

// ============================================================================
// MAIN
// ============================================================================

function main() {
  console.log('Parsing TomBot RAG content...\n');

  // Parse all content types
  const roles = parseRoles();
  const stories = parseStories();
  const trickyQuestions = parseTrickyQuestions();
  const competencies = parseCompetencies();
  const themes = parseThemes();
  const basicInfo = parseBasicInfo();
  const aliases = generateAliases();

  // Combine all chunks
  const allChunks = [
    ...roles,
    ...stories,
    ...trickyQuestions,
    ...competencies,
    ...themes,
    ...basicInfo
  ];

  // Summary
  console.log('Content parsed:');
  console.log(`  Roles: ${roles.length}`);
  console.log(`  Stories: ${stories.length}`);
  console.log(`  Tricky Questions: ${trickyQuestions.length}`);
  console.log(`  Competencies: ${competencies.length}`);
  console.log(`  Themes: ${themes.length}`);
  console.log(`  Basic Info: ${basicInfo.length}`);
  console.log(`  Aliases: ${aliases.length}`);
  console.log(`  ─────────────────────`);
  console.log(`  Total chunks: ${allChunks.length}\n`);

  // Write output
  const output = {
    chunks: allChunks,
    aliases: aliases,
    generated_at: new Date().toISOString()
  };

  const outputPath = join(__dirname, 'chunks.json');
  writeFileSync(outputPath, JSON.stringify(output, null, 2));
  console.log(`Output written to: ${outputPath}`);

  // Print sample chunk for verification
  console.log('\nSample chunk (role_R16):');
  console.log(JSON.stringify(allChunks.find(c => c.id === 'role_R16'), null, 2));
}

main();
