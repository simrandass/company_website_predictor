import os
import time
import requests
import pandas as pd
import tldextract
from rapidfuzz import fuzz

# ==========================================
# 1. SETUP AND FILE CONFIGURATION
# ==========================================
INPUT_FILE = "remaining_test.csv"
OUTPUT_FILE = "add_to_final.csv"

SERPER_API_KEY = "efa6cbe513613e548d0742a7e5cf6cab1ea82a01"
url = "https://google.serper.dev/search"

if not os.path.exists(INPUT_FILE):
    raise FileNotFoundError(f"❌ Cannot find '{INPUT_FILE}' in this folder.")

raw_sheet = pd.read_csv(INPUT_FILE)
raw_sheet.columns = raw_sheet.columns.str.strip().str.replace('', '', regex=False)

total_companies = len(raw_sheet)
print(f"✅ Found {INPUT_FILE} with {total_companies} companies.")
print("🚀 Starting Serper API extraction pipeline...")

all_extracted_rows = []
SOCIAL_DOMAINS = ["linkedin", "facebook", "instagram", "twitter", "youtube", "justdial", "zaubacorp", "indiamart"]

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def check_acronym_match(company_name, domain_str):
    name_str = str(company_name).strip().lower()
    dom_str = str(domain_str).strip().lower()
    
    for word in ["pvt", "ltd", "limited", "private", "inc", "corp", "co", "llp", "trust", "college", "hospital", "campus"]:
        name_str = name_str.replace(f" {word}", "")
        
    words = name_str.split()
    if len(words) < 2:  
        return 0
        
    FILLER_WORDS = ["of", "and", "in", "for", "the", "&"]
    clean_words = [w for w in words if w not in FILLER_WORDS]
    
    acronym = "".join([word[0] for word in clean_words if word]).lower()
    full_acronym = "".join([word[0] for word in words if word]).lower()
    
    if (acronym and acronym in dom_str) or (full_acronym and full_acronym in dom_str):
        return 1
        
    return 0

# ==========================================
# 3. CORE API & FEATURE EXTRACTION LOOP
# ==========================================
# 🔍 HERE IS THE MAIN LOOP iterating through all 250 companies!
for i, company_name in enumerate(raw_sheet["query_name"], 1):
    clean_company_query = str(company_name).strip().strip(",").strip(".").strip()
    
    if "kamajar port" in clean_company_query.lower():
        clean_company_query = "Kamarajar Port Limited"
        
    print(f"[{i}/{total_companies}] 🚀 Querying Google via Serper API for: {clean_company_query}")
    
    try:
        headers = {
            'X-API-KEY': SERPER_API_KEY,
            'Content-Type': 'application/json'
        }
        
        payload = {
            "q": clean_company_query.lower(),
            "num": 3
        }
        
        # ─── NESTED RETRY LOOP FOR NETWORK DROPS ───
        max_retries = 3
        response = None
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=10)
                break  # Connection successful! Break out of the retry loop
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as net_err:
                if attempt < max_retries - 1:
                    print(f"⚠️ Network glitch encountered ({net_err}). Retrying in 5 seconds... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(5)
                else:
                    raise net_err  # No retries left, pass it to the main crash protection block
            
        if response.status_code != 200:
            print(f"❌ API Error {response.status_code} for '{clean_company_query}'")
            time.sleep(5)
            continue
            
        json_data = response.json()
        
        # Fallback Matrix Extraction
        candidate_links = []
        organic_results = json_data.get("organic", [])
        for item in organic_results:
            if item.get("link"):
                candidate_links.append(item.get("link"))
                
        if len(candidate_links) < 3 and "knowledgeGraph" in json_data:
            kg_url = json_data["knowledgeGraph"].get("website")
            if kg_url and kg_url not in candidate_links:
                candidate_links.append(kg_url)
                
        if len(candidate_links) < 3 and organic_results:
            sitelinks = organic_results[0].get("sitelinks", [])
            for sl in sitelinks:
                if sl.get("link") and sl.get("link") not in candidate_links:
                    candidate_links.append(sl.get("link"))

        unique_candidates = list(dict.fromkeys(candidate_links))[:3]

        if not unique_candidates:
            print(f"⚠️ No usable URLs found anywhere in payload for: {clean_company_query}")
            continue

        for index, candidate_url in enumerate(unique_candidates):
            position = index + 1

            clean_domain = tldextract.extract(str(candidate_url)).domain
            similarity = fuzz.token_sort_ratio(clean_company_query.lower(), clean_domain.lower())
            acronym_match = check_acronym_match(clean_company_query, clean_domain)
            is_social = 1 if clean_domain in SOCIAL_DOMAINS else 0

            all_extracted_rows.append({
                "query_name": clean_company_query,
                "candidate_url": candidate_url,
                "search_position": position,            
                "clean_domain_similarity": similarity,  
                "acronym_match": acronym_match,         
                "is_socialmedia": is_social,            
                "is_correct": 0,                        
            })
            
        pd.DataFrame(all_extracted_rows).to_csv(OUTPUT_FILE, index=False)
        time.sleep(1)  

    except Exception as e:
        print(f"❌ Processing error for '{clean_company_query}': {e}")
        time.sleep(3)
        continue

print(f"\n🎉 Process finished! Core matrix successfully saved to '{OUTPUT_FILE}'.")