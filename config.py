"""
ModelBench AI v3.0 — Configuration
"""
import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    RESULTS_FOLDER = os.path.join(BASE_DIR, 'results')

    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB

    # Benchmark params
    DEFAULT_BATCH_SIZE = 1
    DEFAULT_ITERATIONS = 100
    DEFAULT_WARMUP = 10
    MAX_BATCH_SIZE = 1024
    MAX_ITERATIONS = 10000
    MAX_WARMUP = 100
    MIN_BATCH_SIZE = 1
    MIN_ITERATIONS = 1
    MIN_WARMUP = 0

    # Allowed formats
    ALLOWED_MODEL_EXTENSIONS = {'.pkl', '.pt', '.pth', '.h5', '.onnx'}
    ALLOWED_DATA_EXTENSIONS  = {'.csv', '.npy', '.npz'}
    ALLOWED_LABELS_EXTENSIONS = {'.csv', '.npy'}

    # Cleanup
    AUTO_CLEANUP_UPLOADS = True

    # Result retention: auto-delete JSON files older than this many days (None = off)
    RESULT_RETENTION_DAYS = 30

    # Rate limiting: max benchmark calls per IP per window
    RATE_LIMIT_MAX_CALLS = 10
    RATE_LIMIT_WINDOW_SECONDS = 60

    @staticmethod
    def init_app(app):
        os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)
        os.makedirs(app.config.get('RESULTS_FOLDER', 'results'), exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    RATE_LIMIT_MAX_CALLS = 5


class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    MAX_ITERATIONS = 10
    RESULT_RETENTION_DAYS = None


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig,
}
