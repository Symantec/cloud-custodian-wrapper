#!/usr/bin/env python

import argparse
import glob
import multiprocessing
import os

from c7n.commands import validate as cc_validate_yaml
from clean_accounts import main_loop

parallel_process_max = 32
cc_sqs_url = os.environ['CC_SQS_URL']
parallel = bool(os.environ.get('PARALLEL', False))

# the only reason we're doing all this is so we can publish policies to github
# and not have our private account numbers sent to github as well.
# it would be nice if you could just use a 'default' sqs queue from mailer.yml


def get_all_custodian_yaml_files():
    return glob.glob('/custodian/policies/*')


def replace_string_on_files(text_to_search, text_to_replace, files):
    pool = multiprocessing.Pool(processes=parallel_process_max)
    for file in files:
        pool.apply_async(
            replace_string_on_file,
            args=(text_to_search, text_to_replace, file))
    pool.close()
    pool.join()


def replace_string_on_file(text_to_search, text_to_replace, file):
    lines = []
    with open(file) as infile:
        for line in infile:
            line = line.replace(text_to_search, text_to_replace)
            lines.append(line)
    with open(file, 'w') as outfile:
        for line in lines:
            outfile.write(line)


def validate_custodian_yaml_files(custodian_yaml_files):
    cc_validate_options = argparse.Namespace(
        command = 'c7n.commands.validate',
        config  = None,
        configs = custodian_yaml_files,
        debug=False,
        subparser='validate',
        verbose=False
    )
    cc_validate_yaml(cc_validate_options)


if __name__ == '__main__':
    all_custodian_yaml_files = get_all_custodian_yaml_files()
    replace_string_on_files('{CC_SQS_URL}', cc_sqs_url, all_custodian_yaml_files)
    validate_custodian_yaml_files(all_custodian_yaml_files)
    main_loop(run_once=True, parallel=parallel)
    replace_string_on_files(cc_sqs_url, '{CC_SQS_URL}', all_custodian_yaml_files)
