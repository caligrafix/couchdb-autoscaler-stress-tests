from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream

import logging
import math

try:
    config.load_incluster_config()
except config.ConfigException:
    try:
        config.load_kube_config()
    except config.ConfigException:
        raise Exception("Could not configure kubernetes python client")


v1 = client.CoreV1Api()
appsV1Api = client.AppsV1Api()


def get_pods(namespace, label_selector=None, field_selector=None):
    """
    List pods in specific namespace and return pod list with podnames
    """
    pods = []
    logging.info(f"Listing pods in namespace: {namespace}")

    pod_list = v1.list_namespaced_pod(
        namespace, label_selector=label_selector, field_selector=field_selector)

    for pod in pod_list.items:
        logging.info("%s\t%s\t%s" % (pod.metadata.name,
                                     pod.status.phase,
                                     pod.status.pod_ip))
        pods.append(pod.metadata.name)
    return pods


def get_node_pods(namespace, label_selector, node_name):
    '''
    Return a list of pods for specific node 

    :namespace (str)        : K8s namespace, default couchdb
    :label_selector (str)   : Selector to filter pods in k8s, default app=couchdb
    :node_name (str)        : Name of K8s node

    '''
    field_selector = 'spec.nodeName='+node_name
    logging.info(f"get pods of node: {node_name}")
    pods = get_pods(namespace, label_selector=label_selector,
                    field_selector=field_selector)

    return pods


def get_nodes_pods(nodes: list):
    ''' 
    Add list of pods for nodes dictionary

    :nodes (dict): List of Dictionaries with nodes information

    Return nodes with list of pods
    '''
    for node in nodes:
        node_pods = get_node_pods(
            namespace='couchdb', label_selector='app=couchdb', node_name=node['node'])
        node['pods'] = node_pods

    return nodes


def delete_pods(pods, namespace):
    logging.info(f"Deleting PODS {pods} in namespace {namespace}")
    for pod in pods:
        try:
            v1.delete_namespaced_pod(pod, namespace)
        except ApiException as e:
            logging.info(
                "Exception when calling CoreV1Api->delete_namespaced_pod: %s\n" % e)


def watch_pods_state(pods: list, namespace: str, labels: str, desired_state: str = 'Pending'):
    '''Watch pods state and wait until they are all in the desired desired_state state

    Args:
        pods (list)             : List of pods names
        namespace (str)         : Namespace to watch pods
        labels (str)            : Labels to filter pods 
        desired_state (str)     : Desired state for pods
                                   
    '''
    
    pods_desired_status = {pod: False for pod in pods}
    pods_status = {pod: None for pod in pods}

    w = watch.Watch()
    for event in w.stream(func=v1.list_namespaced_pod,
                          namespace=namespace,
                          label_selector=labels):

        # Check if pod is in pods list
        if event['object'].metadata.name in pods:
            pod = event['object'].metadata.name
            pod_status = event['object'].status.phase
            pods_status[pod] = pod_status

        logging.info(
            f"Event: {event['type']} {event['object'].kind} {event['object'].metadata.name} {event['object'].status.phase}")

        if pods_status[pod] == desired_state:
            pods_desired_status[pod] = True

        # Check if all pods are in desired_state
        if all(pods_desired_status.values()):
            logging.info(f"All pods are in {desired_state} State")
            w.stop()
        else:
            logging.info(f"Not all pods are {desired_state}...")


def watch_pod_resurrect(pods: list, namespace: str, labels: str):
    '''Watch for pod terminating and running again

    Args:
        pods (list)             : List of pods names
        namespace (str)         : Namespace to watch pods
        labels (str)            : Labels to filter pods 
                                   
    '''
    pods_status = {pod: None for pod in pods}
    pods_terminating = {pod: False for pod in pods}
    pods_running_after_terminating = {pod: None for pod in pods}

    w = watch.Watch()
    for event in w.stream(func=v1.list_namespaced_pod,
                          namespace=namespace,
                          label_selector=labels):

        # Check if pod is in pods list
        if event['object'].metadata.name in pods:
            pod = event['object'].metadata.name
            pod_status = event['object'].status.phase
            pods_status[pod] = pod_status

        logging.info(
            f"Event: {event['type']} {event['object'].kind} {event['object'].metadata.name} {event['object'].status.phase}")

        if pods_status[pod] == 'Pending':
            pods_terminating[pod] = True

        if pods_terminating[pod] and pods_status[pod] == 'Running':
            pods_running_after_terminating[pod] = True

        # Check if all pods are in desired_state
        if all(pods_running_after_terminating.values()):
            logging.info(f"All pods are recreated and running again")
            w.stop()
        else:
            logging.info(f"Not all pods are recreated yet...")


def get_related_pod_pvc(pods: list, namespace: str):
    '''Get associated pvc to pods

    Args:
        pods (list)     : list of pods names to get his pvc information
        namespace (str) : k8s namespace to find pods and pvcs

    Returns:
        pod_pvc_info (dict): Dictionary with pod name as key, and value a list 
                            with pvc name and % of usage of his associated pv. 
                            {'pod1': ['pvc1', 0.3], 'pod2': ['pvc2', 0.5],...}
    '''
    pod_pvc_info = {}
    for pod in pods:
        pvc_info = []
        api_response = v1.read_namespaced_pod(name=pod, namespace=namespace)

        # Get name of PVC
        pvc_name = api_response.spec.volumes[0].persistent_volume_claim.claim_name
        pvc_info.append(pvc_name)

        # Get value of size PVC
        pvc_metadata = v1.read_namespaced_persistent_volume_claim(
            namespace=namespace, name=pvc_name)

        # logging.info(f'pvc_info: {pvc_metadata}')

        # pvc_size = pvc_info.spec.resources.requests['storage']
        pvc_size = pvc_metadata.status.capacity['storage']

        pvc_info.append(pvc_size)

        pod_pvc_info[pod] = pvc_info
    return pod_pvc_info


def get_namespaces_pvc(namespace):
    return v1.list_namespaced_persistent_volume_claim(namespace)


def patch_namespaced_pvc(namespace: str, pod_pvc_info: dict, resize_percentage: float):
    '''Patch pvc spec to increase the capacity of volumes

    Args:
        namespace (str)             : k8s namespace to manipulate pod and pvc objects
        pod_pvc_info (dict)         : dict with pods and related pvc info
        resize_percentage (float)   : percentage to increse size of volumes
    '''
    for pod, pvc in pod_pvc_info.items():
        pvc_size = int(pvc[1].strip('Gi'))  # Must be in Gi unit
        pvc_resize_number = int(
            math.ceil(pvc_size*(resize_percentage)))  # Upper function
        pvc_resize_value = str(pvc_resize_number)+'Gi'

        spec_body = {'spec': {'resources': {
            'requests': {'storage': pvc_resize_value}}}}

        logging.info(f"resizing {pvc[0]}-{pvc[1]} to {pvc_resize_value}")
        resize_response = v1.patch_namespaced_persistent_volume_claim(
            pvc[0], namespace, spec_body)
        
        #TODO: Add watch to PVC, catch success or error in update size EBS.

        logging.info(f"resize response: {resize_response}")

        # Delete POD associated to PVC
        # delete_pods([pod], namespace)

        # Wait until pod to Running State
        watch_pod_resurrect([pod], namespace, labels=f'app=couchdb, statefulset.kubernetes.io/pod-name={pod}')


def execute_exec_pods(exec_command: str, namespace: str, pod: str):

    resp = stream(v1.connect_get_namespaced_pod_exec, pod, namespace,
                  command=exec_command, stderr=True, stdin=False, stdout=True, tty=False)
    return resp


def get_pods_volumes_info(namespace: str, pods: list, mount_volume_path: str):
    '''Get usage's percentage of each volume associated to pods

    Args:
        namespace (str)         : namespace used for exec command in pods
        pods (list)             : list of pods names monitoring
        mount_volume_path (str) : volume path mounted inside pods

    Returns:
        pods_volumes_info (dict): Dictionary with pods and his % of
                                   volume usage {'pod1':'0.3', 'pod2':0.4,..., 'podN':0.1}.
    '''

    exec_command = ['df', '-Ph', mount_volume_path]
    pods_volumes_info = {}

    for pod in pods:
        # Execute command df inside each POD to obtain %Use of volume associated
        resp = execute_exec_pods(exec_command, namespace, pod)
        df_output_lines = [s.split() for s in resp.splitlines()]
        perc_usage = float(df_output_lines[1][4].strip('%'))/100
        pods_volumes_info[pod] = perc_usage

    return pods_volumes_info


def get_nodes():
    logging.info("Getting k8s nodes...")
    nodes = []
    nodes_iter = v1.list_node()
    for node in nodes_iter.items:
        node_info = {}
        node_info['node'] = node.metadata.name
        node_info['zone'] = node.metadata.labels['topology.kubernetes.io/zone']
        nodes.append(node_info)

    return nodes
