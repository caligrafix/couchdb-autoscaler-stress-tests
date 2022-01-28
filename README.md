# CouchDB k8s Cluster Stress Tests

A set of scenarios to test resilience of Couchdb Cluster 

Table of Contents
  - [Repository Structure](#repository-structure)
  - [Stress Tests](#stress-tests)
  - [Placement Tagging Script](#placement-tagging-script)
  - [Volumes Monitor Script](#volumes-monitor-script)

## Repository Structure
    .
    ├── src                   # Principal Code
    │   ├── couch             # Couchdb Functions
    │   ├── k8s               # Kubernetes Functions
    │   ├── envs.py           # Kubernetes Functions
    │   ├── scenarios.py      # Stress Tests scenarios
    │   ├── scripts.py        # Initialization Script and Monitor Volumes Script
    ├── Dockerfile            # To build this image
    ├── main.py               # Main file 


## Stress Tests 
Stress Tests Scenarios to demostrate Resilience in Couchdb Cluster.
| # | Scenario         | Objective                                                |
|---|------------------|----------------------------------------------------------|
| 0 | Populate CouchDB | Stress Couchdb populating fake data                      |
| 1 | Delete All Pods  | Resilience of Couchdb after deleting all pods of cluster |
| 2 | Delete Some Pods | Writing couchdb data while some pods are down            |
| 3 | Resize PVC       | Resize PVC of specific pods                              |


# How to Run Tests

On the kubernetes cluster that CouchDB is deployed, 
apply the manifest file `stress-test.yaml` overriding container args 
to run different scenarios (0, 1, 2, 3 are supported).

```console
foo@bar:~$ kubectl apply -f stress-test.yaml 
```


