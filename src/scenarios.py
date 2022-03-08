import io
import logging

from requests_threads import AsyncSession
from tqdm import tqdm
from src.couch.couch import *
from src.k8s.k8s import *


class TqdmToLogger(io.StringIO):
    """
        Output stream for TQDM which will output to logger module instead of
        the StdOut.
    """
    logger = None
    level = None
    buf = ''

    def __init__(self, logger, level=None):
        super(TqdmToLogger, self).__init__()
        self.logger = logger
        self.level = level or logging.INFO

    def write(self, buf):
        self.buf = buf.strip('\r\n\t ')

    def flush(self):
        self.logger.log(self.level, self.buf)


def scenario_0_populate_couchdb(couchdb_url: str, n_rows: int, n_it: int, db_names: list, clear: bool = False):
    '''Scenario 0 - Populate COUCHDB Cluster

    Args:
        couchdb_url (str): CouchDB URL Connection
        n_rows (int): Number of rows to insert in DBs
        n_it (int): Number of iterations to insert data in DBs
        db_names (list): Names of the dbs to insert data
    '''
    logging.info(f"Executing scenario 0, populate databases")
    logging.info(f"N_ROWS: {n_rows} - N_IT: {n_it}")
    logger = logging.getLogger()
    tqdm_out = TqdmToLogger(logger, level=logging.INFO)

    couchdb_client = get_couch_client(couchdb_url)

    if clear:
        clear_dbs(couchdb_client) 

    for i in tqdm(range(n_it), file=tqdm_out, mininterval=30,):
        fake_data = generate_random_data(n_rows)
        populate_dbs(couchdb_client, db_names, fake_data)


def scenario_1_delete_all_pods(couchdb_url, namespace, n_rows, db_names, pods):
    """Scenario 1:

    - Clear dbs
    - Create couchdb databases (or select the created ones)
    - Populate with mock data
    - Get pods and load in list
    - Delete all pods in namespace

    :param Object couchdb_url: CouchDB Client Object
    :param str namespace: Kubernetes namespace
    :param int n_rows: Number of rows to insert in DBs
    :param list db_names: Names of the dbs to insert data
    :param list pods: Pod names to manipulate 
    :return: True or false
    """
    logging.info(f"executing scenario 1")

    # Get couchdb Client
    couchdb_client = get_couch_client(couchdb_url)

    # Clear DBS
    clear_dbs(couchdb_client)

    # Generate mock data
    fake_data = generate_random_data(n_rows)

    # Populate dbs with mock data
    populate_dbs(couchdb_client, db_names, fake_data)

    # Delete pods
    delete_pods(pods, namespace)

    # Compare data with the database data
    compare_data(couchdb_client, fake_data)


def scenario_2_delete_some_pods(couchdb_url, namespace, n_rows, db_names, pods):
    """Scenario 2:

        Delete some pods and verify if we can read and write in couchdb

    Steps:
    - Get Couchdb Client
    - Get database initial Info
    - Generate faker data
    - Delete pods
    - Watch for pods states
    - Insert data in couchdb when pods are down
    """
    logging.info(f"executing scenario 2")

    # Get couchdb Client
    couchdb_client = get_couch_client(couchdb_url)

    logging.info(f"Get database initial info:")
    get_database_info(couchdb_client)

    data = generate_random_data(n_rows)

    delete_pods(pods, namespace)

    watch_pods_state(pods, namespace)

    populate_dbs(couchdb_client, db_names, data)

    logging.info(f"Get database final info:")
    get_database_info(couchdb_client)


def scenario_3_resize_pvc(namespace, pods, VOLUME_RESIZE_PERCENTAGE):
    '''Resize pvc associate to a specific pods

    Args:
        namespace (str)                 : k8s namespace to find pods
        pods (list)                     : list of pods names to resize his PVC
        VOLUME_RESIZE_PERCENTAGE (float): % of volume to increase capacity

    Steps:
        - Edit associate PVC to a pods:
        - Edit spec.resources.requests.storage attribute
        - Terminate Pod
        - Watch status of pod and get new values to storage capacity

    '''

    logging.info(f"executing scenario 3")

    # Get PVC Of Pods
    pods_pvc_info = get_related_pod_pvc(pods, namespace)

    # Patch PVC
    logging.info(f"Patching PVC...")
    patch_namespaced_pvc(namespace, pods_pvc_info, VOLUME_RESIZE_PERCENTAGE)


def scenario_4_stress_couchdb(couchdb_url, n_rows, n_it, clear=True):
    # Create views in couchdb to stress cpu consumption
    couch_client = get_couch_client(couchdb_url)

    db_names = [f'python{i}' for i in range(19)]
    fake_data = generate_random_data(n_rows)

    while n_it > 0:
        if clear:
            clear_dbs(couch_client)
        populate_dbs(couch_client, db_names, fake_data)
        n_it -= 1
        logging.info(f"generated faked data: {n_it}")
    # logging.info(map_fun)


async def create_and_query_views(couchdb_url, database, n_querys):
    '''
    Algorithm

    Prerequisites: Scenario 0 is executed and CouchDB is populated.

    1. Create follow view
        function(doc){
            if(doc.date && doc.name){
                emit(doc.date, doc.name);
            }
        }
    2. Query a view 
    '''

    create_view(couchdb_url, database)

    session = AsyncSession(n=n_querys)

    session.run(query_view(couchdb_url, database, n_querys, session))
