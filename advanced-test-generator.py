"""
Advanced Test Data Generator for ModelBench AI
Creates models in multiple frameworks: scikit-learn, PyTorch, TensorFlow, ONNX
"""

import numpy as np
import pandas as pd
import pickle
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import make_classification

print("=" * 70)
print("ModelBench AI - Advanced Test Data Generator")
print("=" * 70)

# Create test_data directory
os.makedirs('test_data', exist_ok=True)

# Generate base dataset
print("\n[1/7] Generating dataset...")
X, y = make_classification(
    n_samples=1000,
    n_features=20,
    n_informative=15,
    n_redundant=5,
    n_classes=2,
    random_state=42
)

# Save data
np.save('test_data/test_data.npy', X)
df = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(20)])
df.to_csv('test_data/test_data.csv', index=False)
print(f"   ✓ Dataset saved (1000 samples, 20 features)")

# ============================================================================
# 1. Scikit-learn Model
# ============================================================================
print("\n[2/7] Creating scikit-learn model...")
try:
    from sklearn.ensemble import RandomForestClassifier
    
    model = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42)
    model.fit(X[:800], y[:800])
    
    with open('test_data/sklearn_model.pkl', 'wb') as f:
        pickle.dump(model, f)
    
    accuracy = model.score(X[800:], y[800:])
    print(f"   ✓ sklearn_model.pkl created (Accuracy: {accuracy:.3f})")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# ============================================================================
# 2. PyTorch Model
# ============================================================================
print("\n[3/7] Creating PyTorch model...")
try:
    import torch
    import torch.nn as nn
    
    class SimpleNN(nn.Module):
        def __init__(self):
            super(SimpleNN, self).__init__()
            self.fc1 = nn.Linear(20, 64)
            self.fc2 = nn.Linear(64, 32)
            self.fc3 = nn.Linear(32, 2)
            self.relu = nn.ReLU()
        
        def forward(self, x):
            x = self.relu(self.fc1(x))
            x = self.relu(self.fc2(x))
            x = self.fc3(x)
            return x
    
    # Train model
    model = SimpleNN()
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    
    X_train = torch.FloatTensor(X[:800])
    y_train = torch.LongTensor(y[:800])
    
    model.train()
    for epoch in range(100):
        optimizer.zero_grad()
        outputs = model(X_train)
        loss = criterion(outputs, y_train)
        loss.backward()
        optimizer.step()
    
    # Evaluate
    model.eval()
    with torch.no_grad():
        X_test = torch.FloatTensor(X[800:])
        outputs = model(X_test)
        _, predicted = torch.max(outputs, 1)
        accuracy = (predicted == torch.LongTensor(y[800:])).float().mean()
    
    # Save as TorchScript
    example_input = torch.randn(1, 20)
    traced_model = torch.jit.trace(model, example_input)
    torch.jit.save(traced_model, 'test_data/pytorch_model.pt')
    
    print(f"   ✓ pytorch_model.pt created (Accuracy: {accuracy:.3f})")
except ImportError:
    print("   ⚠ PyTorch not installed - skipping")
    print("   Install with: pip install torch")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# ============================================================================
# 3. TensorFlow/Keras Model
# ============================================================================
print("\n[4/7] Creating TensorFlow model...")
try:
    import tensorflow as tf
    from tensorflow import keras
    
    # Suppress TF warnings
    tf.get_logger().setLevel('ERROR')
    
    # Create model
    model = keras.Sequential([
        keras.layers.Dense(64, activation='relu', input_shape=(20,)),
        keras.layers.Dense(32, activation='relu'),
        keras.layers.Dense(2, activation='softmax')
    ])
    
    model.compile(
        optimizer='adam',
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    
    # Train
    history = model.fit(
        X[:800], y[:800],
        epochs=50,
        batch_size=32,
        verbose=0,
        validation_split=0.1
    )
    
    # Evaluate
    loss, accuracy = model.evaluate(X[800:], y[800:], verbose=0)
    
    # Save
    model.save('test_data/tensorflow_model.h5')
    
    print(f"   ✓ tensorflow_model.h5 created (Accuracy: {accuracy:.3f})")
except ImportError:
    print("   ⚠ TensorFlow not installed - skipping")
    print("   Install with: pip install tensorflow")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# ============================================================================
# 4. ONNX Model
# ============================================================================
print("\n[5/7] Creating ONNX model...")
try:
    # Try converting from PyTorch
    import torch
    import torch.nn as nn
    
    # Check if torch.onnx is available
    if hasattr(torch, 'onnx'):
        class SimpleNN(nn.Module):
            def __init__(self):
                super(SimpleNN, self).__init__()
                self.fc1 = nn.Linear(20, 64)
                self.fc2 = nn.Linear(64, 32)
                self.fc3 = nn.Linear(32, 2)
                self.relu = nn.ReLU()
            
            def forward(self, x):
                x = self.relu(self.fc1(x))
                x = self.relu(self.fc2(x))
                x = self.fc3(x)
                return x
        
        model = SimpleNN()
        model.eval()
        
        dummy_input = torch.randn(1, 20)
        torch.onnx.export(
            model,
            dummy_input,
            'test_data/onnx_model.onnx',
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
        )
        
        print(f"   ✓ onnx_model.onnx created")
    else:
        print("   ⚠ torch.onnx not available - skipping")
except ImportError:
    print("   ⚠ PyTorch not installed - skipping ONNX export")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# ============================================================================
# 5. Create Different Dataset Sizes
# ============================================================================
print("\n[6/7] Creating datasets of different sizes...")

# Small dataset (100 samples)
X_small, _ = make_classification(n_samples=100, n_features=20, random_state=42)
np.save('test_data/small_data.npy', X_small)
print(f"   ✓ small_data.npy (100 samples)")

# Medium dataset (500 samples)
X_medium, _ = make_classification(n_samples=500, n_features=20, random_state=42)
np.save('test_data/medium_data.npy', X_medium)
print(f"   ✓ medium_data.npy (500 samples)")

# Large dataset (5000 samples)
X_large, _ = make_classification(n_samples=5000, n_features=20, random_state=42)
np.save('test_data/large_data.npy', X_large)
print(f"   ✓ large_data.npy (5000 samples)")

# ============================================================================
# 6. Create Benchmark Guide
# ============================================================================
print("\n[7/7] Creating benchmark guide...")

benchmark_guide = """# ModelBench AI - Benchmark Guide

## Available Test Files

### Models
- `sklearn_model.pkl` - Random Forest Classifier (scikit-learn)
- `pytorch_model.pt` - Neural Network (PyTorch JIT)
- `tensorflow_model.h5` - Neural Network (TensorFlow/Keras)
- `onnx_model.onnx` - Neural Network (ONNX format)

### Datasets
- `test_data.csv` - Standard test data (1000 samples, CSV)
- `test_data.npy` - Standard test data (1000 samples, NumPy)
- `small_data.npy` - Small test data (100 samples)
- `medium_data.npy` - Medium test data (500 samples)
- `large_data.npy` - Large test data (5000 samples)

## Recommended Benchmark Tests

### Test 1: Basic Performance Test
**Objective**: Measure baseline inference performance

- Model: `sklearn_model.pkl`
- Data: `test_data.npy`
- Batch Size: 1
- Iterations: 100
- Warmup: 10

**Expected Result**: ~1-5ms average latency

---

### Test 2: Batch Processing Test
**Objective**: Analyze batch size impact on throughput

Run multiple benchmarks with different batch sizes:
- Batch sizes: 1, 8, 16, 32, 64
- Model: `sklearn_model.pkl`
- Data: `test_data.npy`
- Iterations: 100

**Expected Result**: Higher throughput with larger batches

---

### Test 3: Framework Comparison
**Objective**: Compare inference speed across frameworks

Test all models with same data:
1. `sklearn_model.pkl` + `test_data.npy`
2. `pytorch_model.pt` + `test_data.npy`
3. `tensorflow_model.h5` + `test_data.npy`
4. `onnx_model.onnx` + `test_data.npy`

Settings:
- Batch Size: 1
- Iterations: 100
- Warmup: 10

**Expected Result**: ONNX typically fastest, followed by PyTorch JIT

---

### Test 4: Scalability Test
**Objective**: Test performance with different data sizes

Use `sklearn_model.pkl` with:
1. `small_data.npy` (100 samples)
2. `medium_data.npy` (500 samples)
3. `large_data.npy` (5000 samples)

Settings:
- Batch Size: 32
- Iterations: 50

**Expected Result**: Consistent per-batch latency

---

### Test 5: Stress Test
**Objective**: Identify performance limits and stability

- Model: `sklearn_model.pkl`
- Data: `large_data.npy`
- Batch Size: 128
- Iterations: 500
- Warmup: 20

**Expected Result**: Measure P95 and P99 latency for reliability

---

## Interpreting Results

### Latency Metrics
- **Average**: Overall performance indicator
- **P50**: Typical performance (median)
- **P95**: Performance guarantee for 95% of requests
- **P99**: Worst-case performance (important for SLAs)

### Throughput
- Predictions per second
- Higher is better
- Consider batch size when comparing

### When to Use What

**Low Latency Priority** (Real-time apps):
- Batch size: 1
- Focus on: Average and P95 latency
- Target: <10ms per prediction

**High Throughput Priority** (Batch processing):
- Batch size: 32-128
- Focus on: Throughput
- Target: >1000 predictions/second

**Production SLA** (Enterprise apps):
- Batch size: Based on use case
- Focus on: P95 and P99 latency
- Target: Depends on requirements

---

## Tips for Better Benchmarks

1. **Consistent Environment**: Run benchmarks on same hardware
2. **Warmup**: Always use warmup runs (10+) for accurate results
3. **Iterations**: Use 100+ iterations for statistical significance
4. **Batch Size**: Test multiple batch sizes to find optimal
5. **Compare Apples to Apples**: Same data, same settings
6. **Multiple Runs**: Run benchmarks 3+ times, report average
7. **Monitor Resources**: Check CPU/memory during benchmarks

---

## Example Workflows

### Workflow 1: Model Selection
Goal: Choose best model for production

1. Benchmark all available models
2. Compare average latency and throughput
3. Check P95/P99 for reliability
4. Consider model size and memory usage
5. Select based on requirements

### Workflow 2: Optimization
Goal: Improve existing model performance

1. Benchmark baseline performance
2. Test different batch sizes
3. Try different frameworks (convert to ONNX)
4. Quantize model if applicable
5. Compare improvements

### Workflow 3: Capacity Planning
Goal: Determine infrastructure needs

1. Benchmark with expected load
2. Calculate requests per second needed
3. Determine servers/instances required
4. Test with stress scenarios
5. Plan for peak load + margin

---

## Sample Results Table

| Model      | Avg (ms) | P95 (ms) | P99 (ms) | Throughput |
|------------|----------|----------|----------|------------|
| sklearn    | 2.3      | 3.1      | 4.2      | 434/s      |
| PyTorch    | 1.8      | 2.4      | 3.1      | 555/s      |
| TensorFlow | 2.1      | 2.9      | 3.8      | 476/s      |
| ONNX       | 1.5      | 2.0      | 2.6      | 666/s      |

*Example only - actual results vary by hardware*

---

## Next Steps

1. Run basic benchmarks with provided data
2. Compare results across frameworks
3. Test with your own models
4. Export results for reporting
5. Share findings with your team

Happy Benchmarking!
"""

with open('test_data/BENCHMARK_GUIDE.md', 'w', encoding='utf-8') as f:
    f.write(benchmark_guide)

print(f"   ✓ BENCHMARK_GUIDE.md created")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 70)
print("Advanced Test Data Generation Complete!")
print("=" * 70)

print("\nFiles in 'test_data/' directory:")
print("\nModels:")
models = []
if os.path.exists('test_data/sklearn_model.pkl'):
    models.append("   [OK] sklearn_model.pkl")
if os.path.exists('test_data/pytorch_model.pt'):
    models.append("   [OK] pytorch_model.pt")
if os.path.exists('test_data/tensorflow_model.h5'):
    models.append("   [OK] tensorflow_model.h5")
if os.path.exists('test_data/onnx_model.onnx'):
    models.append("   [OK] onnx_model.onnx")

for model in models:
    print(model)

print("\nDatasets:")
print("   [OK] test_data.csv (1000 samples)")
print("   [OK] test_data.npy (1000 samples)")
print("   [OK] small_data.npy (100 samples)")
print("   [OK] medium_data.npy (500 samples)")
print("   [OK] large_data.npy (5000 samples)")

print("\nDocumentation:")
print("   [OK] BENCHMARK_GUIDE.md")

print("\n" + "=" * 70)
print("Quick Start Guide:")
print("=" * 70)
print("\n1. Start the application:")
print("   python app.py")
print("\n2. Open browser:")
print("   http://localhost:5000")
print("\n3. Upload files from test_data/ directory")
print("\n4. Recommended first test:")
print("   Model: sklearn_model.pkl")
print("   Data: test_data.npy")
print("   Batch Size: 1")
print("   Iterations: 100")
print("\n5. View BENCHMARK_GUIDE.md for more test scenarios")
print("=" * 70)

# Create a quick test script
quick_test = """#!/usr/bin/env python3
'''Quick API test for ModelBench AI'''
import requests
import os

print("Testing ModelBench AI API...")
print("-" * 50)

# Check if files exist
if not os.path.exists('test_data/sklearn_model.pkl'):
    print("Error: Run generate_advanced_test_data.py first!")
    exit(1)

# Test benchmark endpoint
url = 'http://localhost:5000/api/benchmark'

files = {
    'model': open('test_data/sklearn_model.pkl', 'rb'),
    'data': open('test_data/test_data.npy', 'rb')
}

data = {
    'batch_size': 1,
    'num_iterations': 50,
    'warmup_runs': 5
}

print("Sending benchmark request...")
response = requests.post(url, files=files, data=data)

if response.status_code == 200:
    result = response.json()
    print("[OK] Benchmark successful!")
    print(f"\\nResults:")
    print(f"  Model Type: {result['model_type']}")
    print(f"  Avg Latency: {result['metrics']['avg_latency_ms']:.2f}ms")
    print(f"  P95 Latency: {result['metrics']['p95_latency_ms']:.2f}ms")
    print(f"  Throughput: {result['metrics']['throughput_per_sec']:.1f} pred/s")
else:
    print(f"[ERROR] Error: {response.status_code}")
    print(response.text)
"""

with open('test_data/quick_test.py', 'w', encoding='utf-8') as f:
    f.write(quick_test)

print("\nBonus: Created quick_test.py for API testing")
print("   Run with: python test_data/quick_test.py")
print("=" * 70)