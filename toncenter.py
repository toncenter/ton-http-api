#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import yaml

settings = None

def set_settings_file(settings_file):
    if not os.path.exists(settings_file):
        raise Exception("Settings file not found")
    shutil.copyfile(settings_file, os.path.dirname(__file__) + "/config/settings.yaml")
    
    with open(settings_file) as f:
        global settings
        settings = yaml.safe_load(f)

def get_env():
    env = os.environ.copy()
    env['INDEX_FOLDER'] = settings['nginx']['index_folder']
    env['MAIN_DOMAIN'] = settings['nginx']['domains'][0]['host']
    env['WORKERS_NUM'] = str(settings['pyton']['webserver_workers'])
    return env

def construct_compose_files_args():
    cmd = ['docker-compose']
    cmd += ['-f', 'docker-compose.yaml']
    if settings['logs']['enabled']:
        cmd += ['-f', 'docker-compose.logs.yaml']
    if settings['cache']['enabled']:
        cmd += ['-f', 'docker-compose.cache.yaml']
    if settings['ratelimit']['enabled']:
        cmd += ['-f', 'docker-compose.ratelimit.yaml']
    return cmd

def main():
    parser = argparse.ArgumentParser(description='Proxy to docker-compose with correct -f flags and env variables (based on settings file)')

    parser.add_argument('-s', '--settings', metavar='SETTINGS_FILE', type=str, 
        default='settings.yaml', help='settings file in yaml format. Default: settings.yaml')
    parser.add_argument('action', help='action passed to docker-compose (additional arguments are accepted)')
    args, unknown_args = parser.parse_known_args()

    set_settings_file(args.settings)

    cmd = construct_compose_files_args()
    cmd += [args.action]
    cmd += unknown_args

    print(' '.join(cmd))
    completed = subprocess.run(cmd, env=get_env())
    exit(completed.returncode)

if __name__ == '__main__':
    main()