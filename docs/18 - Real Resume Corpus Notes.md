# 18 · Real Resume Corpus: Complete Notes

Nine real resumes, given on 2026-11-05, written by people (not by us) and in many layouts. This document records **everything** in them: every section, skill, project, date, typo and contradiction, plus what our current pipeline does to each file. It is the reference for the extraction fix (doc 07, action item 18) and the source of the test set's expected answers.

**Privacy:** the resumes contain real contact details (only Ajay's) and real client names. This document keeps client and project names, because they are work facts needed for matching. It records emails and phone numbers only as "present", never their values.

---

## 1. The files at a glance

| # | File | Format | Pages | Chars (pipeline) | Name as written | Title line | Stated experience | Dated jobs? | Contact details |
|---|---|---|---|---|---|---|---|---|---|
| R1 | `EMP-1017_ajay_chandani.pdf` | PDF, Google Docs, Letter | 3 | 6,205 | AJAY CHANDANI | Web Developer \| Lead Ecommerce & AI Solutions Engineer \| 13+ Years | 13+ years | **Yes**: 2 jobs with month ranges | Email, phone, LinkedIn, GitHub |
| R2 | `Harsh - Python Updated.docx` | DOCX, **12.47 MB** (embedded fonts), monospace font | 3 (rendered) | 6,050 | Harsh | Python - Developer | 8+ years | **Partly**: one employer, joining date only | None |
| R3 | `Ravi- Full-stack Engineer 5 Yrs_1.doc` | **Legacy .doc** (WPS Office) | 3 (rendered) | ~7,400 (converted) | RAVI | Senior Full-stack Engineer (Agentic AI) | 5+ years | No | None |
| R4 | `Mahesh S - Full-Stack Developer.pdf` | PDF, Google Docs, A4 | 3 | 6,391 | Mahesh S. | Full Stack Developer | "over 6+ years" | No | None |
| R5 | `Rajendra - Full Stack.pdf` | PDF, Google Docs, A4 | 4 | 5,058 | Rajendra | Full Stack Developer | 6+ years | No | None |
| R6 | `Ravi (React-Native Developer).pdf` | PDF, Google Docs, A4 | 4 | 4,087 | Ravi | React Native Developer | 5+ years | No | None |
| R7 | `Vineet - Full Stack.pdf` | PDF, Google Docs, A4 | 4 | 5,056 | Vineet | Full Stack Developer | 6+ years | No | None |
| R8 | `Vineet - MERN.pdf` | PDF, Google Docs, A4 | 4 | 5,035 | Vineet | MERN Stack Developer | 6+ years | No | None |
| R9 | `Vishal (Golang Backend Developer).pdf` | PDF, Google Docs, A4 | 2 | 4,402 | Vishal | Golang developer | 9+ years | No | None |

All layouts are single-column, with no photos, tables or text boxes. Headings are coloured or bold, and some keywords are in bold inside sentences (R5, R7, R8). R2 uses a monospace (typewriter) font throughout.

**The most important fact for the design: 7 of 9 resumes have no work history with dates at all.** Their content is **projects** (5–6 each, never dated) and a stated total ("6+ years"). Our pipeline computes experience and skill years only from dated jobs, so for these 7 people it computes nothing.

---

## 2. Findings across all nine resumes

### 2.1 Structure: what sections exist, and what they're called

| Heading as written | Used in | Covered by our chunker's heading list? |
|---|---|---|
| PROFESSIONAL SUMMARY / Profile Summary / PROFILE SUMMARY | R1 / R2, R4–R9 / R3 | "professional summary" yes; **"profile summary" no** |
| ACHIEVEMENTS | R1 | yes |
| TECHNICAL SKILLS | R1 | yes |
| Technical Expertise / TECHNICAL EXPERTISE | R3–R9 | **no** |
| TECHNICAL SHOWCASE | R3 | **no** |
| Skills | R6 | yes |
| Key Responsibilities | R2 (a section, not tied to any job) | **no** |
| Responsibilities | R6 (a section) | **no** |
| PROFESSIONAL EXPERIENCE | R1 | yes |
| Employment History | R2 (**last** section, one line) | yes |
| KEY PROJECTS | R1 | **no** |
| Project delivered / Projects Delivered | R4, R6 / R5, R7, R8, R9 | **no** |
| PROJECTS / Projects | R3 / R2 | yes |
| EDUCATION / Education | all | yes |

**Section order varies:** R3 puts Education *before* Projects, and R2 puts Employment History *after* Education.

### 2.2 How a project is written (labels vary in every resume)

| Field | Spellings seen |
|---|---|
| Name | `Project Name: X`, `Project Name - X`, `1. X`, `X — Subtitle \| 6 Months \| Role`, bare line `X - Subtitle` |
| Link | `Link:`, `LINK -`, `APP Link:`, `App Link -`, `Web link -`, `App Link:` followed by 2–4 store URLs on later lines |
| Role | `Role: Lead Developer`, `Role - Mobile App Developer`, inside the name line (R1), or missing |
| Technologies | `Tech:`, `Technologies:`, `Technologies -`, `Technology:`, `Technologies Used:`, `Environment:`, and also as a bullet `● Technology: …` inside the list (R3, R5, R7, R8) |
| Duration | Only R1 (`6 Months`, `2 Months`). No project anywhere has dates |
| Sub-lists | `Key Features`, `Key Responsibilities`, `Key Contributions`, `Contributions`, `Highlights` (a one-line summary), `Description` |

### 2.3 Skills: how they're written

1. **"Category: list" lines** (R1 TECHNICAL SKILLS, R3 TECHNICAL SHOWCASE): `Ecommerce & CMS: WordPress (Custom Plugins), WooCommerce, …`. **This is the bug already seen in R1**: the category became the "skill".
2. **Bullets starting with a category label** (R5, R7, R8, R9): `● Backend Engineering: Strong experience with Node.js and Express, building …`, `● Databases: PostgreSQL, MySQ, MongoDB.`
3. **Prose bullets with no list** (R4, R6): `Expert in building scalable … web applications using React.js, leveraging hooks …`.
4. **Activities written as "skills"** (R6 Skills section): Mobile application development, React Native development, Requirement analysis, Software design, Coding and debugging, Testing and quality assurance, Documentation, Implementation. Only "React Native" is a technology.
5. **Project tech lines** are the most reliable evidence of real use in 8 of 9 resumes.
6. **Summary-only claims**, with no project using them:
   - R2: Django.
   - R3: Python, Azure, GCP.
   - R4: "mobile applications" (no mobile technology named) and "cloud platforms".
   - R9: Terraform appears in the summary and one project; MySQL in the summary only.

**Spelling variants of the same skill** (the normaliser must map all of them):

| Canonical | Written as |
|---|---|
| React | React, React.js, ReactJS, ReactJs, React Framework |
| Node.js | Node.js, NodeJS, Nodejs, NodeJs |
| Next.js | Next.js, NextJS |
| React Native | React Native, React-Native |
| PostgreSQL | PostgreSQL, Postgres |
| MongoDB | MongoDB, Mongodb (Atlas), MongoDB collections |
| MySQL | MySQL, **MySQ** (typo, R9) |
| Express | Express, Express.js |
| Go | Golang |
| gRPC | GRPC |
| Twilio | Twilio, **Twillo** (typo, R4) |
| Qdrant | **Quadrant** (`VectorDatabase(Quadrant)`, R2) |
| Amazon ElastiCache | **ElasticCache** (R2) |
| AWS Lambda | AWS Lambda, Lambda, Lambda Functions |
| Amazon S3 | S3, S3 Bucket |
| Amazon API Gateway | API Gateway, API Gateways |
| Amazon OpenSearch | OpenSearch (AOSS), OpenSearch Serverless |
| JavaScript | JavaScript, JS, **"Java script"** (R6: split into two words; read naively it becomes "Java") |
| Terraform | Terraform, terraform |
| Firebase | Firebase, Firebase API, Firestore (Firebase), FCM (Firebase Cloud Messaging) |
| Material UI | Material UI, MUI |
| Hugging Face | Huggingface |
| spaCy | Spacy |
| TensorFlow | Tensorflow |
| GitHub Actions | GitHub Actions |
| REST APIs | REST API, RESTful APIs, Rest APIs, REST/GraphQL |
| OpenAI API | OpenAI, GPT-4, GPT-based LLM Integration |
| RAG | RAG pipelines, RAG-based architectures, RAG-based workflows, RAG-style retrieval, retrieval-augmented generation |

**Dated technology vs. claimed years:** RAG, LangChain, FastEmbed, GPT-4, the OpenAI and Claude APIs, Cursor AI and Antigravity IDE are all recent (2020 or later, most 2023 or later). No resume can have more years in them than they have existed.

### 2.4 Experience: what can be computed

| Resume | Source of total years | Value |
|---|---|---|
| R1 | Dated jobs: Mar 2013 – present | 13.7 years (computed); "13+" stated; matches |
| R2 | Joining date 08 Feb 2018 – present; "8+" stated | 8.7 years; matches. **But** BCA finished 2018 and MCA 2020, so the first two years overlap with study |
| R3 | "5+ years" stated only; B.Tech 2015 | 5+ (graduated 11 years ago, so a gap or unstated earlier work) |
| R4, R5, R7, R8 | Stated only | 6+ |
| R6 | Stated only | 5+ |
| R9 | Stated only | 9+ |

**Stated-years traps** (text that looks like a duration but isn't one):
- R4 MyKids: "children from newborn to **16 years old**".
- R1: "**13+ Yrs** Full-Stack Leadership" (an achievement line, not a skill duration).
- R3's file name: "5 Yrs".
- R1: "(8+ Years)" and "(5 Years 2 Months)" after the job dates (true durations, consistent with the dates).

### 2.5 The same clients appear in many resumes (an agency portfolio)

These resumes come from one company's bench. R2 names its employer as Encoresky Technologies; R1 works there too; R3 links `patrishi-scanner.encoreskydev.com`. Several clients appear again and again, sometimes with different tech stacks per person.

| Client / project | Appears in | Notes |
|---|---|---|
| **Finexity** (fintech, finexity.com) | R4, R5, R7, R8, R9 | R4: React, Node, Postgres, Auth0, CI/CD. R5/R7/R8: React, Node, GraphQL, Auth0. R9: Go, GCP, Terraform, Twilio, Sentry, Dgraph, MongoDB Atlas, Firestore, Auth0, Geth |
| **ArorisHealth** | R3, R5, R7, R8 | Same feature bullets word for word; R3 adds a description and a tech line |
| **YES (Your Employment Solutions)** | R3, R5, R7, R8 | Same bullets word for word; only R5/R7/R8 have the Camunda line |
| **Datumsurge / Datum-Surge** | R2, R9 | Same description sentence. R2: Python, Lambda, DynamoDB, S3, API Gateway, FHIR. R9: Go, AWS, Cognito |
| **SmartGas / Smart Energies** (Nigeria, smartgasng.com) | R4 (web/backend), R6 (mobile) | Different project names for the same client |
| **Warely** (warelypos.com.sg) | R3 (web ordering, Next.js), R6 (POS mobile app, React Native) | |
| **Patrishi Sports** | R1 (Laravel, React, MySQL, Dymo SDK; 6 months), R3 (Next.js, TS, Node, WebSockets) | |
| **AllBetter / ChoreRelief** | R6 (booking app), R9 (**name only**: R9's "Allbetter" links to syfe.com and describes Syfe) | |
| Nexopay | R9 | Its 6 bullets are **word for word** the same as R4's Finexity bullets |

### 2.6 Same or similar resumes for different people: normal, not a problem
R5 (Rajendra) and R7 (Vineet Full Stack) have the same text apart from the name. R7 and R8 are two versions of Vineet's resume, tailored to different roles (Full Stack, MERN). **Companies write and tailor their employees' resumes on purpose, so this is expected.** The system doesn't flag it; each resume is simply extracted correctly. (A near-duplicate check was built and then removed on the user's decision, 2026-11-05.)

- R3's file metadata says Title "Rahul K - Full-stack E" and R2's names its editor. **Metadata is never used as resume facts.**

### 2.7 Contradictions inside a resume (keep as written, flag; never "fix" silently)

| Resume | Contradiction |
|---|---|
| R1 | PeaceAtHome (a parenting portal) lists the same Tech line as the trading platform above it: "Bitvavo & Coinbase APIs, Apple Pay", most likely copy-pasted. Role "Lead Developers" (plural) |
| R2 | Tech says Qdrant ("Quadrant"); Key Features say FAISS. Title "Python - Developer", summary "Full Stack Engineer". Django only in the summary and responsibilities, in no project |
| R3 | Title says "(Agentic AI)", but no project shows agents. Python is claimed, but no project uses it |
| R4 | UncleFitter: Environment "NodeJS, Postgres", but a bullet says React/Next.js. "Mobile applications" claimed, with no mobile technology. "Postgres Auth0" is missing a comma |
| R5/R7/R8 | Two projects numbered "5." |
| R6 | "Development of the apps using Java, Kotlin, and JS in React Native". Warely uses "Room Database" and "MVVM" (native Android terms) inside a React Native project |
| R9 | Title "Golang developer" vs summary "Senior Full Stack Developer". "Allbetter" heading + syfe.com link + Syfe description + "Subscription system, Payments, Scheduling" highlights. First-person sentences ("I consistently develop", "I contributed") |

### 2.8 Exposure is not usage
- R5/R7/R8: "Worked with a team who managed BPM workflows using **Camunda**". Someone else used Camunda.
- R6: "basics of native app development", "iOS basic operations". These are levels, not full skills.
- R2: "Implemented **Huggingface** for extensibility". Real use.

### 2.9 Content that says something about the work, not the person
Client descriptions ("a children's modeling agency representing children from newborn to 16 years old", "smart gas companies, situated in Nigeria", "an enterprise athletic event platform in Aruba") are about the client. The useful facts are the **domain** (fintech, healthcare, logistics, e-commerce, HR, POS, government) and the **features built** (payments, OTP, real-time tracking, Bluetooth, thermal printing).

---

## 3. What our current pipeline does to these files

| # | Problem | Files | Effect |
|---|---|---|---|
| P1 | **`.doc` is refused** at upload ("Save it as .docx or PDF") | R3 | Can't be uploaded |
| P2 | **10 MB upload limit**; R2 is 12.47 MB because 6 fonts are embedded (22 MB unpacked); its text is 6 KB | R2 | Refused at upload |
| P3 | **Header/footer removal deletes real lines.** On 3+ page PDFs, any short line that appears on 60% of pages is treated as a page header | R1: "Tech: Laravel, WordPress, WooCommerce, Bitvavo & Coinbase APIs, Apple Pay" (both copies). R4: "Role: Lead Developer" ×3, "Key Responsibilities:" ×3. R6: "Role - Mobile App Developer" ×3, the bullet "Integrations of Rest APIs, Third-party APIs for Google APIs, Firebase API." ×3. R5/R7/R8: "Contributions:" ×6 | Project roles and a whole tech line are lost before the model even sees the text |
| P4 | **Bulk upload needs `EMP-####_` in the file name** | R2–R9 (8 of 9) | "No employee with code …" unless renamed or uploaded on the employee's page |
| P5 | **No dated jobs means no years** | R3–R9 (R2 partly) | Total experience null, every skill's years null, and the Step 8 experience factor scores nothing |
| P6 | **No projects in the extraction schema** | All; projects are 60–90% of R2–R9 | The main evidence is not structured |
| P7 | **Category headings become skills** | R1, R3 (8 categories), R5/R7/R8 (7 labels), R9 (5 labels) | Junk skills; real skills hidden in evidence |
| P8 | Activities stored as skills | R6 | "Documentation", "Implementation" as skills |
| P9 | Spelling variants and typos not in the catalogue | All (table 2.3) | The same skill stored under several names; missed by search |
| P10 | Heading list incomplete (table 2.1) | All but R1 partly | Sections run together in chunks; projects glued to jobs (R1) |
| P11 | Stated-years regex reads "16 years old" or "13+ Yrs" as a skill duration if that text is the evidence | R4, R1 | Wrong years cap |
| P12 | Name anonymiser replaces every whole word matching a name part of 3+ letters | R2 "Harsh" (an English word), R3/R6 "Ravi" | Rare false replacements |
| P13 | ~~Near-duplicates not detected~~ | R5 = R7, R7 ≈ R8 | Not a problem: companies tailor and reuse resumes on purpose (see 2.6) |
| P14 | Zero-width-only lines (page decorations) and private-use bullets (U+F06C, Wingdings, after converting a Word file) | R6, R9, R3 | Cleaned correctly today (zero-width removed); the private-use bullet is not in our bullet list and stays in the text |
| P15 | One LLM call with a 2,048-token answer cap | All longer resumes | A full extraction of R2 (40+ technologies across 4 projects) is close to the cap |

---

## 4. Each resume in full

### R1 · Ajay Chandani (`EMP-1017_ajay_chandani.pdf`)
- **Header:** name; title line "Web Developer | Lead Ecommerce & AI Solutions Engineer | 13+ Years"; email, phone, "LinkedIn Profile" and "Github" as link text.
- **Summary:** Senior Software Engineer and Solutions Architect, 13+ years; PHP, Laravel, WordPress, WooCommerce, Shopify, BigCommerce; "active focus on" Python, Django, FastAPI; production AI: AI Agents, RAG pipelines, n8n, Voiceflow; client consultation, scoping, project ownership.
- **Achievements:** 13+ yrs full-stack leadership (PHP/Laravel, WordPress/WooCommerce, BigCommerce, Shopify, Python/FastAPI); delivery for clients in US, UK, Australia and the Caribbean; production RAG pipelines, autonomous agents, n8n; **developed Adobe Magento Marketplace extensions**.
- **Technical skills** (6 categories):
  - Ecommerce & CMS: WordPress (custom plugins), WooCommerce, BigCommerce (Stencil CLI, Headless, REST/GraphQL), Shopify (Liquid, APIs), Magento.
  - Backend & Full-Stack: PHP, Laravel, Python, Django, FastAPI, RESTful APIs, GraphQL, MySQL, PostgreSQL.
  - AI & Automation: AI Agents, RAG, n8n, Voiceflow, AI Chatbots, Voice Assistants, OpenAI & Claude APIs.
  - Frontend: JavaScript, React.js, Handlebars.js, HTML5, CSS3, Tailwind CSS.
  - Tools: VS Code, Git, Cursor AI, Claude AI, Antigravity IDE.
  - Leadership: Client Communication, Project Management, Project Ownership.
- **Experience:**
  1. Senior Software Engineer & Technical Lead, Encoresky Technologies Pvt. Ltd., Indore, India; April 2018 – Present ("8+ Years").
     - E-commerce and web platforms on BigCommerce, Shopify, WooCommerce and Laravel.
     - AI chatbots, voice assistants, RAG pipelines.
     - n8n and Voiceflow workflows ("up to 60%" less manual work).
     - REST/GraphQL APIs, webhooks, payment gateways, ERPs, trading platforms, inventory systems.
     - Client-facing technical lead; mentoring; code-review practices; database optimisation.
  2. Software Engineer / Web Developer, Cyber Infrastructure Private Limited (CIS), Indore; March 2013 – "Aprl" [sic] 2018 ("5 Years 2 Months").
     - 50+ sites and e-commerce portals on PHP, WordPress and WooCommerce.
     - Custom WordPress plugins and WooCommerce themes.
     - Overseas clients (US, UK, Australia); sprint deliverables.
     - Payment gateways (Stripe, PayPal, Authorize.Net), shipping carriers, SaaS APIs.
     - Query tuning, caching, front-end performance.
- **Key projects** (undated, with durations; not linked to a job):

  | Project | Duration | Role | Tech | Notes |
  |---|---|---|---|---|
  | Patrishi Sports (sports and event management) | 6 months | Project Manager & Tech Lead | Laravel, React.js, MySQL, REST API, Dymo Hardware SDK | Aruba; registration, payments, rankings; BIB label printing; patrishisports.com |
  | WSMode (automated trading platform and mobile app) | 6 months | PM & Tech Lead | Laravel, WordPress, WooCommerce, Bitvavo & Coinbase APIs, Apple Pay | Yahoo Finance API; trading bots; memberships, affiliates; wsmode.com |
  | PeaceAtHome Parenting Solutions | 4 months | "Lead Developers" | (same Tech line as WSMode) | US courses portal, subscriptions, **Zoom API** |
  | AudioAdvisor (hi-fi audio e-commerce) | 2 months | Lead Developer | BigCommerce, Stencil Framework, JavaScript, Headless APIs | Comparison widgets, checkout |
  | Kindtokidz (kids' toy shop, .com.au) | 4 months | Lead Developer | BigCommerce, Stencil CLI, Handlebars.js, Payment Gateways | Shipping rules, apps |
  | ConnectingDNA (genetic profiles) | 2 months | Lead Developer | WordPress, PHP, Custom Plugin Architecture | Health consultation workflows |
- **Education:**
  - MCA, School of Computer & Electronics, IPS Academy, Indore | RGPV; "Graduated: 2010-2013"; 8.0 CGPA. The institution name wraps onto a second line.
  - BCA, Vikram University, Ujjain (M.P.); "Graduated: 2007-2010"; 69.94%.
- **A correct profile has:** total 13.7 y. PHP ~13.7 y (CIS text plus Laravel at Encoresky implies PHP). WordPress and WooCommerce 13.7 y. Laravel, BigCommerce and Shopify 8.6 y. RAG, n8n and Voiceflow inside the Encoresky job but capped by technology age. Python, Django, FastAPI, React, MySQL, PostgreSQL, GraphQL, Magento, Tailwind and the rest listed (from the skills section or projects; no dated years). Six projects with durations. MCA 2013, BCA 2010.
- **Pipeline today:** see the doc 07 audit (10 errors), plus P3: the WSMode/PeaceAtHome Tech line is deleted.

### R2 · Harsh (`Harsh - Python Updated.docx`)
- **File:** DOCX, 12.47 MB (fonts embedded), last edited by "Chetan Banskar", 2026-03-10. Monospace font. Bullets are Word list formatting, not characters. Header and footer are empty. No tables.
- **Title:** "Python - Developer". **Summary:** "Full Stack Engineer with 8+ years … Python and Django … secure REST APIs, third-party services … cloud-native on AWS … SDLC, Agile, CI/CD, cloud architecture".
- **Key Responsibilities** (a section, not per job):
  - Backend services in Python and Django.
  - REST APIs and third-party APIs.
  - Collaboration with product and design teams.
  - Code reviews, debugging, performance.
  - Unit and integration tests (frontend and backend).
  - CI/CD with GitHub Actions / Jenkins.
  - AWS deployments.
  - Architecture discussions.
- **Projects:**

  | Project | Role | Technologies (as written) | Features / notes |
  |---|---|---|---|
  | AmigoAI - Chatbot-Based E-commerce Platform | Full Stack Engineer | Python, FastAPI, OpenAI, VectorDatabase(Quadrant), Postgres, CI/CD, AWS, Selenium | GPT-4 conversational search; **FAISS** with sentence embeddings; product scraping into PostgreSQL; Docker on AWS; prompt engineering; RAG-style retrieval |
  | Datumsurge | FullStack Engineer | Python, AWS, Lambda Functions, DynamoDB, S3 Bucket, API Gateways | US government; practitioners and patients; **FHIR** |
  | DCLS | Software Developer | Python, CUDA, Flask, CI/CD Pipelines, REST API, Automation/Cronjobs, PostgreSQL, Redis Queue, Docker, AWS, NLTK, Spacy, Tensorflow, Huggingface, Bash Scripting, SQLAlchemy, Bitbucket, JIRA | NLP service: NER, sentiment analysis, text classification, medical terms; input XML/JSON/spaCy docs; ensembles; fine-tuning; single/multi-GPU or CPU training |
  | AnimalHealth Research | AWS Data & AI Engineer | Python, AWS Lambda, S3, EventBridge, SQS, API Gateway, DynamoDB, ElasticCache, OpenSearch (AOSS), LangChain, FastEmbed, GPT-based LLM Integration, CloudWatch, CloudTrail | Event-driven ingestion; WordPress APIs as source; embeddings in OpenSearch Serverless; RAG; KMS, Secrets Manager; parallel Lambda via SQS |
- **Education:**
  - Masters of Computer Application, Maharaja Ranjit Singh College, Indore (RGPV), 2020.
  - Bachelor of Computer Application, Kothari College Of Management Science & Technology, Indore (DAVV), 2018.
- **Employment history (last line):** "Encoresky Technologies Pvt Ltd - Date of joining: 08 Feb, 2018 - Present". No title.
- **A correct profile has:**
  - **One job** at Encoresky, Feb 2018 – present, 8.7 y, title unknown (the headline says Python Developer).
  - All 4 projects; since this is the only employer, they can be linked to that job, marked "assumed".
  - Skills: Python (in every project), AWS (Lambda, S3, DynamoDB, API Gateway, EventBridge, SQS, ElastiCache, OpenSearch, CloudWatch, CloudTrail, KMS, Secrets Manager), FastAPI, Flask, Django (summary only), PostgreSQL, Redis, Docker, CI/CD, GitHub Actions, Jenkins, Selenium, OpenAI/GPT-4, LangChain, FastEmbed, Qdrant, FAISS, RAG, NLP (NLTK, spaCy, Hugging Face, TensorFlow, CUDA), SQLAlchemy, Bash, Bitbucket, Jira.
  - Flag: MCA 2020 / BCA 2018 overlap with the job.
- **Pipeline today:** refused at upload (P1/P2: over 10 MB). If it were accepted, the text extraction is complete. "Employment History" is recognised, but the job has a joining date only, which the date parser must read ("08 Feb, 2018").

### R3 · Ravi, Senior Full-stack Engineer (`Ravi- Full-stack Engineer 5 Yrs_1.doc`)
- **File:** legacy Word `.doc` from WPS Office; metadata title "Rahul K - Full-stack E", author "shr", saved by "Chetan B" (Jan–Feb 2026). Bullets are private-use Wingdings characters (U+F06C) when the file is converted.
- **Title:** "Senior Full-stack Engineer (Agentic AI)".
- **Profile summary** (6 bullets):
  - 5+ years; customer-facing apps and B2B SaaS.
  - TypeScript, React, Next.js, Node.js, Python.
  - Microservices, asynchronous messaging, non-relational databases.
  - MVP to production; AWS/Azure/GCP.
  - AI platforms: data ingestion, model orchestration, API layers, GenAI personalisation and assistants.
  - Embeddings, vector databases, RAG; responsible AI.
- **Technical expertise** (9 bullets, restating the above): REST/GraphQL; MongoDB, Redis, vector databases; Tailwind CSS, Material UI, styled-components.
- **Technical showcase** (8 "Category: list" lines):
  - Languages & Frameworks: TypeScript, React, Next.js, Node.js, Python, GraphQL.
  - Backend & Architecture: REST/GraphQL APIs, microservices, async workflows, messaging systems.
  - Databases & Data Layer: MongoDB, PostgreSQL, Redis, vector databases.
  - AI & Generative Systems: AI/ML pipelines, LLM integrations, embeddings, RAG, internal AI platforms, automation tools.
  - Frontend & UI: Tailwind CSS, Material UI, styled-components.
  - Cloud & DevOps: AWS/Azure/GCP, CI/CD, monitoring.
  - Development Practices: Agile, rapid prototyping, async collaboration, responsible AI.
  - Collaboration & Tooling: GitHub, Bitbucket, Jira, Slack, automated testing and release workflows.
- **Education** (before projects): "B. Tech - RGPV - 2015".
- **Projects:**

  | Project | Technology | Notes |
  |---|---|---|
  | ArorisHealth (arorishealth.com) | Next.js, TypeScript, Node.js, AI/ML services for document parsing, Firebase | Payer-contract analytics for healthcare providers; AI contract parsing; Firebase CSV storage; web push; rate calculations; data visualisation |
  | YES (youremploymentsolutions.com) | ReactJS, NextJS, Node.js, AWS Lambda, Podio (tech line inside the bullets) | Staffing/HR; Lambda; DynamoDB; Indeed-Apply API; automated notifications |
  | Warely (warelypos.com.sg) | React, Next.js, TypeScript, Node.js, Firebase, AI/ML services | Digital ordering; Firebase OTP; MUI and styled-components; Redux and redux-persist; Formik and Yup; Axios; "AI-assisted" ordering insights |
  | PatrishiSports (patrishi-scanner.encoreskydev.com) | Next.js, TypeScript, Node.js, WebSockets, AI/ML services | Running events and rankings; legacy Next.js modernised; real-time CSV race data across screens |
  | Gabpals (admin.gabpals.com) | ReactJS | Admin panel; agent reports; subscriptions; Redux |
- No roles on projects, no durations, no employer, no contact.
- **A correct profile has:** 5+ y stated; TypeScript, React, Next.js, Node.js (all projects), Firebase, Redux, MUI, styled-components, Formik, Yup, Axios, WebSockets, AWS Lambda, DynamoDB, Podio; listed only: Python, GraphQL, MongoDB, PostgreSQL, Redis, Tailwind, Azure, GCP, RAG, embeddings, vector databases; 5 projects; B.Tech RGPV 2015.
- **Pipeline today:** refused at upload (`.doc`).

### R4 · Mahesh S. (`Mahesh S - Full-Stack Developer.pdf`)
- **Title:** Full Stack Developer. **Summary:** "over 6+ years"; web and mobile apps; backend and frontend, cloud, DevOps, "emerging technologies"; microservices; CI/CD; agile teams.
- **Technical expertise** (5 prose bullets): React.js (hooks, functional components, advanced state management); Node.js and Express (REST APIs, custom middleware); PostgreSQL (schema modelling, query tuning, indexing, large migrations); full-stack React + Node + PostgreSQL; Agile, Git, Docker.
- **Projects ("Project delivered"):**

  | Project | Role | Stack (as written) | Notes |
  |---|---|---|---|
  | Davis Imperial - Logistics/Delivery App (App Store) | Lead Developer | Environment: ReactJs, Node.js, & Postgres | Laundry pickup and delivery; admin dashboard; booking; employee leaves; API for mobile |
  | MyKids - Agency Portal (mykidsagency.com) | Lead Developer | Environment: ReactJS, NodeJS, & MySQL | Requirements, data models, **stored procedures and functions**; "newborn to 16 years old" in the description |
  | Finexity – Digital Wealth Creation Platform | Full Stack Developer | Environment: ReactJS, NodeJS, Postgres Auth0, CI/CD, Infrastructure Management | DevOps, CI/CD, deployments, microservices, security analysis, server permissions (bullets identical to R9's Nexopay) |
  | SmartGas (Play Store) | Full Stack Developer | Technologies: Nodejs, MongoDB, Angular, Flutterwave payment Gateway, Seerbit payment Gateway, GRPC, Twillo | Nigeria; multi-role users; online/offline orders; OTP via Twilio; SaaS for retailers; cylinder stock; driver tracking with sockets; gRPC "for load balancing and security" |
  | UncleFitter - Car Repair Services (unclefitter.com) | Lead Developer | Environment: NodeJS, Postgres | Booking; mechanic assignment; real-time tracking; payment gateways; notifications; **React/Next.js** UIs (bullet) |
- **Education:** "Bachelor of Technology - Computer science" (no institution, no year).
- **A correct profile has:** 6+ y stated; Node.js (5/5 projects), React (4), PostgreSQL (3), MySQL, MongoDB, Angular, Next.js, Express, Docker, Git, Auth0, gRPC, Twilio, Flutterwave, Seerbit, WebSockets, CI/CD, stored procedures; Lead Developer on 3 projects; 5 projects.
- **Pipeline today:** P3 deletes all three "Role: Lead Developer" lines, so the strongest seniority signal is gone.

### R5 · Rajendra (`Rajendra - Full Stack.pdf`)
- **Title:** Full Stack Developer. **Summary** (2 paragraphs): 6+ y; Node.js and Express; PostgreSQL, MySQL, MongoDB; React, Next.js, TypeScript; APIs, microservices; AWS serverless (**PDF generation with AWS Lambda and S3**); Docker; client communication; clean architecture.
- **Technical expertise** (7 label-prefixed bullets):
  - Backend Engineering: Node.js, Express, REST APIs, microservices, CI/CD, middleware.
  - Frontend Engineering: React, Next.js, TypeScript, hooks.
  - AWS & Serverless: Lambda, S3, PDF generation and file processing.
  - Databases: PostgreSQL, MySQL, MongoDB.
  - API Tools: Postman, Swagger.
  - DevOps & Version Control: Git, Docker.
  - Agile Delivery: Scrum.
- **Projects ("Projects Delivered"; numbered 1, 2, 3, 4, 5, 5):**

  | # | Project | Role | Tech | Notes |
  |---|---|---|---|---|
  | 1 | ArorisHealth | Full Stack Developer | — | AI contract parsing; Firebase (CSV/PDF); web push; algorithms; data visualisation |
  | 2 | YES (Your Employment Solutions) | Full Stack Developer | ReactJS, NextJS, Node.js, AWS Lambda, Podio | DynamoDB; Indeed-Apply API; "worked with a team who managed BPM workflows using **Camunda**" |
  | 3 | Finexity | Full Stack Developer | React.js, Node.js, GraphQL, Auth0 | Blockchain tokenisation, Apple Wallet, microservices, SaaS onboarding |
  | 4 | GolfDaddy (golfdaddy.com) | Full Stack Developer | ReactJS, NodeJS, MongoDB, Lambda | Tee-time booking, memberships, pricing rules, partner sync, payments, dashboards |
  | 5 | HRMS | **Frontend Developer** | ReactJS, NodeJS, MongoDB | Employees, attendance, leave, payroll screens; calendar scheduling |
  | 5 | QuickCart | Full Stack Developer | ReactJS, NodeJS, Express, MongoDB, REST APIs | Simple ordering system (reads like a demo) |
- **Education:** "Bachelor of Technology (B.Tech.) – Computer Science".
- **A correct profile has:** 6+ y; React (5/6), Node.js (5/6), MongoDB (3), Next.js, TypeScript, Express, GraphQL, Auth0, AWS Lambda, S3, DynamoDB, Firebase, Podio, PostgreSQL and MySQL (listed only), Postman, Swagger, Docker, Git, Scrum; **not** Camunda as a skill.
- **Pipeline today:** P3 deletes 6 "Contributions:" lines (harmless). P7: the 7 labels risk becoming skills. **Identical to R7.**

### R6 · Ravi, React Native Developer (`Ravi (React-Native Developer).pdf`)
- **File:** 4 pages; each page starts or ends with a line of only zero-width spaces (a decoration). About 1,400 characters are invisible.
- **Title:** React Native Developer. **Summary:** 5+ years in mobile app development; React Native; the full SDLC.
- **Skills** (activities): mobile application development, React Native development, requirement analysis, software design, coding and debugging, testing and QA, documentation, implementation.
- **Technical expertise:** mobile apps; Java, Kotlin and JS in React Native; custom UI framework; REST APIs, Google APIs, Firebase API; Git; real-time messaging and remote push notifications.
- **Responsibilities:** teamwork; business logic in "Java script"; choosing stack and architecture; React Native with Android core and basic iOS.
- **Projects ("Project delivered"):**

  | # | Project | Links | Tech | Role | Features |
  |---|---|---|---|---|---|
  | 1 | Smart Energies | smartgasng.com; Play Store | React-Native | Mobile App Developer | Google Maps and Places; real-time location tracking; push; multiple user types; OTP; biometrics; payment gateway; REST/Google/Firebase APIs; image picker; light/dark theme; chat and calling |
  | 2 | Shared Meter Agent – Gas Utility & Bluetooth Communication App | Play Store + App Store | React Native | — | Bluetooth meter communication; gas utility tracking; OTP; REST + Firebase sync; push alerts; phone and tablet UI; offline storage and sync |
  | 3 | AllBetter: Customer and Provider app | allbetterapp.com; 2 Play + 2 App Store (ChoreRelief) | React-Native | Mobile App Developer | Service booking; provider bidding; chat; **Twilio** video calls; notifications |
  | 4 | Freevice [Salon booking app] | — | React Native | — | User and salon-owner apps; Google Maps geolocation; **PayU**; **FCM** push |
  | 5 | Warely POS System | — | React Native | Mobile App Developer | Tablet UI; MVVM; POS payment; cash drawer; thermal printer (USB/LAN/Bluetooth); barcode scanner; REST/Google/Firebase; analytics, bug tracking; offline **SQLite via Room**; in-app update |
- **Education:** "bachelor of engineering - CS" (lowercase, a bullet; no institution or year).
- **A correct profile has:** 5+ y; React Native (5/5), JavaScript, Java, Kotlin, Android (core), iOS (basic), Firebase (FCM, Firebase API), Google Maps/Places, REST APIs, Twilio, PayU, SQLite/Room, Bluetooth, Git, MVVM; activities are **not** skills.
- **Pipeline today:** P3 deletes "Role - Mobile App Developer" ×3 and the Integrations bullet ×3. "Java script" may be read as Java.

### R7 · Vineet, Full Stack (`Vineet - Full Stack.pdf`)
- **Text identical to R5** apart from the first line ("Vineet"). Everything in R5 applies.
- Stored as its own employee, extracted like any other (identical text is normal, see 2.6).

### R8 · Vineet, MERN (`Vineet - MERN.pdf`)
- Same as R7 except:
  - Title "MERN Stack Developer".
  - The Backend Engineering bullet ends "RESTful APIs, and custom middleware" (no "microservices, CI/CD").
- The same person as R7: a role-specific version of the same resume. Upload it as a new version on the same employee's page.

### R9 · Vishal (`Vishal (Golang Backend Developer).pdf`)
- **Title:** "Golang developer" (lowercase). **Summary:**
  - "Senior Full Stack Developer with 9+ years", Golang and Node.js.
  - PostgreSQL, MySQL, MongoDB; AWS, GCP, Terraform, GraphQL and REST.
  - Written in the first person.
- **Technical expertise** (5 label-prefixed lists):
  - Backend Tech stack: Golang, Node.js, Express.js, RESTful APIs, GraphQL APIs.
  - Databases: PostgreSQL, **MySQ**, MongoDB.
  - Testing & Build Tools: Jenkins, Docker.
  - Cloud & DevOps: AWS, GCP, Docker, CI/CD.
  - Version Control & Tools: Git, GitHub, GitLab, Bitbucket, Jira, Airtable.
- **Projects:**

  | Project | Link | Stack | Notes |
  |---|---|---|---|
  | Finexity | finexity.com | Golang, GCP, terraform, Twilio, Sentry, Dgraph, Mongodb (Atlas), Firestore (Firebase), Auth0, Geth | Fintech, real-asset investing via blockchain; microservices; tokenisation; Apple Wallet; SaaS; Auth0. "I contributed as a developer" |
  | Datum-Surge | dmcs.datumsurge.com | Golang, AWS | US government practitioners and patients; government APIs; reusable "global component"; third-party APIs; **AWS Cognito** |
  | Nexopay - Fintech Payment Platform (Role: Full Stack Developer) | nexopay.es | Environment: Golang, Auth0, CI/CD, Infrastructure Management, ReactJS | React + Go; DevOps; microservices; security analysis; permissions (bullets identical to R4's Finexity) |
  | Allbetter – Digital Wealth Management Platform (Role: Full Stack Developer) | **syfe.com** | — | Describes Syfe; highlights subscription system, payments, scheduling; portfolio dashboards; REST/GraphQL; authentication and onboarding |
- **Education:** "Bachelor's of Technologies in Computer Science".
- **A correct profile has:** 9+ y; Go (3/4 projects), Node.js, Express, PostgreSQL, MySQL, MongoDB (Atlas), Dgraph, Firestore, GraphQL, REST, AWS (Cognito), GCP, Terraform, Docker, Jenkins, CI/CD, Auth0, Twilio, Sentry, Geth/Ethereum, blockchain, React (Nexopay), Git, GitHub, GitLab, Bitbucket, Jira, Airtable; flag the Allbetter/Syfe mismatch. Note "Go" is a short word: whole-word matching only.
- **Pipeline today:** 2 pages, so P3 doesn't apply and the text is complete. P7: the 5 labels risk becoming skills.

---

## 5. What this means for the fix (input to action item 18)

1. **Accept what people actually send:**
   - `.doc` (convert with LibreOffice); DOCX over 10 MB when the text is small (limit by text size, or strip embedded fonts).
   - Upload by employee page or by name match, not only by `EMP-####_` file names.
2. **Never delete content as a "header":** only remove a repeated line when it sits at the top or bottom of each page and looks like a header (name, page number, "Confidential"), never a `Label: value` line or a bullet.
3. **Projects are a first-class section:** name, link(s), role, technologies, features, duration (if written), domain, and a link to a job only when the resume shows it (or there's a single employer: "assumed").
4. **Experience without dates:** total years from the stated "N+ years" (marked "stated"); skill strength from **how many projects use it** and where it appears (project tech > job text > skills list > summary only), not only from years.
5. **Skills:**
   - Split "Category: list" lines and label-prefixed bullets in code; never store a category.
   - Separate activities ("Documentation") from technologies.
   - Map every variant and typo in table 2.3.
   - Cap years by technology age.
   - Treat exposure ("a team who … using Camunda") as not a skill.
6. **Headings:** detect by shape (short line, Title Case or CAPS, no full stop) plus an extended word list (table 2.1), never a fixed list alone.
7. ~~Duplicates~~: not needed (2.6). Identical or tailored resumes are normal.
8. **Keep contradictions** as written, with a warning (table 2.7). Never let the model "repair" them.
9. **Ignore file metadata** (R3's "Rahul K" title).
10. **Test set:** these 9 files with the expected profiles in section 4 become the evaluation set for every extraction change (Step 14).

---

## 6. Status after the fix (2026-11-05)

All 15 problems except P13 (not a problem) are fixed in code; see doc 09, section 13 and the doc 07 entry "Step 13b".
`python -m scripts.evaluate_real_resumes --offline` (the code alone, fed a correct model answer): **107 of 107 checks pass**. The 16 checks of the original Step 5 test (`compare_extraction`) still pass.
The run with the real model on the PC is the next step (action item 19).

