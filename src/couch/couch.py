import couchdb
import logging
import random
import requests
import time

from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pprint import pprint
from faker import Faker
from operator import itemgetter


def get_couch_client(url):
    """Initialize the server object.

        :param url: the URI of the server (for example
                    ``http://localhost:5984/``)
    """
    try:
        logging.info(f"Connecting to couchdb server")
        couchdb_client = couchdb.Server(url)
        return couchdb_client
    except Exception as e:
        logging.info(f"Error connecting to couch: {e}")
        raise Exception(
            "Error connecting to couchdb")


def get_database_info(couchdb_client):
    for db in couchdb_client:
        logging.info(f"db: {db}")
        logging.info(f"{db}_total_rows: {couchdb_client[db].info()}")


def select_or_create_db(couchdb_client, db_name):
    while True:
        try:
            if db_name in couchdb_client:
                db = couchdb_client[db_name]
            else:
                try:
                    db = couchdb_client.create(db_name)
                except Exception as error:
                    logging.info(f"Exception: {error}, database '{db_name}' already created")
                    db = couchdb_client[db_name]

        except couchdb.http.ServerError as e:
            logging.info(f'Exception {e}, trying again...')
            continue
        break

    return db


def generate_random_data(n_rows):
    data = []
    fake = Faker('it_IT')
    fake.seed_instance(54321)

    for _ in range(n_rows):
        doc = {'name': fake.name(),
               'address': fake.address(),
               'date': fake.date(),
               'phone_number': fake.phone_number(),
               'email': fake.ascii_company_email(),
               'cordinates': str(fake.latlng()),
               'age': random.randint(1, 30),
               'image': str(fake.image(size=(2, 2), hue='purple', luminosity='bright', image_format='pdf'))}

        data.append(doc)
    return data


def populate_db(db, data):
    count=0
    while True:
        count+=1
        try:
            logging.info(f"retry: {count}")
            db.update(data)
        except Exception as e:
            logging.info(f"exception: {e}")
            logging.info(f"sleep: 10")
            time.sleep(10)
            continue
        break
    return


def populate_dbs(couchdb_client, db_names, fake_data):

    for db_name in db_names:
        # logging.info(f"Attempt to populate DB")
        db = select_or_create_db(couchdb_client, db_name)
        populate_db(db, fake_data)


def clear_dbs(couchdb_client):
    for db in couchdb_client:
        logging.info(f"deleting {db}")
        couchdb_client.delete(db)


def compare_data(couchdb_client, fake_data):
    """
    Compare data between dbs in couchDB and mock data generated by Faker
    """
    # Connect couchdb
    logging.info("In compare data")
    couchdb_data_dict = {}
    attempts = 0

    while attempts < 10:
        logging.info(f"Retry number {attempts}...")
        try:
            for db in couchdb_client:
                db = couchdb_client[db]
                db_docs_list = []
                for item in db.view('_all_docs', include_docs=True):
                    doc = {
                        'name': item.doc['name'],
                        '_id': item.doc['_id'],
                        '_rev': item.doc['_rev']
                    }
                    db_docs_list.append(doc)
                couchdb_data_dict[db.name] = db_docs_list

            for db in couchdb_client:
                # Create lists ordered by _id
                fake_data, couchdb_data = [sorted(l, key=itemgetter(
                    '_id')) for l in (fake_data, couchdb_data_dict[db])]

                pairs = zip(fake_data, couchdb_data)

                # True -> Have differences between pairs
                if(any(x != y for x, y in pairs)):
                    logging.info(
                        f"There are differences between random_data and couchdb_{db}_data")
                    differences = [(x, y) for x, y in pairs if x != y]
                    pprint(differences, width=1)

                else:
                    logging.info(f"Data persisted as expected.")
            break
        except Exception as e:
            logging.info(f"Exception: {e}")
            attempts += 1
            logging.info("Sleeping 30 seconds and retrying")
            time.sleep(30)


def tag_cluster_nodes(couchdb_url: str, nodes_with_pods: list):
    '''
    Tag couchdb cluster nodes (pods) with zone attribute

    :zone (str) : zone of node that pod is allocated
    :pods (list): list of couchdb nodes
    '''
    url_string = couchdb_url+'_node/_local/_nodes/'

    s = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 404 ])
    s.mount(url_string, HTTPAdapter(max_retries=retries))

    for node in nodes_with_pods:
        zone = node['zone']
        node_name = node['node']
        pods = node['pods']
        logging.info(f"tagging nodes on {node_name} with zone {zone}")
        for pod in pods:
            full_url = url_string + f"couchdb@{pod}.couchdb-couchdb.couchdb.svc.cluster.local"

            #Step 0
            res0 = requests.get(full_url).json()

            #Step 1
            payload = {
                "_id" : res0["_id"],
                "_rev": res0["_rev"],
                "zone": zone
            }

            # try:
            res_put = requests.put(full_url, json=payload, params={'w':24})
            res_put.raise_for_status()
            logging.info(f"update node res: {res_put.json()}")
            # Get latest rev to find the updated doc 
            last_rev = res_put.json()['rev']
       
            #Step 2
            res_final_get = s.get(full_url, params={'rev': last_rev})
            #TODO Verificar zone 
            res_final_get.raise_for_status()
            logging.info(f'node doc after tagging: {res_final_get.json()}')
            logging.info(f'node doc after tagging: {res_final_get.status_code}')


def finish_cluster_setup(couchdb_url: str):
    '''Make http request to finish cluster setup

    Args:
        couchdb_url (str): URL String CouchDB
    '''

    url_string = couchdb_url+'_cluster_setup'
    headers = {"content-type": "application/json"}
    payload = '{"action": "finish_cluster"}'

    s = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 404 ])
    s.mount(url_string, HTTPAdapter(max_retries=retries))

    res = s.post(url_string, headers=headers, data=payload)
    res.raise_for_status()
    logging.info(f'finish cluster setup response: {res.json()}')


def create_view(couchdb_url: str, view_name: str, view_string: str, database: str):

    #Delete view if exists
    view_query = f"{couchdb_url}{database}/_design/{view_name}"
    logging.info(f"view_query: {view_query}")
    view_request = requests.get(view_query)
    
    if view_request.status_code == 200:
        view_rev = view_request.json()['_rev']
        delete_query = f"{view_query}?rev={view_rev}"
        logging.info(delete_query)
        del_view = requests.delete(delete_query)
        logging.info(f"deleting view: {del_view.text}")
        del_view.raise_for_status()

    #Create view
    # view = '{"views":{"order_by_date":{"map":"function(doc) { if(doc.date && doc.name) { emit(doc.date, doc.name); }}"}}}'

    res_put = requests.put(f"{couchdb_url}{database}/_design/{view_name}", data=view_string)
    res_put.raise_for_status()
    logging.info(f"creation view result: {res_put.json()}")


def query_view(couchdb_url: str, view_name: str, database: str, threads: int):
    view_url = f"{couchdb_url}{database}/_design/{view_name}/_view/{view_name}"

    logging.info(f"query view {threads} times")
    if threads == 1:
        count=0
        while True:
            count+=1
            try:
                logging.info(f"Attempt N°{count}")
                get_view_result = requests.get(view_url)
                if get_view_result.status_code != 200:
                    logging.info(f"Error {get_view_result.status_code} in {get_view_result.url}")
                    raise Exception(f"Error {get_view_result.status_code}")
            except Exception as e:
                logging.info(f"exception: {e}")
                logging.info(f"Pods are down? - sleep: 10")
                time.sleep(10)
                continue
            break
        logging.info(f"request was completed in {get_view_result.elapsed.total_seconds()} seconds {get_view_result.url}")





    # else:    
    #     THREAD_POOL = threads
    #     session = requests.Session()
    #     session.mount(
    #         'http://', HTTPAdapter(pool_maxsize=THREAD_POOL,
    #                             max_retries=3,
    #                             pool_block=True)
    #     )

    #     def get(url):
    #         response = session.get(url)
    #         logging.info(f"request was completed in {response.elapsed.total_seconds()} seconds {response.url}")
    #         if response.status_code != 200:
    #             logging.error(f"Error {response.status_code} in {response.url}")
    #         return response
               
    #     count=0
    #     while True:
    #         try:
    #             count+=1
    #             logging.info(f"Request Views N°{count}")
    #             with ThreadPoolExecutor(max_workers=THREAD_POOL) as executor:
    #                 for response in list(executor.map(get, [view_url])):
    #                     if response.status_code == 200:
    #                         logging.info(f"response: Success")
    #         except Exception as e:
    #             logging.info(f"exception: {e}")
    #             logging.info(f"Pods are down? - sleep: 10")
    #             time.sleep(10)
    #             continue
    #         break

    #     logging.info(f"Finish query {threads} times view through times")




