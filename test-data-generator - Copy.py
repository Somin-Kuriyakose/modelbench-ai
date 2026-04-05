"""
Test Data Generator for ModelBench AI
Creates sample models and test datasets for benchmarking
"""

import numpy as np
import pandas as pd
import pickle
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.datasets import make_classification, make_regression

print("=" * 60)
print("ModelBench AI - Test Data Generator")
print("=" * 60)

# Create test_data directory
import os
os.makedirs('test_data', exist_ok=True)

# ============================================================================
# 1. Generate Classification Dataset
# ============================================================================
print("\n[1/6] Generating classification dataset...")

X_class, y_class = make_classification(
    n_samples=1000,
    n_features=20,
    n_informative=15,
    n_redundant=5,
    n_classes=2,
    random_state=42
)

# Save as different formats
np.save('test_data/classification_data.npy', X_class)
np.savez('test_data/classification_data.npz', data=X_class, labels=y_class)

df_class = pd.DataFrame(X_class, columns=[f'feature_{i}' for i in range(20)])
df_class.to_csv('test_data/classification_data.csv', index=False)

print(f"   [OK] Classification data saved (1000 samples, 20 features)")
print(f"   [OK] Formats: .npy, .npz, .csv")

# ============================================================================
# 2. Generate Regression Dataset
# ============================================================================
print("\n[2/6] Generating regression dataset...")

X_reg, y_reg = make_regression(
    n_samples=1000,
    n_features=10,
    n_informative=8,
    noise=0.1,
    random_state=42
)

# Save as different formats
np.save('test_data/regression_data.npy', X_reg)
np.savez('test_data/regression_data.npz', data=X_reg, labels=y_reg)

df_reg = pd.DataFrame(X_reg, columns=[f'feature_{i}' for i in range(10)])
df_reg.to_csv('test_data/regression_data.csv', index=False)

print(f"   [OK] Regression data saved (1000 samples, 10 features)")
print(f"   [OK] Formats: .npy, .npz, .csv")

# ============================================================================
# 3. Train and Save Random Forest Classifier (scikit-learn)
# ============================================================================
print("\n[3/6] Training Random Forest Classifier...")

rf_model = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    random_state=42
)
rf_model.fit(X_class[:800], y_class[:800])

with open('test_data/random_forest_classifier.pkl', 'wb') as f:
    pickle.dump(rf_model, f)

print(f"   [OK] Random Forest saved: random_forest_classifier.pkl")
print(f"   [OK] Accuracy: {rf_model.score(X_class[800:], y_class[800:]):.3f}")

# ============================================================================
# 4. Train and Save Logistic Regression (scikit-learn)
# ============================================================================
print("\n[4/6] Training Logistic Regression...")

lr_model = LogisticRegression(max_iter=1000, random_state=42)
lr_model.fit(X_class[:800], y_class[:800])

with open('test_data/logistic_regression.pkl', 'wb') as f:
    pickle.dump(lr_model, f)

print(f"   [OK] Logistic Regression saved: logistic_regression.pkl")
print(f"   [OK] Accuracy: {lr_model.score(X_class[800:], y_class[800:]):.3f}")

# ============================================================================
# 5. Train and Save Gradient Boosting Regressor (scikit-learn)
# ============================================================================
print("\n[5/6] Training Gradient Boosting Regressor...")

gb_model = GradientBoostingRegressor(
    n_estimators=50,
    max_depth=5,
    random_state=42
)
gb_model.fit(X_reg[:800], y_reg[:800])

with open('test_data/gradient_boosting_regressor.pkl', 'wb') as f:
    pickle.dump(gb_model, f)

from sklearn.metrics import r2_score
predictions = gb_model.predict(X_reg[800:])
print(f"   [OK] Gradient Boosting saved: gradient_boosting_regressor.pkl")
print(f"   [OK] R2 Score: {r2_score(y_reg[800:], predictions):.3f}")

# ============================================================================
# 6. Train and Save Decision Tree (scikit-learn)
# ============================================================================
print("\n[6/6] Training Decision Tree Classifier...")

dt_model = DecisionTreeClassifier(max_depth=10, random_state=42)
dt_model.fit(X_class[:800], y_class[:800])

with open('test_data/decision_tree.pkl', 'wb') as f:
    pickle.dump(dt_model, f)

print(f"   [OK] Decision Tree saved: decision_tree.pkl")
print(f"   [OK] Accuracy: {dt_model.score(X_class[800:], y_class[800:]):.3f}")

# ============================================================================
# Create a README file
# ============================================================================
readme_content = """# Test Data for ModelBench AI

This directory contains sample models and datasets for testing the benchmarking platform.

## Datasets

### Classification Data
- classification_data.npy - NumPy array (1000 samples, 20 features)
- classification_data.npz - Compressed NumPy (includes labels)
- classification_data.csv - CSV format (1000 rows, 20 columns)

### Regression Data
- regression_data.npy - NumPy array (1000 samples, 10 features)
- regression_data.npz - Compressed NumPy (includes labels)
- regression_data.csv - CSV format (1000 rows, 10 columns)

## Models (scikit-learn)

### Classification Models
1. random_forest_classifier.pkl
   - Random Forest with 100 estimators
   - Max depth: 10
   - Use with: classification_data.*

2. logistic_regression.pkl
   - Logistic Regression classifier
   - Max iterations: 1000
   - Use with: classification_data.*

3. decision_tree.pkl
   - Decision Tree classifier
   - Max depth: 10
   - Use with: classification_data.*

### Regression Models
1. gradient_boosting_regressor.pkl
   - Gradient Boosting with 50 estimators
   - Max depth: 5
   - Use with: regression_data.*

## Quick Test Examples

### Example 1: Benchmark Random Forest
1. Model: random_forest_classifier.pkl
2. Data: classification_data.csv
3. Batch Size: 32
4. Iterations: 100

### Example 2: Benchmark Logistic Regression
1. Model: logistic_regression.pkl
2. Data: classification_data.npy
3. Batch Size: 1
4. Iterations: 200

### Example 3: Compare Models
Test all classification models with the same data to compare performance.

## Notes

- All models are trained on 80% of the data
- Test data (20%) can be used for validation
- Models are saved in pickle format (.pkl)
- Data is available in multiple formats for testing
"""

with open('test_data/README.md', 'w', encoding='utf-8') as f:
    f.write(readme_content)

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 60)
print("Test Data Generation Complete!")
print("=" * 60)
print("\nFiles created in 'test_data/' directory:")
print("\nDatasets:")
print("   * classification_data.npy")
print("   * classification_data.npz")
print("   * classification_data.csv")
print("   * regression_data.npy")
print("   * regression_data.npz")
print("   * regression_data.csv")
print("\nModels:")
print("   * random_forest_classifier.pkl")
print("   * logistic_regression.pkl")
print("   * decision_tree.pkl")
print("   * gradient_boosting_regressor.pkl")
print("\nReady to test ModelBench AI!")
print("=" * 60)
print("\nQuick Start:")
print("   1. Run: python app.py")
print("   2. Open: http://localhost:5000")
print("   3. Upload a model from test_data/")
print("   4. Upload corresponding data from test_data/")
print("   5. Click 'Run Benchmark'")
print("=" * 60)
