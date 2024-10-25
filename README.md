# ai4os-nvflare-test

## Prerequisities
1. Docker (for deploying clients locally)
2. PAPI (for deploying NVFLARE Dashboard and FL server in Nomad cluster)
3. Python 3.10

## Configuration

### PAPI
Copy [`papi.json.template`](papi.json.template) as `papi.json` and adjust the connection settings.

### Nomad Job
Copy [`job.json.template`](job.json.template) as `job.json` and adjust it. Set the `password` for the NVFLARE Dashboard project admin and `jupyter_password` for the JupyterLab service running in the NVFLARE Dashboard container.

### FL scenario
Copy the [`scenario.json.template`](scenario.json.template) as `scenario.json` and configure. This is the main configuration file for defining the FL scenario; i.e., organizations and their client sites within the federation.

#### Organizations
Define organizations in the FL scenario in the `"organizations": {ORGANIZATION, ...}` dict. Here, keys are used as the names of organizations.

#### Users
Users of particular organizations can be defined in `"organizations": {"orgX": {"users": [USER, ...]}}`, where `USER` is in the following form:
```json lines
{
  "email": "admin@{organization}.eu",
  "password": "password",
  "name": "admin",
  "role": "org_admin",
  "organization": "{organization}"
}
```

The `email` is used for logging into the NVFLARE Dashboard and must be unique within the whole NVFLARE project / scenario. Each organization should have a user with `org_admin` role.

*Note the `{organization}`. It is a placeholder replaced at runtime by the name of the organization.*

#### Clients
Clients of particular organizations can be defined in `"organizations": {"orgX": {"clients": [CLIENT, ...]}}`, where `CLIENT` is in the following form:
```json lines
{
  "organization": "{organization}",
  "capacity": {
    "num_of_gpus": 0,
    "mem_per_gpu_in_GiB": 0
  }
}
```

*Note the `{organization}`. It is a placeholder replaced at runtime by the name of the organization.*

#### Override conf values
Use the `"organizations": { "orgX": {"override": { "user": USER}, "client": CLIENT}` to override and set common parameters within an organization. Placeholder `{organization}` can be used in values as well here.

## Deploying

### 1. Start Nomad job
```commandline
./tool-nvflare.py --cfg-papi papi.json --cfg-job job.json job --start
```
This will deploy and start NVFLARE Dashboard and NVFLARE server autmatically via PAPI and the corresponding Nomad job ID will be returned on success. Copy the id and use it in following commands.

### 2. Deploy Scenario
```commandline
./tool-nvflare.py scenario --cfg-papi papi.json --cfg-job job.json --jobid ${JOB_ID} --init --download --start
```
This will setup all the organizations, users, and clients in the NVFLARE Dashboard, download NVFLARE console as well all the client startup scripts, and execute clients via Docker.

## Accessing NVFLARE FL admin console
```commandline
cd ./admin/startup
./fl_admin.sh
```

### Check connected clients
In the NVFLARE FL admin console run:
```commandline
check_status server
check_status clients
```

Example output:
````commandline
$ ./fl_admin.sh 
User Name: admin
Trying to obtain server address
Obtained server address: cb997d5a-929e-11ef-9381-0f58767684e9-server.ifca-deployments.cloud.ai4eosc.eu:8003
Trying to login, please wait ...
Logged into server at cb997d5a-929e-11ef-9381-0f58767684e9-server.ifca-deployments.cloud.ai4eosc.eu:8003 with SSID: ebc6125d-0a56-4688-9b08-355fe9e4d61a
Type ? to list commands; type "? cmdName" to show usage of a command.
> check_status server
Engine status: stopped
---------------------
| JOB_ID | APP NAME |
---------------------
---------------------
Registered clients: 8 
---------------------------------------------------------------------------------
| CLIENT      | TOKEN                                | LAST CONNECT TIME        |
---------------------------------------------------------------------------------
| org1-site-1 | 2727de99-ccfb-4863-a2fb-c24b53651b8f | Fri Oct 25 08:12:44 2024 |
| org1-site-2 | 8d1109fe-6f74-4445-8810-0f5570d83f09 | Fri Oct 25 08:12:44 2024 |
| org1-site-5 | 44f64ff9-ab27-4f5f-837b-5234f97cf1a3 | Fri Oct 25 08:12:44 2024 |
| org1-site-3 | 58158c07-eb13-4ab7-a37f-fffe4ab60f0c | Fri Oct 25 08:12:44 2024 |
| org1-site-4 | a57ef220-dbd7-4191-96ff-d3d56f66c7a7 | Fri Oct 25 08:12:44 2024 |
| org2-site-1 | 406ce6b5-a726-42ad-ae96-6505fd3e21b2 | Fri Oct 25 08:12:44 2024 |
| org2-site-2 | 91a95a45-fe7a-495c-89c7-f447a5087945 | Fri Oct 25 08:12:44 2024 |
| org3-site-1 | 17917a78-ff58-43fc-af30-2ce1fd9c9de0 | Fri Oct 25 08:12:45 2024 |
---------------------------------------------------------------------------------
Done [185263 usecs] 2024-10-25 10:12:52.127494
> check_status client
---------------------------------------------
| CLIENT      | APP_NAME | JOB_ID | STATUS  |
---------------------------------------------
| org1-site-1 | ?        | ?      | No Jobs |
| org1-site-2 | ?        | ?      | No Jobs |
| org1-site-5 | ?        | ?      | No Jobs |
| org1-site-3 | ?        | ?      | No Jobs |
| org1-site-4 | ?        | ?      | No Jobs |
| org2-site-1 | ?        | ?      | No Jobs |
| org2-site-2 | ?        | ?      | No Jobs |
| org3-site-1 | ?        | ?      | No Jobs |
---------------------------------------------
Done [232817 usecs] 2024-10-25 10:12:56.727239
>
````
