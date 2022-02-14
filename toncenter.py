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

def docker_compose_build(no_cache):
    print("📦 Building docker-compose image")
    cmd = construct_compose_files_args()
    cmd += ['build']
    if no_cache:
        cmd += ['--no-cache']
    print(f"Running command: {' '.join(cmd)}")
    completed_proc = subprocess.run(cmd, env=get_env())
    if completed_proc.returncode:
        print("❌ Building failed")
        exit(-1)
    else:
        print("✅ Building succeeded")

def docker_compose_up():
    print("🚀 Starting docker-compose services")
    cmd = construct_compose_files_args()
    cmd += ['up', '-d']
    print(f"Running command: {' '.join(cmd)}")
    completed_proc = subprocess.run(cmd, env=get_env())
    if completed_proc.returncode:
        print("❌ Starting failed")
        exit(-1)
    else:
        print("✅ Starting succeeded")

def docker_compose_down(clear_volumes):
    print("🛑 Stopping docker-compose services")
    cmd = construct_compose_files_args()
    cmd += ['down']
    cmd += ['--remove-orphans'] # removing orphans every time, since configuration could change
    if clear_volumes:
        cmd += ['-v']
    print(f"Running command: {' '.join(cmd)}")
    completed_proc = subprocess.run(cmd, env=get_env())
    if completed_proc.returncode:
        print("❌ Stopping failed")
        exit(-1)
    else:
        print("✅ Stopping succeeded")

def main():
    parser = argparse.ArgumentParser(description='Manage TON HTTP API services')

    parser.add_argument('-s', '--settings', metavar='SETTINGS_FILE', type=str, 
        default='settings.yaml', help='settings file in yaml format. Default: settings.yaml')
    subparsers = parser.add_subparsers(dest="action", required=True)
    build_parser = subparsers.add_parser('build')
    build_parser.add_argument('--no-cache', action='store_true', help='build without cache')
    up_parser = subparsers.add_parser('up')
    down_parser = subparsers.add_parser('down')
    down_parser.add_argument('-v', '--volumes', action='store_true', help='clear volumes')
    
    args = parser.parse_args()

    set_settings_file(args.settings)

    if args.action == 'build':
        docker_compose_build(args.no_cache)
    elif args.action == 'up':
        docker_compose_up()
    elif args.action == 'down':
        docker_compose_down(args.volumes)


if __name__ == '__main__':
    main()