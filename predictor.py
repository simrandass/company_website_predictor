# predictor.py
import os
import re
import time
import logging
from typing import Optional, Dict, List, Tuple, Union
from urllib.parse import urlparse
import requests
import numpy as np
import joblib
import tldextract

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ---------- Global configuration ----------
_SERPER_API_KEY = os.getenv('SERPER_API_KEY', None)
_MODEL_PATH = None
_predictor_cache = {}

def configure_predictor(serper_api_key: str = None, model_path: str = None):
    global _SERPER_API_KEY, _MODEL_PATH
    if serper_api_key:
        _SERPER_API_KEY = serper_api_key
    if model_path:
        _MODEL_PATH = model_path
    if _MODEL_PATH is None:
        raise ValueError("model_path is required. Call configure_predictor(model_path='...').")


def _get_predictor():
    if _MODEL_PATH is None:
        raise ValueError("MODEL_PATH not set. Call configure_predictor(model_path='...') first.")
    if _SERPER_API_KEY is None:
        raise ValueError("SERPER_API_KEY not set. Call configure_predictor(serper_api_key='...') or set environment variable.")
    key = (_MODEL_PATH, _SERPER_API_KEY)
    if key not in _predictor_cache:
        _predictor_cache[key] = DomainPredictor(_MODEL_PATH, _SERPER_API_KEY)
    return _predictor_cache[key]


class DomainPredictor:
    def __init__(self, model_path: str, serper_api_key: str):
        self.model = joblib.load(model_path)
        self.serper_api_key = serper_api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def _serper_search(self, query: str, num: int = 10) -> dict:
        params = {'api_key': self.serper_api_key, 'q': query, 'num': num}
        for attempt in range(5):
            try:
                resp = self.session.get('https://google.serper.dev/search', params=params, timeout=15)
                if resp.status_code == 429:
                    wait = (2 ** attempt) * 5
                    logger.warning(f"Rate limited. Waiting {wait}s")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except (requests.exceptions.RequestException, ValueError) as e:
                logger.warning(f"Serper attempt {attempt+1} failed: {e}")
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        return {}

    def _extract_domain(self, url: str) -> Optional[str]:
        if not url:
            return None
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain.rstrip('/') if domain else None

    def _is_valid_company_domain(self, domain: str) -> bool:
        if not domain:
            return False
        blacklist = ['linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
                     'youtube.com', 'wikipedia.org', 'glassdoor.com', 'indeed.com',
                     'crunchbase.com', 'bloomberg.com', 'reuters.com', 'static.licdn.com']
        domain_lower = domain.lower()
        for b in blacklist:
            if b in domain_lower:
                return False
        if '.' not in domain:
            return False
        valid_tlds = ['.com', '.org', '.net', '.io', '.co', '.uk', '.de', '.fr',
                      '.cn', '.jp', '.in', '.ai']
        return any(domain_lower.endswith(tld) for tld in valid_tlds)

    def prepare_features_for_result(self, company_name: str, result: Dict, position: int) -> Optional[List[float]]:
        try:
            link = result.get('link', '')
            domain = self._extract_domain(link)
            if not domain:
                return None

            pos = position + 1
            clean_name = re.sub(r'[^a-zA-Z0-9]', '', company_name.lower())
            clean_domain = re.sub(r'[^a-zA-Z0-9]', '', domain.lower())
            if clean_name and clean_domain:
                set1 = set(clean_name)
                set2 = set(clean_domain)
                similarity = len(set1 & set2) / len(set1 | set2) if (set1 | set2) else 0
            else:
                similarity = 0

            company_words = company_name.split()
            company_acronym = ''.join([w[0].lower() for w in company_words if w[0].isalpha()])
            domain_parts = domain.split('.')[0].split('-')
            domain_acronym = ''.join([p[0].lower() for p in domain_parts if p])
            acronym_match = 1 if company_acronym and domain_acronym and company_acronym == domain_acronym else 0

            social = ['linkedin', 'facebook', 'twitter', 'instagram', 'youtube', 'tiktok', 'snapchat']
            is_social = 1 if any(s in domain.lower() for s in social) else 0

            return [pos, similarity, acronym_match, is_social]
        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return None

    def predict_domain(self, company_name: str) -> Tuple[Optional[str], str]:
        try:
            search_results = self._serper_search(company_name, num=10).get('organic', [])
            if not search_results:
                return None, 'ML_NoResults'

            for idx in range(min(3, len(search_results))):
                result = search_results[idx]
                features = self.prepare_features_for_result(company_name, result, idx)
                if features is not None:
                    features_array = np.array(features).reshape(1, -1)
                    prediction = self.model.predict(features_array)[0]
                    if prediction == 1:
                        domain = self._extract_domain(result.get('link', ''))
                        if domain and self._is_valid_company_domain(domain):
                            return (domain, 'ML_Fallback')

            link = search_results[0].get('link', '')
            domain = self._extract_domain(link)
            if domain:
                return (domain, 'ML_FirstResult')
            return None, 'ML_NoValidDomain'
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return None, 'ML_Error'


# ---------- Exported function (ONLY domain returned) ----------
def predict_fallback_domain(company_name: str) -> Optional[str]:
    """
    Predict the official domain using the XGBoost model.
    Returns the predicted domain string, or None if prediction fails.
    """
    predictor = _get_predictor()
    domain, _ = predictor.predict_domain(company_name)
    return domain