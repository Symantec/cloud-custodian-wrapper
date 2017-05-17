# What do I gain by using this wrapper?
- You can run custodian policies on accounts, region and policy combinations in parallel using python multiprocessing library (it's fast!)
- You can do a dryrun for all your custodian runs (also in parallel), and then get a simple report showing only changes that will happen. (across arbitrary accounts, regions and policies)
- There are some workflow scripts for containerizing, deploying to kubernetes, testing changes before they get deployed to production, and having clear awareness around what changes will happen to your accounts _BEFORE_ you click the merge button on a new PR that adds a policy.

# How to deploy to openshift
- If it's your first time deploying, oc create project aws-cloudcustodian
- setup secrets
- upload the secrets to openshift
- ./openshift-deploy.sh

# How to setup secrets
- cp aws-secrets.example.yml aws-secrets.yml, then modify the file
- oc project aws-cloudcustodian
- oc create secret generic aws-cloudcustodian-secrets --from-file=aws-secrets.yml
- export CC_SQS_URL=https://sqs.us-east-1.amazonaws.com/xxxxxx/cloudcustodian-mailer

# How to setup IAM policies
- setup IAM for the main account, each assumed role account, and the lambda role.

# How to run locally
- setup secrets
- setup your iam policies
- pip install -r requirements.txt
- CUSTODIAN_LIVE_FIRE=True ./run_clean_accounts_locally.py

# How to run in reports only mode
- ./run_clean_accounts_locally.py &> /dev/null (this runs in --dryrun by default)
- CUSTODIAN_REPORTS_ONLY_MODE=True ./run_clean_accounts_locally.py

# TODO
- catch errors on run and notify slack channel if the errors repeat often? this could be tricky with so many runs happening, but is important to know where bugs are and to squash them (eg caching issues).
- have emails sent a day before the termination
- write code that checks all the assume roles and makes sure I can send to the SQS queue from all assume roles as a validation
- write a bunch of unit tests proving xyz accounts/regions get touched, and that matched the wrapper config
- kill off some of the global variables I'm abusing, and more explicitly pass input parameters
- setup sns topic for slack notifications
- update jinja so it uses different template prefixes and doesn't interfere with mustache
- setup read only iam credentials/roles for dry-run/reports to run in
- documentation
- render email on openshift deployment
- should switch the ses mailer to sending emails with c7n_mailer functions directly
- do cache validation checks after a run finishes? (cnpickle loads perhaps, if it fails delete it)
- do an optional secret comparison with openshift on deploy?
- only print the red bold font if priority_header is set and is 1?
- sort policies in a way so they cause the least throttling by boto (get all repeated account/region combinations, and evenly distribute them in the array before multiprocessing)
- tag set to make custodian not be able to delete (ldap, mirrors, dns, federation broker), preferred images can't be deleted also (or value_from filters)
- flake8 tests dir
- find out why emails can't be forwarded
- make a lot more policies (SGs, EC2 tags, RDS tags, etc)
- make something that validates the wrapper-config.yml
- make a better API function to call custodian runs (upstream)
- allow the api functions to return log output as a string variable, and not send to stdout/err (upstream)
- send metrics to LMM (need a significant overhaul to how custodian does metrics?)
