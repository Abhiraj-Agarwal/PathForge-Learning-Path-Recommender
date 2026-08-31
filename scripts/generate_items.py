"""Generate the four seed datasets used by PathForge.

Writes (deterministic):
  data/skills.json    -> {"id","name","aliases","cluster","prerequisites"}
  data/courses.json   -> {"id","title","provider","url","description",
                          "level","rating","duration_hours","skill_tags"}
  data/jds.json       -> {"id","title","company","role_family","location",
                          "seniority","description","skills"}
  data/item_bank.json -> {"id","skill_id","cluster","text","options",
                          "correct_index","difficulty"}

The skills graph is hand-curated and validated at generation time:
  * every prerequisite id resolves
  * the DAG is acyclic (Kahn's algorithm) -- a broken edge must crash loudly

Usage:
  python scripts/generate_items.py --out data --seed 42
"""

import argparse
import json
import random
from collections import defaultdict, deque
from pathlib import Path

# --------------------------------------------------------------------------
# 1. THE SKILL DAG  (hand-checked; single source of prerequisite truth)
# --------------------------------------------------------------------------

SKILLS = [
    # ---- foundations -----------------------------------------------------
    {"id": "programming_basics", "name": "Programming Basics",
     "aliases": ["coding basics", "intro to programming", "programming 101"],
     "cluster": "foundations", "prerequisites": []},
    {"id": "python_basics", "name": "Python Fundamentals",
     "aliases": ["python", "python3", "basic python", "python basics"],
     "cluster": "foundations", "prerequisites": ["programming_basics"]},
    {"id": "data_structures", "name": "Data Structures & Algorithms",
     "aliases": ["dsa", "algorithms", "data structures"],
     "cluster": "foundations", "prerequisites": ["python_basics"]},
    {"id": "git_github", "name": "Git & GitHub",
     "aliases": ["git", "version control", "github"],
     "cluster": "foundations", "prerequisites": []},
    {"id": "command_line", "name": "Command Line & Linux",
     "aliases": ["bash", "unix", "terminal", "linux"],
     "cluster": "foundations", "prerequisites": []},
    {"id": "database_fundamentals", "name": "Database Fundamentals",
     "aliases": ["databases", "relational databases", "rdbms"],
     "cluster": "foundations", "prerequisites": ["python_basics"]},
    {"id": "sql_basics", "name": "SQL Basics",
     "aliases": ["sql", "structured query language", "sql queries", "basic sql"],
     "cluster": "foundations", "prerequisites": ["database_fundamentals"]},

    # ---- ml_engineer -----------------------------------------------------
    {"id": "linear_algebra", "name": "Linear Algebra",
     "aliases": ["vectors", "matrices", "linear algebra basics"],
     "cluster": "ml_engineer", "prerequisites": []},
    {"id": "probability_statistics", "name": "Probability & Statistics",
     "aliases": ["statistics", "probability", "statistical inference", "inference"],
     "cluster": "ml_engineer", "prerequisites": []},
    {"id": "calculus", "name": "Calculus",
     "aliases": ["differential calculus", "derivatives", "multivariable calculus"],
     "cluster": "ml_engineer", "prerequisites": []},
    {"id": "python_ml_tooling", "name": "Python for Data (NumPy/Pandas)",
     "aliases": ["numpy", "pandas", "scientific python", "data analysis with python"],
     "cluster": "ml_engineer", "prerequisites": ["python_basics"]},
    {"id": "data_visualization", "name": "Data Visualization",
     "aliases": ["matplotlib", "seaborn", "plotting", "data viz"],
     "cluster": "ml_engineer", "prerequisites": ["python_ml_tooling"]},
    {"id": "ml_fundamentals", "name": "Machine Learning Fundamentals",
     "aliases": ["machine learning", "ml basics", "ml concepts"],
     "cluster": "ml_engineer",
     "prerequisites": ["python_ml_tooling", "linear_algebra", "probability_statistics"]},
    {"id": "supervised_learning", "name": "Supervised Learning",
     "aliases": ["regression", "classification", "scikit-learn", "model fitting"],
     "cluster": "ml_engineer", "prerequisites": ["ml_fundamentals"]},
    {"id": "model_evaluation", "name": "Model Evaluation & Validation",
     "aliases": ["cross validation", "metrics", "model validation", "precision recall"],
     "cluster": "ml_engineer",
     "prerequisites": ["supervised_learning", "probability_statistics"]},
    {"id": "feature_engineering", "name": "Feature Engineering",
     "aliases": ["feature extraction", "data preprocessing", "feature selection"],
     "cluster": "ml_engineer",
     "prerequisites": ["python_ml_tooling", "data_visualization"]},
    {"id": "deep_learning", "name": "Deep Learning Concepts",
     "aliases": ["deep learning", "neural network theory", "backpropagation", "neural networks"],
     "cluster": "ml_engineer", "prerequisites": ["supervised_learning", "calculus"]},
    {"id": "neural_networks", "name": "Neural Network Libraries",
     "aliases": ["pytorch", "tensorflow", "keras", "cnn", "transformers"],
     "cluster": "ml_engineer",
     "prerequisites": ["deep_learning", "python_ml_tooling"]},
    {"id": "computer_vision", "name": "Computer Vision",
     "aliases": ["cv", "image processing", "object detection"],
     "cluster": "ml_engineer", "prerequisites": ["neural_networks"]},
    {"id": "nlp", "name": "Natural Language Processing",
     "aliases": ["text mining", "nlp", "language models"],
     "cluster": "ml_engineer", "prerequisites": ["neural_networks"]},
    {"id": "docker", "name": "Docker & Containers",
     "aliases": ["containers", "containerization", "docker compose"],
     "cluster": "ml_engineer", "prerequisites": ["command_line"]},
    {"id": "kubernetes", "name": "Kubernetes",
     "aliases": ["k8s", "container orchestration", "helm"],
     "cluster": "ml_engineer", "prerequisites": ["docker"]},
    {"id": "cloud_platforms", "name": "Cloud Platforms (AWS/GCP/Azure)",
     "aliases": ["aws", "gcp", "azure", "cloud computing", "ec2"],
     "cluster": "ml_engineer", "prerequisites": ["command_line"]},
    {"id": "mlops", "name": "MLOps",
     "aliases": ["ml pipeline", "model serving", "ml ci/cd", "model registry"],
     "cluster": "ml_engineer",
     "prerequisites": ["model_evaluation", "docker", "git_github"]},
    {"id": "ml_pipelines", "name": "ML Pipeline Orchestration",
     "aliases": ["airflow", "pipeline automation", "mlflow"],
     "cluster": "ml_engineer", "prerequisites": ["mlops", "python_ml_tooling"]},
    {"id": "big_data_tools", "name": "Big Data Tools",
     "aliases": ["spark", "hadoop", "distributed computing"],
     "cluster": "ml_engineer",
     "prerequisites": ["database_fundamentals", "python_ml_tooling"]},
    {"id": "model_deployment", "name": "Model Serving & Deployment",
     "aliases": ["model serving", "rest api for ml", "model api"],
     "cluster": "ml_engineer", "prerequisites": ["mlops", "rest_api_design"]},

    # ---- data_analyst ----------------------------------------------------
    {"id": "excel_analytics", "name": "Excel & Spreadsheets",
     "aliases": ["excel", "spreadsheets", "google sheets"],
     "cluster": "data_analyst", "prerequisites": []},
    {"id": "data_wrangling", "name": "Data Wrangling & Cleaning",
     "aliases": ["data cleaning", "data munging", "tidy data"],
     "cluster": "data_analyst",
     "prerequisites": ["python_ml_tooling", "sql_basics"]},
    {"id": "statistical_analysis", "name": "Statistical Analysis",
     "aliases": ["hypothesis testing", "regression analysis", "inferential statistics"],
     "cluster": "data_analyst",
     "prerequisites": ["probability_statistics", "python_ml_tooling"]},
    {"id": "exploratory_data_analysis", "name": "Exploratory Data Analysis",
     "aliases": ["eda", "data exploration", "exploratory analysis"],
     "cluster": "data_analyst",
     "prerequisites": ["data_wrangling", "data_visualization"]},
    {"id": "sql_advanced", "name": "Advanced SQL",
     "aliases": ["window functions", "query optimization", "advanced sql"],
     "cluster": "data_analyst", "prerequisites": ["sql_basics"]},
    {"id": "business_intelligence", "name": "Business Intelligence",
     "aliases": ["bi", "reporting", "kpi dashboards"],
     "cluster": "data_analyst",
     "prerequisites": ["sql_advanced", "data_visualization"]},
    {"id": "data_storytelling", "name": "Data Storytelling",
     "aliases": ["narrative", "data presentations", "dashboards for executives", "presentations"],
     "cluster": "data_analyst",
     "prerequisites": ["exploratory_data_analysis", "business_intelligence"]},
    {"id": "ab_testing", "name": "A/B Testing & Experimentation",
     "aliases": ["experiment design", "controlled trials", "conversion testing", "ab testing", "a/b testing"],
     "cluster": "data_analyst", "prerequisites": ["statistical_analysis"]},
    {"id": "dashboard_tools", "name": "Dashboard Tools",
     "aliases": ["tableau", "power bi", "looker"],
     "cluster": "data_analyst", "prerequisites": ["business_intelligence"]},

    # ---- backend ---------------------------------------------------------
    {"id": "http_apis", "name": "HTTP & APIs",
     "aliases": ["http", "json", "rest fundamentals", "api basics"],
     "cluster": "backend", "prerequisites": ["python_basics", "command_line"]},
    {"id": "apis_consumption", "name": "Consuming APIs",
     "aliases": ["requests", "api integration", "api clients"],
     "cluster": "backend", "prerequisites": ["http_apis"]},
    {"id": "rest_api_design", "name": "REST API Design",
     "aliases": ["rest", "api design", "endpoints", "openapi"],
     "cluster": "backend", "prerequisites": ["http_apis"]},
    {"id": "web_frameworks", "name": "Web Frameworks",
     "aliases": ["fastapi", "flask", "django", "node express"],
     "cluster": "backend", "prerequisites": ["rest_api_design"]},
    {"id": "authentication", "name": "Auth & Security",
     "aliases": ["oauth", "jwt", "security", "api keys"],
     "cluster": "backend",
     "prerequisites": ["web_frameworks", "database_fundamentals"]},
    {"id": "caching", "name": "Caching & Performance",
     "aliases": ["redis", "caching", "performance tuning"],
     "cluster": "backend", "prerequisites": ["web_frameworks"]},
    {"id": "message_queues", "name": "Message Queues",
     "aliases": ["kafka", "rabbitmq", "event streaming"],
     "cluster": "backend", "prerequisites": ["web_frameworks", "docker"]},
    {"id": "testing_backend", "name": "Backend Testing",
     "aliases": ["pytest", "unit testing", "integration tests", "tdd"],
     "cluster": "backend", "prerequisites": ["web_frameworks"]},
    {"id": "microservices", "name": "Microservices",
     "aliases": ["service architecture", "distributed systems", "soa"],
     "cluster": "backend", "prerequisites": ["rest_api_design", "message_queues"]},
    {"id": "serverless", "name": "Serverless",
     "aliases": ["lambda", "cloud functions", "serverless architecture"],
     "cluster": "backend", "prerequisites": ["cloud_platforms", "rest_api_design"]},
    {"id": "backend_deployment", "name": "Backend Deployment",
     "aliases": ["ci/cd", "devops", "deployment pipelines"],
     "cluster": "backend",
     "prerequisites": ["docker", "cloud_platforms", "web_frameworks"]},

    # ---- frontend --------------------------------------------------------
    {"id": "html_css", "name": "HTML & CSS",
     "aliases": ["html", "css", "markup", "styling"],
     "cluster": "frontend", "prerequisites": []},
    {"id": "javascript", "name": "JavaScript",
     "aliases": ["js", "es6", "ecmascript"],
     "cluster": "frontend", "prerequisites": ["html_css"]},
    {"id": "dom_manipulation", "name": "DOM & Browser APIs",
     "aliases": ["dom", "browser apis", "events", "fetch api"],
     "cluster": "frontend", "prerequisites": ["javascript"]},
    {"id": "typescript", "name": "TypeScript",
     "aliases": ["ts", "typed javascript", "typescript basics"],
     "cluster": "frontend", "prerequisites": ["javascript"]},
    {"id": "modern_js_frameworks", "name": "Modern Frontend Frameworks",
     "aliases": ["react", "vue", "svelte", "component frameworks"],
     "cluster": "frontend", "prerequisites": ["dom_manipulation", "typescript"]},
    {"id": "css_frameworks", "name": "CSS Frameworks",
     "aliases": ["tailwind", "bootstrap", "utility css"],
     "cluster": "frontend", "prerequisites": ["html_css"]},
    {"id": "responsive_design", "name": "Responsive Design",
     "aliases": ["mobile web", "media queries", "mobile-first"],
     "cluster": "frontend",
     "prerequisites": ["html_css", "css_frameworks"]},
    {"id": "api_integration_frontend", "name": "API Integration in the Browser",
     "aliases": ["axios", "xhr", "fetch", "api consumption"],
     "cluster": "frontend", "prerequisites": ["dom_manipulation", "apis_consumption"]},
    {"id": "state_management", "name": "State Management",
     "aliases": ["redux", "context api", "zustand", "state libraries"],
     "cluster": "frontend", "prerequisites": ["modern_js_frameworks"]},
    {"id": "frontend_testing", "name": "Frontend Testing",
     "aliases": ["jest", "cypress", "component testing"],
     "cluster": "frontend", "prerequisites": ["modern_js_frameworks"]},
    {"id": "build_tools", "name": "Build Tools & Bundlers",
     "aliases": ["webpack", "vite", "npm", "module bundlers"],
     "cluster": "frontend",
     "prerequisites": ["modern_js_frameworks", "command_line"]},
    {"id": "frontend_performance", "name": "Frontend Performance",
     "aliases": ["lazy loading", "web vitals", "performance optimization"],
     "cluster": "frontend",
     "prerequisites": ["build_tools", "frontend_testing"]},
]

# --------------------------------------------------------------------------
# 2. COURSES  (curated; raw skill_tags are normalised by normalize_tags.py)
# --------------------------------------------------------------------------

COURSE_BLUEPRINTS = [
    # skill_id, title, provider, url, level, rating, hours, [raw tags]
    ("programming_basics", "Introduction to Programming", "freeCodeCamp", "https://www.freecodecamp.org/learn", "beginner", 4.6, 60,
     ["intro to programming", "programming basics", "coding basics"]),
    ("python_basics", "Python for Everybody", "Coursera", "https://www.py4e.com", "beginner", 4.8, 60,
     ["python", "python basics", "programming"]),
    ("python_basics", "Automate the Boring Stuff with Python", "Udemy", "https://www.udemy.com", "beginner", 4.7, 40,
     ["python3", "python", "automation"]),
    ("data_structures", "Data Structures and Algorithms", "edX", "https://www.edx.org", "intermediate", 4.5, 80,
     ["dsa", "algorithms", "data structures"]),
    ("git_github", "Version Control with Git", "freeCodeCamp", "https://www.freecodecamp.org", "beginner", 4.6, 20,
     ["git", "github", "version control"]),
    ("command_line", "The Linux Command Line", "edX", "https://www.edx.org", "beginner", 4.4, 30,
     ["linux", "bash", "terminal"]),
    ("database_fundamentals", "Database Design and Modelling", "Coursera", "https://www.coursera.org", "intermediate", 4.5, 35,
     ["databases", "rdbms", "sql basics"]),
    ("sql_basics", "SQL for Data Science", "Coursera", "https://www.coursera.org", "beginner", 4.7, 25,
     ["sql", "structured query language", "queries"]),
    ("linear_algebra", "Linear Algebra for Machine Learning", "YouTube", "https://www.deeplearning.ai", "intermediate", 4.7, 18,
     ["linear algebra", "matrices", "vectors"]),
    ("probability_statistics", "Statistics Fundamentals", "Khan Academy", "https://www.khanacademy.org", "beginner", 4.8, 30,
     ["statistics", "probability", "inference"]),
    ("calculus", "Calculus Made Easy", "YouTube", "https://www.youtube.com", "intermediate", 4.3, 20,
     ["calculus", "derivatives"]),
    ("python_ml_tooling", "NumPy and Pandas for Data Analysis", "Datacamp", "https://www.datacamp.com", "intermediate", 4.6, 25,
     ["numpy", "pandas", "scientific python"]),
    ("data_visualization", "Data Visualization with Matplotlib and Seaborn", "Datacamp", "https://www.datacamp.com", "intermediate", 4.4, 20,
     ["matplotlib", "seaborn", "data viz"]),
    ("ml_fundamentals", "Machine Learning Specialization", "DeepLearning.AI", "https://www.deeplearning.ai", "beginner", 4.9, 60,
     ["machine learning", "ml basics", "supervised learning"]),
    ("supervised_learning", "Applied Machine Learning with scikit-learn", "edX", "https://www.edx.org", "intermediate", 4.6, 40,
     ["scikit-learn", "regression", "classification"]),
    ("model_evaluation", "Machine Learning Model Evaluation", "Coursera", "https://www.coursera.org", "intermediate", 4.5, 15,
     ["cross validation", "model validation", "metrics"]),
    ("feature_engineering", "Feature Engineering for Machine Learning", "Kaggle Learn", "https://www.kaggle.com/learn", "intermediate", 4.5, 12,
     ["feature engineering", "data preprocessing"]),
    ("deep_learning", "Neural Networks and Deep Learning", "DeepLearning.AI", "https://www.deeplearning.ai", "intermediate", 4.9, 30,
     ["deep learning", "neural networks", "backpropagation"]),
    ("neural_networks", "PyTorch for Deep Learning", "YouTube", "https://www.youtube.com", "intermediate", 4.7, 25,
     ["pytorch", "tensorflow", "keras"]),
    ("computer_vision", "Deep Learning for Computer Vision", "Coursera", "https://www.coursera.org", "advanced", 4.7, 35,
     ["computer vision", "cnn", "object detection"]),
    ("nlp", "Natural Language Processing with Deep Learning", "edX", "https://www.edx.org", "advanced", 4.8, 40,
     ["nlp", "text mining", "language models"]),
    ("docker", "Docker and Kubernetes: The Complete Guide", "Udemy", "https://www.udemy.com", "intermediate", 4.6, 27,
     ["docker", "containers", "kubernetes"]),
    ("kubernetes", "Kubernetes for Developers", "Coursera", "https://www.coursera.org", "advanced", 4.4, 22,
     ["k8s", "container orchestration"]),
    ("cloud_platforms", "AWS Fundamentals Specialization", "Coursera", "https://www.coursera.org", "beginner", 4.6, 34,
     ["aws", "cloud computing", "ec2"]),
    ("mlops", "Machine Learning Engineering for Production", "DeepLearning.AI", "https://www.deeplearning.ai", "intermediate", 4.7, 38,
     ["mlops", "ml pipeline", "model serving"]),
    ("ml_pipelines", "Data Pipelines with Airflow", "Datacamp", "https://www.datacamp.com", "intermediate", 4.4, 16,
     ["airflow", "pipeline automation"]),
    ("big_data_tools", "Apache Spark Essentials", "Datacamp", "https://www.datacamp.com", "intermediate", 4.5, 21,
     ["spark", "distributed computing"]),
    ("model_deployment", "Deploying Machine Learning Models", "Pluralsight", "https://www.pluralsight.com", "advanced", 4.3, 18,
     ["model serving", "model api", "rest api"]),
    ("excel_analytics", "Excel Skills for Business", "Coursera", "https://www.coursera.org", "beginner", 4.8, 30,
     ["excel", "spreadsheets"]),
    ("data_wrangling", "Data Wrangling in Python", "DataCamp", "https://www.datacamp.com", "intermediate", 4.5, 20,
     ["data cleaning", "pandas", "data munging"]),
    ("statistical_analysis", "Statistical Inference for Data Science", "edX", "https://www.edx.org", "intermediate", 4.5, 28,
     ["hypothesis testing", "regression analysis", "statistics"]),
    ("exploratory_data_analysis", "Exploratory Data Analysis with Python", "Coursera", "https://www.coursera.org", "intermediate", 4.6, 24,
     ["eda", "data exploration", "data viz"]),
    ("sql_advanced", "Advanced SQL: Windows Functions and Optimisation", "Udemy", "https://www.udemy.com", "advanced", 4.5, 14,
     ["window functions", "advanced sql", "query optimization"]),
    ("business_intelligence", "Business Intelligence and Dashboards", "Coursera", "https://www.coursera.org", "intermediate", 4.4, 26,
     ["bi", "reporting", "kpi dashboards"]),
    ("data_storytelling", "Data Storytelling", "LinkedIn Learning", "https://www.linkedin.com/learning", "beginner", 4.5, 8,
     ["data storytelling", "narrative", "presentations"]),
    ("ab_testing", "A/B Testing and Experimentation", "edX", "https://www.edx.org", "intermediate", 4.4, 12,
     ["a/b testing", "experiment design", "hypothesis tests"]),
    ("dashboard_tools", "Tableau Data Visualisation", "Pluralsight", "https://www.pluralsight.com", "intermediate", 4.3, 20,
     ["tableau", "power bi", "looker"]),
    ("http_apis", "HTTP Fundamentals", "freeCodeCamp", "https://www.freecodecamp.org/learn", "beginner", 4.4, 10,
     ["http", "json", "api basics"]),
    ("apis_consumption", "Consuming REST APIs Hands-On", "Udemy", "https://www.udemy.com", "beginner", 4.3, 10,
     ["requests", "api integration", "rest"]),
    ("rest_api_design", "REST API Design Best Practices", "Coursera", "https://www.coursera.org", "intermediate", 4.4, 14,
     ["rest", "api design", "openapi"]),
    ("web_frameworks", "FastAPI Web Development", "Udemy", "https://www.udemy.com", "intermediate", 4.6, 22,
     ["fastapi", "flask", "django"]),
    ("authentication", "Web Security and Authentication", "edX", "https://www.edx.org", "intermediate", 4.3, 18,
     ["oauth", "jwt", "security"]),
    ("caching", "Redis and Caching Patterns", "Udemy", "https://www.udemy.com", "intermediate", 4.4, 15,
     ["redis", "caching", "performance"]),
    ("message_queues", "Kafka Streams in Practice", "Coursera", "https://www.coursera.org", "advanced", 4.3, 20,
     ["kafka", "message queues", "event streaming"]),
    ("testing_backend", "Test-Driven Development with Python", "edX", "https://www.edx.org", "intermediate", 4.5, 16,
     ["pytest", "unit testing", "tdd"]),
    ("microservices", "Microservices Architecture", "Pluralsight", "https://www.pluralsight.com", "advanced", 4.2, 24,
     ["microservices", "distributed systems"]),
    ("serverless", "Serverless with AWS Lambda", "edX", "https://www.edx.org", "intermediate", 4.3, 14,
     ["lambda", "serverless", "cloud functions"]),
    ("backend_deployment", "CI/CD with GitHub Actions", "freeCodeCamp", "https://www.freecodecamp.org", "intermediate", 4.5, 12,
     ["ci/cd", "devops", "deployment"]),
    ("html_css", "Responsive Web Design", "freeCodeCamp", "https://www.freecodecamp.org/learn", "beginner", 4.8, 300,
     ["html", "css", "responsive design"]),
    ("javascript", "JavaScript Algorithms and Data Structures", "freeCodeCamp", "https://www.freecodecamp.org/learn", "beginner", 4.8, 300,
     ["javascript", "es6", "js"]),
    ("dom_manipulation", "Modern JavaScript and the DOM", "Udemy", "https://www.udemy.com", "intermediate", 4.5, 18,
     ["dom", "browser apis", "events"]),
    ("typescript", "TypeScript Essentials", "Pluralsight", "https://www.pluralsight.com", "intermediate", 4.4, 12,
     ["typescript", "typed javascript"]),
    ("modern_js_frameworks", "React and Modern Frontend Frameworks", "Coursera", "https://www.coursera.org", "intermediate", 4.7, 40,
     ["react", "vue", "component frameworks"]),
    ("css_frameworks", "Tailwind CSS and Bootstrap", "YouTube", "https://www.youtube.com", "beginner", 4.4, 10,
     ["tailwind", "bootstrap", "css"]),
    ("responsive_design", "Mobile-First Responsive Design", "freeCodeCamp", "https://www.freecodecamp.org", "beginner", 4.5, 20,
     ["responsive design", "media queries", "mobile web"]),
    ("api_integration_frontend", "Fetching Data in the Browser", "Udemy", "https://www.udemy.com", "intermediate", 4.3, 10,
     ["fetch", "axios", "api consumption"]),
    ("state_management", "State Management with Redux and Context", "Coursera", "https://www.coursera.org", "intermediate", 4.5, 14,
     ["redux", "state management", "context api"]),
    ("frontend_testing", "Test Frontend Apps with Jest and Cypress", "Udemy", "https://www.udemy.com", "intermediate", 4.4, 13,
     ["jest", "cypress", "component testing"]),
    ("build_tools", "Webpack and Vite Build Tooling", "freeCodeCamp", "https://www.freecodecamp.org", "intermediate", 4.3, 12,
     ["webpack", "vite", "npm"]),
    ("frontend_performance", "Web Performance and Core Web Vitals", "Coursera", "https://www.coursera.org", "advanced", 4.4, 12,
     ["web vitals", "lazy loading", "performance"]),
]

# --------------------------------------------------------------------------
# 3. JOB DESCRIPTIONS  (templated text that mentions skills by name/alias)
# --------------------------------------------------------------------------

JD_TEMPLATES = {
    "ml_engineer": {
        "titles": ["Machine Learning Engineer", "ML Engineer", "Machine Learning Engineer II"],
        "lead": ("We are hiring a {title} to build and ship ML systems end to end. "
                 "You will work with product teams to turn business questions into models."),
        "skills": ["python_basics", "linear_algebra", "probability_statistics", "ml_fundamentals",
                   "supervised_learning", "deep_learning", "neural_networks", "model_evaluation",
                   "feature_engineering", "docker", "mlops", "cloud_platforms", "git_github", "data_structures"],
        "mid": ("Day to day you will write production code in {python_basics}, train and validate "
                "models with {supervised_learning} and {model_evaluation}, and ship them with "
                "{docker} and {mlops}. Working knowledge of {deep_learning} and at least one "
                "deep learning framework such as PyTorch or TensorFlow is expected."),
        "tail": ("We value clean {git} history, {cloud_platforms} experience, and a solid grip on "
                 "{linear_algebra} and {probability_statistics}."),
    },
    "data_analyst": {
        "titles": ["Data Analyst", "Business Data Analyst", "Senior Data Analyst"],
        "lead": ("We are hiring a {title} to turn raw data into decisions. "
                 "You will own analyses from data extraction to the final slide."),
        "skills": ["sql_basics", "sql_advanced", "excel_analytics", "data_wrangling", "python_ml_tooling",
                   "statistical_analysis", "exploratory_data_analysis", "data_visualization",
                   "business_intelligence", "dashboard_tools", "ab_testing", "data_storytelling"],
        "mid": ("You will query warehouses with {sql_basics} and {window functions}, clean and shape "
                "data in {pandas}, and build dashboards in {tableau}. Hypothesis tests and "
                "{ab_testing} design are part of the role."),
        "tail": ("Strong {data_visualization} and {data_storytelling} skills are essential; you will "
                 "present findings to non-technical stakeholders weekly."),
    },
    "backend": {
        "titles": ["Backend Engineer", "Backend Developer", "Software Engineer (Backend)"],
        "lead": ("We are hiring a {title} to design and maintain the services behind our platform. "
                 "You will own features from API contract to deployment."),
        "skills": ["python_basics", "http_apis", "rest_api_design", "web_frameworks", "database_fundamentals",
                   "sql_basics", "authentication", "caching", "testing_backend", "docker",
                   "message_queues", "cloud_platforms", "git_github"],
        "mid": ("You will build {rest_api_design} APIs on {fastapi}, model data in {sql}, and harden "
                "them with {authentication} and {caching}. {docker} and {cloud_platforms} are used "
                "for every deployment."),
        "tail": ("We expect {testing_backend} practice, clean {git} workflows, and comfort scaling "
                 "services with {message_queues}."),
    },
    "frontend": {
        "titles": ["Frontend Engineer", "Frontend Developer", "UI Engineer"],
        "lead": ("We are hiring a {title} to craft fast, accessible interfaces. "
                 "You will partner with designers and API teams to ship features."),
        "skills": ["html_css", "javascript", "typescript", "dom_manipulation", "modern_js_frameworks",
                   "css_frameworks", "responsive_design", "api_integration_frontend", "state_management",
                   "frontend_testing", "build_tools", "frontend_performance"],
        "mid": ("You will build components with {react} and {typescript}, style with {tailwind}, and "
                "wire them to APIs using {fetch}. Async UI, especially {api_integration_frontend}, "
                "is core to this role."),
        "tail": ("We care about {frontend_testing}, {build_tools}, and {frontend_performance}; "
                 "delightful and fast wins."),
    },
}

COMPANIES = ["Northwind Labs", "Helio Analytics", "Vantage ML", "Cloudline", "Pixelforge",
             "Quantia", "Rivendata", "LoopSystems", "Orbit Health", "Meridian Bank",
             "Atlas Retail", "Bloom Energy", "Sentry AI", "Cascade Robotics", "Nimbus Travel"]

LOCATIONS = ["Remote", "San Francisco, CA", "New York, NY", "Austin, TX", "London, UK",
             "Berlin, DE", "Bengaluru, IN", "Singapore, SG", "Toronto, CA", "Amsterdam, NL"]

SENIORITIES = ["Associate", "Mid-level", "Senior"]

# --------------------------------------------------------------------------
# 4. ITEM BANK
#    a) one glossary item per skill  (all answers are true definitions)
#    b) hand-authored scenario items for the demo-critical skills
# --------------------------------------------------------------------------

GLOSSARY = {
    "programming_basics": "Writing step-by-step instructions a computer can execute.",
    "python_basics": "A general-purpose programming language known for clean, readable syntax.",
    "data_structures": "Organising data in ways that make storage and retrieval efficient.",
    "git_github": "Tracking changes to code over time and collaborating through a hosted platform.",
    "command_line": "Driving a computer by typing text commands into a shell like Bash.",
    "database_fundamentals": "Designing relational stores of data organised into tables with keys.",
    "sql_basics": "Using a query language to read and manipulate data stored in relational databases.",
    "linear_algebra": "The maths of vectors, matrices, and their transformations.",
    "probability_statistics": "Quantifying uncertainty and drawing conclusions from data.",
    "calculus": "The maths of rates of change and accumulation used to train models.",
    "python_ml_tooling": "Using NumPy and Pandas to manipulate numeric and tabular data.",
    "data_visualization": "Turning numbers into charts and plots to reveal patterns.",
    "ml_fundamentals": "Teaching computers to find patterns from examples instead of rules.",
    "supervised_learning": "Training models on labelled examples to predict outcomes for new data.",
    "model_evaluation": "Measuring how well a model generalises using hold-out data and metrics.",
    "feature_engineering": "Transforming raw data into the inputs that help models learn",
    "deep_learning": "Training multi-layer neural networks by backpropagating prediction errors.",
    "neural_networks": "Building and training deep models with libraries like PyTorch or TensorFlow.",
    "computer_vision": "Enabling machines to interpret images and video.",
    "nlp": "Enabling machines to understand and generate human language.",
    "docker": "Packaging an application and its dependencies into a portable container image.",
    "kubernetes": "Orchestrating and scaling containers reliably across a cluster.",
    "cloud_platforms": "Provisioning compute and storage on AWS, GCP, or Azure.",
    "mlops": "The discipline of deploying, monitoring, and retraining machine learning models.",
    "ml_pipelines": "Automating the steps that move data from raw source to trained model.",
    "big_data_tools": "Processing datasets too large for a single machine using Spark and friends.",
    "model_deployment": "Exposing a trained model behind an API so applications can call it.",
    "excel_analytics": "Analysing small-to-medium datasets with spreadsheets and formulas.",
    "data_wrangling": "Cleaning and reshaping messy raw data into analysis-ready tables.",
    "statistical_analysis": "Using hypothesis tests and regression to make data-driven decisions.",
    "exploratory_data_analysis": "Profiling data with summary stats and plots before formal modelling.",
    "sql_advanced": "Writing window functions and optimising slow queries at scale.",
    "business_intelligence": "Building the dashboards and reports that run a business day-to-day.",
    "data_storytelling": "Turning analysis into a clear narrative an audience can act on.",
    "ab_testing": "Running controlled experiments to decide which version wins.",
    "dashboard_tools": "Authoring interactive dashboards with Tableau, Power BI, or Looker.",
    "http_apis": "Exchanging data between clients and servers over HTTP with JSON.",
    "apis_consumption": "Calling other services' endpoints from your own code.",
    "rest_api_design": "Designing consistent, predictable HTTP endpoints and resources.",
    "web_frameworks": "Building backend applications quickly with FastAPI, Flask, or Django.",
    "authentication": "Verifying who a user is and protecting endpoints and data from abuse.",
    "caching": "Storing frequently-read data in memory (Redis) to cut response times.",
    "message_queues": "Moving work between services asynchronously via Kafka or RabbitMQ.",
    "testing_backend": "Automating unit and integration tests to keep backends safe.",
    "microservices": "Splitting a system into small services that own one responsibility each.",
    "serverless": "Running functions on demand, paying only when they're invoked.",
    "backend_deployment": "Shipping backend changes to production through CI/CD pipelines.",
    "html_css": "Structuring pages with HTML and styling them with CSS.",
    "javascript": "The scripting language that makes web pages interactive.",
    "dom_manipulation": "Reading and updating the page tree the browser renders.",
    "typescript": "JavaScript with static types for larger codebases.",
    "modern_js_frameworks": "Building componentised UIs with React, Vue, or Svelte.",
    "css_frameworks": "Using Tailwind or Bootstrap for consistent styling fast.",
    "responsive_design": "Making layouts adapt to phones, tablets, and desktops.",
    "api_integration_frontend": "Calling backend endpoints directly from browser code.",
    "state_management": "Tracking shared UI state so components stay in sync.",
    "frontend_testing": "Automating UI checks with Jest, Cypress, or similar.",
    "build_tools": "Bundling and optimising frontend assets with Vite or Webpack.",
    "frontend_performance": "Making pages load and respond quickly for real users.",
}

# Hand-authored scenario items: list of (skill_id, question, options, correct_index)
SCENARIO_ITEMS = [
    ("python_basics", "Which data structure is immutable in Python?",
     ["List", "Dictionary", "Set", "Tuple"], 3),
    ("python_basics", "What keyword does Python use to define a function?",
     ["func", "def", "function", "lambda"], 1),
    ("sql_basics", "Which clause filters rows BEFORE grouping?",
     ["WHERE", "HAVING", "GROUP BY", "ORDER BY"], 0),
    ("sql_basics", "Which SQL statement reads data from a table?",
     ["READ", "SELECT", "FETCH", "OPEN"], 1),
    ("git_github", "Which command saves your changes to the local repository?",
     ["git push", "git commit", "git add", "git clone"], 1),
    ("git_github", "What does 'git pull' do?",
     ["Uploads local commits", "Fetches and merges remote changes",
      "Deletes the remote branch", "Shows the diff of the last commit"], 1),
    ("ml_fundamentals", "Which term describes learning from unlabelled data?",
     ["Supervised learning", "Unsupervised learning", "Reinforcement learning", "Transfer learning"], 1),
    ("ml_fundamentals", "What is 'overfitting'?",
     ["The model memorises training data and fails on new data",
      "The model learns nothing from training",
      "The training data is too small to load",
      "The loss stays constant forever"], 0),
    ("supervised_learning", "Which problem is classification?",
     ["Predicting a house price", "Detecting whether an email is spam",
      "Estimating revenue next quarter", "Forecasting temperature"], 1),
    ("model_evaluation", "Which metric suits a heavily imbalanced binary classifier?",
     ["Accuracy", "F1-score", "Mean squared error", "Perplexity"], 1),
    ("docker", "What does a Docker container primarily provide?",
     ["An isolated environment with the app and its dependencies",
      "A hosted git repository",
      "A SQL database engine",
      "A JavaScript runtime"], 0),
    ("web_frameworks", "Which of these is a Python web framework?",
     ["React", "FastAPI", "Node", "Angular"], 1),
    ("javascript", "Which keyword declares a block-scoped variable in modern JavaScript?",
     ["var", "let", "int", "constrain"], 1),
    ("probability_statistics", "What does a p-value below 0.05 typically suggest?",
     ["The result is unlikely under the null hypothesis",
      "The sample size is too large",
      "The experiment is definitely correct",
      "The data has no variance"], 0),
    ("data_wrangling", "Which Pandas operation joins two dataframes on a key column?",
     ["merge", "broadcast", "transpose", "apply"], 0),
    ("linear_algebra", "Which mathematics deals with vectors and matrices?",
     ["Calculus", "Linear algebra", "Number theory", "Trigonometry"], 1),
    ("neural_networks", "Which structure is typical of a deep neural network?",
     ["Many layers between input and output", "A single lookup table",
      "An array sorted at load time", "A JSON tree of endpoints"], 0),
    ("mlops", "Which task belongs to MLOps?",
     ["Training a model and shipping it to production safely",
      "Writing SQL views",
      "Designing a landing page",
      "Configuring a load balancer DNS record"], 0),
    ("command_line", "Which command lists files in the current directory?",
     ["ls", "cd", "mkdir", "pwd"], 0),
    ("rest_api_design", "Which HTTP method is conventionally used to update a resource?",
     ["GET", "PUT", "POST", "DELETE"], 1),
]


def normalize_text(text):
    return " ".join(text.lower().split())


def build_skills():
    ids = [s["id"] for s in SKILLS]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate skill ids in SKILLS")
    by_id = {s["id"]: s for s in SKILLS}
    for s in SKILLS:
        for prereq in s["prerequisites"]:
            if prereq not in by_id:
                raise ValueError(f"Skill '{s['id']}' has unknown prerequisite '{prereq}'")

    # Acyclic check -- Kahn's algorithm
    indegree = {s["id"]: 0 for s in SKILLS}
    adjacency = defaultdict(list)
    for s in SKILLS:
        for prereq in s["prerequisites"]:
            adjacency[prereq].append(s["id"])
            indegree[s["id"]] += 1
    ready = deque([n for n, d in indegree.items() if d == 0])
    visited = 0
    while ready:
        node = ready.popleft()
        visited += 1
        for nxt in adjacency[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
    if visited != len(SKILLS):
        raise ValueError("skills.json would contain a cycle -- fix prerequisites before shipping")
    return SKILLS


def build_courses():
    courses = []
    for idx, (skill_id, title, provider, url, level, rating, hours, tags) in enumerate(COURSE_BLUEPRINTS, start=1):
        courses.append({
            "id": f"course_{idx:03d}",
            "title": title,
            "provider": provider,
            "url": url,
            "description": f"{title} -- a {level}-level resource tagged for {skill_id}.",
            "level": level,
            "rating": rating,
            "duration_hours": hours,
            "skill_tags": tags,
        })
    return courses


def _alias_lookup():
    lookup = {}
    for s in SKILLS:
        lookup[s["id"]] = s
    return lookup


def build_jds(rng, count=55):
    by_id = {s["id"]: s for s in SKILLS}
    jds = []
    role_cycle = ["ml_engineer", "data_analyst", "backend", "frontend"]
    used = set()
    skill_pool = {role: templates["skills"] for role, templates in JD_TEMPLATES.items()}

    idx = 0
    while len(jds) < count:
        role = role_cycle[idx % len(role_cycle)]
        tpl = JD_TEMPLATES[role]
        # keep each role well represented by repeating the cycle a few times
        title = tpl["titles"][rng.randrange(len(tpl["titles"]))]
        company = rng.choice(COMPANIES)
        key = (company, title)
        if key in used:
            idx += 1
            continue
        used.add(key)
        idx += 1

        # pick 8-13 of the role's skills (order shuffled so demand varies)
        skills = rng.sample(tpl["skills"], rng.randint(8, len(tpl["skills"])))
        skill_ids = list(skills)

        # slightly perturb ids/aliases used inside the free text
        def mention(sid):
            s = by_id[sid]
            return rng.choice([s["name"]] + s["aliases"])

        # templates may reference a skill by id OR any of its aliases
        tokens = {"title": title}
        for s in SKILLS:
            tokens.setdefault(s["id"], mention(s["id"]))
            for alias in s["aliases"]:
                tokens.setdefault(alias, s["name"])

        lead = tpl["lead"].format(**tokens)
        mid = tpl["mid"].format(**tokens)
        tail = tpl["tail"].format(**tokens)
        description = "\n".join([lead.strip(), mid.strip(), tail.strip()])

        jds.append({
            "id": f"jd_{len(jds) + 1:03d}",
            "title": title,
            "company": company,
            "role_family": role,
            "location": rng.choice(LOCATIONS),
            "seniority": rng.choice(SENIORITIES),
            "description": description,
            "skills": skill_ids,
        })
    return jds


def build_items(rng):
    by_id = {s["id"]: s for s in SKILLS}
    items = []
    n = 0

    def emit(skill_id, text, options, difficulty):
        nonlocal n
        n += 1
        return {"id": f"item_{n:03d}",
                "skill_id": skill_id,
                "cluster": by_id[skill_id]["cluster"],
                "text": text,
                "options": options,
                "correct_index": 0,
                "difficulty": difficulty}

    # Glossary items -- correct option always first; distractors sampled from
    # other clusters so options never accidentally describe the same skill.
    glossary_ids = list(GLOSSARY.keys())
    for skill_id in glossary_ids:
        target_line = GLOSSARY[skill_id]
        pool = [oid for oid in glossary_ids if oid != skill_id and by_id[oid]["cluster"] != by_id[skill_id]["cluster"]]
        distractors = rng.sample(pool, 3)
        options = [target_line] + [GLOSSARY[oid] for oid in distractors]
        rng.shuffle(options)
        correct_index = options.index(target_line)
        item = emit(skill_id, f"Which statement best describes {by_id[skill_id]['name']}?",
                    options, "medium")
        item["correct_index"] = correct_index
        items.append(item)

    # Scenario items for demo-critical skills
    for skill_id, text, options, correct_index in SCENARIO_ITEMS:
        item = emit(skill_id, text, options, "medium")
        item["correct_index"] = correct_index
        items.append(item)

    for item in items:
        if not (0 <= item["correct_index"] < len(item["options"])):
            raise ValueError(f"bad correct_index on {item['id']}")
        if len(set(normalize_text(o) for o in item["options"])) != len(item["options"]):
            raise ValueError(f"duplicate/near-duplicate options on {item['id']}")
    return items


def write_json(path: Path, rows):
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate PathForge seed datasets")
    parser.add_argument("--out", default="data", help="output directory (default: data)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    parser.add_argument("--jds", type=int, default=55, help="number of job descriptions to generate")
    args = parser.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    skills = build_skills()
    courses = build_courses()
    jds = build_jds(rng, count=args.jds)
    items = build_items(rng)

    write_json(out / "skills.json", skills)
    write_json(out / "courses.json", courses)
    write_json(out / "jds.json", jds)
    write_json(out / "item_bank.json", items)

    counts = {"skills": len(skills), "courses": len(courses),
              "jds": len(jds), "item_bank": len(items)}
    total = sum(counts.values())
    print(f"Wrote {total} rows to {out}")
    for name, count in counts.items():
        print(f"  {name:10s} {count}")


if __name__ == "__main__":
    main()