#!/usr/bin/python3

import os
import time
import json
import urllib
import requests
import argparse
import shutil
import string
import random

# something like ./emulate.py --api http://localhost:8081 --auth `cat ../kernelci-docker-lucj/.kernelci_token`

parser = argparse.ArgumentParser()
parser.add_argument("--auth", dest='auth_key', help="authorization token")
parser.add_argument("--api", dest='api', help="url of kci api")
args = parser.parse_args()

auth_key = args.auth_key
api = args.api
describe = 'dummydescribe-{}'.format(int(time.time()))
branch = 'master'

commit = '25b67b1781a4a34b7547e{}'.format(int(time.time()))
tree = 'dummytree'

def create_lab(lab_name):
    headers = {
    "Authorization": auth_key,
    "Content-Type": "application/json"
    }

    payload = {
        "name": lab_name,
        "contact": {
            "name": "Test",
            "surname": "Tester",
            "email": "test@testface.test"
        }
    }

    url = urllib.parse.urljoin(api, "/lab")
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    token_dir = os.path.join(os.getcwd(), "dummyfiles/boots")
    os.makedirs(token_dir, exist_ok=True)
    token_file = os.path.join(token_dir, "token-{}".format(lab_name))
    if response.status_code == 201:
        result = json.loads(response.content)
        token = result['result'][0]['token']
        with open(token_file, "w") as labfile:
            labfile.write(token)
        return token
    else:
        print(response.text)
        with open(token_file, "r") as labfile:
            return labfile.read().strip()


def do_post_retry(url=None, data=None, headers=None, files=None):
    retry = True
    while retry:
        try:
            response = requests.post(url, data=data, headers=headers, files=files)
            if str(response.status_code)[:1] != "2":
                raise Exception(response.content)
            else:
                return response.content, response.status_code
                retry = False
        except Exception as e:
            print("ERROR: failed to publish")
            print(e)
            time.sleep(10)

def create_dummy_file(path, size):
    print("creating path {}".format(path))
    with open(path, "wb") as out:
        out.seek((1024 * 1024 * size) - 1)
        out.write(b'\0')

def create_build_files(path, warnings=False, errors=False):
    logfile = 'build.log'
    dest = os.path.join(path, logfile)
    os.makedirs(path, exist_ok=True)
    log_path = os.path.join(os.getcwd(), 'dummyfiles', 'builds', logfile)
    shutil.copy(log_path, dest)
    if warnings:
        with open(dest, 'a') as outfile:
            for x in range(0, warnings):
                #print("writing a warning to {}".format(dest))
                outfile.write('../drivers/soc/rockchip/pm_domains.c:{}:21: warning: {} warning here\n\n'.format(x, x))
    if errors:
        with open(dest, 'a') as outfile:
            for x in range(0, errors):
                outfile.write('clang: error: assembler command failed with exit code 1\n\n')

def create_build_json(path, resource, arch, environment, defconfig, result):
    output = os.path.join(path, 'build.json')
    build_json = {
        "compiler_version_full": "{} (Debian 7.3.0-19) 7.3.0".format(environment[:-2]),
        "kconfig_fragments": None,
        "build_environment": environment,
        "build_time": 7.34,
        "text_offset": "0x01000000",
        "kernel_config": "kernel.config",
        "build_platform": ["Linux", "6430u", "4.15.0-1-amd64", "#1 SMP Debian 4.15.4-1 (2018-02-18)", "x86_64", ""],
        "vmlinux_file_size": 1226748,
        "git_describe": describe,
        "build_log": "build.log",
        "cross_compile": "None",
        "git_describe_v": describe,
        "dtb_dir": None,
        "system_map": "System.map",
        "build_threads": 6,
        "vmlinux_bss_size": 49152,
        "kernel_image": "bzImage",
        "job": tree,
        "git_url": "https://dummyurl.git",
        "vmlinux_data_size": 109248,
        "arch": arch,
        "compiler": environment[:-2],
        "file_server_resource": resource,
        "compiler_version": None,
        "modules": None,
        "defconfig": defconfig,
        "defconfig_full": defconfig,
        "git_branch": branch,
        "git_commit": commit,
        "build_result": result,
        "vmlinux_text_size": 620549}
    if result == 'FAIL':
        build_json['kernel_image'] = None
    with open(output, 'w') as out:
        json.dump(build_json, out, indent=4, sort_keys=True)


def post_build(arch, environment, defconfig, result, warnings, errors):
    path = '{}/{}/{}/{}/{}/{}'.format(tree, branch, describe, arch, defconfig, environment)
    print("Posting build to {}: {} ({} warnings)".format(path, result, warnings))
    build_data = {
        'kernel': describe,
        'file_server_resource': path,
        'build_environment': environment,
        'defconfig': defconfig,
        'job': tree,
        'defconfig_full': defconfig,
        'git_branch': branch,
        'path': path,
        'arch': arch}
    headers = {'Authorization': auth_key}
    artifacts = []
    install_path = os.path.join(os.getcwd(), "dummyfiles", tree, branch, describe, arch, defconfig, environment)
    create_build_files(install_path, warnings, errors)
    create_build_json(install_path, path, arch, environment, defconfig, result)
    count = 1
    for root, dirs, files in os.walk(install_path):
        if count == 1:
            top_dir = root
        for file_name in files:
            name = file_name
            if root != top_dir:
                # Get the relative subdir path
                subdir = root[len(top_dir)+1:]
                name = os.path.join(subdir, file_name)
            artifacts.append(('file' + str(count),
                              (name,
                               open(os.path.join(root, file_name), 'rb'))))
            count += 1
    upload_url = urllib.parse.urljoin(api, '/upload')
    #print("Uploading build to storage...")
    #print(artifacts)
    publish_response, status_code = do_post_retry(
        url=upload_url, data=build_data, headers=headers, files=artifacts)
    build_url = urllib.parse.urljoin(api, '/build')
    #print(build_data)
    headers['Content-Type'] = 'application/json'
    do_post_retry(url=build_url, data=json.dumps(build_data),
                  headers=headers)

def api_builds_finished():
    print("Marking build finished and requesting build email")
    headers = {}
    headers['Authorization'] = auth_key
    headers['Content-Type'] = 'application/json'
    data = {'job': tree, 'kernel': describe, 'git_branch': branch}

    job_url = urllib.parse.urljoin(api, '/job')
    do_post_retry(url=job_url, data=json.dumps(data), headers=headers)

def request_email(type='build', format='txt'):
    headers = {}
    headers['Authorization'] = auth_key
    headers['Content-Type'] = 'application/json'
    data = {'job': tree, 'kernel': describe, 'git_branch': branch}
    email_data = data
    if type == 'build':
        email_data['build_report'] = 1
    else:
        email_data['boot_report'] = 1
    email_data['send_to'] = ["matt@blacklabsystems.com"]
    email_data['format'] = [format]
    email_data['delay'] = 1
    send_url = urllib.parse.urljoin(api, '/send')
    do_post_retry(url=send_url, data=json.dumps(data), headers=headers)

def create_lab_name():
    letters = string.ascii_lowercase
    return 'lab-' + ''.join(random.choice(letters) for i in range(8))

def post_boot(environment, arch, defconfig, result='PASS'):
    path = '{}/{}/{}/{}/{}/{}'.format(tree, branch, describe, arch, defconfig, environment)
    print("Pushing a boot: {}".format(path))
    headers = {}
    lab_name = create_lab_name()
    lab_auth_key = create_lab(lab_name)
    headers['Authorization'] = lab_auth_key
    headers['Content-Type'] = 'application/json'
    boot_data = {
        'lab_name': lab_name,
        'kernel': describe,
        'file_server_resource': path,
        'build_environment': environment,
        'defconfig': defconfig,
        'board': 'board1',
        'device_type': 'devtype',
        'job': tree,
        'defconfig_full': defconfig,
        'git_branch': branch,
        'git_commit': commit,
        'path': path,
        'boot_result': result,
        'boot_time': 120,
        'arch': arch,
        'version': 1.1}
    boot_url = urllib.parse.urljoin(api, '/boot')
    publish_response, status_code = do_post_retry(url=boot_url, data=json.dumps(boot_data), headers=headers)

# build_fake_data = []
# arch_list = ['x86_64', 'i386', 'arm64', 'mips', 'arm', 'riscv']
# #arch_list = ['arm64', 'arm']
# for arch in arch_list:
#     for defconfig in ['defconfig', 'tinyconfig', 'allnoconfig']:
#         for environment in ['gcc-8', 'clang-8', 'gcc-7']:
#             build_fake_data.append({'environment': environment, 'arch': arch, 'defconfig': defconfig, 'result': random.choice(['FAIL', 'PASS'])})
#
#
# for fd in build_fake_data:
#     post_build('arm64', 'gcc-7', 'defconfig', 'PASS', 4)

# post_build('arm64', 'compiler-0', 'defconfig', 'PASS', 0, 0)
# post_build('arm64', 'compiler-1', 'defconfig', 'PASS', 1, 0)
# post_build('arm64', 'compiler-1', 'otherconfig', 'PASS', 1, 0)
# post_build('arm64', 'compiler-2', 'defconfig', 'PASS', 2, 0)
# post_build('arm64', 'compiler-fail1', 'defconfig', 'FAIL', False, 1)
# post_build('arm64', 'compiler-fail', 'otherconfig', 'FAIL', False, 0)
# post_build('arm64', 'compiler-fail2', 'fail2config', 'FAIL', False, 2)
# post_build('arm', 'compiler-fail', 'defconfig', 'FAIL', False, 0)
# post_build('arm', 'compiler-fail2', 'warn1config', 'FAIL', 1, 2)
# post_build('arm', 'compiler-fail', 'otherconfig', 'FAIL', False, 0)
# post_build('arm', 'compiler-fail2', 'warn2config', 'FAIL', 2, 2)
# post_build('arm', 'compiler-1', 'allnoconfig', 'PASS', 1, 0)
# post_build('arm', 'compiler-2', 'defconfig', 'PASS', 2, 0)
# post_build('arm', 'compiler-3', 'defconfig', 'PASS', 3, 0)

post_build('arm64', 'gcc-8', 'defconfig', 'PASS', 1, 1)
post_build('arm64', 'clang-8', 'defconfig', 'PASS', 2, 2)

time.sleep(1)
api_builds_finished()
#api_builds_finished('html')
time.sleep(1)
post_boot('gcc-8', 'arm64', 'defconfig', 'FAIL')
#post_boot('gcc-8', 'arm64', 'defconfig', 'PASS')
post_boot('clang-8', 'arm64', 'defconfig', 'FAIL')
#post_boot('clang-8', 'arm64', 'defconfig', 'PASS')
# post_boot('gcc-8', 'arm', 'PASS')
# post_boot('gcc-8', 'arm64', 'PASS')
# post_boot('clang-8', 'arm64', 'FAIL')
# post_boot('clang-8', 'mips', 'FAIL')
# post_boot('clang-8', 'x86', 'FAIL')
#request_email('boot', 'txt')
time.sleep(1)
#request_email('build', 'txt')
#request_email('build', 'html')
#request_email('boot', 'html')
request_email('boot', 'txt')
