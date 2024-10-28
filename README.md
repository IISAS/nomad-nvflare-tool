# ai4os-nvflare-test

## Prerequisities
1. Docker (for deploying clients locally)
2. [oidc-agent](https://github.com/indigo-dc/oidc-agent) (follow the [guide](https://github.com/ai4os/ai4-papi/tree/nvflare?tab=readme-ov-file#generate-a-token-via-the-terminal) on generating token via the terminal)
3. [PAPI - nvflare branch](https://github.com/ai4os/ai4-papi/tree/nvflare) (for deploying NVFLARE Dashboard and FL server in Nomad cluster)
4. Python 3.10

## Configuration

### PAPI
Copy [`papi.json.template`](papi.json.template) as `papi.json` and adjust the connection settings.

### Nomad Job
Copy [`job.json.template`](job.json.template) as `job.json` and adjust it. Set the `password` for the NVFLARE Dashboard project admin and `jupyter_password` for the JupyterLab service running in the NVFLARE FL Server container.

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
./tool_nvflare.py --cfg-papi papi.json --cfg-job job.json job --start
```
This will deploy and start NVFLARE Dashboard and NVFLARE server autmatically via PAPI and the corresponding Nomad job ID will be returned on success. Copy the id and use it in following commands.

### 2. Deploy Scenario
```commandline
./tool_nvflare.py --cfg-papi papi.json --cfg-job job.json scenario --jobid ${JOB_ID} --init --download --start
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
./fl_admin.sh 
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

### Running a sample FL job
We will use an official NVFLARE [hello-world-sag](https://github.com/NVIDIA/NVFlare/tree/main/examples/hello-world/hello-numpy-sag) FL application.

#### Prerequisities
* FL server and clients are deployed and running
* project admin can log into the NVFLARE FL admin console

#### Prepare the job
Copy the [`./fl_apps/hello-numpy-sag/`](./fl_apps/hello-numpy-sag/) into extracted NVFLARE console transfer folder [`./admin/transfer/`](./admin/transfer/) and adjust its configuration to your needs:
```commandline
cp -r ./fl_apps/hello-numpy-sag/ ./admin/
```

#### Submit the job
Log into the NVFLARE FL admin console and submit the `hello-numpy-sag` job:
```commandline
cd ./admin/startup
./fl_admin.sh 
User Name: admin
Trying to obtain server address
Obtained server address: cb997d5a-929e-11ef-9381-0f58767684e9-server.ifca-deployments.cloud.ai4eosc.eu:8003
Trying to login, please wait ...
Logged into server at cb997d5a-929e-11ef-9381-0f58767684e9-server.ifca-deployments.cloud.ai4eosc.eu:8003 with SSID: ebc6125d-0a56-4688-9b08-355fe9e4d61a
Type ? to list commands; type "? cmdName" to show usage of a command.
> submit_job hello-numpy-sag
Submitted job: e932cf0d-3908-4b2c-96f0-2ffdb9708de5
Done [316984 usecs] 2024-10-25 12:10:47.055917
```

#### List the jobs and check the submitted job is running
```commandline
> list_jobs 
-----------------------------------------------------------------------------------------------------------------------------------
| JOB ID                               | NAME            | STATUS             | SUBMIT TIME                      | RUN DURATION   |
-----------------------------------------------------------------------------------------------------------------------------------
| e932cf0d-3908-4b2c-96f0-2ffdb9708de5 | hello-numpy-sag | RUNNING            | 2024-10-25T10:10:46.960484+00:00 | 0:00:09.181133 |
-----------------------------------------------------------------------------------------------------------------------------------
Done [186609 usecs] 2024-10-25 12:10:56.605332

```

#### Checking the job meta after it's finished
```commandline
> get_job_meta e932cf0d-3908-4b2c-96f0-2ffdb9708de5
{
  "name": "hello-numpy-sag",
  "resource_spec": {},
  "min_clients": 8,
  "deploy_map": {
    "app": [
      "@ALL"
    ]
  },
  "submitter_name": "admin",
  "submitter_org": "",
  "submitter_role": "project_admin",
  "job_folder_name": "hello-numpy-sag",
  "job_id": "e932cf0d-3908-4b2c-96f0-2ffdb9708de5",
  "submit_time": 1729851046.960484,
  "submit_time_iso": "2024-10-25T10:10:46.960484+00:00",
  "start_time": "2024-10-25 10:10:47.402870",
  "duration": "0:01:08.576837",
  "data_storage_format": 2,
  "status": "FINISHED:COMPLETED",
  "job_deploy_detail": [
    "server: OK",
    "org1-site-1: OK",
    "org1-site-2: OK",
    "org1-site-5: OK",
    "org1-site-3: OK",
    "org1-site-4: OK",
    "org2-site-1: OK",
    "org2-site-2: OK",
    "org3-site-1: OK"
  ],
  "schedule_count": 1,
  "last_schedule_time": 1729851047.1672068,
  "schedule_history": [
    "2024-10-25 10:10:47: scheduled"
  ]
}
Done [182111 usecs] 2024-10-25 12:13:03.511191
```

#### Other job outputs
```commandline
ls -al ./org1/org1-site-1/e932cf0d-3908-4b2c-96f0-2ffdb9708de5/model
total 12
drwxr-xr-x 2 stevo stevo 4096 okt 25 12:10 .
drwxr-xr-x 4 stevo stevo 4096 okt 25 12:11 ..
-rw-r--r-- 1 stevo stevo  164 okt 25 12:11 best_numpy.npy
```
