#!/usr/bin/env python

import glob
import multiprocessing
import os
import sys
import yaml

from easyprocess import EasyProcess
from clean_accounts import main_loop

parallel_process_max = 32
cc_sqs_url           = os.environ['CC_SQS_URL']

# the only reason we're doing all this is so we can publish policies to github
# and not have our private account numbers sent to github as well.
# it would be nice if you could just use a 'default' sqs queue from mailer.yml


def run_custodian_yaml_validation(file):
  return True


def get_all_custodian_yaml_files():
  yaml_files = glob.glob('/custodian/policies/*') + glob.glob('/custodian/reports/*')
  return yaml_files


def replace_string_on_files(text_to_search, text_to_replace, files):
  pool = multiprocessing.Pool(processes=parallel_process_max)
  for file in files:
    pool.apply_async(replace_string_on_file, args=(text_to_search, text_to_replace, file))
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


def validate_custodian_yaml_file(custodian_yaml_file):
  shell_fork   = EasyProcess(['custodian', 'validate', custodian_yaml_file]).call(timeout=10)
  exit_code    = shell_fork.return_code
  shell_output = '%s%s' % (shell_fork.stdout, shell_fork.stderr)
  if exit_code != 0:
    msg = 'Failed validation for file %s\n%s\n\n' % (custodian_yaml_file, shell_output)
    sys.stdout.write(msg)
    sys.stdout.flush()
    return False
  return True


def get_policy_names(directory):
  list_of_policy_names = {}
  for abs_filename in glob.glob(directory):
    policy_file = open(abs_filename, 'r')
    yaml_data = yaml.load(policy_file)
    for policy_name in yaml_data['policies']:
      list_of_policy_names[(policy_name['name'])] = ''
    policy_file.close()
  return list_of_policy_names


def verify_all_reports_exist():
  list_of_policy_names = get_policy_names('/custodian/policies/*')
  list_of_report_names = get_policy_names('/custodian/reports/*')
  list_of_missing_reports = []
  for policy_name in list_of_policy_names.iteritems():
    # import ipdb
    # ipdb.set_trace()
    if policy_name[0] not in list_of_report_names:
      report_abs_filename = '/custodian/reports/%s.report.yml' % policy_name[0]
      list_of_missing_reports.append(report_abs_filename)
  if len(list_of_missing_reports) > 0:
    exception_msg = 'The following reports are missing: %s' % list_of_missing_reports
    print(exception_msg)
    sys.stdout.flush()
    sys.exit(1)


def validate_custodian_yaml_files(custodian_yaml_files):
  pool = multiprocessing.Pool(processes=parallel_process_max)
  failed_validation = False
  return_values = []
  for custodian_yaml_file in custodian_yaml_files:
    return_value = pool.apply_async(validate_custodian_yaml_file, args=(custodian_yaml_file, ))
    return_values.append(return_value)
  for validation_passed in return_values:
    validation_passed.wait()
    if not validation_passed.get():
      failed_validation = True
  if failed_validation:
    sys.stdout.write('\n\nFailed to validate one or more custodian yaml files, exiting 1...\n\n')
    sys.exit(1)
  pool.close()
  pool.join()


all_custodian_yaml_files = get_all_custodian_yaml_files()
verify_all_reports_exist()
replace_string_on_files('{CC_SQS_URL}', cc_sqs_url, all_custodian_yaml_files)
validate_custodian_yaml_files(all_custodian_yaml_files)
main_loop(run_once=True)
replace_string_on_files(cc_sqs_url, '{CC_SQS_URL}', all_custodian_yaml_files)
