#!/usr/bin/env python3

from distutils.util import strtobool
import os
import sys
import jinja2
import yaml


def gen_nginx_conf(input_file, output_file):
    print("👷 Generating config for nginx...")

    domains = os.getenv('TON_API_DOMAINS').split(':')

    with open(input_file, 'r') as f:
        template = jinja2.Template(f.read())
    template_args = {
        'index_folder' : os.getenv('TON_API_INDEX_FOLDER'),
        'analytics_enabled' : strtobool(os.getenv('TON_API_ANALYTICS_ENABLED')),
        'domains' : domains
    }
    outputText = template.render(template_args)
    outputText = "# This file was automatically generated by gen_config.py\n" + outputText
    
    with open(output_file, 'w') as f:
        f.write(outputText)

    print("✅ Config for nginx created.")

def main():
    gen_nginx_conf(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    main()