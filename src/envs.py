import os

from dotenv import load_dotenv

load_dotenv()

# Load env vars
namespace = os.getenv('EKS_NAMESPACE')
couchdb_user = os.getenv('adminUsername')
couchdb_password = os.getenv('adminPassword')
couchdb_svc = os.getenv('COUCHDB_SVC')
couchdb_port = os.getenv('COUCHDB_PORT')
db_names = [i for i in os.environ.get("COUCHDB_DB_NAMES").split(" ")]
couchdb_url = f"http://{couchdb_user}:{couchdb_password}@{couchdb_svc}:{couchdb_port}/"
n_rows = int(os.getenv('COUCHDB_INSERT_ROWS'))
pods = [pod for pod in os.environ.get("POD_NAMES").split(" ")]
n_it = int(os.getenv('COUCHDB_N_IT'))
VOLUME_THRESHOLD = float(os.getenv('VOLUME_THRESHOLD'))
VOLUME_RESIZE_PERCENTAGE = float(os.getenv('VOLUME_RESIZE_PERCENTAGE'))
MOUNT_VOLUME_PATH = os.getenv('VOLUME_MOUNT_PATH')