#!/usr/bin/env python

import argparse
import boto3
import datetime
import glob
import os
import sys
import time
import yaml

from c7n.commands import validate as cc_validate_yaml
from dateutil.tz import gettz
from pkg_resources import load_entry_point


def get_all_custodian_yaml_files(policy_dir='/custodian/policies/*'):
    return glob.glob(policy_dir)


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


def get_secrets():
    secrets_file = open('/secrets/aws-secrets.yml', 'r')
    secrets = yaml.load(secrets_file)
    secrets_file.close()
    return secrets


def set_aws_custodian_account_env_secrets(secrets):
    aws_custodian_account = secrets['aws_custodian_account']
    os.environ['AWS_SECRET_ACCESS_KEY'] = secrets['accounts'][
        aws_custodian_account]['AWS_SECRET_ACCESS_KEY']
    os.environ['AWS_ACCESS_KEY_ID'] = secrets['accounts'][
        aws_custodian_account]['AWS_ACCESS_KEY_ID']


def update_lambda_mailer(logger):
    logger.info('updating the mailer lambda function')
    sys.argv = ['c7n-mailer', '-c', '/custodian/email/email-config.yml']
    load_entry_point('c7n-mailer', 'console_scripts', 'c7n-mailer')()


def aws_get_all_regions():
    aws_session = boto3.session.Session()
    return aws_session.get_available_regions('ec2')


def get_file_contents(file_name):
    file = open(file_name, 'r')
    file_contents = file.read()
    file.close()
    return file_contents


def get_wrapper_config():
    wrapper_config_file = get_file_contents('/custodian/config/wrapper_config.yml')
    wrapper_config = yaml.load(wrapper_config_file)
    return wrapper_config


def get_sts_role(account_name, secrets):
    sts_role = False
    if secrets['accounts'][account_name]['sts_role']:
        sts_role = secrets['accounts'][account_name]['sts_role']
    return sts_role


def get_latest_file_change_time():
    latest_file = max(glob.iglob('*'), key=os.path.getctime)
    file_epoch_time = os.path.getctime(latest_file)
    dt_obj = datetime.datetime.fromtimestamp(file_epoch_time, tz=gettz('US/Pacific'))
    return dt_obj.strftime('%Y %b %d %H:%M %Z')


def log_start_of_cycle(custodian_live_fire, reports_only_mode):

    def get_hash_header(msg):
        return '\n\n########################    %s    ########################\n\n' % msg
    if custodian_live_fire:
        sys.stdout.write(get_hash_header('THIS IS LIVE FIRE. CHANGES ARE BEING MADE!!!'))
    elif reports_only_mode:
        sys.stdout.write(get_hash_header('THIS IS REPORTS ONLY MODE. NO CHANGES ARE BEING MADE'))
    else:
        sys.stdout.write(get_hash_header('THIS IS A DRY RUN. NO CHANGES ARE BEING MADE'))
    sys.stdout.flush()


def log_end_of_cycle_sleeping(seconds_between_full_fun, start_time,
                              qty_custodian_run_commands, logging):
    seconds_for_cycle_to_complete = round(time.time() - start_time, 1)
    minutes_interval_gap = round((seconds_between_full_fun / 60.0), 1)
    if qty_custodian_run_commands > 0:
        average_seconds_per_custodian_run = str(
            round(seconds_for_cycle_to_complete / qty_custodian_run_commands,
                  1))
    else:
        average_seconds_per_custodian_run = 'N/A'
    sys.stdout.write('\n\n')
    sys.stdout.flush()
    log_msg = ('Ran a full cycle in %s seconds. %s custodian runs happened at an average of %s'
    ' seconds per run. Going to sleep for %s minutes') % (seconds_for_cycle_to_complete,
        qty_custodian_run_commands, average_seconds_per_custodian_run, minutes_interval_gap)
    logging.info(log_msg)
    sys.stdout.write('\n\n')
    sys.stdout.flush()
