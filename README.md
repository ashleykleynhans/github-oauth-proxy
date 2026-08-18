# Github oAuth2 Proxy for Spinnaker

[![Python Version: 3.12](
https://img.shields.io/badge/Python%20application-v3.12-blue
)](https://www.python.org/downloads/release/python-3123/)
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

This proxy not only calls the Github user endpoint, but also calls
the Github orgs and emails endpoints in order to gather more verbose
information about a user so that you can require one or more of the
following permissions:

- User must belong to a specific Github organization.
- User must have an email account associated with their Github account
that matches a specific domain name.
- User must have their email account that matches a specific domain
name set as their primary email address on their Github account.

## Prerequisites

1. Install [ngrok](https://ngrok.com/).
   ```bash
   brew install ngrok
   ```
2. Ensure your System Python3 version is 3.12.
   ```bash
   python3 -V
   ```
3. If your System Python is not 3.12:
   ```bash
   brew install python@3.12
   brew link python@3.12
   ```

## Configuring required conditions, and/or user mapping (optional)

These steps are completely **optional**, and only need to be
configured if you require additional preconditions for a Github
user to be able to log in to Spinnaker.

1. Create a file called `config.yml`.
2. If you require that a Github user is a member of your specific
Github organisation, insert the following content:
   ```yaml
   ---
   github:
     required:
       org: ExampleDotCom
   ```
3. If you require that a Github user has your company email configured
as one of their email addresses in their Github account:
   ```yaml
   ---
   github:
     required:
       email:
         domain: example.com
   ```
4. If you require that a Github user has your company email configured
   as one of their email addresses, and that it is set as their primary
   email address in their Github account:
   ```yaml
   ---
   github:
     required:
       email:
         domain: example.com
         domain_required_as_primary: true
   ```
5. If you want to map the Github username/login to something more
   meaningful:
   ```yaml
   ---
   spinnaker:
     username_mapping:
       githubuser123: marcus
       githubuser456: susan
       githubuser789: james
   ```
   For example, if the Github username is `githubuser123`, it will be
   remapped to `marcus` etc.

## Running Tests

1. Create a Python 3.12 Virtual Environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install the test and development dependencies:
   ```bash
   pip3 install -r requirements-dev.txt
   ```
3. Run the tests:
   ```bash
   pytest -v
   ```
   A coverage report will be included automatically.

4. Run the linter and type checker:
   ```bash
   ruff check .
   mypy github_auth.py webhook.py
   ```

## Testing your Webhook

1. Run the webhook receiver from your terminal. The app is served with
   [waitress](https://docs.pylonsproject.org/projects/waitress/), a
   production WSGI server.
   ```bash
   python3 webhook.py
   ```
2. Open a new terminal window and use [ngrok](https://ngrok.com/) to create
   a URL that is publicly accessible through the internet by creating a tunnel
   to the webhook receiver that is running on your local machine.
   ```bash
   ngrok http 8090
   ```
3. Note that the ngrok URL will change if you stop ngrok and run it again,
   so keep it running in a separate terminal window, otherwise you will not
   be able to test your webhook successfully.
4. Take note of the URL that is returned by ngrok (don't stop it).
5. Edit/create your `/home/spinnaker/.hal/default/profiles/gate-local.yml`
   Gate configuration file, and insert the following contents, obviously
   replacing the `clientId`, `clientSecret`, `preEstablishedRedirectUri`
   and `userInfoUri` with your own.
   ```yml
   security:
     oauth2:
       enabled: true
       client:
         clientId: YOUR_GITHUB_CLIENT_ID_GOES_HERE
         clientSecret: YOUR_GITHUB_CLIENT_SECRET_GOES_HERE
         accessTokenUri: https://github.com/login/oauth/access_token
         userAuthorizationUri: https://github.com/login/oauth/authorize
         scope: user:email,read:org
         preEstablishedRedirectUri: http://YOUR_GATE_URL/login
         useCurrentUri: false
       resource:
         userInfoUri: https://f00d-00-111-0-111.ngrok.io/info
       userInfoMapping:
         email: email
         firstName: firstname
         lastName: lastname
         username: username
   ```

## Deploy to AWS Lambda

1. Create a Python 3.12 Virtual Environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Upgrade pip.
   ```bash
   python3 -m pip install --upgrade pip
   ```
3. Install the Python dependencies that are required by the Webhook receiver:
   ```bash
   pip3 install -r requirements-deploy.txt
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
           "runtime": "python3.12",
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
9. Update your `userInfoUri` URL in your Spinnaker
   `/home/spinnaker/.hal/default/profiles/gate-local.yml` configuration file
   to the one returned by the `zappa deploy` command and append the
   `/info` endpoint.
   ```yaml
       resource:
         userInfoUri: https://1d602d00.execute-api.us-east-1.amazonaws.com/user/info
   ```
10. You can view your logs by running:
   ```bash
   zappa tail
   ```

## Deploy using Docker

A [Dockerfile](Dockerfile) and [docker-bake.hcl](docker-bake.hcl) are included
so the proxy can also be run as a container.

### Pulling the image

Pre-built images are published to the GitHub Container Registry (GHCR) on
every push to `main` and for every release tag:

```bash
docker pull ghcr.io/ashleykleynhans/github-oauth-proxy:latest
```

Release tags publish versioned images, e.g. `ghcr.io/ashleykleynhans/github-oauth-proxy:1.2.0`.

### Running the container

The container listens on port `8090`, runs as a non-root user, and includes a
healthcheck against the `/` endpoint. Mount your `config.yml` (optional) at
`/app/config.yml` inside the container:

```bash
docker run -d \
  --name github-oauth-proxy \
  -p 8090:8090 \
  -v /path/to/config.yml:/app/config.yml:ro \
  ghcr.io/ashleykleynhans/github-oauth-proxy:latest
```

Then point Spinnaker's `userInfoUri` at
`http://YOUR_GATE_URL:8090/info` as described in
[Testing your Webhook](#testing-your-webhook).

### Building locally

Build the image with [Docker Bake](https://docs.docker.com/build/bake/):

```bash
docker buildx bake --set github-oauth-proxy.tags=github-oauth-proxy:dev
```

The `--set` override tags the image (CI tags it via
[docker/metadata-action](https://github.com/docker/metadata-action)); without
it the image is built untagged.

### Release process

Tagging a release publishes versioned images to GHCR. The workflow matches
plain semver tags, so no `v` prefix is required:

```bash
git tag 1.3.0
git push origin 1.3.0
```

The workflow tags the image `1.3.0` and `1.3`, and also refreshes `latest`.

## Community and Contributing

Pull requests and issues on [GitHub](https://github.com/ashleykleynhans/github-oauth-proxy)
are welcome. Bug fixes and new features are encouraged.

## Appreciate my work?

<a href="https://www.buymeacoffee.com/ashleyk" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>
