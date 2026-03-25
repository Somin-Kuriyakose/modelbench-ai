"""
New :
  • Async benchmark jobs with progress polling
  • Memory profiling (tracemalloc + psutil RSS)
  • CPU utilization tracking per run
  • Accuracy / quality metrics (accuracy, F1, RMSE, R², MAE) with optional labels upload
  • Model introspection (sklearn class, params, n_features, feature importances, size)
  • Batch-size sweep (auto-profile multiple batch sizes in one shot)
  • Result tagging & notes
  • Bulk CSV export (all results)
  • In-memory rate limiting per IP
  • Result retention policy (auto-delete old JSON files)
  • Latency histogram data in benchmark result
  • Pickle security warning flag in result
"""

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import json
import time
import uuid
import pickle
import logging
import platform
import threading
import tracemalloc
import numpy as np
from collections import defaultdict
from datetime import datetime, timedelta
from io import BytesIO
import pandas as pd

from config import config

# ── Optional ML framework imports ─────────────────────────────────────────────
try:
    import torch
    TORCH_AVAILABLE = True
    TORCH_VERSION = torch.__version__
except ImportError:
    TORCH_AVAILABLE = False
    TORCH_VERSION = None

try:
    import tensorflow as tf
    TF_AVAILABLE = True
    TF_VERSION = tf.__version__
except ImportError:
    TF_AVAILABLE = False
    TF_VERSION = None

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
    ONNX_VERSION = ort.__version__
except ImportError:
    ONNX_AVAILABLE = False
    ONNX_VERSION = None

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from sklearn import base as _skbase
    from sklearn.metrics import (accuracy_score, f1_score,
                                  mean_squared_error, r2_score,
                                  mean_absolute_error)
    import sklearn as _sklearn
    SKLEARN_AVAILABLE = True
    SKLEARN_VERSION = _sklearn.__version__
except ImportError:
    SKLEARN_AVAILABLE = False
    SKLEARN_VERSION = None

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("modelbench")

# ── In-memory rate limiter ────────────────────────────────────────────────────
_rate_store: dict[str, list] = defaultdict(list)
_rate_lock = threading.Lock()


def _rate_limit_ok(ip: str, max_calls: int, window: int) -> bool:
    now = time.time()
    with _rate_lock:
        calls = [t for t in _rate_store[ip] if now - t < window]
        if len(calls) >= max_calls:
            _rate_store[ip] = calls
            return False
        calls.append(now)
        _rate_store[ip] = calls
        return True


def rate_limited(fn):
    """Decorator that applies per-IP rate limiting from app config."""
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        from flask import current_app, request as req
        ip = req.remote_addr or "unknown"
        max_calls = current_app.config.get("RATE_LIMIT_MAX_CALLS", 10)
        window = current_app.config.get("RATE_LIMIT_WINDOW_SECONDS", 60)
        if not _rate_limit_ok(ip, max_calls, window):
            return jsonify({
                "error": f"Rate limit exceeded — max {max_calls} benchmarks per {window}s per IP."
            }), 429
        return fn(*args, **kwargs)

    return wrapper


# ── Async job store ───────────────────────────────────────────────────────────
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _create_job() -> str:
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "pending",
            "progress": 0,
            "result": None,
            "error": None,
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
        }
    return job_id


def _update_job(job_id: str, **kwargs):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def _get_job(job_id: str) -> dict:
    with _jobs_lock:
        return dict(_jobs.get(job_id, {}))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_ext(filename: str, allowed: set) -> bool:
    return os.path.splitext(filename)[1].lower() in allowed


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _safe_int(v, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _result_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def _cleanup_old_results(folder: str, max_age_days: int) -> int:
    """Delete result JSON files older than max_age_days. Returns count removed."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    removed = 0
    for fname in os.listdir(folder):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(folder, fname)
        try:
            if datetime.fromtimestamp(os.path.getmtime(fpath)) < cutoff:
                os.remove(fpath)
                removed += 1
        except OSError:
            pass
    if removed:
        logger.info("Retention: removed %d old results", removed)
    return removed


# ── Model introspection ───────────────────────────────────────────────────────

def _introspect(model, model_type: str) -> dict:
    info: dict = {"framework": model_type}
    try:
        info["class_name"] = type(model).__name__
        info["module"] = type(model).__module__

        if model_type == "sklearn" and SKLEARN_AVAILABLE:
            params = model.get_params()
            info["params"] = {k: str(v) for k, v in list(params.items())[:20]}
            if hasattr(model, "n_features_in_"):
                info["n_features_in"] = int(model.n_features_in_)
            if hasattr(model, "classes_"):
                info["n_classes"] = int(len(model.classes_))
                info["classes"] = [str(c) for c in model.classes_[:20]]
            if hasattr(model, "n_estimators"):
                info["n_estimators"] = int(model.n_estimators)
            if hasattr(model, "max_depth"):
                info["max_depth"] = model.max_depth
            if hasattr(model, "feature_importances_"):
                fi = model.feature_importances_
                info["feature_importances_top10"] = [
                    round(float(v), 5) for v in sorted(fi, reverse=True)[:10]
                ]
            buf = BytesIO()
            pickle.dump(model, buf)
            info["model_size_kb"] = round(buf.tell() / 1024, 1)
            info["is_classifier"] = bool(_skbase.is_classifier(model))
            info["is_regressor"] = bool(_skbase.is_regressor(model))

        elif model_type == "pytorch" and TORCH_AVAILABLE:
            try:
                info["num_parameters"] = int(sum(p.numel() for p in model.parameters()))
            except Exception:
                pass

        elif model_type == "tensorflow" and TF_AVAILABLE:
            try:
                info["num_parameters"] = int(model.count_params())
                info["num_layers"] = len(model.layers)
            except Exception:
                pass

        elif model_type == "onnx" and ONNX_AVAILABLE:
            try:
                info["inputs"] = [
                    {"name": i.name, "shape": list(i.shape), "dtype": str(i.type)}
                    for i in model.get_inputs()
                ]
                info["outputs"] = [
                    {"name": o.name, "shape": list(o.shape), "dtype": str(o.type)}
                    for o in model.get_outputs()
                ]
            except Exception:
                pass

    except Exception as e:
        info["introspection_error"] = str(e)

    return info


# ── Accuracy / quality metrics ────────────────────────────────────────────────

def _accuracy_metrics(predictions: np.ndarray, labels: np.ndarray,
                      is_classifier: bool) -> dict:
    metrics: dict = {}
    try:
        preds = np.array(predictions).flatten()
        true = labels.flatten()
        n = min(len(preds), len(true))
        if n == 0:
            return {"error": "Empty prediction or label array"}
        preds, true = preds[:n], true[:n]

        if is_classifier and SKLEARN_AVAILABLE:
            preds_int = np.round(preds).astype(int)
            metrics["accuracy"]  = round(float(accuracy_score(true, preds_int)), 4)
            avg = "weighted" if len(np.unique(true)) > 2 else "binary"
            metrics["f1_score"]  = round(float(
                f1_score(true, preds_int, average=avg, zero_division=0)), 4)
        else:
            metrics["rmse"]    = round(float(np.sqrt(mean_squared_error(true, preds))), 4)
            metrics["mae"]     = round(float(mean_absolute_error(true, preds)), 4)
            metrics["r2_score"] = round(float(r2_score(true, preds)), 4)

        metrics["n_samples_evaluated"] = int(n)
    except Exception as e:
        metrics["error"] = str(e)
    return metrics


# ── Model benchmarker ─────────────────────────────────────────────────────────

class ModelBenchmarker:
    FRAMEWORK_MAP = {
        ".pkl": "sklearn",
        ".pt":  "pytorch",
        ".pth": "pytorch",
        ".h5":  "tensorflow",
        ".onnx": "onnx",
    }

    def __init__(self, model_path: str):
        self.model_path = model_path
        ext = os.path.splitext(model_path)[1].lower()
        self.model_type = self.FRAMEWORK_MAP.get(ext)
        if not self.model_type:
            raise ValueError(f"Unsupported model extension: {ext}")
        self.model = None
        self._load()

    # ── Loaders ───────────────────────────────────────────────────────────
    def _load(self):
        {
            "sklearn":     self._load_sklearn,
            "pytorch":     self._load_pytorch,
            "tensorflow":  self._load_tensorflow,
            "onnx":        self._load_onnx,
        }[self.model_type]()

    def _load_sklearn(self):
        with open(self.model_path, "rb") as f:
            self.model = pickle.load(f)

    def _load_pytorch(self):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is not installed")
        self.model = torch.jit.load(self.model_path)
        self.model.eval()

    def _load_tensorflow(self):
        if not TF_AVAILABLE:
            raise RuntimeError("TensorFlow is not installed")
        self.model = tf.keras.models.load_model(self.model_path)

    def _load_onnx(self):
        if not ONNX_AVAILABLE:
            raise RuntimeError("ONNX Runtime is not installed")
        self.model = ort.InferenceSession(self.model_path)

    # ── Predictors ────────────────────────────────────────────────────────
    def predict(self, data: np.ndarray):
        return {
            "sklearn":    lambda d: self.model.predict(d),
            "pytorch":    lambda d: self._pt_predict(d),
            "tensorflow": lambda d: self.model.predict(d, verbose=0),
            "onnx":       lambda d: self._onnx_predict(d),
        }[self.model_type](data)

    def _pt_predict(self, data):
        with torch.no_grad():
            return self.model(torch.FloatTensor(data)).numpy()

    def _onnx_predict(self, data):
        name = self.model.get_inputs()[0].name
        return self.model.run(None, {name: data.astype(np.float32)})[0]

    # ── Main benchmark ────────────────────────────────────────────────────
    def benchmark(self, test_data: np.ndarray, *,
                  batch_size: int = 1,
                  num_iterations: int = 100,
                  warmup_runs: int = 10,
                  labels: np.ndarray = None,
                  progress_cb=None) -> dict:

        n = len(test_data)
        if n == 0:
            raise ValueError("Test data is empty")

        # Build batch list
        batches = [test_data[i:i + batch_size] for i in range(0, n, batch_size)]
        if len(batches) < num_iterations:
            extended = []
            while len(extended) < num_iterations:
                extended.extend(batches)
            batches = extended[:num_iterations]
        else:
            batches = batches[:num_iterations]

        # Warmup
        for b in batches[:min(warmup_runs, len(batches))]:
            self.predict(b)

        # Memory baseline
        tracemalloc.start()
        proc = psutil.Process() if PSUTIL_AVAILABLE else None
        cpu_samples = []
        all_preds = []

        # Timed runs
        latencies = []
        for idx, batch in enumerate(batches):
            if proc:
                cpu_samples.append(proc.cpu_percent(interval=None))

            t0 = time.perf_counter()
            preds = self.predict(batch)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000)
            all_preds.append(preds)

            if progress_cb and idx % max(1, num_iterations // 20) == 0:
                progress_cb(int(idx / num_iterations * 90))  # 0-90%, 100 set when saved

        mem_current, mem_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        lat = np.array(latencies)

        # Build histogram buckets (20 bins)
        hist_counts, hist_edges = np.histogram(lat, bins=20)
        histogram = {
            "counts": hist_counts.tolist(),
            "edges":  [round(float(e), 3) for e in hist_edges.tolist()],
        }

        metrics: dict = {
            "avg_latency_ms":    round(float(np.mean(lat)), 4),
            "median_latency_ms": round(float(np.median(lat)), 4),
            "p50_latency_ms":    round(float(np.percentile(lat, 50)), 4),
            "p90_latency_ms":    round(float(np.percentile(lat, 90)), 4),
            "p95_latency_ms":    round(float(np.percentile(lat, 95)), 4),
            "p99_latency_ms":    round(float(np.percentile(lat, 99)), 4),
            "min_latency_ms":    round(float(np.min(lat)), 4),
            "max_latency_ms":    round(float(np.max(lat)), 4),
            "std_latency_ms":    round(float(np.std(lat)), 4),
            "throughput_per_sec": round(float(1000 / np.mean(lat) * batch_size), 2),
            "total_predictions": len(batches) * batch_size,
            "total_time_ms":     round(float(np.sum(lat)), 2),
            "memory_current_kb": round(mem_current / 1024, 1),
            "memory_peak_kb":    round(mem_peak / 1024, 1),
        }

        if proc:
            if cpu_samples:
                metrics["cpu_avg_pct"] = round(float(np.mean(cpu_samples)), 1)
                metrics["cpu_max_pct"] = round(float(np.max(cpu_samples)), 1)
            try:
                rss = proc.memory_info().rss
                metrics["ram_rss_mb"] = round(rss / (1024 ** 2), 1)
            except Exception:
                pass

        # Accuracy metrics (optional)
        accuracy_metrics: dict = {}
        if labels is not None and SKLEARN_AVAILABLE:
            try:
                concat = np.concatenate([np.array(p).flatten() for p in all_preds])
                is_clf = (self.model_type == "sklearn" and
                          hasattr(self.model, "classes_"))
                accuracy_metrics = _accuracy_metrics(concat, labels, is_clf)
            except Exception as e:
                accuracy_metrics = {"error": str(e)}

        return {
            "model_type":       self.model_type,
            "model_file":       os.path.basename(self.model_path),
            "batch_size":       batch_size,
            "num_iterations":   num_iterations,
            "warmup_runs":      warmup_runs,
            "data_samples":     n,
            "timestamp":        datetime.now().isoformat(),
            "metrics":          metrics,
            "accuracy_metrics": accuracy_metrics,
            "introspection":    _introspect(self.model, self.model_type),
            "histogram":        histogram,
            "latencies":        [round(float(v), 4) for v in lat.tolist()],
            "is_pickle":        self.model_type == "sklearn",
        }

    # ── Batch sweep ───────────────────────────────────────────────────────
    def sweep(self, test_data: np.ndarray, batch_sizes: list,
              num_iterations: int = 50, warmup_runs: int = 5) -> list:
        results = []
        for bs in batch_sizes:
            try:
                res = self.benchmark(test_data, batch_size=bs,
                                     num_iterations=num_iterations,
                                     warmup_runs=warmup_runs)
                m = res["metrics"]
                results.append({
                    "batch_size":        bs,
                    "avg_latency_ms":    m["avg_latency_ms"],
                    "p99_latency_ms":    m["p99_latency_ms"],
                    "throughput_per_sec": m["throughput_per_sec"],
                    "total_time_ms":     m["total_time_ms"],
                    "memory_peak_kb":    m["memory_peak_kb"],
                })
            except Exception as exc:
                results.append({"batch_size": bs, "error": str(exc)})
        return results


# ── Data loaders ──────────────────────────────────────────────────────────────

def _load_data(path: str) -> np.ndarray:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(path)
        return df.select_dtypes(include=[np.number]).values
    elif ext == ".npy":
        return np.load(path)
    elif ext == ".npz":
        arc = np.load(path)
        return arc[arc.files[0]]
    raise ValueError(f"Unsupported data format: {ext}")


def _load_labels(path: str) -> np.ndarray:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(path, header=None).values.flatten()
    elif ext == ".npy":
        return np.load(path).flatten()
    raise ValueError(f"Unsupported labels format: {ext}")


# ── Shared benchmark runner (sync + async) ────────────────────────────────────

def _do_benchmark(app, model_path, data_path, labels_path,
                  batch_size, num_iterations, warmup_runs,
                  progress_cb=None) -> dict:
    labels = None
    if labels_path and os.path.exists(labels_path):
        try:
            labels = _load_labels(labels_path)
        except Exception as e:
            logger.warning("Could not load labels: %s", e)

    data = _load_data(data_path)
    bench = ModelBenchmarker(model_path)
    return bench.benchmark(data,
                           batch_size=batch_size,
                           num_iterations=num_iterations,
                           warmup_runs=warmup_runs,
                           labels=labels,
                           progress_cb=progress_cb)


def _save_result(results_folder: str, data: dict) -> str:
    rid = _result_id()
    with open(os.path.join(results_folder, f"benchmark_{rid}.json"), "w") as f:
        json.dump(data, f, indent=2)
    return rid


def _maybe_cleanup(app, *paths):
    if app.config.get("AUTO_CLEANUP_UPLOADS", True):
        for p in filter(None, paths):
            try:
                os.remove(p)
            except OSError:
                pass


def _maybe_retention(app):
    days = app.config.get("RESULT_RETENTION_DAYS")
    if days:
        _cleanup_old_results(app.config["RESULTS_FOLDER"], days)


def _parse_files(app, request_obj, require_labels=False):
    """Extract and save uploaded files. Returns (model_path, data_path, labels_path)."""
    model_file = request_obj.files.get("model")
    data_file  = request_obj.files.get("data")

    if not model_file or not data_file:
        raise ValueError("Both model and data files are required.")
    if not _validate_ext(model_file.filename, app.config["ALLOWED_MODEL_EXTENSIONS"]):
        raise ValueError(f"Invalid model format. Allowed: {', '.join(app.config['ALLOWED_MODEL_EXTENSIONS'])}")
    if not _validate_ext(data_file.filename, app.config["ALLOWED_DATA_EXTENSIONS"]):
        raise ValueError(f"Invalid data format. Allowed: {', '.join(app.config['ALLOWED_DATA_EXTENSIONS'])}")

    prefix = uuid.uuid4().hex[:8]
    model_path = os.path.join(app.config["UPLOAD_FOLDER"],
                              f"{prefix}_{secure_filename(model_file.filename)}")
    data_path  = os.path.join(app.config["UPLOAD_FOLDER"],
                              f"{prefix}_{secure_filename(data_file.filename)}")
    model_file.save(model_path)
    data_file.save(data_path)

    labels_path = None
    lf = request_obj.files.get("labels")
    if lf and lf.filename:
        if not _validate_ext(lf.filename, app.config.get("ALLOWED_LABELS_EXTENSIONS", {".csv", ".npy"})):
            raise ValueError("Invalid labels format. Allowed: .csv, .npy")
        labels_path = os.path.join(app.config["UPLOAD_FOLDER"],
                                   f"{prefix}_{secure_filename(lf.filename)}")
        lf.save(labels_path)

    return model_path, data_path, labels_path


# ── Routes ─────────────────────────────────────────────────────────────────────

def register_routes(app: Flask):

    @app.route("/")
    def index():
        return render_template("landing.html")

    @app.route("/features")
    def features():
        return render_template("features.html")

    @app.route("/faq")
    def faq():
        return render_template("faq.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/app")
    def benchmark_app():
        return render_template("app.html")

    # ── Sync benchmark ────────────────────────────────────────────────────
    @app.route("/api/benchmark", methods=["POST"])
    @rate_limited
    def run_benchmark():
        try:
            model_path, data_path, labels_path = _parse_files(app, request)
            bs  = _clamp(_safe_int(request.form.get("batch_size"),    app.config["DEFAULT_BATCH_SIZE"]),
                         app.config["MIN_BATCH_SIZE"], app.config["MAX_BATCH_SIZE"])
            it  = _clamp(_safe_int(request.form.get("num_iterations"), app.config["DEFAULT_ITERATIONS"]),
                         app.config["MIN_ITERATIONS"], app.config["MAX_ITERATIONS"])
            wu  = _clamp(_safe_int(request.form.get("warmup_runs"),   app.config["DEFAULT_WARMUP"]),
                         app.config["MIN_WARMUP"], app.config["MAX_WARMUP"])

            try:
                results = _do_benchmark(app, model_path, data_path, labels_path, bs, it, wu)
            finally:
                _maybe_cleanup(app, model_path, data_path, labels_path)

            rid = _save_result(app.config["RESULTS_FOLDER"], results)
            results["result_id"] = rid
            _maybe_retention(app)
            logger.info("Benchmark %s done — %.2fms avg", rid, results["metrics"]["avg_latency_ms"])
            return jsonify(results)

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception:
            logger.exception("Sync benchmark failed")
            return jsonify({"error": "Internal benchmark error"}), 500

    # ── Async benchmark ───────────────────────────────────────────────────
    @app.route("/api/benchmark/async", methods=["POST"])
    @rate_limited
    def run_benchmark_async():
        try:
            model_path, data_path, labels_path = _parse_files(app, request)
            bs = _clamp(_safe_int(request.form.get("batch_size"),    app.config["DEFAULT_BATCH_SIZE"]),
                        app.config["MIN_BATCH_SIZE"], app.config["MAX_BATCH_SIZE"])
            it = _clamp(_safe_int(request.form.get("num_iterations"), app.config["DEFAULT_ITERATIONS"]),
                        app.config["MIN_ITERATIONS"], app.config["MAX_ITERATIONS"])
            wu = _clamp(_safe_int(request.form.get("warmup_runs"),   app.config["DEFAULT_WARMUP"]),
                        app.config["MIN_WARMUP"], app.config["MAX_WARMUP"])

            job_id = _create_job()

            def bg():
                try:
                    _update_job(job_id, status="running", progress=5)

                    def cb(pct):
                        _update_job(job_id, progress=pct)

                    results = _do_benchmark(app, model_path, data_path, labels_path,
                                            bs, it, wu, progress_cb=cb)
                    rid = _save_result(app.config["RESULTS_FOLDER"], results)
                    results["result_id"] = rid
                    _update_job(job_id, status="done", progress=100,
                                result=results, finished_at=datetime.now().isoformat())
                    _maybe_retention(app)
                except Exception as exc:
                    logger.exception("Async job %s failed", job_id)
                    _update_job(job_id, status="error", error=str(exc),
                                finished_at=datetime.now().isoformat())
                finally:
                    _maybe_cleanup(app, model_path, data_path, labels_path)

            threading.Thread(target=bg, daemon=True).start()
            return jsonify({"job_id": job_id, "status": "pending"})

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception:
            logger.exception("Failed to start async benchmark")
            return jsonify({"error": "Internal error"}), 500

    # ── Job status ────────────────────────────────────────────────────────
    @app.route("/api/jobs/<job_id>")
    def job_status(job_id):
        job = _get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        resp = {k: v for k, v in job.items() if k != "result"}
        if job.get("status") == "done" and job.get("result"):
            resp["result_id"] = job["result"].get("result_id")
        return jsonify(resp)

    @app.route("/api/jobs/<job_id>/result")
    def job_result(job_id):
        job = _get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        if job.get("status") != "done":
            return jsonify({"error": "Job not finished yet"}), 202
        return jsonify(job.get("result", {}))

    # ── Batch-size sweep ──────────────────────────────────────────────────
    @app.route("/api/sweep", methods=["POST"])
    @rate_limited
    def batch_sweep():
        try:
            model_path, data_path, labels_path = _parse_files(app, request)
            raw = request.form.get("batch_sizes", "1,8,32,128")
            try:
                sizes = [_clamp(int(x.strip()), 1, 512)
                         for x in raw.split(",") if x.strip()][:8]
            except ValueError:
                sizes = [1, 8, 32, 128]

            it = _clamp(_safe_int(request.form.get("num_iterations"), 50), 1, 500)
            wu = _clamp(_safe_int(request.form.get("warmup_runs"), 5), 0, 50)

            try:
                data = _load_data(data_path)
                bench = ModelBenchmarker(model_path)
                sweep_data = bench.sweep(data, sizes, num_iterations=it, warmup_runs=wu)
            finally:
                _maybe_cleanup(app, model_path, data_path, labels_path)

            valid = [r for r in sweep_data if "error" not in r]
            best_tp = max(valid, key=lambda r: r["throughput_per_sec"], default=None)
            best_lt = min(valid, key=lambda r: r["avg_latency_ms"],     default=None)

            return jsonify({
                "model_type":  bench.model_type,
                "model_file":  os.path.basename(model_path),
                "sweep":       sweep_data,
                "best_throughput_batch_size": best_tp["batch_size"] if best_tp else None,
                "best_latency_batch_size":    best_lt["batch_size"] if best_lt else None,
                "timestamp":   datetime.now().isoformat(),
            })

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception:
            logger.exception("Sweep failed")
            return jsonify({"error": "Internal sweep error"}), 500

    # ── Results CRUD ──────────────────────────────────────────────────────
    @app.route("/api/results")
    def list_results():
        rows = []
        for fname in os.listdir(app.config["RESULTS_FOLDER"]):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(app.config["RESULTS_FOLDER"], fname)) as f:
                    d = json.load(f)
                d["result_id"] = fname.replace("benchmark_", "").replace(".json", "")
                d.pop("latencies",  None)
                d.pop("histogram",  None)
                rows.append(d)
            except (json.JSONDecodeError, OSError):
                continue
        rows.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return jsonify(rows)

    @app.route("/api/results/<result_id>")
    def get_result(result_id):
        result_id = secure_filename(result_id)
        p = os.path.join(app.config["RESULTS_FOLDER"], f"benchmark_{result_id}.json")
        if not os.path.exists(p):
            return jsonify({"error": "Result not found"}), 404
        with open(p) as f:
            d = json.load(f)
        d["result_id"] = result_id
        return jsonify(d)

    @app.route("/api/results/<result_id>", methods=["DELETE"])
    def delete_result(result_id):
        result_id = secure_filename(result_id)
        p = os.path.join(app.config["RESULTS_FOLDER"], f"benchmark_{result_id}.json")
        if not os.path.exists(p):
            return jsonify({"error": "Result not found"}), 404
        os.remove(p)
        return jsonify({"deleted": result_id})

    # ── Tagging ───────────────────────────────────────────────────────────
    @app.route("/api/results/<result_id>/tag", methods=["POST", "DELETE"])
    def tag_result(result_id):
        result_id = secure_filename(result_id)
        p = os.path.join(app.config["RESULTS_FOLDER"], f"benchmark_{result_id}.json")
        if not os.path.exists(p):
            return jsonify({"error": "Result not found"}), 404
        with open(p) as f:
            d = json.load(f)
        if request.method == "DELETE":
            d.pop("tag", None)
            d.pop("notes", None)
        else:
            body = request.get_json(silent=True) or {}
            if "tag" in body:
                d["tag"] = str(body["tag"])[:80]
            if "notes" in body:
                d["notes"] = str(body["notes"])[:512]
        with open(p, "w") as f:
            json.dump(d, f, indent=2)
        return jsonify({"result_id": result_id, "tag": d.get("tag"), "notes": d.get("notes")})

    # ── Compare ───────────────────────────────────────────────────────────
    @app.route("/api/compare", methods=["POST"])
    def compare_results():
        body = request.get_json(silent=True) or {}
        ids  = body.get("result_ids", [])
        if len(ids) < 2:
            return jsonify({"error": "Provide at least 2 result_ids."}), 400
        out = []
        for rid in ids[:10]:
            rid = secure_filename(rid)
            p = os.path.join(app.config["RESULTS_FOLDER"], f"benchmark_{rid}.json")
            if not os.path.exists(p):
                continue
            with open(p) as f:
                d = json.load(f)
            d["result_id"] = rid
            d.pop("latencies",  None)
            d.pop("histogram",  None)
            out.append(d)
        if len(out) < 2:
            return jsonify({"error": "Not enough results found."}), 404
        return jsonify({"comparison": out})

    # ── Export single ─────────────────────────────────────────────────────
    @app.route("/api/export/<result_id>")
    def export_result(result_id):
        result_id = secure_filename(result_id)
        p = os.path.join(app.config["RESULTS_FOLDER"], f"benchmark_{result_id}.json")
        if not os.path.exists(p):
            return jsonify({"error": "Result not found"}), 404
        with open(p) as f:
            d = json.load(f)
        flat = {**d.get("metrics", {})}
        for k, v in (d.get("accuracy_metrics") or {}).items():
            flat[f"acc_{k}"] = v
        flat.update({
            "result_id": result_id,
            "model_type": d.get("model_type"),
            "model_file": d.get("model_file"),
            "batch_size": d.get("batch_size"),
            "num_iterations": d.get("num_iterations"),
            "warmup_runs": d.get("warmup_runs"),
            "data_samples": d.get("data_samples"),
            "timestamp": d.get("timestamp"),
            "tag": d.get("tag", ""),
            "notes": d.get("notes", ""),
        })
        buf = BytesIO()
        pd.DataFrame([flat]).to_csv(buf, index=False)
        buf.seek(0)
        return send_file(buf, mimetype="text/csv", as_attachment=True,
                         download_name=f"benchmark_{result_id}.csv")

    # ── Bulk export ───────────────────────────────────────────────────────
    @app.route("/api/export/all")
    def export_all():
        rows = []
        for fname in os.listdir(app.config["RESULTS_FOLDER"]):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(app.config["RESULTS_FOLDER"], fname)) as f:
                    d = json.load(f)
                flat = {**d.get("metrics", {})}
                for k, v in (d.get("accuracy_metrics") or {}).items():
                    flat[f"acc_{k}"] = v
                flat["result_id"]     = fname.replace("benchmark_", "").replace(".json", "")
                flat["model_type"]    = d.get("model_type")
                flat["model_file"]    = d.get("model_file")
                flat["batch_size"]    = d.get("batch_size")
                flat["num_iterations"] = d.get("num_iterations")
                flat["timestamp"]     = d.get("timestamp")
                flat["tag"]           = d.get("tag", "")
                flat["notes"]         = d.get("notes", "")
                rows.append(flat)
            except (json.JSONDecodeError, OSError):
                continue
        if not rows:
            return jsonify({"error": "No results to export"}), 404
        rows.sort(key=lambda x: x.get("timestamp", ""))
        buf = BytesIO()
        pd.DataFrame(rows).to_csv(buf, index=False)
        buf.seek(0)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return send_file(buf, mimetype="text/csv", as_attachment=True,
                         download_name=f"modelbench_all_{ts}.csv")

    # ── System info ───────────────────────────────────────────────────────
    @app.route("/api/system")
    def system_info():
        info = {
            "platform":  platform.platform(),
            "python":    platform.python_version(),
            "processor": platform.processor() or "unknown",
            "frameworks": {
                "pytorch":     {"available": TORCH_AVAILABLE,   "version": TORCH_VERSION},
                "tensorflow":  {"available": TF_AVAILABLE,      "version": TF_VERSION},
                "onnx_runtime":{"available": ONNX_AVAILABLE,    "version": ONNX_VERSION},
                "sklearn":     {"available": SKLEARN_AVAILABLE, "version": SKLEARN_VERSION},
                "psutil":      {"available": PSUTIL_AVAILABLE,  "version": _psutil_ver()},
            },
        }
        if TORCH_AVAILABLE and torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
        if PSUTIL_AVAILABLE:
            vm = psutil.virtual_memory()
            info["total_ram_gb"]     = round(vm.total     / 1024**3, 1)
            info["available_ram_gb"] = round(vm.available / 1024**3, 1)
            info["cpu_count_logical"] = psutil.cpu_count(logical=True)
            info["cpu_count_physical"]= psutil.cpu_count(logical=False)
            info["cpu_freq_mhz"]      = round(psutil.cpu_freq().current, 0) if psutil.cpu_freq() else None
        return jsonify(info)

    @app.route("/health")
    def health():
        return jsonify({"status": "healthy", "version": "3.0"})


def _psutil_ver():
    try:
        return psutil.__version__
    except Exception:
        return None


# ── Error handlers ─────────────────────────────────────────────────────────────

def register_error_handlers(app: Flask):
    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large (max 100 MB)."}), 413

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found."}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error."}), 500


# ── App factory ───────────────────────────────────────────────────────────────

def create_app(config_name: str = "default") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    register_routes(app)
    register_error_handlers(app)
    return app


app = create_app(os.environ.get("FLASK_CONFIG", "default"))

if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════╗")
    print("║          ModelBench AI  v3.0                 ║")
    print("║   ML Model Performance Benchmarking          ║")
    print("╚══════════════════════════════════════════════╝\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
