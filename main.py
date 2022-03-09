# External libraries
import sys
import time
import logging

# Internal code
from src.scenarios import *
from src.envs import *


def main():
    args = sys.argv[1:]

    if len(args) == 2 and args[0] == '--scenario':
        scenario = int(args[1])
        logging.info(f'scenario: {scenario}')

        if scenario == 0:
            scenario_0_populate_couchdb(
                couchdb_url, n_rows, n_it, db_names)

        elif scenario == 1:
            scenario_1_delete_all_pods(
                couchdb_url, namespace, n_rows, db_names, pods)

        elif scenario == 2:
            logging.info(f"-----------------------------------")
            logging.info(f"Scenario 2: delete pod-0, and pod-1")
            scenario_2_delete_some_pods(
                couchdb_url, namespace, n_rows, db_names, pods[0:-1])
            logging.info(f"Sleeping 30 seconds")
            time.sleep(30)
            logging.info(f"-----------------------------------")
            logging.info(f"Scenario 2: delete pod-1, and pod-2")
            scenario_2_delete_some_pods(
                couchdb_url, namespace, n_rows, db_names, pods[1:]
            )
            logging.info(f"Sleeping 30 seconds")
            time.sleep(30)
            logging.info(f"-----------------------------------")
            logging.info(f"Scenario 2: delete pod-0")
            scenario_2_delete_some_pods(
                couchdb_url, namespace, n_rows, db_names, [pods[0]]
            )
            logging.info(f"Sleeping 30 seconds")
            time.sleep(30)
            logging.info(f"-----------------------------------")
            logging.info(f"Scenario 1: delete pod-1")
            scenario_2_delete_some_pods(
                couchdb_url, namespace, n_rows, db_names, [pods[1]]
            )
            logging.info(f"Sleeping 30 seconds")
            time.sleep(30)
            logging.info(f"-----------------------------------")
            logging.info(f"Scenario 2: delete pod-2")
            scenario_2_delete_some_pods(
                couchdb_url, namespace, n_rows, db_names, [pods[2]]
            )
            logging.info("Finished scenario 2")

        elif scenario == 3:
            scenario_3_resize_pvc(
                namespace, pods)

        elif scenario == 4:
            scenario_4_stress_couchdb(
                couchdb_url, n_rows, n_it, clear=True)

        elif scenario == 5:
            create_and_query_views(
                couchdb_url, database="db1", n_querys=1
            )

    else:
        raise Exception(
            "You must provide --scenario as first argument")


if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logging.getLogger('faker').setLevel(logging.ERROR)
    logging.getLogger('kubernetes').setLevel(logging.ERROR)
    logging.getLogger("PIL.Image").setLevel(logging.CRITICAL + 1)
    main()
