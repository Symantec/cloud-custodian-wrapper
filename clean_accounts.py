#!/usr/bin/env python


import boto.ec2
import datetime
import glob
import logging
import multiprocessing
import os
import sys
import time
import yaml

from easyprocess import EasyProcess
from pkg_resources import load_entry_point

__requires__ = 'c7n-mailer'

reports_only_mode      = os.environ.get('CUSTODIAN_REPORTS_ONLY_MODE', False)
custodian_live_fire    = os.environ.get('CUSTODIAN_LIVE_FIRE', False)
custodian_run_interval = 900
policy_dir_prefix      = '/custodian/policies/'
logger                 = logging.getLogger('custodian.policy')
parallel_process_max   = 32
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def update_lambda_mailer():
  logger.info('updating the mailer lambda function')
  sys.argv = ['c7n-mailer', '-c', '/custodian/email/email-config.yml']
  load_entry_point('c7n-mailer', 'console_scripts', 'c7n-mailer')()


def get_secrets():
  secrets_file = open('/secrets/aws-secrets.yml', 'r')
  secrets      = yaml.load(secrets_file)
  secrets_file.close()
  return secrets


def aws_get_all_regions():
  all_regions = []
  boto_region_objects = boto.ec2.regions()
  for boto_region_object in boto_region_objects:
    all_regions.append(boto_region_object.name)
  return all_regions


def get_wrapper_config():
  wrapper_config_file = open('/custodian/wrapper-config.yml', 'r')
  wrapper_config      = yaml.load(wrapper_config_file)
  wrapper_config_file.close()
  return wrapper_config


def get_argv_custodian_run_cmd(sts_role, region, policy, account_name):
  # doing argv like this is quite ugly, though cloud custodian has no api or easy way to
  # call their libraries. This is the least ugly option and most readable/intuitive.
  if custodian_live_fire and reports_only_mode:
    sys.exit('You can not run in live fire mode and reports mode at the same time.')
  if custodian_live_fire:
    custodian_output = s3_logging_bucket
  else:
    custodian_output = 'dry_run/%s/%s' % (account_name, region)
  policy_abs_filename = '/custodian/policies/%s' % policy

  if custodian_live_fire and sts_role:
    custodian_cmd = ['custodian', 'run', '--region', region, '--cache-period=0', '-c', policy_abs_filename, '--assume', sts_role, '-s', custodian_output]
  elif custodian_live_fire and not sts_role:
    custodian_cmd = ['custodian', 'run', '--region', region, '--cache-period=0', '-c', policy_abs_filename, '-s', s3_logging_bucket]
  elif not custodian_live_fire and sts_role:
    custodian_cmd = ['custodian', 'run', '--region', region, '--cache-period=0', '-c', policy_abs_filename, '--assume', sts_role, '-s', custodian_output, '--dryrun']
  elif not custodian_live_fire and not sts_role:
    custodian_cmd = ['custodian', 'run', '--region', region, '--cache-period=0', '-c', policy_abs_filename, '-s', custodian_output, '--dryrun']
  return custodian_cmd


def get_policy_names(file):
  list_of_policy_names = []
  policy_file = open(file, 'r')
  yaml_data = yaml.load(policy_file)
  for policy_name in yaml_data['policies']:
    list_of_policy_names.append((policy_name['name']))
  policy_file.close()
  return list_of_policy_names


def set_aws_custodian_account_env_secrets(secrets):
  aws_custodian_account = secrets['aws_custodian_account']
  os.environ['AWS_SECRET_ACCESS_KEY'] = secrets['accounts'][aws_custodian_account]['AWS_SECRET_ACCESS_KEY']
  os.environ['AWS_ACCESS_KEY_ID'] = secrets['accounts'][aws_custodian_account]['AWS_ACCESS_KEY_ID']


def get_sts_role(account_name, secrets):
  sts_role = False
  if secrets['accounts'][account_name]['sts_role']:
    sts_role = secrets['accounts'][account_name]['sts_role']
  return sts_role


def get_latest_file_change():
  latest_file = max(glob.iglob('*'), key=os.path.getctime)
  return os.path.getctime(latest_file)


def log_start_of_cycle(custodian_live_fire):
  if custodian_live_fire:
    sys.stdout.write('\n\n########################    THIS IS LIVE FIRE. CHANGES ARE BEING MADE!!!    ########################\n\n')
  elif reports_only_mode:
    sys.stdout.write('\n\n########################    THIS IS REPORTS ONLY MODE. NO CHANGES ARE BEING MADE    ########################\n\n')
  else:
    sys.stdout.write('\n\n########################    THIS IS A DRY RUN. NO CHANGES ARE BEING MADE    ########################\n\n')
  sys.stdout.flush()


def log_end_of_cycle_sleeping(seconds_between_full_fun, start_time, qty_custodian_run_commands):
  sys.stdout.write('\n\n')
  seconds_for_cycle_to_complete     = round(time.time() - start_time, 1)
  minutes_interval_gap              = round((seconds_between_full_fun / 60.0), 1)
  if qty_custodian_run_commands > 0:
    average_seconds_per_custodian_run = str(round(seconds_for_cycle_to_complete / qty_custodian_run_commands, 1))
  else:
    average_seconds_per_custodian_run = 'N/A'
  sys.stdout.write('\n\n')
  log_msg = '''Ran a full cycle in %s seconds. %s custodian runs happened at an average of %s seconds per run. Going to\
 sleep for %s minutes''' % (seconds_for_cycle_to_complete, qty_custodian_run_commands, average_seconds_per_custodian_run, minutes_interval_gap)
  logging.info(log_msg)
  sys.stdout.write('\n\n')
  sys.stdout.flush()


def get_all_custodian_report_commands():
  custodian_report_commands = []
  for account_name in wrapper_config['accounts'].keys():
    all_regions_exist = 'all_regions' in wrapper_config['accounts'][account_name] and wrapper_config['accounts'][account_name]['all_regions']

    if all_regions_exist:
      for aws_region in aws_all_regions:
        custodian_report_commands = custodian_report_commands + get_custodian_report_cmds(account_name, all_listed_regions_policies, aws_region)

    if 'regions' in wrapper_config['accounts'][account_name]:
      aws_regions = wrapper_config['accounts'][account_name]['regions'].keys()

    for aws_region in aws_regions:
      # for each region, run region specific report policies if they exist
      region_policies_exist = wrapper_config['accounts'][account_name]['regions'][aws_region] and 'region_policies' in wrapper_config['accounts'][account_name]['regions'][aws_region]
      # if region_specific_policies exist, run all_listed_regions_policies and region_specific_policies for this region
      if region_policies_exist:
        region_specific_policies = wrapper_config['accounts'][account_name]['regions'][aws_region]['region_policies']
        if all_regions_exist:
          region_policies = region_specific_policies
        else:
          region_policies = region_specific_policies + all_listed_regions_policies
        custodian_report_commands = custodian_report_commands + get_custodian_report_cmds(account_name, region_policies, aws_region)
      # if not region_specific_policies exist, just run the all_listed_regions_policies for this region
      elif not all_regions_exist:
        custodian_report_commands = custodian_report_commands + get_custodian_report_cmds(account_name, all_listed_regions_policies, aws_region)
  return custodian_report_commands


def get_reports_from_policy(policy_filename):
  list_of_report_policy_names = []
  policy_file = open(policy_filename, 'r')
  yaml_data = yaml.load(policy_file)
  for policy_name in yaml_data['policies']:
    list_of_report_policy_names.append((policy_name['name']))
  policy_file.close()
  return list_of_report_policy_names


def get_custodian_report_cmds(account_name, policies, region):
  custodian_report_commands = []
  for policy in policies:
    report_policies = get_reports_from_policy(policy)
    for report_policy in report_policies:
      # --dryrun makes resources.json for every policy/account/region, so we're skipping ones that are empty
      cached_dryrun_resource  = '/custodian/dry_run/%s/%s/%s/resources.json' % (account_name, region, report_policy)
      cached_dry_run_filesize = os.stat(cached_dryrun_resource).st_size
      if cached_dry_run_filesize < 3:
        continue
      custodian_report_commands.append((account_name, get_argv_custodian_report_cmd(report_policy=report_policy, account_name=account_name, region=region)))
  return custodian_report_commands


def get_argv_custodian_report_cmd(report_policy, account_name, region):
  custodian_cached_output = 'dry_run/%s/%s' % (account_name, region)
  report_policy_abs_filename = '/custodian/reports/%s.report.yml' % report_policy
  return ['custodian', 'report', '-s', custodian_cached_output, '--format', 'grid', report_policy_abs_filename]


def get_all_custodian_run_commands():
  custodian_run_commands = []
  for account_name in wrapper_config['accounts'].keys():
    # for each account, set the sts role
    sts_role    = get_sts_role(account_name, secrets)
    all_regions_exist = 'all_regions' in wrapper_config['accounts'][account_name] and wrapper_config['accounts'][account_name]['all_regions']

    if all_regions_exist:
      custodian_run_commands = custodian_run_commands + get_custodian_run_cmds(account_name, aws_all_regions, sts_role, all_listed_regions_policies)

    if 'regions' in wrapper_config['accounts'][account_name]:
      aws_regions = wrapper_config['accounts'][account_name]['regions'].keys()

      for region in aws_regions:
        # for each region, run region specific policies if they exist
        region_policies_exist = wrapper_config['accounts'][account_name]['regions'][region] and 'region_policies' in wrapper_config['accounts'][account_name]['regions'][region]
        # if region_specific_policies exist, run all_listed_regions_policies and region_specific_policies for this region
        if region_policies_exist:
          region_specific_policies = wrapper_config['accounts'][account_name]['regions'][region]['region_policies']
          if all_regions_exist:
            region_policies = region_specific_policies
          else:
            region_policies = region_specific_policies + all_listed_regions_policies
          custodian_run_commands = custodian_run_commands + get_custodian_run_cmds(account_name, [region], sts_role, region_policies)
        # if not region_specific_policies exist, just run the all_listed_regions_policies for this region
        elif not all_regions_exist:
          custodian_run_commands = custodian_run_commands + get_custodian_run_cmds(account_name, [region], sts_role, all_listed_regions_policies)
  return custodian_run_commands


def get_custodian_run_cmds(account_name, aws_regions, sts_role, policies):
  custodian_run_commands = []
  for region in aws_regions:
    for policy in policies:
      custodian_run_commands.append((account_name, get_argv_custodian_run_cmd(sts_role=sts_role, region=region, policy=policy, account_name=account_name)))
  return custodian_run_commands


def run_custodian_region_and_policy(custodian_run_command, account_name):
  # this is my hack for keeping each run's stdout/stderr in a contiguous block so it doesn't interweave from the parallelization
  # all this could be avoided if things weren't randomly sent to stdout or stderr, and if I could just call various api functions
  # and have the output returned to me directly in a variable.
  # We also do EasyProcess instead of subprocess, because python 2.7 doesn't easily provide timeout or cleanup of forks
  # this is probably a custodian bug, but all the output goes to stderr (even on successful runs)
  shell_fork = EasyProcess(custodian_run_command).call(timeout=80)  # 80 is is 10x my average run time of 8 seconds.
  shell_output = '%s%s' % (shell_fork.stdout, shell_fork.stderr)
  region = custodian_run_command[3]
  run_custodian_log_msg = '\n########################    account: %s - region: %s    ########################\n%s\n' % (account_name, region, shell_output)
  if reports_only_mode:
    report_yaml = custodian_run_command[-1]
    run_custodian_log_msg = '\n########################    account: %s - policy: %s    ########################\n%s\n' % (account_name, report_yaml, shell_output)
    if len(run_custodian_log_msg.split('\n')) <= 7:
      return
  sys.stdout.write(run_custodian_log_msg)
  sys.stdout.flush()


def main_loop(parallel=True, run_once=False):
  while True:
    start_time = time.time()
    pool = multiprocessing.Pool(processes=parallel_process_max)
    log_start_of_cycle(custodian_live_fire)
    # loop over each account in wrapper_config.yml
    # go over all_custodian_commands
    for custodian_run_command in all_custodian_commands:
      account_name          = custodian_run_command[0]
      custodian_run_command = custodian_run_command[1]
      if parallel:
        pool.apply_async(run_custodian_region_and_policy, args=(custodian_run_command, account_name))
      else:
        run_custodian_region_and_policy(custodian_run_command, account_name)
    pool.close()
    pool.join()
    log_end_of_cycle_sleeping(custodian_run_interval, start_time, qty_custodian_run_commands)
    if run_once:
      return
    time.sleep(custodian_run_interval)


secrets             = get_secrets()
s3_logging_bucket   = secrets['s3_logging_bucket']
wrapper_config      = get_wrapper_config()
aws_all_regions     = aws_get_all_regions()
# These are 'special' regions so they get removed.
aws_all_regions.remove('cn-north-1')
aws_all_regions.remove('us-gov-west-1')
all_listed_regions_policies = wrapper_config['all_listed_regions_policies']
set_aws_custodian_account_env_secrets(secrets)
start_log_msg = 'Running cloud custodian... latest file change was on: %s' % (datetime.datetime.fromtimestamp(get_latest_file_change()).strftime('%c'))
logging.info(start_log_msg)
if custodian_live_fire:
  update_lambda_mailer()
if reports_only_mode:
  all_custodian_commands = get_all_custodian_report_commands()
else:
  all_custodian_commands = get_all_custodian_run_commands()
qty_custodian_run_commands = len(all_custodian_commands)

if __name__ == '__main__':
  main_loop()
