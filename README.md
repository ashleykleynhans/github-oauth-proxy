# Github oAuth2 Proxy for Spinnaker

[![Python Version: 3.9](
https://img.shields.io/badge/Python%20application-v3.9-blue
)](https://www.python.org/downloads/release/python-3913/)
[![License: GPL 3.0](
https://img.shields.io/github/license/ashleykleynhans/github-oauth-proxy
)](https://opensource.org/licenses/GPL-3.0)

## Background

Spinnaker supports the Github oAuth2 provider, but unfortunately the
detail from the user profile is not very useful to restrict access to
the Spinnaker instance based on permissions, such as requiring the user
to belong to a specific Github organization for example.  This means
that anyone with a Github account is then able to log in to your
Spinnaker instance.

This proxy not only calls the user endpoint, but also the orgs and
emails endpoints for the user in order to gather more verbose information
about a user so that you can require one or more of the following
permissions:

- User must belong to a specific Github organization.
- User must have an email account associated with their Github account
that matches a specific domain name,
- User must have their email account that matches a specific domain
name set as their primary email address on their Github account.

## Prerequisites

1. Install [ngrok](https://ngrok.com/).
```bash
brew install ngrok
```
2. Ensure your System Python3 version is 3.9, but greater than 3.9.1.
```bash
python3 -V
```
3. If your System Python is not 3.9:
```bash
brew install python@3.9
brew link python@3.9
```
4. If your Sytem Python is 3.9 but not greater than 3.9.1:
```bash
brew update
brew upgrade python@3.9
```

## Testing your Webhook

1. Run the webhook receiver from your terminal.
```bash
python3 webhook.py
```
2. Open a new terminal window and use [ngrok](https://ngrok.com/) to create
a URL that is publicly accessible through the internet by creating a tunnel
to the webhook receiver that is running on your local machine.
```bash
ngrok http 8090
```
4. Note that the ngrok URL will change if you stop ngrok and run it again,
   so keep it running in a separate terminal window, otherwise you will not
   be able to test your webhook successfully.
5. Update your `userInfoUri` configuration in Spinnaker to the URL that is
   displayed while ngrok is running **(be sure to use the https one)**, and
   append the `/info` endpoint.
```bash
hal config security authn oauth2 edit \
  --user-info-uri https://f00d-00-111-0-111.ngrok.io/info
```
6. Configure the required oAuth2 scopes in your Spinnaker configuration.
```bash
hal config security authn oauth2 edit \
  --scope user:email,read:org
```

## Deploy to AWS Lambda

1. Create a Python 3.9 Virtual Environment:
```bash
python3 -m venv venv/py3.9
source venv/py3.9/bin/activate
```
2. Upgrade pip.
```bash
python3 -m pip install --upgrade pip
```
3. Install the Python dependencies that are required by the Webhook receiver:
```bash
pip3 install -r requirements.txt
```
4. Create a file called `zappa_settings.json` and insert the JSON content below
to configure your AWS Lambda deployment:
```json
{
    "user": {
        "app_function": "webhook.app",
        "aws_region": "us-west-2",
        "lambda_description": "Github oAuth2 Proxy for Spinnaker",
        "profile_name": "default",
        "project_name": "yourproject",
        "runtime": "python3.9",
        "s3_bucket": "github-oauth2-proxy",
        "tags": {
           "service": "github-oauth2-proxy"
        }
    }
}
```
5. Use [Zappa](https://github.com/Zappa/Zappa) to deploy your Webhook
to AWS Lambda (this is installed as part of the dependencies above):
```bash
zappa deploy
```
6. Take note of the URL that is returned by the `zappa deploy` command,
eg. `https://1d602d00.execute-api.us-east-1.amazonaws.com/github-webhook`
   (obviously use your own and don't copy and paste this one, or your
Webhook will not work).

**NOTE:** If you get the following error when running the `zappa deploy` command:

<pre>
botocore.exceptions.ClientError:
An error occurred (IllegalLocationConstraintException) when calling
the CreateBucket operation: The unspecified location constraint
is incompatible for the region specific endpoint this request was sent to.
</pre>

This error usually means that your S3 bucket name is not unique, and that you
should change it to something different, since the S3 bucket names are not
namespaced and are global for everyone.

7. Check the status of the API Gateway URL that was created by zappa:
```bash
zappa status
```
8. Test your webhook by making a curl request to the URL that was returned
by `zappa deploy`:
```
curl https://1d602d00.execute-api.us-east-1.amazonaws.com/user
```
You should expect the following response:
```json
{"status":"ok"}
```
9. Update your `userInfoUri` URL in Spinnaker to the one returned by the
`zappa deploy` command and append the `/info` endpoint.
```bash
hal config security authn oauth2 edit \
  --user-info-uri https://1d602d00.execute-api.us-east-1.amazonaws.com/user/info
```
10. You can view your logs by running:
```bash
zappa tail
```