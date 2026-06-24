import os
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score

# ==========================================
# 1. LOAD AND CLEAN LABELED DATA
# ==========================================
DATA_FILE = "final_training.csv" 

if not os.path.exists(DATA_FILE):
    raise FileNotFoundError(f"❌ Cannot find '{DATA_FILE}'. Make sure it's in this folder!")

print(f"📖 Reading {DATA_FILE}...")
df = pd.read_csv(DATA_FILE)
df.columns = df.columns.str.strip()  # Strip spaces from column headers

# 🧹 BULLETPROOF CLEANUP: Handles 'True', 'true', '1.0', '1', and converts everything else to 0
df["is_correct"] = df["is_correct"].astype(str).str.strip().str.lower()
df["is_correct"] = df["is_correct"].apply(lambda x: 1 if x in ['1', '1.0', 'true'] else 0)

print("\n📊 Final Class Breakdown in 'is_correct' target:")
print(df["is_correct"].value_counts())
print("--------------------------------------------------")

# ==========================================
# 2. SEPARATE FEATURES (X) AND TARGET (y)
# ==========================================
feature_columns = [
    "search_position",
    "text_similarity_score",
    "is_aggregator_domain",
    "url_length"
]

X = df[feature_columns]
y = df["is_correct"]

# 80% to train the model, 20% held back to test its accuracy
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print(f"📊 Dataset Split Complete! Training rows: {len(X_train)} | Testing rows: {len(X_test)}")

# ==========================================
# 3. INITIALIZE AND TRAIN RANDOM FOREST
# ==========================================
print("\n🌲 Training the Random Forest Committee...")

model = RandomForestClassifier(
    n_estimators=50,         # Number of decision trees
    max_depth=3,             # Shallow trees prevent overfitting on a small dataset
    class_weight="balanced", # Compensates for the imbalance of 0s vs 1s
    random_state=42
)
model.fit(X_train, y_train)

# ==========================================
# 4. EVALUATE MODEL QUALITY
# ==========================================
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("\n🎯 --- RANDOM FOREST PERFORMANCE ---")
print(f"✅ Overall Accuracy: {accuracy * 100:.2f}%")
print("\n📋 Detailed Breakdown Metrics:")
print(classification_report(y_test, y_pred))

# ==========================================
# 5. SAVE THE MODEL
# ==========================================
MODEL_OUTPUT = "rf_website_predictor.pkl"
joblib.dump(model, MODEL_OUTPUT)
print(f"\n💾 Success! Saved trained Random Forest brain as '{MODEL_OUTPUT}'")