# custodian email pipeline
- We use groupon's gleemail: https://github.com/groupon/gleemail
- This allows us to have a simple abstraction for crafting the email, that turns into the shit show html email table blob thing
- Install the required packages by running ./install_dev_email_tools.sh
- To send a test email do: EMAIL_TO=john@example.com EMAIL_FROM=ses_allowed_email@example.com ./ses_send_mock_jinja_email.py
  - You can do comma separated for EMAIL_TO to send to several people.
- ses_send_mock_jinja_email.py will automatically write the custodian template file when you run it
- node_modules/gleemail/bin/gleemail start; if you want to use the UI for fast feedback on changes (or to integrate with litmus)

# TODO
- integrate an input parameter to select which policy you want to send an email for
- pull the subject from the policy