#!/usr/bin/env python

import argparse
import csv
import os
import sys
import utils
import yaml

from c7n.policy import PolicyCollection
from c7n.reports.csvout import Formatter, fs_record_set
from c7n.resources import load_resources as load_c7n_resources
from tabulate import tabulate


def print_reports():
    all_valid_report_cache_file_names = get_all_valid_report_cache_filenames('dry_run')
    all_valid_report_names = get_all_valid_report_names(all_valid_report_cache_file_names)
    report_to_policy_map = get_report_name_to_report_yaml_map(all_valid_report_names)
    load_c7n_resources()
    sys.stdout.write('\nSkipping validation of lambda policies [those without a filter block]\n')
    for valid_report_cache_file_name in all_valid_report_cache_file_names.keys():
        report_obj, options, account, region, report_name = get_report_obj(
            valid_report_cache_file_name, report_to_policy_map)
        print_report(report_obj, options, account, region, report_name)


# this makes a mapping of a report name to the yaml data for the report
# we infer the yaml data from the policy directly to avoid the overhead
# of manually making reports
def get_report_name_to_report_yaml_map(all_valid_report_cache_file_names):
    policy_file_names = os.listdir('policies')
    report_name_to_policy_map = {}
    for policy_file_name in policy_file_names:
        policy_abs_file_path = '/custodian/policies/%s' % policy_file_name
        policy_file_contents = utils.get_file_contents(policy_abs_file_path)
        policy_file_yaml     = yaml.load(policy_file_contents)
        for sub_policy in policy_file_yaml['policies']:

            def not_a_lambda_policy(policy_yaml):
                return 'filters' in policy_yaml
            found_valid_report_policy = sub_policy['name'] in all_valid_report_cache_file_names
            if found_valid_report_policy and not_a_lambda_policy(sub_policy):
                report_policy_yaml = sub_policy
                report_policy_yaml.pop('actions', None)
                report_policy_yaml = {'policies': [report_policy_yaml]}
                report_name_to_policy_map[sub_policy['name']] = report_policy_yaml

    return report_name_to_policy_map


def get_all_valid_report_names(all_valid_report_cache_file_names):
    all_valid_report_names = {}
    for valid_report_cache_file_name in all_valid_report_cache_file_names:
        all_valid_report_names[(valid_report_cache_file_name.split('/')[-2])] = ''
    return list(set(all_valid_report_names))


# this function returns any files named resources.json in dry_run
# that are larger than 3 bytes
def get_all_valid_report_cache_filenames(cache_dir):

    def file_not_empty(abs_filepath):
        cached_dry_run_filesize = os.stat(abs_filepath).st_size
        if cached_dry_run_filesize > 3:
            return True
        else:
            return False
    all_valid_report_cache_json_files = {}
    # file_names is list of files from each sud dir (recursively)
    for root, dir_names, file_names in os.walk(cache_dir):
        for file_name in file_names:
            abs_filepath = '%s/%s' % (root, file_name)
            if file_name == 'resources.json' and file_not_empty(abs_filepath):
                all_valid_report_cache_json_files[os.path.join(root, file_name)] = ''
    return all_valid_report_cache_json_files


def get_report_obj(valid_report_cache_file_name, report_to_policy_map):
    account, region, report_name = valid_report_cache_file_name.split('/')[1:-1]
    dry_run_cache_dir = '/'.join(valid_report_cache_file_name.split('/')[0:-2])
    options = argparse.Namespace(
        account_id = None,
        assume_role = None,
        cache = None,
        command = 'c7n.commands.report',
        config = None,
        days = 1,
        debug = False,
        field = [],  # ['HEADER=Tags'],
        format = 'grid',
        log_group = None,
        no_default_fields = False,
        output_dir = dry_run_cache_dir,
        policy_filter = None,
        profile = None,
        raw = None,
        region = region,
        regions = '',
        resource_type = None,
        subparser = 'report',
        verbose = False
    )
    report_policy = PolicyCollection(report_to_policy_map[report_name], options)
    return [report_policy.policies[0], options, account, region, report_name]


def print_report(report_obj, options, account, region, report_name):
    hash_str = '###################'
    report_header = '\n\n%s Account: %s - Region: %s - Report %s %s\n' % (hash_str, account, region,
        report_name, hash_str)
    sys.stdout.write(report_header)
    formatter = Formatter(
        report_obj.resource_manager,
        extra_fields=options.field,
        no_default_fields=options.no_default_fields,
    )
    records = fs_record_set(report_obj.ctx.output_path, report_obj.name)
    rows = formatter.to_csv(records)
    if options.format == 'csv':
        writer = csv.writer(options.raw, formatter.headers())
        writer.writerow(formatter.headers())
        writer.writerows(rows)
    else:
        # We special case CSV, and for other formats we pass to tabulate
        print(tabulate(rows, formatter.headers(), tablefmt=options.format))
