#!/usr/bin/env python3
import re
import sys
import logging
import tempfile

from urllib.parse import urljoin
from requests import Response

logging.basicConfig(
    format='%(asctime)s | %(name)s | %(levelname)s : %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger('tool-nvflare')

import argparse
import cgi
import json
import os
import requests
import subprocess
import time


def load_config(file: str) -> dict:
    logger.debug(f'loading configuration: {file}')
    with open(file, mode='r') as f:
        return json.load(f)


def expand_vars(x: list | dict, vars: dict = {}):
    if isinstance(x, dict):
        for k, v in x.items():
            if isinstance(v, list | dict):
                x[k] = expand_vars(v, vars)
            if isinstance(v, str):
                for var, replacement in vars.items():
                    x[k] = v.replace(var, replacement)
    elif isinstance(x, list):
        for i in range(len(x)):
            x[i] = expand_vars(x[i], vars)
    return x

def expand_vars_and_override(x: list | dict, d_override: dict = {}, vars: dict = {}):
    x = expand_vars(x, vars)
    d_override = expand_vars(d_override, vars)
    if isinstance(x, list):
        for i in range(len(x)):
            x[i].update(d_override)
    elif isinstance(x, dict):
        x.update(d_override)
    return x


def wait_for_url(url: str, status_code: int = 200, num_retries: int = -1):
    attempt = 0
    while requests.get(url).status_code != status_code:
        attempt+=1
        if -1 < num_retries < attempt:
            raise Exception(f'url check for response code {status_code} failed after {attempt}/{num_retries} attempts')
        if attempt == 1:
            logger.info('waiting for NVFLARE Dashboard to be ready')
        print('.', end='', sep='', file=sys.stdout, flush=True)
        time.sleep(1)
    if attempt > 0:
        print()


class PAPIClient:

    def __init__(
            self,
            host: str,
            oidc_account: str,
            tool_name: str = 'ai4os-nvflare',
            vo: str = 'vo.ai4eosc.eu',
            **kwargs
    ):
        self.host = host.rstrip('/')
        self.oidc_account = oidc_account
        self.tool_name = tool_name
        self.vo = vo

    def __get_access_token(self):
        access_token = subprocess.run(['oidc-token', self.oidc_account], capture_output=True, text=True).stdout.strip()
        logger.debug(f'access-token: {access_token}')
        return access_token

    def get(
            self,
            path: str = '',
            headers: dict = {},
            params: dict = {}
    ):
        url = self.host + path
        logger.debug(f'url: {url}')

        _headers = {
            'Authorization': f'Bearer {self.__get_access_token()}',
            'Content-Type': 'application/json'
        }
        _headers.update(headers)
        logger.debug(f'headers: {_headers}')

        _params = {}
        _params.update(params)
        logger.debug(f'params: {_params}')

        r = requests.get(
            url,
            headers=_headers,
            params=_params,
        ).json()
        logger.debug(f'r:\n{json.dumps(r, indent=2)}')
        return r

    def post(
            self,
            path: str = '',
            headers: dict = {},
            params: dict = {},
            data: dict = {}
    ):
        url = self.host + path
        logger.debug(f'url: {url}')

        _headers = {
            'Authorization': f'Bearer {self.__get_access_token()}',
            'Content-Type': 'application/json'
        }
        _headers.update(headers)
        logger.debug(f'headers: {_headers}')

        _params = {}
        _params.update(params)
        logger.debug(f'params: {_params}')

        _data = {}
        _data.update(data)
        logger.debug(f'data: {_data}')

        r = requests.post(
            url,
            headers=_headers,
            params=_params,
            data=json.dumps(_data)
        ).json()
        logger.debug(f'r:\n{json.dumps(r, indent=2)}')
        return r

    def deploy_tool_nvflare(
            self,
            **cfg: dict
    ):
        logger.debug(f'PAPIClient.deploy_tool_nvflare(tool_name={self.tool_name}, vo={self.vo}, **cfg={cfg})')

        params={
            'tool_name': self.tool_name,
            'vo': self.vo
        }
        logger.debug(f'params:\n{json.dumps(params, indent=2)}')

        data={
            "general": {
                "nvfl_server_jupyter_password": "",
                "nvfl_dashboard_username": "",
                "nvfl_dashboard_password": "",
                "nvfl_dashboard_project_short_name": "",
                "nvfl_dashboard_project_title": "",
                "nvfl_dashboard_project_description": "",
                "nvfl_dashboard_project_app_location": "",
                "nvfl_dashboard_project_starting_date": "",
                "nvfl_dashboard_project_end_date": "",
                "nvfl_dashboard_project_public": False,
                "nvfl_dashboard_project_frozen": False
            },
            "storage": {
                "rclone_user": "",
                "rclone_password": ""
            }
        }
        # map configuration from json file to the tool's in PAPI
        for subconf in ['dashboard', 'server']:
            cfg_dashboard=cfg[subconf]
            for k,v in cfg_dashboard.items():
                data['general']['nvfl_%s_%s' % (subconf,k)]=v
        logger.debug(f'data:\n{json.dumps(data, indent=2)}')

        r = self.post(
            path='/v1/deployments/tools/',
            params=params,
            data=data
        )
        if 'status' in r.keys() and r['status'] == 'success':
            return r['job_ID']
        raise Exception(r)

    def get_job_endpoints(
            self,
            job_ID: str,
            full_info: bool = False
    ):
        r = self.get(
            path=f'/v1/deployments/tools/{job_ID}',
            params={
                'vo': self.vo,
                'full_info': full_info
            }
        )
        return r['endpoints']


class NVFLDashboardClient:

    def __init__(
            self,
            base_url: str,
            username: str | None = None,
            password: str | None = None,
            **kwargs
    ):
        self.__base_url = base_url
        if username and password:
            self.__username = username
            self.__password = password
            self.__access_token = self.login()

    def get_base_url(self):
        return self.__base_url

    def return_json_if_status_ok(self, resp: Response):
        if resp.status_code not in [200, 201]:
            raise Exception(resp)
        resp_json = resp.json()
        if 'status' in resp_json and resp_json['status'] == 'ok':
            return resp_json
        raise Exception(resp_json)

    def _get(
            self,
            path: str = {},
            access_token: str | None = None,
            params: dict | None = {}
    ):
        url = urljoin(self.__base_url, path)
        headers = {
            'Content-type': 'application/json'
        }
        if access_token:
            headers.update({'Authorization': f'Bearer {access_token}'})
        resp = requests.get(
            url=url,
            headers=headers,
            params=params
        )
        return self.return_json_if_status_ok(resp)

    def _post(
            self,
            path: str = {},
            access_token: str | None = None,
            req: dict = {},
            **kwargs
    ):
        url = urljoin(self.__base_url, path)
        headers = {
            'Content-type': 'application/json'
        }
        if access_token:
            headers.update({'Authorization': f'Bearer {access_token}'})
        resp = requests.post(
            url=url,
            headers=headers,
            data=json.dumps(req),
            **kwargs
        )
        return self.return_json_if_status_ok(resp)

    def _patch(
            self,
            path: str = {},
            access_token: str | None = None,
            req: dict = {}
    ):
        url = urljoin(self.__base_url, path)
        headers = {
            'Content-type': 'application/json'
        }
        if access_token:
            headers.update({'Authorization': f'Bearer {access_token}'})
        resp = requests.patch(
            url=url,
            headers=headers,
            data=json.dumps(req)
        )
        return self.return_json_if_status_ok(resp)

    def login(self):
        resp = self._post(
            path='/api/v1/login',
            req={
                'email': self.__username,
                'password': self.__password
            }
        )
        self.__access_token = resp['access_token']
        self.user = resp['user']
        return self.__access_token

    def get_access_token(self):
        if self.__access_token:
            return self.__access_token
        return self.login()

    def create_one_user(
            self,
            email: str,
            name: str,
            password: str,
            organization: str,
            role: str,
            **kwargs
    ):
        return self._post(
            path='/api/v1/users',
            req={
                'email': email,
                'name': name,
                'password': password,
                'confirm_password': password,
                'organization': organization,
                'role': role
            }
        )['user']

    def update_user(
            self,
            id: str,
            req: dict = {}
    ):
        return self._patch(
            path=f'/api/v1/users/{id}',
            access_token=self.get_access_token(),
            req=req
        )['user']

    def create_one_client(
            self,
            name: str,
            organization: str,
            capacity: dict | None = {},
            num_of_gpus: int | None = None,
            mem_per_gpu_in_gib: int | None = None
    ):
        _capacity = {
            'num_of_gpus': 0,
            'mem_per_gpu_in_GiB': 0
        }
        if capacity:
            _capacity.update(capacity)
        if num_of_gpus:
            _capacity.update({'num_of_gpus': num_of_gpus})
        if mem_per_gpu_in_gib:
            _capacity.update({'mem_per_gpu_in_gib': mem_per_gpu_in_gib})
        return self._post(
            path='/api/v1/clients',
            access_token=self.get_access_token(),
            req={
                'name': name,
                'organization': organization,
                'capacity': _capacity
            }
        )['client']

    def update_client(
            self,
            id: str,
            req: dict = {}
    ):
        return self._patch(
            path=f'/api/v1/clients/{id}',
            access_token=self.get_access_token(),
            req=req
        )['client']

    def get_user(self):
        return self.user

    def get_users_by_role(
            self,
            roles: str | list = [],
            users: list | None = None
    ):
        if isinstance(roles, str):
            roles = [roles]
        if not users:
            users = self.get_users()
        matched_users = []
        for user in users:
            if user['role'] in roles:
                matched_users.append(user)
        return matched_users

    def get_project_admin(self):
        return self.get_users_by_role('project_admin')[0]

    def create_users(self, cfg):
        users = []
        for user_cfg in cfg:
            user = self.create_one_user(**user_cfg)
            logger.info('user %s registered in NVFLARE Dashboard' % user['email'])
            users.append(user)
        logger.debug(f'users:\n{json.dumps(users, indent=2)}')
        return users

    def get_users(self):
        return self._get(
            path='/api/v1/users',
            access_token=self.get_access_token()
        )['user_list']

    def approve_users(self, users):
        users_updated = []
        for user in users:
            user = self.update_user(
                id=user['id'],
                req={'approval_state': 100}
            )
            if user['approval_state'] != 100:
                logger.error(f'could not approve user %s in NVFLARE Dashboard' % user['email'])
                raise Exception()
            logger.info('user %s approved in NVFLARE Dashboard' % user['email'])
            users_updated.append(user)
        logger.debug(f'users:\n{json.dumps(users_updated, indent=2)}')
        return users_updated

    def create_clients(self, cfg):
        clients = []
        for client_cfg in cfg:
            client = self.create_one_client(**client_cfg)
            logger.info('client %s added in NVFLARE Dashboard' % client['name'])
            clients.append(client)
        logger.debug(f'clients:\n{json.dumps(clients, indent=2)}')
        return clients

    def approve_clients(self, clients):
        clients_updated = []
        for client in clients:
            client = self.update_client(
                id=client['id'],
                req={'approval_state': 100}
            )
            if client['approval_state'] != 100:
                logger.error(f'could not approve client %s in NVFLARE Dashboard' % client['name'])
                raise Exception()
            logger.info('client %s approved in NVFLARE Dashboard' % client['name'])
            clients_updated.append(client)
        return clients_updated

    def get_clients(self, org: str | None):
        clients = self._get(
            path='/api/v1/clients',
            access_token=self.get_access_token()
        )['client_list']
        if not org:
            return clients
        matched_clients = []
        for client in clients:
            if client['organization'] == org:
                matched_clients.append(client)
        return matched_clients

    def download_blob(
            self,
            path: str,
            dir: str,
            filename: str | None = None,
            data: dict | None = {},
            access_token: str | None = None,
    ):
        url = urljoin(self.__base_url, path)
        headers = {
            'Content-type': 'application/json'
        }
        if access_token:
            headers.update({'Authorization': f'Bearer {access_token}'})
        resp = requests.post(
            url=url,
            headers=headers,
            data=json.dumps(data),
            allow_redirects=True
        )
        if resp.status_code != 200:
            raise Exception(resp.status_code)
        header = resp.headers.get('Content-Disposition')
        if header:
            value, params = cgi.parse_header(header)
            if value and params and value == 'attachment' and 'filename' in params:
                filename = params['filename']
        if not filename:
            filename = tempfile.TemporaryFile(delete=False)
        else:
            filename = os.path.join(dir, filename)
        with open(filename, mode='wb') as f:
            f.write(resp.content)
        return filename

    def download_flare_console(
            self,
            pin: str | None = '1234',
            dir: str | None = os.path.join('.'),
            filename: str | None = None,
    ):
        id = self.user['id']
        path = f'/api/v1/users/{id}/blob'
        filename = self.download_blob(
            path=path,
            dir=dir,
            filename=filename,
            data={'pin': pin},
            access_token=self.get_access_token()
        )
        return filename

    def download_client_startup_kit(
            self,
            id: int,
            pin: str | None = '1234',
            dir: str | None = os.path.join('.'),
            filename: str | None = None,
    ):
        path = f'/api/v1/clients/{id}/blob'
        filename = self.download_blob(
            path=path,
            dir=dir,
            filename=filename,
            data={'pin': pin},
            access_token=self.get_access_token()
        )
        return filename


def do_start_job(papi: PAPIClient, **cfg: dict):
    # 1) deploy NVFL Dashboard and start FL server
    job_ID = papi.deploy_tool_nvflare(**cfg)
    logger.debug(f'job_ID: {job_ID}')
    return job_ID


def init_nvfl_dashboard_client(
        endpoint: str,
        username: str,
        password: str
) -> NVFLDashboardClient:
    wait_for_url(endpoint)
    return NVFLDashboardClient(endpoint, username, password)

def get_org_users_cfg(org: str, org_cfg: dict):
    return expand_vars_and_override(org_cfg['users'], org_cfg['override']['user'], {'{organization}': org})

def get_org_clients_cfg(org: str, org_cfg: dict):
    return expand_vars_and_override(org_cfg['clients'], org_cfg['override']['client'], {'{organization}': org})

def get_org_admin(users):
    for user in users:
        if user['role'] == 'org_admin':
            return user
    logger.error(f'missing a user with org_admin role')
    raise Exception()

def get_user_password(users_cfg, user):
    for user_cfg in users_cfg:
        if user_cfg['email'] == user['email']:
            return user_cfg['password']
    return None

def init_organization(org, org_cfg, project_admin: NVFLDashboardClient):
    users_cfg = get_org_users_cfg(org, org_cfg)
    if len(users_cfg) < 1:
        logger.error(f'missing users in organization {org} config')
        raise Exception()
    org_admin_cfg = get_org_admin(users_cfg)
    users = project_admin.create_users(users_cfg)
    users = project_admin.approve_users(users)
    org_admin = NVFLDashboardClient(project_admin.get_base_url(), org_admin_cfg['email'], org_admin_cfg['password'])
    clients_cfg = get_org_clients_cfg(org, org_cfg)
    if len(clients_cfg) < 1:
        logger.warning(f'missing clients in organization {org} config')
    clients = org_admin.create_clients(clients_cfg)
    clients = project_admin.approve_clients(clients)
    return users, clients

def do_scenario_init(nvfl_project_admin, cfg_scenario):
    orgs = {}
    for org, org_cfg in cfg_scenario['organizations'].items():
        org_users, org_clients = init_organization(org, org_cfg, nvfl_project_admin)
        orgs[org]={'users': org_users, 'clients': org_clients}
    return orgs

def unzip_file(file: str, dir: str, pin: str):
    commands = [f'unzip -x -o -P {pin} {file} -d {dir}']
    processes = [subprocess.Popen(cmd, shell=True) for cmd in commands]
    # following code does not preserve file permissions
    # with zipfile.ZipFile(file, 'r') as zip_ref:
    #     logger.info(f'extracting {file} to {dir}')
    #     zip_ref.extractall(dir, pwd=bytes(pin, 'utf-8'))


def do_download_nvflare_scripts(project_admin, cfg_scenario, working_dir: str = os.path.curdir, download_dir: str = 'downloads', extract_dir: str = os.path.curdir, extract=False):
    pin = '1234'
    if not os.path.isabs(extract_dir):
        extract_dir = os.path.join(working_dir, extract_dir)
        extract_dir = os.path.normpath(extract_dir)
    if not os.path.isabs(download_dir):
        download_dir = os.path.join(working_dir, download_dir)
        download_dir = os.path.normpath(download_dir)
    os.makedirs(download_dir, exist_ok=True)
    zip_flare_console = project_admin.download_flare_console(pin=pin, dir=download_dir)
    logger.info(f'downloaded flare console: {zip_flare_console}')
    if extract:
        os.makedirs(extract_dir, exist_ok=True)
        unzip_file(file=zip_flare_console, dir=extract_dir, pin=pin)
    for org, org_cfg in cfg_scenario['organizations'].items():
        users_cfg = get_org_users_cfg(org, org_cfg)
        org_admin_cfg = get_org_admin(users_cfg)
        org_admin = NVFLDashboardClient(project_admin.get_base_url(), org_admin_cfg['email'], org_admin_cfg['password'])
        clients = org_admin.get_clients(org=org)
        for client in clients:
            zip_client_startup_script = org_admin.download_client_startup_kit(client['id'], dir=download_dir)
            logger.info(f'downloaded startup script: {zip_client_startup_script}')
            if extract:
                unzip_file(zip_client_startup_script, dir=os.path.join(extract_dir, org), pin=pin)


def start_client(client, working_dir, clients_dir, data_dir, client_name_prefix: str = ''):
    if not os.path.isabs(working_dir):
        working_dir = os.path.abspath(working_dir)
    if not os.path.isabs(data_dir):
        data_dir = os.path.join(working_dir, data_dir)
        data_dir = os.path.normpath(data_dir)
    if not os.path.isabs(clients_dir):
        clients_dir = os.path.join(working_dir, clients_dir)
        clients_dir = os.path.normpath(clients_dir)
    my_data_dir = os.path.join(data_dir, client['organization'], client['name'])
    os.makedirs(my_data_dir, exist_ok=True)
    client_dir = os.path.join(clients_dir, client['organization'], client['name'])
    client_startup_dir = os.path.join(client_dir, 'startup')
    logger.info('starting client %s with docker ...' % client['name'])
    client_name_prefix = client_name_prefix.strip()
    commands = [
        rf"sed -i -E 's/(docker\s+run\s+[^\n]+?--name)=({re.escape(client['name'])})/\1={client_name_prefix + '_' if len(client_name_prefix) > 0 else ''}\2/g' {client_dir}/startup/docker.sh",
        f'export MY_DATA_DIR={my_data_dir}; cd {working_dir}; mkdir -p $MY_DATA_DIR; cd {client_startup_dir}; ./docker.sh -d'
    ]
    processes = [subprocess.Popen(cmd, shell=True) for cmd in commands]


def do_start_clients(cfg_scenario, nvfl_dashboard_endpoint, working_dir: str = os.path.curdir, clients_dir: str = os.path.curdir, data_dir: str = 'data', client_name_prefix: str = ''):
    for org, org_cfg in cfg_scenario['organizations'].items():
        users_cfg = expand_vars_and_override(org_cfg['users'], org_cfg['override']['user'], {'{organization}': org})
        org_admin_cfg = get_org_admin(users_cfg)
        org_admin = NVFLDashboardClient(nvfl_dashboard_endpoint, org_admin_cfg['email'], org_admin_cfg['password'])
        clients = org_admin.get_clients(org=org)
        for client in clients:
            start_client(client, working_dir, clients_dir, data_dir, client_name_prefix=client_name_prefix)


def main(args):
    logger.setLevel(args.log_level)

    cfg_papi = load_config(file=args.cfg_papi)
    cfg_job = load_config(file=args.cfg_job)

    papi = PAPIClient(**cfg_papi)

    dir_jobs = os.environ.get('NVFL_JOBS_DIR', os.path.join(os.path.curdir, 'jobs'))
    os.makedirs(dir_jobs, exist_ok=True)

    def get_job_dir(job_ID):
        return os.path.join(dir_jobs, job_ID)

    if args.subcommand == 'job':
        if args.start:
            job_ID = papi.deploy_tool_nvflare(**cfg_job)
            logger.debug(f'job_ID: {job_ID}')
            print(job_ID, file=sys.stdout, flush=True)
            os.makedirs(get_job_dir(job_ID))
            nvfl_dashboard_endpoint = papi.get_job_endpoints(job_ID)['dashboard']
            logging.info(f'NVFLARE Dashboard: {nvfl_dashboard_endpoint}')
 
    if args.subcommand == 'scenario':
        logger.debug(f'args.jobid: {args.jobid}')
        logger.debug('os.environ[\'NVFL_JOBID\']: %s', os.environ.get('NVFL_JOBID', None))
        job_ID = os.environ.get('NVFL_JOBID', args.jobid)
        logger.debug(f'job_ID: {job_ID}')
        if not job_ID:
            print('--jobid argument or NVFL_JOBID env var is required', file=sys.stderr, flush=True)
            sys.exit(1)
        nvfl_dashboard_endpoint = papi.get_job_endpoints(job_ID)['dashboard']
        logging.info(f'NVFLARE Dashboard: {nvfl_dashboard_endpoint}')
        nvfl_server_jupyter_endpoint = papi.get_job_endpoints(job_ID)['server-jupyter']
        logging.info(f'NVFLARE FL Server JupyterLab: {nvfl_server_jupyter_endpoint}')
        nvfl_project_admin = init_nvfl_dashboard_client(
            endpoint=nvfl_dashboard_endpoint,
            username=cfg_job['dashboard']['username'],
            password=cfg_job['dashboard']['password']
        )
        cfg_scenario = load_config(file=args.cfg)
        if args.init:
            orgs = do_scenario_init(nvfl_project_admin, cfg_scenario)
            logger.debug('scenario:\n%s' % json.dumps(orgs, indent=2))
        if args.download:
            do_download_nvflare_scripts(nvfl_project_admin, cfg_scenario, working_dir=get_job_dir(job_ID), extract=True)
        if args.start:
            do_start_clients(cfg_scenario, nvfl_dashboard_endpoint, working_dir=get_job_dir(job_ID), client_name_prefix=job_ID)




if __name__ == "__main__":

    parser = argparse.ArgumentParser(allow_abbrev=False)

    parser.add_argument('--log-level', action='store', type=str, default='INFO')
    parser.add_argument('--cfg-papi', action='store', type=str, default='papi.json', help='PAPI configuration file')
    parser.add_argument('--cfg-job', action='store', type=str, default='job.json', help='Nomad job configuration file')

    subparsers = parser.add_subparsers(
        dest='subcommand',
        required=True,
        title='subcommands',
        description='valid subcommands',
        help='additional help'
    )

    job_parser = subparsers.add_parser('job')
    job_parser.add_argument('--start', action='store_true')

    scenario_parser = subparsers.add_parser('scenario')
    scenario_parser.add_argument('--jobid', action='store', type=str, default=None, help='Nomad job ID')
    scenario_parser.add_argument('--cfg', action='store', type=str, default='scenario.json', help='scenario configuration file')

    g = scenario_parser.add_argument_group()
    g.add_argument('--init', action='store_true')
    g.add_argument('--download', action='store_true')
    g.add_argument('--start', action='store_true')

    args = parser.parse_args()
    main(args)
