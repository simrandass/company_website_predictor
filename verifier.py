# verifier.py
import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# ==========================================
# 1. AUTHENTICATION & CLIENT INITIALIZATION
# ==========================================
# Google GenAI automatically looks for the GEMINI_API_KEY environment variable.
if not os.environ.get("GEMINI_API_KEY"):
    raise ValueError("CRITICAL: GEMINI_API_KEY environment variable is missing.")

client = genai.Client()

# ==========================================
# 2. DEFINING THE OUTPUT STRUCTURE CONTRACT
# ==========================================
class ValidationVerdict(BaseModel):
    is_correct: bool = Field(
        description="True if the candidate domain belongs to the target company. False otherwise."
    )
    confidence_score: float = Field(
        description="Confidence metrics ranking from 0.0 (completely unsure) to 1.0 (absolute certainty)."
    )
    reasoning: str = Field(
        description="Detailed logical analysis of findings, cross-references, or clues discovered during Google search."
    )
    verified_website: str = Field(
        description="The verified base domain name. If is_correct is False, provide the newly discovered official domain here."
    )

# ==========================================
# 3. CORE VERIFICATION ENGINE
# ==========================================
def verify_pipeline_output(company_name: str, predicted_domain: str) -> dict:
    """
    Tier 3 Audit Layer: Leverages Gemini 3.5 Flash alongside 
    Native Google Search Grounding to verify a discovered domain.
    """
    
    # Context-driven prompt engineered to enforce clean verification mechanics
    # Context-driven prompt engineered to enforce clean verification mechanics
    prompt = f"""
    You are an autonomous corporate data QA engineer. Your primary function is to verify
    if the candidate domain matches the provided company profile.

    - Target Entity: "{company_name}"
    - Candidate Domain to Evaluate: "{predicted_domain}"

    STRICT AUDIT RULES:
    1. Activate your google_search tool.
    2. Identify the MAIN official corporate root domain for "{company_name}".
    3. REJECT subdomains! If the candidate domain is a news, career, press, regional, or blog subdomain (e.g., 'news.microsoft.com' or 'careers-meli.mercadolibre.com'), you MUST set 'is_correct' to False.
    4. If 'is_correct' is False, set 'verified_website' to the clean base ROOT domain (e.g., 'microsoft.com' or 'mercadolibre.com').
    5. Clean your final 'verified_website' down to its core domain string (remove 'www.', subdomains, protocols, or trailing slashes).
    """

    # Build the structural system execution parameters
    config = types.GenerateContentConfig(
        # Inject Google Search directly into the execution thread
        #tools=[types.Tool(google_search=types.GoogleSearch())],
        
        # Enforce strict structured JSON parsing matching our Pydantic model
        response_mime_type="application/json",
        response_schema=ValidationVerdict,
        
        # Setting temperature to 1.0 is officially recommended by Google for search grounding tasks
        temperature=1.0, 
    )

    try:
        # We use gemini-3.5-flash as it is highly performant and cost-optimized for search routing tasks
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=config
        )
        
        # Turn the validated string output directly into a standard Python dictionary
        return json.loads(response.text)

    except Exception as e:
        print(f"[-] Gemini Verification Layer Fault for '{company_name}': {e}")
        
        # Fail-safe backup data payload to prevent crashing your core iteration loops
        return {
            "is_correct": False,
            "confidence_score": 0.0,
            "reasoning": f"Automated Exception Triggered: {str(e)}",
            "verified_website": predicted_domain
        }