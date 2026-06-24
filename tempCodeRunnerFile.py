
# ==========================================
DATA_FILE = "final_training.csv" 

if not os.path.exists(DATA_FILE):
    raise FileNotFoundError(f"❌ Cannot find '{DATA_FILE}'. Make sure it's in this folder!")
