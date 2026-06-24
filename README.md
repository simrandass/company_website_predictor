Corporate Domain Matching & Verification Pipeline
An end-to-end Machine Learning pipeline engineered to find official, canonical corporate homepages from raw company names using search engine metadata, cross-validated classification models, and custom feature engineering.

This system evaluates live search result candidates and utilizes a dual-model framework to cleanly filter out junk domains, social media profiles, and foreign copycats.

Model Benchmarking & Performance
Both models were rigorously tested using 5-Fold GroupKFold Cross-Validation over a manually labeled training set to ensure the system generalizes flawlessly across completely unseen company names.

Head-to-Head Scoreboard (Class 1 / Correct Links)
Overall Accuracy: Random Forest: 88.40% | XGBoost: 91.33%

Precision (Trustworthiness of choices): Random Forest: 80.00% | XGBoost: 83.03%

Recall (Ability to catch true sites): Random Forest: 86.00% | XGBoost: 92.21%

F1-Score (Balanced Harmonic Mean): Random Forest: 83.00% | XGBoost: 87.38%

Result: The pipeline natively defaults to the XGBoost Classifier due to its significant 6.21% jump in Recall and superior Precision control against False Positives.

Engineered Feature Architecture (5-Dimensional Vector)
For every company query, the top 3 search candidates are extracted and converted into a numerical matrix across 5 distinct feature dimensions:

search_position [Integer]: The rank position (1, 2, or 3) returned by the search engine.

clean_domain_similarity [Float]: Token-sort Levenshtein distance ratio between the raw company name and the extracted domain core string.

acronym_match [Binary]: Automatically strips legal corporate noise (Pvt, Ltd, LLP) to evaluate if the domain matches the initials of the enterprise.

is_socialmedia [Binary]: Flag indicating if the domain belongs to public scrapers or social hubs (like LinkedIn, Facebook, Instagram, Zaubacorp).

is_regional_tld [Binary]: New Feature. Uses tldextract to track regional extensions (like .in, .co.in, .net.in) to securely bias the model toward the primary domestic entity.

Tech Stack & Dependencies
Core Framework: Python 3.x, Jupyter Notebook

Machine Learning: XGBoost Classifier, Scikit-Learn (Random Forest, GroupKFold, Metrics Evaluation)

Text Processing: RapidFuzz (String Similarity Matrix calculations)

URL Parsing: Tldextract (Public Suffix List Extraction)

Data Pipelines: Pandas, NumPy, Joblib (Model Serialization)

Infrastructure: Requests, Serper (Google Search) API

Architecture & Implementation Layout
The repository contains standalone cells addressing different phases of the lifecycle:


