"""
Skill normalisation: many spellings -> one canonical name.

Why not let the LLM do it? It is inconsistent across thousands of resumes ("K8s", "Kubernetes (k8s)",
"kubernetes"). A dictionary is exact, fast, free, and easy for you to extend.

Add your company's skills to CATALOG over time: canonical name -> (category, [aliases]).
Aliases are matched case-insensitively.
"""
import re

CATALOG: dict[str, tuple[str, list[str]]] = {
    # ---- languages ----
    "Python": ("language", ["python3", "python 3", "python (scripting)"]),
    "Java": ("language", ["core java", "java se", "java ee"]),
    "JavaScript": ("language", ["js", "java script", "es6", "ecmascript"]),
    "TypeScript": ("language", ["ts"]),
    "Go": ("language", ["golang", "go lang"]),
    "C#": ("language", ["c sharp", "csharp"]),
    "SQL": ("language", ["t-sql", "pl/sql"]),
    "Bash": ("language", ["shell scripting", "shell", "bash scripting"]),
    # ---- backend frameworks ----
    "Django": ("framework", ["django framework"]),
    "Django REST Framework": ("framework", ["drf", "django rest", "django-rest-framework"]),
    "FastAPI": ("framework", ["fast api"]),
    "Flask": ("framework", []),
    "Spring Boot": ("framework", ["springboot", "spring-boot"]),
    "Spring MVC": ("framework", []),
    ".NET": ("framework", ["dotnet", "asp.net", "asp.net mvc", ".net core", "asp.net core"]),
    "Node.js": ("framework", ["node", "nodejs", "node js"]),
    "Express": ("framework", ["express.js", "expressjs"]),
    "Celery": ("framework", []),
    "gRPC": ("framework", ["grpc"]),
    "REST APIs": ("concept", ["rest", "rest api", "restful", "restful apis", "rest apis"]),
    "Microservices": ("concept", ["microservice", "micro-services"]),
    "GraphQL": ("framework", []),
    # ---- frontend ----
    "React": ("framework", ["react.js", "reactjs", "react js"]),
    "Next.js": ("framework", ["nextjs", "next js"]),
    "Angular": ("framework", ["angular 2+", "angular2", "angular 2", "angular 2+ (angular)"]),
    "AngularJS": ("framework", ["angular.js", "angular 1", "angularjs (1.x)"]),
    "Redux": ("framework", []),
    "Tailwind CSS": ("framework", ["tailwind", "tailwindcss"]),
    "RxJS": ("framework", []),
    "NgRx": ("framework", []),
    # ---- databases ----
    "PostgreSQL": ("database", ["postgres", "postgresql", "psql"]),
    "MySQL": ("database", []),
    "MongoDB": ("database", ["mongo"]),
    "Redis": ("database", []),
    "Oracle": ("database", ["oracle db", "oracle database"]),
    "Snowflake": ("database", []),
    "BigQuery": ("database", ["google bigquery"]),
    # ---- devops / cloud ----
    "Kubernetes": ("devops", ["k8s", "kube"]),
    "Docker": ("devops", ["docker containers"]),
    "Helm": ("devops", ["helm charts"]),
    "Terraform": ("devops", ["hashicorp terraform"]),
    "Ansible": ("devops", []),
    "ArgoCD": ("devops", ["argo cd", "argo-cd"]),
    "Jenkins": ("devops", []),
    "GitHub Actions": ("devops", []),
    "Azure DevOps": ("devops", []),
    "Prometheus": ("devops", []),
    "Grafana": ("devops", []),
    "AWS": ("cloud", ["amazon web services"]),
    "Azure": ("cloud", ["microsoft azure"]),
    "GCP": ("cloud", ["google cloud", "google cloud platform"]),
    "Amazon EKS": ("cloud", ["eks", "aws eks"]),
    "AKS": ("cloud", ["azure kubernetes service"]),
    "AWS SageMaker": ("cloud", ["sagemaker", "amazon sagemaker"]),
    # ---- data ----
    "Apache Kafka": ("data", ["kafka"]),
    "PySpark": ("data", ["spark", "apache spark"]),
    "Apache Airflow": ("data", ["airflow"]),
    "dbt": ("data", []),
    "pandas": ("data", []),
    # ---- AI / ML ----
    "PyTorch": ("ml", []),
    "scikit-learn": ("ml", ["sklearn", "scikit learn"]),
    "Hugging Face Transformers": ("ml", ["hugging face", "huggingface", "transformers"]),
    "LangChain": ("ml", []),
    "RAG": ("ml", ["retrieval-augmented generation", "retrieval augmented generation"]),
    "Vector Databases": ("ml", ["vector database", "vector db", "vector databases"]),
    "ChromaDB": ("ml", ["chroma"]),
    "FAISS": ("ml", []),
    "MLflow": ("ml", []),
    "Kubeflow": ("ml", []),
    "vLLM": ("ml", []),
    "NLP": ("ml", ["natural language processing"]),
    "LLMs": ("ml", ["llm", "large language models", "large language model"]),
    # ---- testing ----
    "pytest": ("testing", []),
    "Selenium": ("testing", ["selenium webdriver"]),
    "Playwright": ("testing", []),
    "Cypress": ("testing", []),
    "JMeter": ("testing", ["apache jmeter"]),
    "Jest": ("testing", []),
    "Postman": ("testing", []),
    # ---- other ----
    "Git": ("tool", ["github", "gitlab"]),
}

# Build one lookup table: lowercase spelling -> canonical name
_LOOKUP: dict[str, str] = {}
for canonical, (_category, aliases) in CATALOG.items():
    _LOOKUP[canonical.lower()] = canonical
    for alias in aliases:
        _LOOKUP[alias.lower()] = canonical

_PARENS = re.compile(r"\(([^)]*)\)")
_LEVEL_WORDS = re.compile(r"\b(basic|beginner|intermediate|advanced|expert|\d+\s*(yrs?|years?))\b", re.IGNORECASE)


def category_of(name: str) -> str | None:
    entry = CATALOG.get(name)
    return entry[0] if entry else None


def _lookup(text: str) -> str | None:
    key = re.sub(r"\s+", " ", text).strip(" .,;:-").lower()
    return _LOOKUP.get(key)


def normalize_skill(raw: str) -> list[str]:
    """
    One written skill -> one or more canonical names.
      "k8s (EKS)"          -> ["Kubernetes", "Amazon EKS"]
      "Django (basic)"     -> ["Django"]
      "AWS (EC2, RDS, S3)" -> ["AWS"]            (EC2 etc. are not in the catalog, so ignored)
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


# A framework or tool written in a job's text implies the language was used there too.
# (Used by job-level grounding in postprocess.py: "FastAPI" in a job's text -> Python is allowed for that job.)
IMPLIED_LANGUAGE: dict[str, str] = {
    "Django": "Python", "Django REST Framework": "Python", "FastAPI": "Python", "Flask": "Python",
    "Celery": "Python", "pytest": "Python", "pandas": "Python", "PySpark": "Python",
    "PyTorch": "Python", "scikit-learn": "Python",
    "Spring Boot": "Java", "Spring MVC": "Java",
    ".NET": "C#",
}


def spellings(name: str) -> list[str]:
    """Every known way of writing a canonical skill: 'Kubernetes' -> ['Kubernetes', 'k8s', 'kube']."""
    entry = CATALOG.get(name)
    return [name, *entry[1]] if entry else [name]
