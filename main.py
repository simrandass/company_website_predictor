# main.py
import os
import time
import contextlib
import pandas as pd
from dotenv import load_dotenv

# 1. Load keys into environment variables first
load_dotenv()

# 2. Import core pipeline dependencies
from scraper import get_linkedin_domain, configure_scraper
from predictor import predict_fallback_domain, configure_predictor
from verifier import verify_pipeline_output

CSV_FILE = "companies.csv"

@contextlib.contextmanager
def atomic_save_csv(filename):
    """Prevents file corruption by writing data to a temporary file first."""
    temp_filename = filename + ".tmp"
    try:
        yield temp_filename
        if os.path.exists(temp_filename):
            if os.path.exists(filename):
                os.remove(filename)
            os.rename(temp_filename, filename)
    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise e

def initialize_pipeline_assets(model_path_input: str):
    """Initializes sub-modules using environment variables for keys and a direct path for the model."""
    serper_key = os.getenv("SERPER_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not serper_key:
        raise ValueError("CRITICAL: SERPER_API_KEY is missing from environment variables.")
    if not gemini_key:
        raise ValueError("CRITICAL: GEMINI_API_KEY is missing from environment variables.")
    if not os.path.exists(model_path_input):
        raise FileNotFoundError(f"CRITICAL: Direct model asset path not found at: '{model_path_input}'")

    configure_scraper(serper_api_key=serper_key, headless=True)
    configure_predictor(serper_api_key=serper_key, model_path=model_path_input)
    print(f"[+] Operational Assets Initialized. Model Loaded from: {model_path_input}")

def run_orchestrator(model_filepath: str):
    """Main pipeline execution hook accepting model path parameters directly."""
    try:
        initialize_pipeline_assets(model_filepath)
    except Exception as e:
        print(f"[-] Boot Error: {e}")
        return

    if not os.path.exists(CSV_FILE):
        print(f"[-] Initializing template structure: {CSV_FILE}")
        df_init = pd.DataFrame(columns=["company_name", "resolved_domain", "status", "notes"])
        df_init.to_csv(CSV_FILE, index=False)
        print("[!] Please populate company_name rows in companies.csv and restart.")
        return

    # Force empty columns to be loaded as text strings, preventing float64 crashes
    df = pd.read_csv(CSV_FILE, dtype={
        "company_name": str,
        "resolved_domain": str,
        "status": str,
        "notes": str
    })
    
    unprocessed_rows = df[df["status"].isna() | (df["status"] == "Pending")]

    if unprocessed_rows.empty:
        print("[+] Processing complete. No empty rows found.")
        return

    print(f"[*] Beginning evaluation on {len(unprocessed_rows)} entries.\n")

    for index, row in unprocessed_rows.iterrows():
        name = row["company_name"]
        predicted_domain = None
        source_tier = "None"

        print(f"--- Processing Target: {name} ---")

        # Tier 1: Scraper
        try:
            predicted_domain = get_linkedin_domain(name)
            if predicted_domain:
                source_tier = "LinkedIn"
        except Exception as e:
            print(f"    [!] Scraper crashed: {e}")
        
        # Tier 2: XGBoost Fallback
        if not predicted_domain:
            print(f"    [-] Routing '{name}' to Tier 2 Framework...")
            try:
                predicted_domain = predict_fallback_domain(name)
                if predicted_domain:
                    source_tier = "XGBoost"
            except Exception as e:
                print(f"    [!] Predictor module crashed: {e}")

        # Post-Discovery Validation Check
        if not predicted_domain:
            print(f"    [X] No domain found for {name}.")
            df.at[index, "status"] = "Failed"
            df.at[index, "notes"] = "Undiscovered by baseline modules."
            with atomic_save_csv(CSV_FILE) as temp_path:
                df.to_csv(temp_path, index=False)
            continue

        # Tier 3: Gemini Verification Loop with internal string inspection
        while True:
            print(f"    [*] Verification: Evaluating {source_tier} choice ('{predicted_domain}') with Gemini...")
            try:
                audit = verify_pipeline_output(name, predicted_domain)
                
                # Check if verifier.py passed back an internal 429 fallback dictionary
                reasoning_text = audit.get("reasoning", "")
                if "Automated Exception Triggered" in reasoning_text or "429" in reasoning_text:
                    print("    [!] verifier.py caught an internal 429 rate limit. Activating backoff...")
                    print("        Sleeping for 60 seconds before trying this company again...")
                    time.sleep(60)
                    continue  # Jump back to the top of the while loop and retry
                
                if "is_correct" in audit:
                    break  # Genuine AI response generated successfully! Break the loop.
                else:
                    raise Exception("Gemini returned invalid or empty schema structure.")
            except Exception as api_err:
                print(f"    [!] Error encountered: {api_err}")
                print("        Sleeping for 60 seconds before trying this company again...")
                time.sleep(60)

        # Apply verified updates to your sheet rows cleanly
        if audit["is_correct"]:
            print(f"    [✓] Audited & Confirmed.")
            df.at[index, "resolved_domain"] = str(predicted_domain)
            df.at[index, "status"] = "Verified"
            df.at[index, "notes"] = f"Validated via {source_tier}. Confidence: {audit['confidence_score']}"
        else:
            print(f"    [▲] Amended by Verification Layer -> '{audit['verified_website']}'")
            df.at[index, "resolved_domain"] = str(audit["verified_website"])
            df.at[index, "status"] = "AI_Corrected"
            df.at[index, "notes"] = f"Modified from {source_tier}. Reason: {audit['reasoning']}"

        # Write current index checkpoint state directly to disk
        with atomic_save_csv(CSV_FILE) as temp_path:
            df.to_csv(temp_path, index=False)
            
    print("[+] Complete.")

if __name__ == "__main__":
    TARGET_MODEL = "company_predictor_XGBmodel.joblib" 
    run_orchestrator(model_filepath=TARGET_MODEL)