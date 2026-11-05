"""
Skill normalisation and detection: many spellings -> one canonical name.

Why not let the LLM do it? It is inconsistent across thousands of resumes ("K8s", "Kubernetes (k8s)",
"kubernetes"), it turns headings like "Ecommerce & CMS" into skills, and it drops skills that are only
listed (doc 07 audit: Python, Django and FastAPI disappeared from a resume that lists them). A dictionary is
exact, fast, free, and easy for you to extend.

CATALOG: canonical name -> (category, [aliases]). Aliases are matched case-insensitively, on whole words.
Spellings found in the real resumes (doc 18) are included: "Golang", "Postgres", "ReactJs", "Twillo",
"MySQ", "Quadrant" (for Qdrant), "ElasticCache", "Java script".

Extend it over time: add the skill, its category and the spellings your resumes use. Run
`python -m scripts.evaluate_real_resumes` afterwards to see the effect.
"""
import re
from functools import lru_cache

CATALOG: dict[str, tuple[str, list[str]]] = {
    # ---- languages ----
    "Python": ("language", ["python3", "python 3", "python (scripting)"]),
    "Java": ("language", ["core java", "java se", "java ee", "j2ee"]),
    "JavaScript": ("language", ["js", "java script", "es6", "ecmascript", "vanilla js"]),
    "TypeScript": ("language", ["ts"]),
    "Go": ("language", ["golang", "go lang"]),
    "C#": ("language", ["c sharp", "csharp"]),
    "C++": ("language", ["cpp"]),
    "PHP": ("language", ["php7", "php 7", "php8", "php 8", "core php"]),
    "Ruby": ("language", []),
    "Kotlin": ("language", []),
    "Swift": ("language", []),
    "Dart": ("language", []),
    "Rust": ("language", []),
    "Scala": ("language", []),
    "SQL": ("language", ["t-sql", "pl/sql", "plsql"]),
    "Bash": ("language", ["shell scripting", "bash scripting", "shell script", "shell scripts"]),
    "HTML": ("frontend", ["html5", "html 5"]),
    "CSS": ("frontend", ["css3", "css 3"]),
    # ---- backend frameworks and APIs ----
    "Django": ("framework", ["django framework"]),
    "Django REST Framework": ("framework", ["drf", "django rest", "django-rest-framework"]),
    "FastAPI": ("framework", ["fast api"]),
    "Flask": ("framework", []),
    "SQLAlchemy": ("framework", []),
    "Celery": ("framework", []),
    "Spring Boot": ("framework", ["springboot", "spring-boot"]),
    "Spring MVC": ("framework", []),
    "Hibernate": ("framework", []),
    ".NET": ("framework", ["dotnet", "asp.net", "asp.net mvc", ".net core", "asp.net core"]),
    "Node.js": ("framework", ["node", "nodejs", "node js"]),
    "Express": ("framework", ["express.js", "expressjs", "express js"]),
    "NestJS": ("framework", ["nest.js", "nest js"]),
    "Laravel": ("framework", ["laravel framework"]),
    "CodeIgniter": ("framework", ["code igniter"]),
    "Symfony": ("framework", []),
    "Ruby on Rails": ("framework", ["rails", "ror"]),
    "gRPC": ("framework", []),
    "Protobuf": ("framework", ["protocol buffers", "protobuf3"]),
    "GraphQL": ("framework", ["graphql apis", "graphql api"]),
    "REST APIs": ("practice", ["rest", "rest api", "restful", "restful api", "restful apis", "rest apis",
                               "rest services", "restful services", "rest/graphql"]),
    "WebSockets": ("framework", ["websocket", "web sockets", "socket.io", "sockets"]),
    "Microservices": ("practice", ["microservice", "micro-services", "microservices architecture",
                                   "microservice architecture"]),
    "Serverless": ("practice", ["serverless architecture", "serverless functions"]),
    "Webhooks": ("practice", ["webhook"]),
    "Swagger": ("tool", ["openapi", "swagger ui"]),
    "Postman": ("tool", []),
    # ---- frontend ----
    "React": ("frontend", ["react.js", "reactjs", "react js", "react framework"]),
    "Next.js": ("frontend", ["nextjs", "next js"]),
    "Angular": ("frontend", ["angular 2+", "angular2", "angular 2", "angular 2+ (angular)"]),
    "AngularJS": ("frontend", ["angular.js", "angular 1", "angularjs (1.x)"]),
    "Vue.js": ("frontend", ["vue", "vuejs", "vue js", "vue.js 3"]),
    "Nuxt.js": ("frontend", ["nuxt", "nuxtjs"]),
    "Svelte": ("frontend", []),
    "jQuery": ("frontend", ["jquery"]),
    "Redux": ("frontend", ["redux toolkit", "rtk"]),
    "redux-persist": ("frontend", ["redux persist"]),
    "Zustand": ("frontend", []),
    "Tailwind CSS": ("frontend", ["tailwind", "tailwindcss"]),
    "Bootstrap": ("frontend", []),
    "Material UI": ("frontend", ["mui", "material-ui", "materialui"]),
    "styled-components": ("frontend", ["styled components"]),
    "Sass": ("frontend", ["scss"]),
    "Handlebars.js": ("frontend", ["handlebars", "handlebarsjs"]),
    "Formik": ("frontend", []),
    "Storybook": ("frontend", []),
    "Yup": ("frontend", []),
    "Axios": ("frontend", []),
    "RxJS": ("frontend", []),
    "NgRx": ("frontend", []),
    "Webpack": ("frontend", []),
    "Vite": ("frontend", []),
    # ---- mobile ----
    "React Native": ("mobile", ["react-native", "reactnative"]),
    "Flutter": ("mobile", []),
    "Android": ("mobile", ["android development", "android core", "native android"]),
    "iOS": ("mobile", ["ios development"]),
    "Expo": ("mobile", []),
    "Room": ("mobile", ["room database", "room db"]),
    "MVVM": ("practice", ["mvvm architecture"]),
    # ---- e-commerce and CMS ----
    "WordPress": ("cms", ["wordpress (custom plugins)", "wp", "wordpress plugins", "wordpress development"]),
    "WooCommerce": ("cms", ["woo commerce"]),
    "Shopify": ("cms", ["shopify plus"]),
    "Liquid": ("cms", ["shopify liquid"]),
    "BigCommerce": ("cms", ["big commerce"]),
    "Stencil": ("cms", ["stencil cli", "stencil framework", "bigcommerce stencil"]),
    "Magento": ("cms", ["adobe magento", "magento 2", "adobe commerce"]),
    "Drupal": ("cms", []),
    "Strapi": ("cms", []),
    "Headless commerce": ("cms", ["headless", "headless apis", "headless commerce"]),
    # ---- databases ----
    "PostgreSQL": ("database", ["postgres", "postgresql", "psql"]),
    "MySQL": ("database", ["mysq"]),
    "MongoDB": ("database", ["mongo", "mongodb atlas", "mongodb (atlas)"]),
    "Redis": ("database", ["redis queue", "rq"]),
    "SQLite": ("database", []),
    "Oracle": ("database", ["oracle db", "oracle database"]),
    "SQL Server": ("database", ["mssql", "ms sql", "microsoft sql server"]),
    "DynamoDB": ("database", ["amazon dynamodb", "aws dynamodb"]),
    "Firestore": ("database", ["cloud firestore", "firestore (firebase)"]),
    "Dgraph": ("database", []),
    "Elasticsearch": ("database", ["elastic search", "elk"]),
    "Amazon OpenSearch": ("database", ["opensearch", "opensearch (aoss)", "aoss", "opensearch serverless",
                                       "amazon opensearch serverless"]),
    "Snowflake": ("database", []),
    "BigQuery": ("database", ["google bigquery"]),
    "Stored procedures": ("database", ["stored procedure", "stored procedures and functions"]),
    # ---- cloud ----
    "AWS": ("cloud", ["amazon web services"]),
    "Azure": ("cloud", ["microsoft azure"]),
    "GCP": ("cloud", ["google cloud", "google cloud platform"]),
    "AWS Lambda": ("cloud", ["lambda", "lambda functions", "aws lambda functions"]),
    "Amazon S3": ("cloud", ["s3", "s3 bucket", "aws s3", "s3 buckets"]),
    "Amazon API Gateway": ("cloud", ["api gateway", "api gateways", "aws api gateway"]),
    "Amazon SQS": ("cloud", ["sqs", "aws sqs"]),
    "Amazon EventBridge": ("cloud", ["eventbridge", "aws eventbridge"]),
    "Amazon ElastiCache": ("cloud", ["elasticache", "elasticcache", "elastic cache"]),
    "Amazon CloudWatch": ("cloud", ["cloudwatch"]),
    "AWS CloudTrail": ("cloud", ["cloudtrail"]),
    "AWS Cognito": ("cloud", ["cognito", "aws-cognito", "amazon cognito"]),
    "AWS KMS": ("cloud", ["kms"]),
    "AWS Secrets Manager": ("cloud", ["secrets manager"]),
    "Amazon EC2": ("cloud", ["ec2", "aws ec2"]),
    "Amazon RDS": ("cloud", ["rds", "aws rds"]),
    "Amazon EKS": ("cloud", ["eks", "aws eks"]),
    "AKS": ("cloud", ["azure kubernetes service"]),
    "AWS SageMaker": ("cloud", ["sagemaker", "amazon sagemaker"]),
    "Firebase": ("cloud", ["firebase api", "firebase cloud", "google firebase"]),
    "Firebase Cloud Messaging": ("cloud", ["fcm", "fcm push notifications"]),
    "Vercel": ("cloud", []),
    "Heroku": ("cloud", []),
    "DigitalOcean": ("cloud", ["digital ocean"]),
    # ---- devops ----
    "Kubernetes": ("devops", ["k8s", "kube"]),
    "Docker": ("devops", ["docker containers", "dockerization", "dockerized", "dockerised", "containerization"]),
    "Helm": ("devops", ["helm charts"]),
    "Terraform": ("devops", ["hashicorp terraform"]),
    "Ansible": ("devops", []),
    "Bicep": ("devops", ["azure bicep"]),
    "ArgoCD": ("devops", ["argo cd", "argo-cd"]),
    "Jenkins": ("devops", []),
    "GitHub Actions": ("devops", []),
    "GitLab CI": ("devops", ["gitlab ci/cd", "gitlab-ci"]),
    "Azure DevOps": ("devops", []),
    "CI/CD": ("devops", ["ci cd", "ci/cd pipelines", "ci/cd pipeline", "continuous integration",
                         "continuous delivery", "continuous deployment"]),
    "Nginx": ("devops", []),
    "Linux": ("devops", ["ubuntu", "centos"]),
    "Prometheus": ("devops", []),
    "Grafana": ("devops", []),
    "Sentry": ("devops", []),
    "Cron jobs": ("devops", ["cronjobs", "cron", "cronjob", "automation/cronjobs"]),
    # ---- data ----
    "Apache Kafka": ("data", ["kafka"]),
    "RabbitMQ": ("data", ["rabbit mq"]),
    "PySpark": ("data", ["spark", "apache spark"]),
    "Apache Airflow": ("data", ["airflow"]),
    "dbt": ("data", []),
    "pandas": ("data", []),
    "NumPy": ("data", ["numpy"]),
    "Web scraping": ("data", ["scraping", "product scraping"]),
    # ---- AI / ML ----
    "Machine Learning": ("ml", ["ml", "machine-learning"]),
    "Generative AI": ("ml", ["genai", "gen ai", "generative-ai"]),
    "LLMs": ("ml", ["llm", "large language models", "large language model", "llm integration", "llm integrations"]),
    "OpenAI API": ("ml", ["openai", "open ai", "openai apis", "chatgpt api", "gpt-4", "gpt-4o", "gpt 4", "gpt-3.5",
                          "gpt-based llm integration", "gpt"]),
    "Claude API": ("ml", ["anthropic api", "claude apis"]),
    "Prompt engineering": ("ml", ["prompt engineering", "prompting"]),
    "RAG": ("ml", ["retrieval-augmented generation", "retrieval augmented generation", "rag pipelines",
                   "rag pipeline", "rag-based architectures", "rag-based workflows", "rag-style retrieval",
                   "rag (retrieval-augmented generation)"]),
    "AI agents": ("ml", ["ai agents", "ai agent", "autonomous agents", "agentic ai", "llm agents"]),
    "AI chatbots": ("ml", ["chatbots", "chatbot", "ai chatbot", "conversational ai"]),
    "Voice assistants": ("ml", ["voice assistant", "voice bots", "voicebot"]),
    "Embeddings": ("ml", ["sentence embeddings", "vector embeddings", "text embeddings"]),
    "Vector Databases": ("ml", ["vector database", "vector db", "vector databases", "vectordatabase", "vector search"]),
    "LangChain": ("ml", []),
    "LlamaIndex": ("ml", ["llama index"]),
    "FastEmbed": ("ml", []),
    "ChromaDB": ("ml", ["chroma"]),
    "FAISS": ("ml", []),
    "Qdrant": ("ml", ["quadrant"]),
    "Pinecone": ("ml", []),
    "Weaviate": ("ml", []),
    "MLflow": ("ml", []),
    "Kubeflow": ("ml", []),
    "vLLM": ("ml", []),
    "LLM serving": ("ml", ["model serving", "llm deployment", "llm inference"]),
    "Ollama": ("ml", []),
    "NLP": ("ml", ["natural language processing"]),
    "Named Entity Recognition": ("ml", ["ner"]),
    "PyTorch": ("ml", []),
    "TensorFlow": ("ml", ["tensorflow 2"]),
    "scikit-learn": ("ml", ["sklearn", "scikit learn"]),
    "Hugging Face Transformers": ("ml", ["hugging face", "huggingface", "transformers"]),
    "spaCy": ("ml", ["spacy"]),
    "NLTK": ("ml", []),
    "BERT": ("ml", ["bert models", "bert model"]),
    "CUDA": ("ml", []),
    "LLM evaluation": ("ml", ["llm evaluation", "llm evals", "rag evaluation", "evaluation of llms"]),
    "n8n": ("ml", ["n8n automation", "n8n automations"]),
    "Voiceflow": ("ml", []),
    # ---- integrations and SaaS APIs ----
    "Stripe": ("integration", []),
    "PayPal": ("integration", []),
    "Authorize.Net": ("integration", ["authorize net", "authorizenet"]),
    "Razorpay": ("integration", []),
    "PayU": ("integration", ["payu payment gateway"]),
    "Flutterwave": ("integration", ["flutterwave payment gateway"]),
    "Seerbit": ("integration", ["seerbit payment gateway"]),
    "Payment gateways": ("integration", ["payment gateway", "payment gateway apis", "payment gateways integration"]),
    "Apple Pay": ("integration", []),
    "Apple Wallet": ("integration", []),
    "Twilio": ("integration", ["twillo"]),
    "Auth0": ("integration", []),
    "OAuth": ("integration", ["oauth2", "oauth 2.0"]),
    "JWT": ("integration", ["json web tokens"]),
    "Google Maps API": ("integration", ["google maps", "google maps and places", "google places", "google map"]),
    "Zoom API": ("integration", []),
    "Podio": ("integration", []),
    "Camunda": ("integration", []),
    "Indeed Apply API": ("integration", ["indeed-apply api", "indeed apply"]),
    "Coinbase API": ("integration", ["coinbase", "coinbase apis"]),
    "Bitvavo API": ("integration", ["bitvavo"]),
    "Blockchain": ("integration", ["blockchain technology", "blockchain-based tokenization", "blockchain-driven tokenization"]),
    "Geth": ("integration", ["go-ethereum"]),
    "Bluetooth": ("integration", ["ble", "bluetooth low energy"]),
    "Push notifications": ("integration", ["push notification", "remote push notifications", "web push notifications",
                                           "web push"]),
    "FHIR": ("integration", []),
    "Dymo SDK": ("integration", ["dymo hardware sdk"]),
    # ---- testing ----
    "pytest": ("testing", []),
    "Selenium": ("testing", ["selenium webdriver"]),
    "Playwright": ("testing", []),
    "Cypress": ("testing", []),
    "JMeter": ("testing", ["apache jmeter"]),
    "Jest": ("testing", []),
    "Unit testing": ("testing", ["unit tests", "unit and integration tests", "integration tests"]),
    # ---- tools ----
    "Git": ("tool", ["version control"]),
    "GitHub": ("tool", []),
    "GitLab": ("tool", []),
    "Bitbucket": ("tool", []),
    "Jira": ("tool", []),
    "Confluence": ("tool", []),
    "Slack": ("tool", []),
    "Airtable": ("tool", []),
    "VS Code": ("tool", ["vscode", "visual studio code"]),
    "Cursor": ("tool", ["cursor ai", "cursor ide"]),
    "Claude Code": ("tool", ["claude ai"]),
    "Antigravity IDE": ("tool", ["antigravity", "google antigravity"]),
    # ---- ways of working ----
    "Agile": ("practice", ["agile methodologies", "agile methodology", "agile delivery", "agile workflows"]),
    "Scrum": ("practice", []),
    "DevOps": ("practice", ["devops practices"]),
    "Project management": ("practice", ["project manager"]),
    "Client communication": ("practice", ["client interaction", "client consultation", "client-facing"]),
    "Code review": ("practice", ["code reviews"]),
    "Hiring": ("practice", ["recruiting", "interviewing"]),
    "People management": ("practice", ["team management", "people manager", "line management"]),
    "System design": ("practice", ["system architecture"]),
    "Mentoring": ("practice", ["mentored", "mentorship"]),
    "SaaS": ("practice", ["saas platform", "b2b saas"]),
}

# The first year a technology could be used. A skill can't have more years than its technology has existed:
# "RAG pipelines" inside a job that started in 2018 count from 2020, not from 2018 (doc 07 audit).
TECH_SINCE: dict[str, int] = {
    "TypeScript": 2012, "Go": 2009, "Kotlin": 2016, "Swift": 2014, "Dart": 2011, "Rust": 2015,
    "FastAPI": 2018, "Django REST Framework": 2011, "NestJS": 2017, "Laravel": 2011, "Node.js": 2009,
    "Express": 2010, "gRPC": 2016, "GraphQL": 2015, "Spring Boot": 2014,
    "React": 2013, "Next.js": 2016, "Angular": 2016, "Vue.js": 2014, "Nuxt.js": 2016, "Svelte": 2016,
    "Redux": 2015, "redux-persist": 2016, "Zustand": 2019, "Tailwind CSS": 2017, "Material UI": 2014,
    "styled-components": 2016, "Formik": 2017, "Axios": 2014, "Vite": 2020,
    "React Native": 2015, "Flutter": 2017, "Expo": 2015, "Room": 2017,
    "WooCommerce": 2011, "Shopify": 2006, "BigCommerce": 2009, "Stencil": 2016, "Strapi": 2015,
    "DynamoDB": 2012, "Firestore": 2017, "Dgraph": 2016, "Amazon OpenSearch": 2021,
    "AWS Lambda": 2014, "Amazon EventBridge": 2019, "AWS Cognito": 2014, "Amazon EKS": 2018, "AKS": 2018,
    "AWS SageMaker": 2017, "Firebase": 2012, "Firebase Cloud Messaging": 2016, "Vercel": 2015,
    "Kubernetes": 2014, "Docker": 2013, "Helm": 2016, "Terraform": 2014, "ArgoCD": 2018,
    "GitHub Actions": 2019, "Prometheus": 2012, "Grafana": 2014,
    "Apache Kafka": 2011, "PySpark": 2014, "Apache Airflow": 2015, "dbt": 2016,
    "Generative AI": 2022, "LLMs": 2020, "OpenAI API": 2020, "Claude API": 2023, "Prompt engineering": 2020,
    "RAG": 2020, "AI agents": 2023, "Embeddings": 2013, "Vector Databases": 2019, "LangChain": 2022,
    "LlamaIndex": 2022, "FastEmbed": 2023, "ChromaDB": 2022, "FAISS": 2017, "Qdrant": 2021, "Pinecone": 2019,
    "Weaviate": 2019, "MLflow": 2018, "Kubeflow": 2018, "vLLM": 2023, "Ollama": 2023, "PyTorch": 2016,
    "TensorFlow": 2015, "Hugging Face Transformers": 2018, "spaCy": 2015, "LLM evaluation": 2022,
    "n8n": 2019, "Voiceflow": 2019, "BERT": 2018, "LLM serving": 2022, "Storybook": 2016, "Bicep": 2020, "Flutterwave": 2016, "Seerbit": 2018, "Apple Pay": 2014,
    "Apple Wallet": 2012, "Auth0": 2013, "Zoom API": 2013, "Indeed Apply API": 2012, "Coinbase API": 2012,
    "Bitvavo API": 2018, "Geth": 2015, "FHIR": 2014, "Playwright": 2020, "Cypress": 2017, "Jest": 2014,
    "Airtable": 2012, "VS Code": 2015, "Cursor": 2023, "Claude Code": 2025, "Antigravity IDE": 2025,
}

# Common English words that are also skill names: only matched when written with a capital letter
# ("Go", "React", "REST"), so "to go live", "react quickly" and "the rest" are not skills.
_CASE_SENSITIVE = {
    "go", "react", "rest", "express", "node", "spark", "shell", "chroma", "kube", "transformers", "helm",
    "flask", "jest", "yup", "room", "cron", "expo", "liquid", "stencil", "headless", "lambda",
    "swift", "rust", "dart", "ruby", "rails", "ts", "js", "ml", "wp", "ble", "rq", "rtk", "kms", "ner",
    "gpt", "s3", "sqs", "rds", "ec2", "eks", "fcm", "aoss", "cursor", "slack", "elk", "mui",
    "antigravity", "prompting", "cronjob", "cronjobs", "android",
    "ios", "angular", "vue", "nuxt", "svelte", "drupal", "scrum", "agile", "devops", "saas",
    "mentored", "mentorship", "openapi", "headless apis", "version control", "llm",
}

# Build one lookup table: lowercase spelling -> canonical name
_LOOKUP: dict[str, str] = {}
for _canonical, (_category, _aliases) in CATALOG.items():
    _LOOKUP[_canonical.lower()] = _canonical
    for _alias in _aliases:
        _LOOKUP[_alias.lower()] = _canonical

_PARENS = re.compile(r"\(([^)]*)\)")
_LEVEL_WORDS = re.compile(r"\b(basic|basics|beginner|intermediate|advanced|expert|\d+\s*\+?\s*(yrs?|years?))\b",
                          re.IGNORECASE)


def category_of(name: str) -> str | None:
    entry = CATALOG.get(name)
    return entry[0] if entry else None


def is_known(name: str) -> bool:
    return name in CATALOG


def _lookup(text: str) -> str | None:
    key = re.sub(r"\s+", " ", text).strip(" .,;:-").lower()
    return _LOOKUP.get(key)


def normalize_skill(raw: str) -> list[str]:
    """
    One written skill -> one or more canonical names.
      "k8s (EKS)"          -> ["Kubernetes", "Amazon EKS"]
      "Django (basic)"     -> ["Django"]
      "AWS (EC2, RDS, S3)" -> ["AWS", "Amazon EC2", "Amazon RDS", "Amazon S3"]
      "React (1 yr)"       -> ["React"]
      "Bicep"              -> ["Bicep"]          (unknown skills are kept as written)
    """
    raw = (raw or "").strip()
    if not raw:
        return []

    whole = _lookup(raw)                        # 1. the exact spelling is known ("Angular 2+")
    if whole:
        return [whole]

    inner_parts = [p for group in _PARENS.findall(raw) for p in group.split(",")]
    outer = _PARENS.sub("", raw)                # 2. strip "(...)" and try again
    outer = _LEVEL_WORDS.sub("", outer)
    results: list[str] = []
    main = _lookup(outer)
    if main:
        results.append(main)
    elif "/" in outer and all(_lookup(p) for p in outer.split("/")):
        results.extend(_lookup(p) for p in outer.split("/"))   # "Python/Django" -> both
    else:
        cleaned = re.sub(r"\s+", " ", outer).strip(" .,;:-")
        if cleaned:
            results.append(cleaned)             # unknown: keep the person's own spelling

    for part in inner_parts:                    # 3. known skills inside the brackets count too
        known = _lookup(part)
        if known and known not in results:
            results.append(known)
    return results


def spellings(name: str) -> list[str]:
    """Every known way of writing a canonical skill: 'Kubernetes' -> ['Kubernetes', 'k8s', 'kube']."""
    entry = CATALOG.get(name)
    return [name, *entry[1]] if entry else [name]


# --------------------------------------------------------------------------- finding skills in text
@lru_cache(maxsize=1)
def _matcher() -> re.Pattern:
    """One regex for every spelling, longest first ("react native" wins over "react", "node.js" over "node")."""
    spellings_sorted = sorted(_LOOKUP, key=len, reverse=True)
    parts = []
    for s in spellings_sorted:
        p = re.escape(s).replace(r"\ ", r"[\s\-]+")       # "react native" also matches "react-native"
        parts.append(p)
    return re.compile(r"(?<![A-Za-z0-9])(" + "|".join(parts) + r")(?![A-Za-z0-9+#])", re.IGNORECASE)


def find_skills(text: str) -> list[tuple[str, int, int]]:
    """
    Every catalogue skill written in a text, with its position: [(canonical, start, end), ...].
      "Built APIs with Node.js and Express; deployed to AWS Lambda" -> Node.js, Express, AWS Lambda
    Whole words only; common English words ("go", "react", "rest") only when capitalised.
    """
    found = []
    for m in _matcher().finditer(text or ""):
        written = m.group(1)
        key = re.sub(r"[\s\-]+", " ", written.lower())
        if key in _CASE_SENSITIVE and written == written.lower():
            continue
        if key in ("ts", "js", "ml", "ner", "kms", "gpt") and not written.isupper():
            continue                                       # "ts"/"js" only as "TS"/"JS"
        canonical = _LOOKUP.get(key) or _LOOKUP.get(written.lower())
        if canonical is None:                              # "react-native" written with a hyphen
            canonical = _LOOKUP.get(written.lower().replace("-", " ")) or _LOOKUP.get(key.replace(" ", "-"))
        if canonical:
            found.append((canonical, m.start(1), m.end(1)))
    return found


def skills_in(text: str) -> list[str]:
    """The distinct catalogue skills in a text, in order of first mention."""
    return list(dict.fromkeys(name for name, _, _ in find_skills(text)))


# --------------------------------------------------------------------------- relations between skills
# Using the key skill means using these too (for YEARS of use): a Laravel job is a PHP job, a WooCommerce
# shop runs on WordPress, Django code is Python. Doc 07 audit: PHP got 5.2 years instead of ~13.7.
IMPLIED_USE: dict[str, list[str]] = {
    "Django": ["Python"], "Django REST Framework": ["Django", "Python"], "FastAPI": ["Python"],
    "Flask": ["Python"], "Celery": ["Python"], "pytest": ["Python"], "pandas": ["Python"],
    "PySpark": ["Python"], "PyTorch": ["Python"], "scikit-learn": ["Python"], "SQLAlchemy": ["Python"],
    "spaCy": ["Python", "NLP"], "NLTK": ["Python", "NLP"], "LangChain": ["Python"],
    "Spring Boot": ["Java"], "Spring MVC": ["Java"], "Hibernate": ["Java"], ".NET": ["C#"],
    "Laravel": ["PHP"], "CodeIgniter": ["PHP"], "Symfony": ["PHP"], "WordPress": ["PHP"],
    "WooCommerce": ["WordPress", "PHP"], "Magento": ["PHP"], "Drupal": ["PHP"], "Ruby on Rails": ["Ruby"],
    "Express": ["Node.js", "JavaScript"], "NestJS": ["Node.js", "TypeScript"], "Node.js": ["JavaScript"],
    "React": ["JavaScript"], "Next.js": ["React", "JavaScript"], "Vue.js": ["JavaScript"],
    "Nuxt.js": ["Vue.js", "JavaScript"], "Angular": ["TypeScript"], "AngularJS": ["JavaScript"],
    "React Native": ["JavaScript"], "Redux": ["JavaScript"], "jQuery": ["JavaScript"],
    "Handlebars.js": ["JavaScript"], "Flutter": ["Dart"], "Stencil": ["BigCommerce", "Handlebars.js"],
    "Liquid": ["Shopify"], "Tailwind CSS": ["CSS"], "Sass": ["CSS"], "Bootstrap": ["CSS"],
    "AWS Lambda": ["AWS"], "Amazon S3": ["AWS"], "Amazon API Gateway": ["AWS"], "Amazon SQS": ["AWS"],
    "Amazon EventBridge": ["AWS"], "Amazon ElastiCache": ["AWS"], "Amazon CloudWatch": ["AWS"],
    "AWS CloudTrail": ["AWS"], "AWS Cognito": ["AWS"], "AWS KMS": ["AWS"], "AWS Secrets Manager": ["AWS"],
    "Amazon EC2": ["AWS"], "Amazon RDS": ["AWS"], "DynamoDB": ["AWS"], "Amazon OpenSearch": ["AWS"],
    "Amazon EKS": ["AWS", "Kubernetes"], "AKS": ["Azure", "Kubernetes"], "AWS SageMaker": ["AWS"],
    "Firestore": ["Firebase"], "Firebase Cloud Messaging": ["Firebase"], "GitHub Actions": ["CI/CD"],
    "GitLab CI": ["CI/CD"], "Jenkins": ["CI/CD"], "Azure DevOps": ["CI/CD"], "Geth": ["Blockchain"],
    "RAG": ["LLMs"], "OpenAI API": ["LLMs"], "Claude API": ["LLMs"],
}

# Having the key skill implies (part of) another one. Used by matching (Step 7):
# a role needing "Kubernetes" gives partial credit to someone with "Amazon EKS" or "AKS".
SKILL_IMPLIES: dict[str, list[str]] = {
    "Amazon EKS": ["Kubernetes", "AWS"],
    "AKS": ["Kubernetes", "Azure"],
    "Helm": ["Kubernetes"],
    "ArgoCD": ["Kubernetes", "CI/CD"],
    "Kubeflow": ["Kubernetes"],
    "Django REST Framework": ["Django", "REST APIs", "Python"],
    "Django": ["Python"],
    "FastAPI": ["REST APIs", "Python"],
    "Flask": ["REST APIs", "Python"],
    "Spring Boot": ["Java", "Microservices"],
    "Spring MVC": ["Java"],
    "Next.js": ["React"],
    "Node.js": ["JavaScript"],
    "Express": ["Node.js", "REST APIs"],
    "NestJS": ["Node.js", "TypeScript"],
    "Laravel": ["PHP"],
    "WordPress": ["PHP"],
    "WooCommerce": ["WordPress", "PHP"],
    "Magento": ["PHP"],
    "React Native": ["React", "JavaScript"],
    "PySpark": ["Python"],
    "AWS SageMaker": ["AWS"],
    "AWS Lambda": ["AWS", "Serverless"],
    "DynamoDB": ["AWS"],
    "RAG": ["LLMs", "Vector Databases"],
    "LangChain": ["LLMs"],
    "LlamaIndex": ["LLMs"],
    "OpenAI API": ["LLMs"],
    "vLLM": ["LLMs"],
    "LLM serving": ["LLMs"],
    "Prompt engineering": ["LLMs"],
    "LLM evaluation": ["LLMs"],
    "ChromaDB": ["Vector Databases"],
    "FAISS": ["Vector Databases"],
    "Qdrant": ["Vector Databases"],
    "Pinecone": ["Vector Databases"],
    "Hugging Face Transformers": ["NLP"],
    "spaCy": ["NLP"],
    "GitHub Actions": ["CI/CD"],
    "Jenkins": ["CI/CD"],
    "Azure DevOps": ["CI/CD"],
    "GitHub": ["Git"],
    "GitLab": ["Git"],
    "Bitbucket": ["Git"],
    "Firestore": ["Firebase"],
}

# Kept for older imports: frameworks that imply a programming language.
IMPLIED_LANGUAGE: dict[str, str] = {k: v[-1] for k, v in IMPLIED_USE.items()
                                    if CATALOG.get(v[-1], ("",))[0] == "language"}

_IMPLIES_LOWER = {k.lower(): v for k, v in SKILL_IMPLIES.items()}


def implied_by(name: str) -> list[str]:
    """Skills that having `name` implies (case-insensitive): implied_by("Amazon EKS") -> ["Kubernetes", "AWS"]."""
    return _IMPLIES_LOWER.get((name or "").lower(), [])


def with_implied_use(names: list[str]) -> list[str]:
    """The skills plus what using them implies, transitively: ["WooCommerce"] -> WooCommerce, WordPress, PHP."""
    out = list(dict.fromkeys(names))
    i = 0
    while i < len(out):
        for extra in IMPLIED_USE.get(out[i], []):
            if extra not in out:
                out.append(extra)
        i += 1
    return out


def _phrase_norm(text: str) -> str:
    # lowercase, punctuation -> space, "/" kept as its own word ("ci/cd" -> "ci / cd", "a/b" -> "a / b")
    text = re.sub(r"[^a-z0-9+#./]+", " ", (text or "").lower()).replace("/", " / ")
    return re.sub(r"\s+", " ", text).strip()


def skills_in_phrase(phrase: str) -> list[str]:
    """
    Known skills mentioned INSIDE a longer phrase (used for role requirements, Step 7):
      "retrieval-augmented generation using vector databases" -> ["RAG", "Vector Databases"]
      "nlp fundamentals"                                      -> ["NLP"]
      "strong communication"                                  -> []
    Longest spellings are matched first, and matched words are blanked out,
    so "llm evaluation" gives "LLM evaluation", not also "LLMs".
    """
    text = f" {_phrase_norm(phrase)} "
    found: list[str] = []
    for spelling in sorted(_LOOKUP, key=len, reverse=True):
        key = f" {_phrase_norm(spelling)} "
        if len(key.strip()) < 2 or key not in text:
            continue
        text = text.replace(key, " | ")
        canonical = _LOOKUP[spelling]
        if canonical not in found:
            found.append(canonical)
    return found
