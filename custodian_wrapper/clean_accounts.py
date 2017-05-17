#!/usr/bin/env python

import logging
import multiprocessing
import os
import reports
import sys
import time
import utils

from easyprocess import EasyProcess

__requires__ = 'c7n-mailer'

custodian_live_fire    = os.environ.get('CUSTODIAN_LIVE_FIRE', False)
custodian_run_interval = 900
logger                 = logging.getLogger('custodian.policy')
parallel_process_max   = 16
reports_only_mode      = os.environ.get('CUSTODIAN_REPORTS_ONLY_MODE', False)
secrets                = utils.get_secrets()
utils.set_aws_custodian_account_env_secrets(secrets)
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def get_argv_custodian_run_cmd(sts_role, region, policy, account_name, s3_logging_bucket):
    if custodian_live_fire and reports_only_mode:
        sys.exit('You can not run in live fire mode and reports mode at the same time.')

    if custodian_live_fire:
        custodian_output = s3_logging_bucket
    else:
        custodian_output = 'dry_run/%s/%s' % (account_name, region)

    policy_abs_filename = '/custodian/policies/%s' % policy
    cache_option        = '--cache=/custodian/aws_cache/%s.%s.cache' % (account_name, region)
    cache_period        = '--cache-period=14'
    metrics             = '-m'
    custodian_cmd = [
        'custodian', 'run', '--region', region, cache_option, cache_period, '-c',
        policy_abs_filename, '--assume', sts_role, '-s', custodian_output, metrics, '--dryrun'
    ]
    if custodian_live_fire:
        custodian_cmd.pop()
    return custodian_cmd


def get_all_custodian_run_commands(wrapper_config, secrets, aws_all_regions,
        all_listed_regions_policies, s3_logging_bucket):
    custodian_run_commands = []
    for account_name in wrapper_config['accounts'].keys():
        # for each account, set the sts role
        sts_role = utils.get_sts_role(account_name, secrets)
        all_regions_set = 'all_regions' in wrapper_config['accounts'][account_name]
        all_regions = all_regions_set and wrapper_config['accounts'][account_name]['all_regions']

        if all_regions:
            custodian_run_commands = custodian_run_commands + \
                get_custodian_run_cmds(
                    account_name,
                    aws_all_regions,
                    sts_role,
                    all_listed_regions_policies,
                    s3_logging_bucket)

        if 'regions' in wrapper_config['accounts'][account_name]:
            aws_regions = wrapper_config['accounts'][account_name][
                'regions'].keys()

            for region in aws_regions:
                # for each region, run region specific policies if they exist
                region_policies_set = wrapper_config['accounts'][account_name]['regions'][region]
                region_policies = region_policies_set and 'region_policies' in wrapper_config[
                    'accounts'][account_name]['regions'][region]
                # if region_specific_policies exist, run
                # all_listed_regions_policies and region_specific_policies for
                # this region
                if region_policies:
                    region_specific_policies = wrapper_config['accounts'][
                        account_name]['regions'][region]['region_policies']
                    if all_regions:
                        region_policies = region_specific_policies
                    else:
                        region_policies = region_specific_policies + all_listed_regions_policies
                    custodian_run_commands = custodian_run_commands + \
                        get_custodian_run_cmds(
                            account_name, [region], sts_role, region_policies, s3_logging_bucket)
                # if not region_specific_policies exist, just run the
                # all_listed_regions_policies for this region
                elif not all_regions:
                    custodian_run_commands = custodian_run_commands + \
                        get_custodian_run_cmds(account_name, [region], sts_role,
                            all_listed_regions_policies, s3_logging_bucket)
    return custodian_run_commands


def get_custodian_run_cmds(account_name, aws_regions, sts_role, policies, s3_logging_bucket):
    custodian_run_commands = []
    for region in aws_regions:
        for policy in policies:
            custodian_cmd = get_argv_custodian_run_cmd(
                sts_role          = sts_role,
                region            = region,
                policy            = policy,
                account_name      = account_name,
                s3_logging_bucket = s3_logging_bucket
            )
            custodian_cmd_tuple = (account_name, custodian_cmd)
            custodian_run_commands.append(custodian_cmd_tuple)
    return custodian_run_commands


def run_custodian_region_and_policy(custodian_run_command, account_name):
    # this is my hack for keeping each run's stdout/stderr in a contiguous block so it doesn't
    # interweave from the parallelization all this could be avoided if things weren't randomly
    # sent to stdout or stderr, and if I could just call various api functions and have the
    # output returned to me directly in a variable. We also do EasyProcess instead of subprocess,
    # because python 2.7 doesn't easily provide timeout or cleanup of forks his is probably a
    # custodian bug, but all the output goes to stderr (even on successful runs) 80 is is 10x
    # my average run time of 8 seconds.
    shell_fork = EasyProcess(custodian_run_command).call(timeout=80)
    shell_output = '%s%s' % (shell_fork.stdout, shell_fork.stderr)
    hash_str = '########################'
    if reports_only_mode:
        report_yaml = custodian_run_command[-1]
        run_custodian_log_msg = '\n%s    account: %s - policy: %s    %s\n%s\n' % (
            hash_str, account_name, report_yaml, hash_str, shell_output)
    else:
        region = '                      region: %s' % custodian_run_command[3].ljust(14, ' ')
        account_name = '-+-+- account: %s -+-+-' % account_name
        policy_filename = custodian_run_command[7].split('/custodian/policies/')[1]
        run_custodian_log_msg = '\n%s %s %s                  policy_file: %s   \n%s\n' % (
            hash_str, region, account_name, policy_filename, shell_output)
    print(run_custodian_log_msg)
    sys.stdout.flush()


def clear_all_cache(cache_dir):
    cache_files = os.listdir(cache_dir)
    for cache_file in cache_files:
        cache_file_abs_path = '%s/%s' % (cache_dir, cache_file)
        os.remove(cache_file_abs_path)


def main_loop(parallel=True, run_once=False, update_mailer=False):
    aws_cache_dir               = 'aws_cache'
    s3_logging_bucket           = secrets['s3_logging_bucket']
    wrapper_config              = utils.get_wrapper_config()
    all_listed_regions_policies = wrapper_config['all_listed_regions_policies']
    aws_all_regions             = utils.aws_get_all_regions()
    last_edit_time              = utils.get_latest_file_change_time()
    start_log_msg               = '\n\nLatest code file change was on: %s' % last_edit_time
    all_custodian_commands      = get_all_custodian_run_commands(wrapper_config, secrets,
        aws_all_regions, all_listed_regions_policies, s3_logging_bucket)
    logging.info(start_log_msg)
    qty_custodian_run_commands = len(all_custodian_commands)
    if update_mailer:
        utils.update_lambda_mailer(logger)
    while True:
        if os.path.exists(aws_cache_dir):
            clear_all_cache(aws_cache_dir)
        start_time = time.time()
        pool = multiprocessing.Pool(processes=parallel_process_max)
        utils.log_start_of_cycle(custodian_live_fire, reports_only_mode)
        for custodian_run_command in all_custodian_commands:
            account_name = custodian_run_command[0]
            custodian_run_command = custodian_run_command[1]
            if parallel:
                pool.apply_async(
                    run_custodian_region_and_policy,
                    args=(custodian_run_command, account_name))
            else:
                run_custodian_region_and_policy(custodian_run_command,
                                                account_name)
        pool.close()
        pool.join()
        utils.log_end_of_cycle_sleeping(custodian_run_interval, start_time,
                                  qty_custodian_run_commands, logging)
        if run_once:
            sys.exit(0)
        time.sleep(custodian_run_interval)


if reports_only_mode:
        reports.print_reports()
        sys.exit(0)

if __name__ == '__main__':
    if custodian_live_fire:
        # note, the mailer doesn't update when run locally. Only when run through docker.
        utils.update_lambda_mailer(logger)
    main_loop()
